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
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_weights_csv, smart_output_path, limit_layers


class GeoShapleyLiteAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    SAMPLE = "SAMPLE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "xai_geoshapley_lite"

    def displayName(self):
        return "XAI: GeoShapley-lite Approximation"

    def group(self):
        return "Explainability"

    def groupId(self):
        return "xai"

    def shortHelpString(self):
        return (
            "<p><b>Per-cell linear attribution of suitability deviation from a sampled global baseline, "
            "approximating a first-order Shapley decomposition.</b></p>"
            "<p><b>Inputs:</b> Up to 6 criterion rasters (normalized, aligned, same dimensions); "
            "optional weights CSV (comma-separated, one per criterion; equal weights if blank); "
            "sample size for baseline estimation (>=200, default 2000).<br>"
            "<b>Output:</b> Single Float32 attribution raster in range [-100, 100]. "
            "Positive values = local weighted criteria exceed the global baseline; "
            "negative = they fall below it. Nodata where any criterion is nodata.<br>"
            "<b>Method:</b> A global baseline (mean value) is estimated per criterion from a random sample "
            "of valid overlapping cells drawn without replacement. "
            "Each cell's attribution = sum_i(weight_i * (criterion_i - baseline_i)), "
            "approximating a first-order Shapley decomposition around the sample mean. "
            "This avoids the exponential cost (2^n) of exact Shapley computation "
            "while preserving the marginal-contribution interpretation.<br>"
            "<b>Typical use:</b> Map where local conditions pull suitability above or below the regional average. "
            "Use alongside local contribution maps to distinguish single-criterion dominance from broad consensus.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return GeoShapleyLiteAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, "Weights CSV (optional)", defaultValue="", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SAMPLE,
                "Sample size for baseline estimation",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=2000,
                minValue=200,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "GeoShapley-lite attribution raster"))

    def _write_like(self, template_ds, output_path, array, nodata):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            output_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
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
        layers = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 6, "criterion rasters")
        if not layers:
            raise QgsProcessingException("At least one criterion raster is required.")
        weights = parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), len(layers))
        sample_size = int(self.parameterAsInt(parameters, self.SAMPLE, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, layers[0], "xai_geoshapley_lite")

        arrays = []
        nodata = None
        template_ds = None
        valid_mask = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            nd = ds.GetRasterBand(1).GetNoDataValue()
            if template_ds is None:
                template_ds = ds
                nodata = nd
                valid_mask = np.isfinite(arr)
                if nodata is not None:
                    valid_mask &= arr != nodata
            else:
                m = np.isfinite(arr)
                if nd is not None:
                    m &= arr != nd
                valid_mask &= m
            arrays.append(arr)

        h, w = arrays[0].shape
        idx = np.flatnonzero(valid_mask.ravel())
        if idx.size == 0:
            raise QgsProcessingException("No valid overlapping cells across criterion rasters.")
        rng = np.random.default_rng(11)
        if idx.size > sample_size:
            idx = rng.choice(idx, size=sample_size, replace=False)
        baseline = []
        for arr in arrays:
            baseline.append(float(np.mean(arr.ravel()[idx])))

        # GeoShapley-lite:
        # weighted local contribution around a sampled global baseline.
        out_arr = np.zeros((h, w), dtype=np.float32)
        for i, arr in enumerate(arrays):
            centered = arr - baseline[i]
            out_arr += centered * float(weights[i])
            if feedback.isCanceled():
                break
        out_arr = np.clip(out_arr, -100.0, 100.0)
        if nodata is not None:
            out_arr[~valid_mask] = nodata
        self._write_like(template_ds, out, out_arr, nodata)
        return {self.OUTPUT: out}
