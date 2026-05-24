# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)


class PriorityZoningFromSuitabilityAlgorithm(QgsProcessingAlgorithm):
    SUIT = "SUIT"
    CONF = "CONF"
    OPP = "OPP"
    SUIT_MED = "SUIT_MED"
    SUIT_HIGH = "SUIT_HIGH"
    CONF_MED = "CONF_MED"
    CONF_HIGH = "CONF_HIGH"
    OPP_HIGH = "OPP_HIGH"
    BLOCK = "BLOCK"
    OUT_INDEX = "OUT_INDEX"
    OUT_ZONE = "OUT_ZONE"

    def name(self):
        return "priority_zoning_from_suitability"

    def displayName(self):
        return "Compose: Priority Zoning from Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return PriorityZoningFromSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUIT, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONF, "Confidence raster (0-100, optional)", optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.OPP, "Opportunity-loss raster (0-100, optional)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUIT_MED,
                "Suitability medium threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=50.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUIT_HIGH,
                "Suitability high threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=75.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONF_MED,
                "Confidence medium threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=60.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONF_HIGH,
                "Confidence high threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=80.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OPP_HIGH,
                "Opportunity-loss high threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=70.0,
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_INDEX, "priority_index"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_ZONE, "priority_zone"))

    @staticmethod
    def _create_output(template_ds, out_path, nodata, dtype=gdal.GDT_Float32):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            out_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            dtype,
            options=["COMPRESS=LZW", "TILED=YES"],
        )
        out_ds.SetGeoTransform(template_ds.GetGeoTransform())
        out_ds.SetProjection(template_ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(float(nodata))
        return out_ds, out_band

    def processAlgorithm(self, parameters, context, feedback):
        suit_rl = self.parameterAsRasterLayer(parameters, self.SUIT, context)
        conf_rl = self.parameterAsRasterLayer(parameters, self.CONF, context)
        opp_rl = self.parameterAsRasterLayer(parameters, self.OPP, context)
        suit_med = float(self.parameterAsDouble(parameters, self.SUIT_MED, context))
        suit_high = float(self.parameterAsDouble(parameters, self.SUIT_HIGH, context))
        conf_med = float(self.parameterAsDouble(parameters, self.CONF_MED, context))
        conf_high = float(self.parameterAsDouble(parameters, self.CONF_HIGH, context))
        opp_high = float(self.parameterAsDouble(parameters, self.OPP_HIGH, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out_idx = self.parameterAsOutputLayer(parameters, self.OUT_INDEX, context)
        out_zone = self.parameterAsOutputLayer(parameters, self.OUT_ZONE, context)

        ds_s = gdal.Open(suit_rl.source(), gdal.GA_ReadOnly)
        if ds_s is None:
            raise QgsProcessingException("Cannot open suitability raster.")
        bs = ds_s.GetRasterBand(1)
        nds = bs.GetNoDataValue()
        xsize = ds_s.RasterXSize
        ysize = ds_s.RasterYSize

        ds_c = None
        bc = None
        ndc = None
        if conf_rl is not None:
            ds_c = gdal.Open(conf_rl.source(), gdal.GA_ReadOnly)
            if ds_c is None:
                raise QgsProcessingException("Cannot open confidence raster.")
            if ds_c.RasterXSize != xsize or ds_c.RasterYSize != ysize:
                raise QgsProcessingException("Confidence raster must match suitability dimensions.")
            bc = ds_c.GetRasterBand(1)
            ndc = bc.GetNoDataValue()

        ds_o = None
        bo = None
        ndo = None
        if opp_rl is not None:
            ds_o = gdal.Open(opp_rl.source(), gdal.GA_ReadOnly)
            if ds_o is None:
                raise QgsProcessingException("Cannot open opportunity-loss raster.")
            if ds_o.RasterXSize != xsize or ds_o.RasterYSize != ysize:
                raise QgsProcessingException("Opportunity-loss raster must match suitability dimensions.")
            bo = ds_o.GetRasterBand(1)
            ndo = bo.GetNoDataValue()

        out_nodata = nds if nds is not None else -9999.0
        ds_out_idx, b_out_idx = self._create_output(ds_s, out_idx, out_nodata, dtype=gdal.GDT_Float32)
        ds_out_zone, b_out_zone = self._create_output(ds_s, out_zone, out_nodata, dtype=gdal.GDT_Int16)

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

                s = bs.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                s = np.clip(s, 0.0, 100.0)
                valid = np.isfinite(s)
                if nds is not None:
                    valid &= s != nds

                if bc is not None:
                    c = bc.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c = np.clip(c, 0.0, 100.0)
                    vc = np.isfinite(c)
                    if ndc is not None:
                        vc &= c != ndc
                    valid &= vc
                else:
                    c = np.full((rows, cols), 75.0, dtype=np.float32)

                if bo is not None:
                    o = bo.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    o = np.clip(o, 0.0, 100.0)
                    vo = np.isfinite(o)
                    if ndo is not None:
                        vo &= o != ndo
                    valid &= vo
                else:
                    o = np.zeros((rows, cols), dtype=np.float32)

                idx = np.clip((0.60 * s) + (0.30 * c) - (0.20 * o), 0.0, 100.0).astype(np.float32)

                zone = np.zeros((rows, cols), dtype=np.int16)
                # 4: Constraint-revisit critical (high potential lost)
                zone[valid & (o >= opp_high)] = 4
                # 3: Immediate priority
                zone[valid & (o < opp_high) & (s >= suit_high) & (c >= conf_high)] = 3
                # 2: Detailed feasibility
                zone[valid & (zone == 0) & (s >= suit_med) & (c >= conf_med)] = 2
                # 1: Longlist candidate
                zone[valid & (zone == 0) & (s >= suit_med)] = 1
                # 0: Low priority remains

                out_idx_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_zone_arr = np.full((rows, cols), int(out_nodata), dtype=np.int16)
                out_idx_arr[valid] = idx[valid]
                out_zone_arr[valid] = zone[valid]

                b_out_idx.WriteArray(out_idx_arr, xoff, yoff)
                b_out_zone.WriteArray(out_zone_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        ds_out_idx = None
        ds_out_zone = None
        ds_s = None
        ds_c = None
        ds_o = None
        return {self.OUT_INDEX: out_idx, self.OUT_ZONE: out_zone}
