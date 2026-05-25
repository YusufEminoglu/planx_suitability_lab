# -*- coding: utf-8 -*-
from __future__ import annotations

from itertools import combinations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
)

from .._mcda_utils import ensure_list


class ScenarioDominanceMatrixAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    EPS = "EPS"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_dominance_matrix"

    def displayName(self):
        return "Reporting: Scenario Dominance Matrix"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ScenarioDominanceMatrixAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario suitability rasters (2..12)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.MASK, "Optional analysis mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.EPS,
                "Tie epsilon (absolute difference)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0.0,
                maxValue=20.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario dominance matrix", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:12]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)
        eps = float(self.parameterAsDouble(parameters, self.EPS, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        names = [l.name() for l in layers]
        n_s = len(layers)
        datasets = []
        bands = []
        nodatas = []
        xsize = None
        ysize = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            b = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All scenario rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(b)
            nodatas.append(b.GetNoDataValue())

        m_band = None
        m_nodata = None
        if mask is not None:
            m_ds = gdal.Open(mask.source(), gdal.GA_ReadOnly)
            if m_ds is None:
                raise QgsProcessingException("Cannot open mask raster.")
            if m_ds.RasterXSize != xsize or m_ds.RasterYSize != ysize:
                raise QgsProcessingException("Mask raster must match scenario raster dimensions.")
            m_band = m_ds.GetRasterBand(1)
            m_nodata = m_band.GetNoDataValue()

        win_counts = np.zeros((n_s, n_s), dtype=np.float64)
        lose_counts = np.zeros((n_s, n_s), dtype=np.float64)
        tie_counts = np.zeros((n_s, n_s), dtype=np.float64)
        total_pair = np.zeros((n_s, n_s), dtype=np.float64)
        mean_diff_sum = np.zeros((n_s, n_s), dtype=np.float64)

        pairs = list(combinations(range(n_s), 2))
        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)
        done = 0

        for yoff in range(0, ysize, block):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    break
                cols = min(block, xsize - xoff)

                arrs = []
                valids = []
                for i, b in enumerate(bands):
                    raw = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    v = np.isfinite(raw)
                    nd = nodatas[i]
                    if nd is not None:
                        v &= raw != nd
                    arrs.append(np.clip(raw, 0.0, 100.0))
                    valids.append(v)

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    mv = np.isfinite(ma)
                    if m_nodata is not None:
                        mv &= ma != m_nodata
                    mv &= ma > 0.5
                else:
                    mv = None

                for i, j in pairs:
                    valid = valids[i] & valids[j]
                    if mv is not None:
                        valid &= mv
                    if not np.any(valid):
                        continue
                    ai = arrs[i][valid].astype(np.float64)
                    aj = arrs[j][valid].astype(np.float64)
                    diff = ai - aj
                    n = float(diff.size)
                    total_pair[i, j] += n
                    total_pair[j, i] += n
                    mean_diff_sum[i, j] += float(np.sum(diff))
                    mean_diff_sum[j, i] += float(np.sum(-diff))

                    wins_i = float(np.sum(diff > eps))
                    wins_j = float(np.sum(diff < -eps))
                    ties = float(np.sum(np.abs(diff) <= eps))
                    win_counts[i, j] += wins_i
                    lose_counts[i, j] += wins_j
                    tie_counts[i, j] += ties
                    win_counts[j, i] += wins_j
                    lose_counts[j, i] += wins_i
                    tie_counts[j, i] += ties

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        fields = QgsFields()
        fields.append(QgsField("row_type", QVariant.String))
        fields.append(QgsField("scenario_a", QVariant.String))
        fields.append(QgsField("scenario_b", QVariant.String))
        fields.append(QgsField("wins_pct", QVariant.Double))
        fields.append(QgsField("loss_pct", QVariant.Double))
        fields.append(QgsField("tie_pct", QVariant.Double))
        fields.append(QgsField("mean_diff", QVariant.Double))
        fields.append(QgsField("net_dom", QVariant.Double))
        fields.append(QgsField("rank", QVariant.Int))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        # Pairwise rows
        for i, j in pairs:
            n = total_pair[i, j]
            if n <= 0:
                continue
            wp = float(100.0 * win_counts[i, j] / n)
            lp = float(100.0 * lose_counts[i, j] / n)
            tp = float(100.0 * tie_counts[i, j] / n)
            md = float(mean_diff_sum[i, j] / n)
            nd = float(wp - lp)
            f = QgsFeature(fields)
            f["row_type"] = "PAIR"
            f["scenario_a"] = names[i]
            f["scenario_b"] = names[j]
            f["wins_pct"] = wp
            f["loss_pct"] = lp
            f["tie_pct"] = tp
            f["mean_diff"] = md
            f["net_dom"] = nd
            f["rank"] = 0
            sink.addFeature(f)

        # Scenario summary rows
        summary = []
        for i in range(n_s):
            ns = []
            for j in range(n_s):
                if i == j:
                    continue
                n = total_pair[i, j]
                if n <= 0:
                    continue
                wp = float(100.0 * win_counts[i, j] / n)
                lp = float(100.0 * lose_counts[i, j] / n)
                ns.append(wp - lp)
            net = float(np.mean(ns)) if ns else 0.0
            summary.append((names[i], net))
        summary.sort(key=lambda x: (-x[1], x[0]))
        for rank, (name, net) in enumerate(summary, start=1):
            f = QgsFeature(fields)
            f["row_type"] = "SCENARIO"
            f["scenario_a"] = name
            f["scenario_b"] = "__ALL__"
            f["wins_pct"] = 0.0
            f["loss_pct"] = 0.0
            f["tie_pct"] = 0.0
            f["mean_diff"] = 0.0
            f["net_dom"] = float(net)
            f["rank"] = int(rank)
            sink.addFeature(f)

        if summary:
            feedback.pushInfo(f"Dominance leader: {summary[0][0]} (net_dom={summary[0][1]:.2f})")
        return {self.OUTPUT: dest}

