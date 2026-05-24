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


class OpportunityLossMapAlgorithm(QgsProcessingAlgorithm):
    SUIT = "SUIT"
    CONSTRAINT = "CONSTRAINT"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCK = "BLOCK"
    OUT_LOSS = "OUT_LOSS"
    OUT_CLASS = "OUT_CLASS"

    def name(self):
        return "opportunity_loss_map"

    def displayName(self):
        return "Compose: Opportunity Loss Map (Hard Constraint Trade-off)"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return OpportunityLossMapAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUIT, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MEDIUM,
                "Medium-loss threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=40.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH,
                "High-loss threshold",
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_LOSS, "opportunity_loss_score"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_CLASS, "opportunity_loss_class"))

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
        suit = self.parameterAsRasterLayer(parameters, self.SUIT, context)
        con = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        med = float(self.parameterAsDouble(parameters, self.MEDIUM, context))
        high = float(self.parameterAsDouble(parameters, self.HIGH, context))
        if high <= med:
            raise QgsProcessingException("High-loss threshold must be greater than medium-loss threshold.")
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out_loss = self.parameterAsOutputLayer(parameters, self.OUT_LOSS, context)
        out_class = self.parameterAsOutputLayer(parameters, self.OUT_CLASS, context)

        ds_s = gdal.Open(suit.source(), gdal.GA_ReadOnly)
        ds_c = gdal.Open(con.source(), gdal.GA_ReadOnly)
        if ds_s is None or ds_c is None:
            raise QgsProcessingException("Cannot open suitability or constraint raster.")
        if ds_s.RasterXSize != ds_c.RasterXSize or ds_s.RasterYSize != ds_c.RasterYSize:
            raise QgsProcessingException("Suitability and constraint rasters must share identical dimensions.")

        bs = ds_s.GetRasterBand(1)
        bc = ds_c.GetRasterBand(1)
        nds = bs.GetNoDataValue()
        ndc = bc.GetNoDataValue()
        xsize = ds_s.RasterXSize
        ysize = ds_s.RasterYSize
        out_nodata = nds if nds is not None else -9999.0

        ds_out_loss, b_out_loss = self._create_output(ds_s, out_loss, out_nodata, dtype=gdal.GDT_Float32)
        ds_out_cls, b_out_cls = self._create_output(ds_s, out_class, out_nodata, dtype=gdal.GDT_Int16)

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

                s_arr = bs.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                c_arr = bc.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)

                valid_s = np.isfinite(s_arr)
                if nds is not None:
                    valid_s &= s_arr != nds
                valid_c = np.isfinite(c_arr)
                if ndc is not None:
                    valid_c &= c_arr != ndc
                valid = valid_s & valid_c

                s_arr = np.clip(s_arr, 0.0, 100.0)
                fail = valid & (c_arr <= 0.5)
                pass_or_invalid = ~fail

                loss = np.zeros((rows, cols), dtype=np.float32)
                loss[fail] = s_arr[fail]

                cls = np.zeros((rows, cols), dtype=np.int16)
                cls[(fail) & (loss > 0) & (loss < med)] = 1
                cls[(fail) & (loss >= med) & (loss < high)] = 2
                cls[(fail) & (loss >= high)] = 3

                out_loss_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_cls_arr = np.full((rows, cols), int(out_nodata), dtype=np.int16)
                out_loss_arr[valid] = loss[valid]
                out_cls_arr[valid] = cls[valid]
                out_loss_arr[pass_or_invalid & valid] = 0.0
                out_cls_arr[pass_or_invalid & valid] = 0

                b_out_loss.WriteArray(out_loss_arr, xoff, yoff)
                b_out_cls.WriteArray(out_cls_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        ds_out_loss = None
        ds_out_cls = None
        ds_s = None
        ds_c = None

        return {self.OUT_LOSS: out_loss, self.OUT_CLASS: out_class}
