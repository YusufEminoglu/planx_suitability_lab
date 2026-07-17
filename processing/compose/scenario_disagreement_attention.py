# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .._mcda_utils import ensure_list, smart_output_path


class ScenarioDisagreementAttentionAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    CONSTRAINT = "CONSTRAINT"
    STD_REF = "STD_REF"
    HIGH_MEAN = "HIGH_MEAN"
    BLOCK = "BLOCK"
    OUT_SCORE = "OUT_SCORE"
    OUT_CLASS = "OUT_CLASS"

    def name(self):
        return "scenario_disagreement_attention"

    def displayName(self):
        return "Compose: Scenario Disagreement Attention"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return ScenarioDisagreementAttentionAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Quantifies cross-scenario conflict per cell and assigns "
            "attention classes for planning review.</b></p>\n"
            "<p><b>Inputs:</b> 2–10 scenario suitability rasters (0–100); "
            "optional constraint mask (0/1); "
            "reference std for full disagreement (default 18); "
            "high-mean threshold for critical conflict (default 70); "
            "block size 64–2048.<br>\n"
            "<b>Output:</b> Disagreement score raster (Float32, 0–100); "
            "attention class raster (Byte, 0–4). "
            "Score nodata = −9999, class nodata = 255.<br>\n"
            "<b>Method:</b> Per cell, std across scenarios normalised by "
            "reference std: score = (std/ref_std)×100 clipped 0–100. "
            "Classes: 0=low (<20), 1=watch (≥20), 2=review (≥40), "
            "3=high conflict (≥60), 4=critical (≥75 with high mean). "
            "High mean + high conflict flags areas needing urgent attention.<br>\n"
            "<b>Typical use:</b> Pinpoint locations where scenarios diverge "
            "most, prioritising field validation or stakeholder deliberation.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario suitability rasters (2..10)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Optional hard constraint raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STD_REF,
                "Reference std interpreted as 100 disagreement score",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=18.0,
                minValue=1.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH_MEAN,
                "High suitability threshold for critical conflict",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_SCORE, "Output disagreement score raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_CLASS, "Output attention class raster (0..4)"))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:10]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        std_ref = float(self.parameterAsDouble(parameters, self.STD_REF, context))
        high_mean = float(self.parameterAsDouble(parameters, self.HIGH_MEAN, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        ds_list = []
        b_list = []
        nd_list = []
        xsize = None
        ysize = None
        proj = None
        gt = None
        for rl in layers:
            ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open scenario raster: {rl.name()}")
            band = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
                proj = ds.GetProjection()
                gt = ds.GetGeoTransform()
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All scenario rasters must share the same grid dimensions.")
            ds_list.append(ds)
            b_list.append(band)
            nd_list.append(band.GetNoDataValue())

        c_band = None
        c_nd = None
        if constraint is not None:
            c_ds = gdal.Open(constraint.source(), gdal.GA_ReadOnly)
            if c_ds is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if c_ds.RasterXSize != xsize or c_ds.RasterYSize != ysize:
                raise QgsProcessingException("Constraint raster must match scenario grid dimensions.")
            c_band = c_ds.GetRasterBand(1)
            c_nd = c_band.GetNoDataValue()

        out_score = self.parameterAsOutputLayer(parameters, self.OUT_SCORE, context)
        out_class = self.parameterAsOutputLayer(parameters, self.OUT_CLASS, context)
        out_score = smart_output_path(out_score, layers[0], "scenario_disagreement_score")
        out_class = smart_output_path(out_class, layers[0], "scenario_disagreement_class")
        drv = gdal.GetDriverByName("GTiff")
        o_score = drv.Create(out_score, xsize, ysize, 1, gdal.GDT_Float32, options=["TILED=YES", "COMPRESS=LZW"])
        o_class = drv.Create(out_class, xsize, ysize, 1, gdal.GDT_Byte, options=["TILED=YES", "COMPRESS=LZW"])
        if o_score is None or o_class is None:
            raise QgsProcessingException("Could not create disagreement output rasters.")
        o_score.SetProjection(proj)
        o_score.SetGeoTransform(gt)
        o_class.SetProjection(proj)
        o_class.SetGeoTransform(gt)
        bo_score = o_score.GetRasterBand(1)
        bo_class = o_class.GetRasterBand(1)
        bo_score.SetNoDataValue(-9999.0)
        bo_class.SetNoDataValue(255)

        n = len(b_list)
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

                arr_stack = []
                valid = None
                for i, b in enumerate(b_list):
                    arr = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    arr = np.clip(arr, 0.0, 100.0)
                    ok = np.isfinite(arr)
                    nd = nd_list[i]
                    if nd is not None:
                        ok &= arr != nd
                    valid = ok if valid is None else (valid & ok)
                    arr_stack.append(arr)

                if c_band is not None:
                    ca = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_ok = np.isfinite(ca)
                    if c_nd is not None:
                        c_ok &= ca != c_nd
                    c_ok &= ca > 0.5
                    valid &= c_ok

                out_s = np.full((rows, cols), -9999.0, dtype=np.float32)
                out_c = np.full((rows, cols), 255, dtype=np.uint8)

                if np.any(valid):
                    stack = np.stack(arr_stack, axis=0)
                    means = np.mean(stack, axis=0)
                    stds = np.std(stack, axis=0)
                    score = np.clip((stds / max(std_ref, 1e-9)) * 100.0, 0.0, 100.0).astype(np.float32)

                    cls = np.zeros((rows, cols), dtype=np.uint8)
                    cls = np.where(score >= 20.0, 1, cls)  # Watch
                    cls = np.where(score >= 40.0, 2, cls)  # Review
                    cls = np.where(score >= 60.0, 3, cls)  # High conflict
                    cls = np.where((score >= 75.0) & (means >= high_mean), 4, cls)  # Critical conflict

                    out_s[valid] = score[valid]
                    out_c[valid] = cls[valid]

                bo_score.WriteArray(out_s, xoff, yoff)
                bo_class.WriteArray(out_c, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        bo_score.FlushCache()
        bo_class.FlushCache()
        o_score = None
        o_class = None
        return {self.OUT_SCORE: out_score, self.OUT_CLASS: out_class}
