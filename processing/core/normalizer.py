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
from .._mcda_utils import smart_output_path, style_raster_output


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

    def shortHelpString(self):
        return (
            "<p><b>Transforms a raw criterion raster to a 0-100 suitability scale using one of "
            "seven fuzzy or linear normalisation functions.</b></p>"
            "<p><b>Inputs:</b> Input raster (single-band); method: Min-Max Benefit (0), Min-Max Cost (1), "
            "Fuzzy Linear Benefit (2), Fuzzy Linear Cost (3), Fuzzy Sigmoid Benefit (4), "
            "Fuzzy Sigmoid Cost (5), Fuzzy Gaussian Benefit (6); low bound (min or lower breakpoint); "
            "high bound (max or upper breakpoint, must be > low); midpoint for sigmoid/gaussian curves (default 50); "
            "spread for sigmoid/gaussian steepness (>0, default 10).<br>"
            "<b>Output:</b> Single-band Float32 LZW-compressed GeoTIFF, values clipped 0-100, "
            "original nodata cells preserved unchanged.<br>"
            "<b>Method:</b> Benefit min-max: (x-low)/(high-low)*100. Cost min-max: (high-x)/(high-low)*100. "
            "Sigmoid benefit: 100/(1+e^-z) with z = (x-mid)/spread clamped to [-60,60]. "
            "Sigmoid cost: 100 minus the sigmoid benefit. Gaussian benefit: 100*exp(-0.5*((x-mid)/spread)^2). "
            "The entire raster is read into memory (NumPy) - very large rasters may exhaust RAM. "
            "Nodata cells are detected from the input band's nodata value and excluded from computation.<br>"
            "<b>Typical use:</b> Standardising heterogeneous criteria (slope, distance, land value, "
            "population density) to a common 0-100 scale before weighted overlay. "
            "Use benefit methods when higher raw values are desirable; cost when lower is better.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return NormalizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input raster"))
        self.addParameter(QgsProcessingParameterEnum(self.METHOD, "Method", options=self.METHODS, defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LOW,
                "Low bound (min or lower breakpoint)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH,
                "High bound (max or upper breakpoint)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MID,
                "Midpoint (sigmoid/gaussian)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=50.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPREAD,
                "Spread (>0) for sigmoid/gaussian",
                type=QgsProcessingParameterNumber.Type.Double,
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
        style_raster_output(context, out, "score")
        return {self.OUTPUT: out}
