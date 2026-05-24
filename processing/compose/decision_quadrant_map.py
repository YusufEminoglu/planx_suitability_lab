# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)
from .._mcda_utils import smart_output_path


class DecisionQuadrantMapAlgorithm(QgsProcessingAlgorithm):
    SUITABILITY = "SUITABILITY"
    DISAGREEMENT = "DISAGREEMENT"
    CONSTRAINT = "CONSTRAINT"
    SUIT_HIGH = "SUIT_HIGH"
    DISAGREE_HIGH = "DISAGREE_HIGH"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "decision_quadrant_map"

    def displayName(self):
        return "Compose: Decision Quadrant Map"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return DecisionQuadrantMapAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUITABILITY, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.DISAGREEMENT, "Disagreement score raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Optional hard constraint raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUIT_HIGH,
                "High suitability threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DISAGREE_HIGH,
                "High disagreement threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=60.0,
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Output decision quadrant class raster"))

    def processAlgorithm(self, parameters, context, feedback):
        suit_rl = self.parameterAsRasterLayer(parameters, self.SUITABILITY, context)
        dis_rl = self.parameterAsRasterLayer(parameters, self.DISAGREEMENT, context)
        con_rl = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        suit_thr = float(self.parameterAsDouble(parameters, self.SUIT_HIGH, context))
        dis_thr = float(self.parameterAsDouble(parameters, self.DISAGREE_HIGH, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        ds_s = gdal.Open(suit_rl.source(), gdal.GA_ReadOnly)
        ds_d = gdal.Open(dis_rl.source(), gdal.GA_ReadOnly)
        if ds_s is None or ds_d is None:
            raise QgsProcessingException("Cannot open suitability/disagreement raster.")
        if ds_s.RasterXSize != ds_d.RasterXSize or ds_s.RasterYSize != ds_d.RasterYSize:
            raise QgsProcessingException("Suitability and disagreement rasters must share identical dimensions.")

        b_s = ds_s.GetRasterBand(1)
        b_d = ds_d.GetRasterBand(1)
        nd_s = b_s.GetNoDataValue()
        nd_d = b_d.GetNoDataValue()

        c_band = None
        c_nd = None
        if con_rl is not None:
            ds_c = gdal.Open(con_rl.source(), gdal.GA_ReadOnly)
            if ds_c is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if ds_c.RasterXSize != ds_s.RasterXSize or ds_c.RasterYSize != ds_s.RasterYSize:
                raise QgsProcessingException("Constraint raster must match suitability/disagreement grid.")
            c_band = ds_c.GetRasterBand(1)
            c_nd = c_band.GetNoDataValue()

        out_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out_path = smart_output_path(out_path, suit_rl, "decision_quadrant_map")
        drv = gdal.GetDriverByName("GTiff")
        out = drv.Create(
            out_path,
            ds_s.RasterXSize,
            ds_s.RasterYSize,
            1,
            gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW"],
        )
        if out is None:
            raise QgsProcessingException("Could not create decision quadrant raster.")
        out.SetProjection(ds_s.GetProjection())
        out.SetGeoTransform(ds_s.GetGeoTransform())
        bo = out.GetRasterBand(1)
        bo.SetNoDataValue(255)

        xsize = ds_s.RasterXSize
        ysize = ds_s.RasterYSize
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

                s = b_s.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                d = b_d.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                s = np.clip(s, 0.0, 100.0)
                d = np.clip(d, 0.0, 100.0)
                valid = np.isfinite(s) & np.isfinite(d)
                if nd_s is not None:
                    valid &= s != nd_s
                if nd_d is not None:
                    valid &= d != nd_d

                if c_band is not None:
                    c = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_ok = np.isfinite(c)
                    if c_nd is not None:
                        c_ok &= c != c_nd
                    c_ok &= c > 0.5
                    valid &= c_ok

                cls = np.full((rows, cols), 255, dtype=np.uint8)
                if np.any(valid):
                    high_s = s >= suit_thr
                    high_d = d >= dis_thr
                    q = np.zeros((rows, cols), dtype=np.uint8)
                    q = np.where(high_s & (~high_d), 1, q)      # High suitability, low conflict
                    q = np.where(high_s & high_d, 2, q)         # High suitability, high conflict
                    q = np.where((~high_s) & (~high_d), 3, q)   # Low suitability, low conflict
                    q = np.where((~high_s) & high_d, 4, q)      # Low suitability, high conflict
                    cls[valid] = q[valid]

                bo.WriteArray(cls, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        bo.FlushCache()
        out = None
        return {self.OUTPUT: out_path}
