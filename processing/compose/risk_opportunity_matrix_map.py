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


class RiskOpportunityMatrixMapAlgorithm(QgsProcessingAlgorithm):
    ROBUST = "ROBUST"
    UNC_STD = "UNC_STD"
    CONSTRAINT = "CONSTRAINT"
    ROBUST_HIGH = "ROBUST_HIGH"
    STD_HIGH = "STD_HIGH"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "risk_opportunity_matrix_map"

    def displayName(self):
        return "Compose: Risk-Opportunity Matrix Map"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return RiskOpportunityMatrixMapAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.ROBUST, "Robust suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.UNC_STD, "Uncertainty std raster (0-100 approx)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Optional hard constraint raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ROBUST_HIGH,
                "High robust suitability threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STD_HIGH,
                "High uncertainty (std) threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=15.0,
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Output risk-opportunity class raster"))

    def processAlgorithm(self, parameters, context, feedback):
        robust_rl = self.parameterAsRasterLayer(parameters, self.ROBUST, context)
        std_rl = self.parameterAsRasterLayer(parameters, self.UNC_STD, context)
        con_rl = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        robust_thr = float(self.parameterAsDouble(parameters, self.ROBUST_HIGH, context))
        std_thr = float(self.parameterAsDouble(parameters, self.STD_HIGH, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        ds_r = gdal.Open(robust_rl.source(), gdal.GA_ReadOnly)
        ds_s = gdal.Open(std_rl.source(), gdal.GA_ReadOnly)
        if ds_r is None or ds_s is None:
            raise QgsProcessingException("Cannot open robust/std rasters.")
        if ds_r.RasterXSize != ds_s.RasterXSize or ds_r.RasterYSize != ds_s.RasterYSize:
            raise QgsProcessingException("Robust and std rasters must share identical dimensions.")

        b_r = ds_r.GetRasterBand(1)
        b_s = ds_s.GetRasterBand(1)
        nd_r = b_r.GetNoDataValue()
        nd_s = b_s.GetNoDataValue()

        c_band = None
        c_nd = None
        if con_rl is not None:
            ds_c = gdal.Open(con_rl.source(), gdal.GA_ReadOnly)
            if ds_c is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if ds_c.RasterXSize != ds_r.RasterXSize or ds_c.RasterYSize != ds_r.RasterYSize:
                raise QgsProcessingException("Constraint raster must match robust/std grid.")
            c_band = ds_c.GetRasterBand(1)
            c_nd = c_band.GetNoDataValue()

        out_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out_path = smart_output_path(out_path, robust_rl, "risk_opportunity_matrix")
        drv = gdal.GetDriverByName("GTiff")
        out = drv.Create(
            out_path,
            ds_r.RasterXSize,
            ds_r.RasterYSize,
            1,
            gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW"],
        )
        if out is None:
            raise QgsProcessingException("Could not create risk-opportunity raster.")
        out.SetProjection(ds_r.GetProjection())
        out.SetGeoTransform(ds_r.GetGeoTransform())
        bo = out.GetRasterBand(1)
        bo.SetNoDataValue(255)

        xsize = ds_r.RasterXSize
        ysize = ds_r.RasterYSize
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

                rr = b_r.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                ss = b_s.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                valid = np.isfinite(rr) & np.isfinite(ss)
                if nd_r is not None:
                    valid &= rr != nd_r
                if nd_s is not None:
                    valid &= ss != nd_s
                rr = np.clip(rr, 0.0, 100.0)
                ss = np.clip(ss, 0.0, 100.0)

                if c_band is not None:
                    cc = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    cv = np.isfinite(cc)
                    if c_nd is not None:
                        cv &= cc != c_nd
                    cv &= cc > 0.5
                    valid &= cv

                cls = np.full((rows, cols), 255, dtype=np.uint8)
                if np.any(valid):
                    high_robust = rr >= robust_thr
                    high_unc = ss >= std_thr
                    q = np.zeros((rows, cols), dtype=np.uint8)
                    q = np.where(high_robust & (~high_unc), 1, q)      # Invest now
                    q = np.where(high_robust & high_unc, 2, q)         # Validate then invest
                    q = np.where((~high_robust) & (~high_unc), 3, q)   # Low strategic value
                    q = np.where((~high_robust) & high_unc, 4, q)      # Defer and monitor
                    cls[valid] = q[valid]

                bo.WriteArray(cls, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        bo.FlushCache()
        out = None
        return {self.OUTPUT: out_path}
