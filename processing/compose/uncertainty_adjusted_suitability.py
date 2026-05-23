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


class UncertaintyAdjustedSuitabilityAlgorithm(QgsProcessingAlgorithm):
    MEAN = "MEAN"
    STD = "STD"
    RISK = "RISK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "uncertainty_adjusted_suitability"

    def displayName(self):
        return "Compose: Uncertainty-Adjusted Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return UncertaintyAdjustedSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.MEAN, "Uncertainty mean raster (unc_mean)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.STD, "Uncertainty std raster (unc_std)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RISK,
                "Risk aversion factor (lambda)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.0,
                maxValue=5.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_robust"))

    def _create_output(self, template_ds, out_path, nodata):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            out_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=["COMPRESS=LZW", "TILED=YES"],
        )
        out_ds.SetGeoTransform(template_ds.GetGeoTransform())
        out_ds.SetProjection(template_ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(float(nodata))
        return out_ds, out_band

    def processAlgorithm(self, parameters, context, feedback):
        mean_rl = self.parameterAsRasterLayer(parameters, self.MEAN, context)
        std_rl = self.parameterAsRasterLayer(parameters, self.STD, context)
        lam = float(self.parameterAsDouble(parameters, self.RISK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        ds_m = gdal.Open(mean_rl.source(), gdal.GA_ReadOnly)
        ds_s = gdal.Open(std_rl.source(), gdal.GA_ReadOnly)
        if ds_m is None or ds_s is None:
            raise QgsProcessingException("Cannot open uncertainty mean/std rasters.")
        if ds_m.RasterXSize != ds_s.RasterXSize or ds_m.RasterYSize != ds_s.RasterYSize:
            raise QgsProcessingException("Mean and std rasters must have same dimensions.")

        bm = ds_m.GetRasterBand(1)
        bs = ds_s.GetRasterBand(1)
        ndm = bm.GetNoDataValue()
        nds = bs.GetNoDataValue()
        out_nodata = ndm if ndm is not None else (nds if nds is not None else -9999.0)

        mean = bm.ReadAsArray().astype(np.float32)
        std = bs.ReadAsArray().astype(np.float32)
        valid = np.isfinite(mean) & np.isfinite(std)
        if ndm is not None:
            valid &= mean != ndm
        if nds is not None:
            valid &= std != nds

        robust = np.clip(mean - lam * std, 0.0, 100.0).astype(np.float32)
        robust = np.where(valid, robust, out_nodata).astype(np.float32)

        out_ds, out_band = self._create_output(ds_m, out, out_nodata)
        out_band.WriteArray(robust)
        out_ds = None
        ds_m = None
        ds_s = None
        return {self.OUTPUT: out}

