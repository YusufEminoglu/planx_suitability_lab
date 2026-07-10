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


class ScenarioConsensusZoneAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    CONSTRAINT = "CONSTRAINT"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    OUT_COUNT = "OUT_COUNT"
    OUT_ZONE = "OUT_ZONE"

    def name(self):
        return "scenario_consensus_zone"

    def displayName(self):
        return "Compose: Scenario Consensus Zone"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return ScenarioConsensusZoneAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Maps per-cell scenario agreement counts and classifies "
            "consensus zones.</b></p>\n"
            "<p><b>Inputs:</b> 2–10 scenario suitability rasters (0–100); "
            "optional constraint mask (0/1); "
            "medium suitability threshold (default 60); "
            "high suitability threshold (default 75); block size 64–2048.<br>\n"
            "<b>Output:</b> Consensus count raster (Byte, 0..N scenarios); "
            "consensus zone raster (Byte, 0–4). "
            "Nodata=255 where inputs are invalid.<br>\n"
            "<b>Method:</b> Per cell, count scenarios meeting medium (≥med) "
            "and high (≥high) thresholds. Zone classes by agreement ratio: "
            "0=none, 1=≥50% medium, 2=≥75% medium, 3=≥60% high, "
            "4=≥85% near-unanimous high. "
            "Chunk-aware block processing.<br>\n"
            "<b>Typical use:</b> Identify robust planning zones where multiple "
            "scenarios agree on suitability, vs. contested areas.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario suitability rasters (2..10)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Optional hard constraint raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MEDIUM,
                "Medium suitability threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=60.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH,
                "High suitability threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=75.0,
                minValue=0.0,
                maxValue=100.0,
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_COUNT, "Output consensus count raster"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_ZONE, "Output consensus zone raster"))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:10]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        medium = float(self.parameterAsDouble(parameters, self.MEDIUM, context))
        high = float(self.parameterAsDouble(parameters, self.HIGH, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        if high < medium:
            raise QgsProcessingException("High threshold must be greater than or equal to medium threshold.")

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

        out_count = self.parameterAsOutputLayer(parameters, self.OUT_COUNT, context)
        out_zone = self.parameterAsOutputLayer(parameters, self.OUT_ZONE, context)
        out_count = smart_output_path(out_count, layers[0], "scenario_consensus_count")
        out_zone = smart_output_path(out_zone, layers[0], "scenario_consensus_zone")
        drv = gdal.GetDriverByName("GTiff")
        o_count = drv.Create(out_count, xsize, ysize, 1, gdal.GDT_Byte, options=["TILED=YES", "COMPRESS=LZW"])
        o_zone = drv.Create(out_zone, xsize, ysize, 1, gdal.GDT_Byte, options=["TILED=YES", "COMPRESS=LZW"])
        if o_count is None or o_zone is None:
            raise QgsProcessingException("Could not create consensus output rasters.")
        o_count.SetProjection(proj)
        o_count.SetGeoTransform(gt)
        o_zone.SetProjection(proj)
        o_zone.SetGeoTransform(gt)
        bo_count = o_count.GetRasterBand(1)
        bo_zone = o_zone.GetRasterBand(1)
        bo_count.SetNoDataValue(255)
        bo_zone.SetNoDataValue(255)

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

                valid = None
                high_count = None
                med_count = None
                for i, b in enumerate(b_list):
                    arr = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    arr = np.clip(arr, 0.0, 100.0)
                    ok = np.isfinite(arr)
                    nd = nd_list[i]
                    if nd is not None:
                        ok &= arr != nd
                    valid = ok if valid is None else (valid & ok)
                    is_high = (arr >= high).astype(np.uint8)
                    is_med = (arr >= medium).astype(np.uint8)
                    high_count = is_high if high_count is None else (high_count + is_high)
                    med_count = is_med if med_count is None else (med_count + is_med)

                if c_band is not None:
                    ca = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_ok = np.isfinite(ca)
                    if c_nd is not None:
                        c_ok &= ca != c_nd
                    c_ok &= ca > 0.5
                    valid &= c_ok

                out_c = np.full((rows, cols), 255, dtype=np.uint8)
                out_z = np.full((rows, cols), 255, dtype=np.uint8)

                if np.any(valid):
                    hc = np.clip(high_count[valid], 0, n).astype(np.uint8)
                    mc = np.clip(med_count[valid], 0, n).astype(np.uint8)
                    ratio_high = hc.astype(np.float32) / float(n)
                    ratio_med = mc.astype(np.float32) / float(n)

                    # Zone classes:
                    # 0 = no/very low consensus
                    # 1 = medium consensus
                    # 2 = high medium-threshold consensus
                    # 3 = high high-threshold consensus
                    # 4 = near-unanimous high-threshold consensus
                    z = np.zeros_like(hc, dtype=np.uint8)
                    z = np.where(ratio_med >= 0.50, 1, z)
                    z = np.where(ratio_med >= 0.75, 2, z)
                    z = np.where(ratio_high >= 0.60, 3, z)
                    z = np.where(ratio_high >= 0.85, 4, z)
                    out_c[valid] = hc
                    out_z[valid] = z

                bo_count.WriteArray(out_c, xoff, yoff)
                bo_zone.WriteArray(out_z, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        bo_count.FlushCache()
        bo_zone.FlushCache()
        o_count = None
        o_zone = None
        return {self.OUT_COUNT: out_count, self.OUT_ZONE: out_zone}
