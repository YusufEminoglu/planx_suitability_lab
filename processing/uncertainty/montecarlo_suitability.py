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


class MonteCarloSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    ITER = "ITER"
    SIGMA = "SIGMA"
    OUT_MEAN = "OUT_MEAN"
    OUT_STD = "OUT_STD"
    OUT_P05 = "OUT_P05"
    OUT_P50 = "OUT_P50"
    OUT_P95 = "OUT_P95"
    OUT_STAB = "OUT_STAB"

    def name(self):
        return "montecarlo_suitability"

    def displayName(self):
        return "Uncertainty: Monte Carlo Suitability"

    def group(self):
        return "Uncertainty"

    def groupId(self):
        return "uncertainty"

    def createInstance(self):
        return MonteCarloSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ITER,
                "Iterations",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=300,
                minValue=20,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIGMA,
                "Noise sigma (0-0.5, relative)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.08,
                minValue=0.0,
                maxValue=0.5,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_MEAN, "unc_mean"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_STD, "unc_std"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P05, "unc_p05"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P50, "unc_p50"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P95, "unc_p95"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_STAB, "stability_index"))

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
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        iterations = int(self.parameterAsInt(parameters, self.ITER, context))
        sigma = float(self.parameterAsDouble(parameters, self.SIGMA, context))

        out_mean = self.parameterAsOutputLayer(parameters, self.OUT_MEAN, context)
        out_std = self.parameterAsOutputLayer(parameters, self.OUT_STD, context)
        out_p05 = self.parameterAsOutputLayer(parameters, self.OUT_P05, context)
        out_p50 = self.parameterAsOutputLayer(parameters, self.OUT_P50, context)
        out_p95 = self.parameterAsOutputLayer(parameters, self.OUT_P95, context)
        out_stb = self.parameterAsOutputLayer(parameters, self.OUT_STAB, context)

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open input raster for Monte Carlo simulation.")
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()

        valid_mask = np.isfinite(arr)
        if nodata is not None:
            valid_mask &= arr != nodata
        base = np.clip(arr, 0.0, 100.0)
        if not np.any(valid_mask):
            raise QgsProcessingException("Input suitability raster has no valid cells.")

        rng = np.random.default_rng(42)
        sims = np.empty((iterations, base.shape[0], base.shape[1]), dtype=np.float32)
        scale = np.maximum(base / 100.0, 0.05)
        for i in range(iterations):
            if feedback.isCanceled():
                break
            noise = rng.normal(loc=0.0, scale=sigma, size=base.shape).astype(np.float32)
            sim = np.clip(base * (1.0 + noise * scale), 0.0, 100.0)
            sim[~valid_mask] = np.nan
            sims[i] = sim
            if i % 10 == 0:
                feedback.setProgress(int((i / max(1, iterations)) * 100))

        mean_arr = np.nanmean(sims, axis=0)
        std_arr = np.nanstd(sims, axis=0)
        p05_arr = np.nanpercentile(sims, 5, axis=0)
        p50_arr = np.nanpercentile(sims, 50, axis=0)
        p95_arr = np.nanpercentile(sims, 95, axis=0)
        spread = np.maximum(p95_arr - p05_arr, 0.0)
        stab_arr = np.clip(100.0 - spread, 0.0, 100.0)

        if nodata is not None:
            for out_arr in (mean_arr, std_arr, p05_arr, p50_arr, p95_arr, stab_arr):
                out_arr[~valid_mask] = nodata

        self._write_like(ds, out_mean, mean_arr, nodata)
        self._write_like(ds, out_std, std_arr, nodata)
        self._write_like(ds, out_p05, p05_arr, nodata)
        self._write_like(ds, out_p50, p50_arr, nodata)
        self._write_like(ds, out_p95, p95_arr, nodata)
        self._write_like(ds, out_stb, stab_arr, nodata)
        feedback.setProgress(100)
        return {
            self.OUT_MEAN: out_mean,
            self.OUT_STD: out_std,
            self.OUT_P05: out_p05,
            self.OUT_P50: out_p50,
            self.OUT_P95: out_p95,
            self.OUT_STAB: out_stb,
        }

