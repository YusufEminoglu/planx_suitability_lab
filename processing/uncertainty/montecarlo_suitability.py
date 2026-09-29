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
from .._mcda_utils import smart_output_path


class MonteCarloSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    ITER = "ITER"
    SIGMA = "SIGMA"
    BLOCK = "BLOCK"
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

    def shortHelpString(self):
        return (
            "<p><b>Quantifies suitability uncertainty via chunk-based Monte Carlo simulation "
            "with Gaussian perturbation of the composite score.</b></p>"
            "<p><b>Inputs:</b> Input suitability raster (Float32, 0-100 scale); "
            "iterations (>=20, default 300); "
            "noise sigma (0.0-0.5 relative, default 0.08); "
            "block size in pixels (64-2048, default 256).<br>"
            "<b>Output:</b> Six Float32 rasters - unc_mean, unc_std, unc_p05 (5th percentile), "
            "unc_p50 (median), unc_p95 (95th percentile), "
            "stability_index (100 minus P95-P05 spread; 0-100, higher = more stable). "
            "Nodata cells preserved across all outputs.<br>"
            "<b>Method:</b> Each cell's base value is perturbed over N iterations: "
            "sim = base * (1 + N(0, sigma)), clipped to 0-100. "
            "A fixed random seed (42) ensures reproducibility. "
            "Processing uses configurable pixel blocks for memory efficiency. "
            "Per-cell summary statistics (mean, std, percentiles) are computed across all iterations; "
            "stability_index captures the confidence-interval width (100 - (P95-P05)).<br>"
            "<b>Typical use:</b> Illustrate how much a finished score moves under a chosen level of noise. "
            "The noise is independent per cell and scaled by the score, so the outputs follow from the input "
            "score and sigma; they do not model which weight or criterion is uncertain. To see which weight "
            "drives the map, use <i>Uncertainty: One-at-a-Time Weight Sensitivity</i>.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return MonteCarloSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ITER,
                "Iterations",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=300,
                minValue=20,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIGMA,
                "Noise sigma (0-0.5, relative)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.08,
                minValue=0.0,
                maxValue=0.5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_MEAN, "unc_mean"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_STD, "unc_std"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P05, "unc_p05"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P50, "unc_p50"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P95, "unc_p95"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_STAB, "stability_index"))

    def _create_like(self, template_ds, output_path, nodata):
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
        out_band = out_ds.GetRasterBand(1)
        if nodata is not None:
            out_band.SetNoDataValue(float(nodata))
        return out_ds, out_band

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        iterations = int(self.parameterAsInt(parameters, self.ITER, context))
        sigma = float(self.parameterAsDouble(parameters, self.SIGMA, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        out_mean = self.parameterAsOutputLayer(parameters, self.OUT_MEAN, context)
        out_std = self.parameterAsOutputLayer(parameters, self.OUT_STD, context)
        out_p05 = self.parameterAsOutputLayer(parameters, self.OUT_P05, context)
        out_p50 = self.parameterAsOutputLayer(parameters, self.OUT_P50, context)
        out_p95 = self.parameterAsOutputLayer(parameters, self.OUT_P95, context)
        out_stb = self.parameterAsOutputLayer(parameters, self.OUT_STAB, context)
        out_mean = smart_output_path(out_mean, rl, "montecarlo_unc_mean")
        out_std = smart_output_path(out_std, rl, "montecarlo_unc_std")
        out_p05 = smart_output_path(out_p05, rl, "montecarlo_unc_p05")
        out_p50 = smart_output_path(out_p50, rl, "montecarlo_unc_p50")
        out_p95 = smart_output_path(out_p95, rl, "montecarlo_unc_p95")
        out_stb = smart_output_path(out_stb, rl, "montecarlo_stability_index")

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open input raster for Monte Carlo simulation.")
        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        xsize = ds.RasterXSize
        ysize = ds.RasterYSize

        mean_ds, mean_band = self._create_like(ds, out_mean, nodata)
        std_ds, std_band = self._create_like(ds, out_std, nodata)
        p05_ds, p05_band = self._create_like(ds, out_p05, nodata)
        p50_ds, p50_band = self._create_like(ds, out_p50, nodata)
        p95_ds, p95_band = self._create_like(ds, out_p95, nodata)
        stb_ds, stb_band = self._create_like(ds, out_stb, nodata)

        rng = np.random.default_rng(42)
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
                base = band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                valid = np.isfinite(base)
                if nodata is not None:
                    valid &= base != nodata
                base = np.clip(base, 0.0, 100.0)

                if not np.any(valid):
                    fill = np.full((rows, cols), nodata if nodata is not None else np.nan, dtype=np.float32)
                    mean_band.WriteArray(fill, xoff, yoff)
                    std_band.WriteArray(fill, xoff, yoff)
                    p05_band.WriteArray(fill, xoff, yoff)
                    p50_band.WriteArray(fill, xoff, yoff)
                    p95_band.WriteArray(fill, xoff, yoff)
                    stb_band.WriteArray(fill, xoff, yoff)
                    done += 1
                    feedback.setProgress(int((done / total_blocks) * 100))
                    continue

                scale = np.maximum(base / 100.0, 0.05)
                noise = rng.normal(loc=0.0, scale=sigma, size=(iterations, rows, cols)).astype(np.float32)
                sims = np.clip(base[None, :, :] * (1.0 + noise * scale[None, :, :]), 0.0, 100.0)
                sims = np.where(valid[None, :, :], sims, np.nan).astype(np.float32)

                mean_arr = np.nanmean(sims, axis=0).astype(np.float32)
                std_arr = np.nanstd(sims, axis=0).astype(np.float32)
                p05_arr = np.nanpercentile(sims, 5, axis=0).astype(np.float32)
                p50_arr = np.nanpercentile(sims, 50, axis=0).astype(np.float32)
                p95_arr = np.nanpercentile(sims, 95, axis=0).astype(np.float32)
                spread = np.maximum(p95_arr - p05_arr, 0.0)
                stb_arr = np.clip(100.0 - spread, 0.0, 100.0).astype(np.float32)

                if nodata is not None:
                    mean_arr[~valid] = nodata
                    std_arr[~valid] = nodata
                    p05_arr[~valid] = nodata
                    p50_arr[~valid] = nodata
                    p95_arr[~valid] = nodata
                    stb_arr[~valid] = nodata

                mean_band.WriteArray(mean_arr, xoff, yoff)
                std_band.WriteArray(std_arr, xoff, yoff)
                p05_band.WriteArray(p05_arr, xoff, yoff)
                p50_band.WriteArray(p50_arr, xoff, yoff)
                p95_band.WriteArray(p95_arr, xoff, yoff)
                stb_band.WriteArray(stb_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        mean_ds = None
        std_ds = None
        p05_ds = None
        p50_ds = None
        p95_ds = None
        stb_ds = None
        ds = None
        return {
            self.OUT_MEAN: out_mean,
            self.OUT_STD: out_std,
            self.OUT_P05: out_p05,
            self.OUT_P50: out_p50,
            self.OUT_P95: out_p95,
            self.OUT_STAB: out_stb,
        }
