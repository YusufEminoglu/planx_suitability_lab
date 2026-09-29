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

from .._mcda_utils import ensure_list, smart_output_path, limit_layers


class RegretFragilityMapAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    LOW = "LOW"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    OUT_SCORE = "OUT_SCORE"
    OUT_CLASS = "OUT_CLASS"

    def name(self):
        return "regret_fragility_map"

    def displayName(self):
        return "Compose: Regret Fragility Map"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return RegretFragilityMapAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Maps scenario-spread fragility to identify cells "
            "sensitive to scenario choice.</b></p>\n"
            "<p><b>Inputs:</b> 2–12 scenario suitability rasters (0–100); "
            "optional analysis mask (0/1); "
            "low fragility threshold (default 12); high fragility threshold "
            "(default 25); block size 64–2048.<br>\n"
            "<b>Output:</b> Fragility score raster (Float32, 0–100, "
            "nodata=−9999); fragility class raster (Byte, nodata=255).<br>\n"
            "<b>Method:</b> Per cell, spread = max − min across scenarios. "
            "Score = spread (higher = more scenario-dependent). "
            "Classes: 0=stable (spread < low), 1=watch (low ≤ spread < high), "
            "2=fragile (spread ≥ high). "
            "Chunk-aware block processing.<br>\n"
            "<b>Typical use:</b> Screening for scenario-robust sites: "
            "stable cells are reliable regardless of scenario; "
            "fragile cells require scenario-specific contingency plans.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario suitability rasters (2..12)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.MASK, "Optional analysis mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LOW,
                "Low fragility threshold (score)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=12.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH,
                "High fragility threshold (score)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=25.0,
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_SCORE, "Regret fragility score raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_CLASS, "Regret fragility class raster"))

    def processAlgorithm(self, parameters, context, feedback):
        layers = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 12, "scenario rasters")
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)
        low = float(self.parameterAsDouble(parameters, self.LOW, context))
        high = float(self.parameterAsDouble(parameters, self.HIGH, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        if high < low:
            high = low

        datasets = []
        bands = []
        nodatas = []
        xsize = None
        ysize = None
        proj = None
        gt = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            b = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
                proj = ds.GetProjection()
                gt = ds.GetGeoTransform()
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

        out_score = self.parameterAsOutputLayer(parameters, self.OUT_SCORE, context)
        out_class = self.parameterAsOutputLayer(parameters, self.OUT_CLASS, context)
        out_score = smart_output_path(out_score, layers[0], "regret_fragility_score")
        out_class = smart_output_path(out_class, layers[0], "regret_fragility_class")
        drv = gdal.GetDriverByName("GTiff")
        ds_score = drv.Create(out_score, xsize, ysize, 1, gdal.GDT_Float32, options=["TILED=YES", "COMPRESS=LZW"])
        ds_class = drv.Create(out_class, xsize, ysize, 1, gdal.GDT_Byte, options=["TILED=YES", "COMPRESS=LZW"])
        if ds_score is None or ds_class is None:
            raise QgsProcessingException("Could not create regret fragility outputs.")
        ds_score.SetProjection(proj)
        ds_score.SetGeoTransform(gt)
        ds_class.SetProjection(proj)
        ds_class.SetGeoTransform(gt)
        b_score = ds_score.GetRasterBand(1)
        b_class = ds_class.GetRasterBand(1)
        b_score.SetNoDataValue(-9999.0)
        b_class.SetNoDataValue(255)

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
                    valid = np.isfinite(raw)
                    nd = nodatas[i]
                    if nd is not None:
                        valid &= raw != nd
                    arrs.append(np.clip(raw, 0.0, 100.0))
                    valids.append(valid)

                valid_all = np.ones((rows, cols), dtype=bool)
                for v in valids:
                    valid_all &= v

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    mv = np.isfinite(ma)
                    if m_nodata is not None:
                        mv &= ma != m_nodata
                    mv &= ma > 0.5
                    valid_all &= mv

                score = np.full((rows, cols), -9999.0, dtype=np.float32)
                cls = np.full((rows, cols), 255, dtype=np.uint8)
                if np.any(valid_all):
                    stack = np.stack([a for a in arrs], axis=0)
                    spread = np.max(stack, axis=0) - np.min(stack, axis=0)
                    spread = np.clip(spread, 0.0, 100.0).astype(np.float32)
                    c = np.zeros((rows, cols), dtype=np.uint8)
                    c = np.where(spread < low, 0, c)
                    c = np.where((spread >= low) & (spread < high), 1, c)
                    c = np.where(spread >= high, 2, c)
                    score[valid_all] = spread[valid_all]
                    cls[valid_all] = c[valid_all]

                b_score.WriteArray(score, xoff, yoff)
                b_class.WriteArray(cls, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        b_score.FlushCache()
        b_class.FlushCache()
        ds_score = None
        ds_class = None
        return {self.OUT_SCORE: out_score, self.OUT_CLASS: out_class}
