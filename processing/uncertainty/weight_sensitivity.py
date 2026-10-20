# -*- coding: utf-8 -*-
"""Uncertainty: One-at-a-Time Weight Sensitivity (Chen, Yu & Khan, 2010)."""
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)
from qgis.PyQt.QtCore import QMetaType

from .._mcda_utils import (
    ensure_list,
    infer_layer_label,
    limit_layers,
    oat_perturbed_weights,
    parse_weights_csv,
    wlc_score,
)

MAX_CRITERIA = 12
CHANGE_NODATA = -9999.0


class WeightSensitivityOATAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    PERTURBATION = "PERTURBATION"
    CHANGE_THRESHOLD = "CHANGE_THRESHOLD"
    CONSTRAINT = "CONSTRAINT"
    FOCUS = "FOCUS"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"
    OUTPUT_CHANGE = "OUTPUT_CHANGE"

    def name(self):
        return "weight_sensitivity_oat"

    def displayName(self):
        return "Uncertainty: One-at-a-Time Weight Sensitivity"

    def group(self):
        return "Uncertainty"

    def groupId(self):
        return "uncertainty"

    def createInstance(self):
        return WeightSensitivityOATAlgorithm()

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def shortHelpString(self):
        return (
            "<p><b>Which criterion's weight actually drives the suitability map? Changes one "
            "weight at a time and measures how much the WLC result moves.</b></p>"
            "<p><b>Inputs:</b> the criterion rasters and weights you would give "
            "<i>Compose: WLC Suitability</i> (up to 12, normalised 0-100, identical grids); "
            "perturbation in percent (default 20: each weight is tried at 1.2x and 0.8x); "
            "change threshold in score points (default 5); optional constraint mask (0/1, "
            "cells failing it are left out of the statistics because their score is 0 "
            "whatever the weights); optional focus criterion (1-based) and change raster.<br>"
            "<b>Renormalisation rule:</b> when weight w<sub>i</sub> becomes "
            "w<sub>i</sub>' = w<sub>i</sub>(1 &plusmn; p), clipped to [0, 1], every other weight is "
            "multiplied by (1 - w<sub>i</sub>') / (1 - w<sub>i</sub>), so they keep their proportions "
            "and all weights still sum to 1. A criterion that already carries all the weight "
            "cannot be perturbed.<br>"
            "<b>Output table (one row per criterion, ranked):</b> weight, weight_up, weight_down, "
            "mac_up / mac_down (mean absolute change in the 0-100 score over valid cells for the "
            "raised / lowered weight), mac (their mean - the ranking key), max_abs_change, "
            "share_changed_pct (percent of cells whose score moves by more than the threshold "
            "in either direction), rank (1 = most influential).<br>"
            "<b>Change raster (optional):</b> for the focus criterion, the larger of |S<sub>up</sub> - S| "
            "and |S<sub>down</sub> - S| per cell - where on the map that weight matters.<br>"
            "<b>When to use it instead of Monte Carlo:</b> <i>Uncertainty: Monte Carlo "
            "Suitability</i> adds random noise to a finished score; it cannot tell you which "
            "weight matters. This tool answers how much your own uncertainty about each weight "
            "changes the map. Reference: Chen, Y., Yu, J. & Khan, S. (2010), Environmental "
            "Modelling &amp; Software 25(12): 1582-1591.</p>"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.INPUT_RASTERS, f"Criterion rasters (max {MAX_CRITERIA}, normalized 0-100)",
            QgsProcessing.SourceType.TypeRaster))
        self.addParameter(QgsProcessingParameterString(
            self.WEIGHTS_CSV, "Weights CSV (as for WLC; equal weights if blank)",
            defaultValue="", optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.PERTURBATION, "Weight perturbation (percent)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=20.0,
            minValue=1.0, maxValue=90.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CHANGE_THRESHOLD, "Change threshold (score points)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=5.0,
            minValue=0.0, maxValue=100.0))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.FOCUS, "Focus criterion for the change raster (1-based, 0 = none)",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=0,
            minValue=0, maxValue=MAX_CRITERIA))
        self.addParameter(QgsProcessingParameterNumber(
            self.BLOCK, "Block size (pixels)",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=512,
            minValue=64, maxValue=2048))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Weight sensitivity table", QgsProcessing.SourceType.TypeVector))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_CHANGE, "Focus criterion change raster", optional=True,
            createByDefault=False))

    def processAlgorithm(self, parameters, context, feedback):
        layers = limit_layers(ensure_list(self.parameterAsLayerList(
            parameters, self.INPUT_RASTERS, context)), MAX_CRITERIA, "criterion rasters")
        if len(layers) < 2:
            raise QgsProcessingException("Weight sensitivity needs at least two criterion rasters.")
        n = len(layers)
        weights = np.array(parse_weights_csv(
            self.parameterAsString(parameters, self.WEIGHTS_CSV, context), n), dtype=np.float64)
        fraction = self.parameterAsDouble(parameters, self.PERTURBATION, context) / 100.0
        threshold = self.parameterAsDouble(parameters, self.CHANGE_THRESHOLD, context)
        focus = self.parameterAsInt(parameters, self.FOCUS, context)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        if focus > n:
            raise QgsProcessingException(f"Focus criterion {focus} does not exist; there are {n} criteria.")

        perturbed = [(oat_perturbed_weights(weights, i, +fraction),
                      oat_perturbed_weights(weights, i, -fraction)) for i in range(n)]

        datasets, bands, nodatas = [], [], []
        xsize = ysize = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            if xsize is None:
                xsize, ysize = ds.RasterXSize, ds.RasterYSize
            elif (ds.RasterXSize, ds.RasterYSize) != (xsize, ysize):
                raise QgsProcessingException("All criterion rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(ds.GetRasterBand(1))
            nodatas.append(bands[-1].GetNoDataValue())

        c_band = c_nodata = None
        if constraint is not None:
            c_ds = gdal.Open(constraint.source(), gdal.GA_ReadOnly)
            if c_ds is None or (c_ds.RasterXSize, c_ds.RasterYSize) != (xsize, ysize):
                raise QgsProcessingException("Constraint raster must match the criterion grid.")
            c_band = c_ds.GetRasterBand(1)
            c_nodata = c_band.GetNoDataValue()

        change_band = None
        change_path = None
        if focus > 0:
            change_path = self.parameterAsOutputLayer(parameters, self.OUTPUT_CHANGE, context)
        if change_path:
            out_ds = gdal.GetDriverByName("GTiff").Create(
                change_path, xsize, ysize, 1, gdal.GDT_Float32, options=["COMPRESS=LZW", "TILED=YES"])
            out_ds.SetGeoTransform(datasets[0].GetGeoTransform())
            out_ds.SetProjection(datasets[0].GetProjection())
            change_band = out_ds.GetRasterBand(1)
            change_band.SetNoDataValue(CHANGE_NODATA)

        sum_up = np.zeros(n)
        sum_down = np.zeros(n)
        max_abs = np.zeros(n)
        over = np.zeros(n)
        cells = 0
        total_blocks = max(1, ((xsize + block - 1) // block) * ((ysize + block - 1) // block))
        done = 0
        for yoff in range(0, ysize, block):
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    return {}
                cols = min(block, xsize - xoff)
                arrs = []
                valid = np.ones((rows, cols), dtype=bool)
                for j, band in enumerate(bands):
                    a = band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    ok = np.isfinite(a)
                    if nodatas[j] is not None:
                        ok &= a != nodatas[j]
                    valid &= ok
                    arrs.append(a)
                if c_band is not None:
                    c = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_ok = np.isfinite(c)
                    if c_nodata is not None:
                        c_ok &= c != c_nodata
                    valid &= c_ok & (c > 0.5)
                stack = np.stack(arrs, axis=0)
                base = wlc_score(stack, weights)
                focus_change = np.zeros((rows, cols), dtype=np.float32)
                count = int(valid.sum())
                cells += count
                for i, (w_up, w_down) in enumerate(perturbed):
                    d_up = np.abs(wlc_score(stack, w_up) - base)
                    d_down = np.abs(wlc_score(stack, w_down) - base)
                    worst = np.maximum(d_up, d_down)
                    if count:
                        sum_up[i] += float(d_up[valid].sum())
                        sum_down[i] += float(d_down[valid].sum())
                        max_abs[i] = max(max_abs[i], float(worst[valid].max()))
                        over[i] += float((worst[valid] > threshold).sum())
                    if focus == i + 1:
                        focus_change = worst
                if change_band is not None:
                    change_band.WriteArray(
                        np.where(valid, focus_change, CHANGE_NODATA).astype(np.float32), xoff, yoff)
                done += 1
                feedback.setProgress(int(100 * done / total_blocks))

        if cells == 0:
            raise QgsProcessingException("No valid cells: every cell is nodata or fails the constraint.")

        mac_up = sum_up / cells
        mac_down = sum_down / cells
        mac = (mac_up + mac_down) / 2.0
        order = sorted(range(n), key=lambda i: (-mac[i], i))
        rank = {i: r + 1 for r, i in enumerate(order)}

        fields = QgsFields()
        for name, kind in (("criterion_id", QMetaType.Type.Int), ("criterion", QMetaType.Type.QString),
                           ("weight", QMetaType.Type.Double), ("weight_up", QMetaType.Type.Double),
                           ("weight_down", QMetaType.Type.Double), ("mac_up", QMetaType.Type.Double),
                           ("mac_down", QMetaType.Type.Double), ("mac", QMetaType.Type.Double),
                           ("max_abs_change", QMetaType.Type.Double),
                           ("share_changed_pct", QMetaType.Type.Double), ("rank", QMetaType.Type.Int)):
            fields.append(QgsField(name, kind))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields,
                                          Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        for i in order:
            f = QgsFeature(fields)
            f.setAttributes([
                i + 1, infer_layer_label(layers[i], f"criterion_{i + 1}"),
                round(float(weights[i]), 6), round(float(perturbed[i][0][i]), 6),
                round(float(perturbed[i][1][i]), 6), round(float(mac_up[i]), 6),
                round(float(mac_down[i]), 6), round(float(mac[i]), 6),
                round(float(max_abs[i]), 6), round(100.0 * float(over[i]) / cells, 4), rank[i],
            ])
            sink.addFeature(f)

        top = order[0]
        feedback.pushInfo(
            f"Most influential weight: criterion {top + 1} "
            f"({infer_layer_label(layers[top], f'criterion_{top + 1}')}), mean absolute change "
            f"{mac[top]:.3f} points for a {fraction * 100:.0f}% weight change over {cells} cells.")
        result = {self.OUTPUT: dest}
        if change_band is not None:
            change_band.FlushCache()
            change_band = None
            out_ds = None
            result[self.OUTPUT_CHANGE] = change_path
        return result
