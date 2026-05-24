# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)
from .._mcda_utils import smart_output_path


class NormalizerAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    METHOD = "METHOD"
    LOW = "LOW"
    HIGH = "HIGH"
    MID = "MID"
    SPREAD = "SPREAD"
    OUTPUT = "OUTPUT"

    METHODS = [
        "Min-Max (Benefit)",
        "Min-Max (Cost)",
        "Fuzzy Linear (Benefit)",
        "Fuzzy Linear (Cost)",
        "Fuzzy Sigmoid (Benefit)",
        "Fuzzy Sigmoid (Cost)",
        "Fuzzy Gaussian (Benefit)",
    ]

    def name(self):
        return "normalizer_reclassifier"

    def displayName(self):
        return "Core: Normalizer/Reclassifier"

    def group(self):
        return "Core"

    def groupId(self):
        return "core"

    def createInstance(self):
        return NormalizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input raster"))
        self.addParameter(QgsProcessingParameterEnum(self.METHOD, "Method", options=self.METHODS, defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LOW,
                "Low bound (min or lower breakpoint)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH,
                "High bound (max or upper breakpoint)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MID,
                "Midpoint (sigmoid/gaussian)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=50.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPREAD,
                "Spread (>0) for sigmoid/gaussian",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=10.0,
                minValue=0.0001,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Normalized raster (0-100)"))

    def _write_like(self, template_ds, output_path, array, nodata):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            output_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=["COMPRESS=LZW", "TILED=YES"],
        )
        out_ds.SetGeoTransform(template_ds.GetGeoTransform())
        out_ds.SetProjection(template_ds.GetProjection())
        band = out_ds.GetRasterBand(1)
        band.WriteArray(array.astype(np.float32))
        if nodata is not None:
            band.SetNoDataValue(float(nodata))
        band.FlushCache()
        out_ds = None

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        method = int(self.parameterAsEnum(parameters, self.METHOD, context))
        low = float(self.parameterAsDouble(parameters, self.LOW, context))
        high = float(self.parameterAsDouble(parameters, self.HIGH, context))
        mid = float(self.parameterAsDouble(parameters, self.MID, context))
        spread = float(self.parameterAsDouble(parameters, self.SPREAD, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, rl, "normalizer_reclassifier")

        if high <= low:
            raise QgsProcessingException("HIGH must be greater than LOW.")
        if spread <= 0:
            raise QgsProcessingException("SPREAD must be greater than 0.")

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open input raster for normalization.")
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()

        valid = np.isfinite(arr)
        if nodata is not None:
            valid &= arr != nodata
        norm = np.zeros_like(arr, dtype=np.float32)

        x = arr.astype(np.float32)
        if method in (0, 2):  # benefit min-max / fuzzy linear benefit
            norm = (x - low) / (high - low)
        elif method in (1, 3):  # cost min-max / fuzzy linear cost
            norm = (high - x) / (high - low)
        elif method == 4:  # sigmoid benefit
            z = np.clip((x - mid) / spread, -60.0, 60.0)
            norm = 1.0 / (1.0 + np.exp(-z))
        elif method == 5:  # sigmoid cost
            z = np.clip((x - mid) / spread, -60.0, 60.0)
            norm = 1.0 - (1.0 / (1.0 + np.exp(-z)))
        elif method == 6:  # gaussian benefit
            norm = np.exp(-0.5 * ((x - mid) / spread) ** 2)

        norm = np.clip(norm, 0.0, 1.0) * 100.0
        if nodata is not None:
            norm[~valid] = nodata
        self._write_like(ds, out, norm, nodata)
        return {self.OUTPUT: out}
