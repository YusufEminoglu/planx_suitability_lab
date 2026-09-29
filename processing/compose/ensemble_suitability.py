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
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_weights_csv, smart_output_path, limit_layers


class EnsembleSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    CONSTRAINT = "CONSTRAINT"
    BLOCK = "BLOCK"
    OUT_MEAN = "OUT_MEAN"
    OUT_STD = "OUT_STD"
    OUT_P10 = "OUT_P10"
    OUT_P90 = "OUT_P90"
    OUT_CONF = "OUT_CONF"

    def name(self):
        return "ensemble_suitability"

    def displayName(self):
        return "Compose: Ensemble Suitability (Mean/Uncertainty/Confidence)"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return EnsembleSuitabilityAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Synthesises multiple scenario suitability rasters into ensemble "
            "statistics and confidence.</b></p>\n"
            "<p><b>Inputs:</b> 2–8 suitability rasters (each 0–100); "
            "optional scenario weights CSV (default equal); "
            "optional constraint mask (0/1); block size 64–2048.<br>\n"
            "<b>Output:</b> Five rasters (all Float32): "
            "weighted mean (0–100), unweighted std (0–100 approx), "
            "10th percentile, 90th percentile, "
            "confidence index (100−std, higher = stronger agreement). "
            "Constraint-failing cells set to 0.<br>\n"
            "<b>Method:</b> Chunk-aware: per block, scenario rasters are stacked; "
            "weighted mean via tensordot, std and percentiles via numpy. "
            "Confidence = 100 − clip(std, 0, 100). "
            "Provides a robust central estimate plus spread diagnostics.<br>\n"
            "<b>Typical use:</b> Cross-scenario synthesis to identify "
            "consistently suitable areas and quantify scenario-driven uncertainty.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Input suitability rasters (2..8, each 0-100)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.WEIGHTS_CSV,
                "Scenario weights CSV (optional, defaults equal)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_MEAN, "ensemble_mean"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_STD, "ensemble_std"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P10, "ensemble_p10"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_P90, "ensemble_p90"))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUT_CONF, "ensemble_confidence"))

    @staticmethod
    def _create_output(template_ds, out_path, nodata):
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
        layers = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 8, "scenario rasters")
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two suitability rasters.")
        n = len(layers)
        weights = np.array(parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), n), dtype=np.float32)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)

        out_mean = self.parameterAsOutputLayer(parameters, self.OUT_MEAN, context)
        out_std = self.parameterAsOutputLayer(parameters, self.OUT_STD, context)
        out_p10 = self.parameterAsOutputLayer(parameters, self.OUT_P10, context)
        out_p90 = self.parameterAsOutputLayer(parameters, self.OUT_P90, context)
        out_conf = self.parameterAsOutputLayer(parameters, self.OUT_CONF, context)
        out_mean = smart_output_path(out_mean, layers[0], "ensemble_mean")
        out_std = smart_output_path(out_std, layers[0], "ensemble_std")
        out_p10 = smart_output_path(out_p10, layers[0], "ensemble_p10")
        out_p90 = smart_output_path(out_p90, layers[0], "ensemble_p90")
        out_conf = smart_output_path(out_conf, layers[0], "ensemble_confidence")

        datasets = []
        bands = []
        nodatas = []
        xsize = None
        ysize = None
        template_ds = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            b = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
                template_ds = ds
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All input rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(b)
            nodatas.append(b.GetNoDataValue())

        c_band = None
        c_nodata = None
        if constraint is not None:
            cds = gdal.Open(constraint.source(), gdal.GA_ReadOnly)
            if cds is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if cds.RasterXSize != xsize or cds.RasterYSize != ysize:
                raise QgsProcessingException("Constraint raster must match input grid dimensions.")
            c_band = cds.GetRasterBand(1)
            c_nodata = c_band.GetNoDataValue()

        # A fixed value outside the 0-100 score range: borrowing the first
        # input's nodata (often 0 for byte rasters) turned real scores of 0
        # and constraint-excluded cells into nodata.
        out_nodata = -9999.0
        mean_ds, mean_band = self._create_output(template_ds, out_mean, out_nodata)
        std_ds, std_band = self._create_output(template_ds, out_std, out_nodata)
        p10_ds, p10_band = self._create_output(template_ds, out_p10, out_nodata)
        p90_ds, p90_band = self._create_output(template_ds, out_p90, out_nodata)
        conf_ds, conf_band = self._create_output(template_ds, out_conf, out_nodata)

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

                arrs = []
                valid = np.ones((rows, cols), dtype=bool)
                for j, b in enumerate(bands):
                    a = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    a = np.clip(a, 0.0, 100.0)
                    arrs.append(a)
                    m = np.isfinite(a)
                    nd = nodatas[j]
                    if nd is not None:
                        m &= a != nd
                    valid &= m
                stack = np.stack(arrs, axis=0)

                if c_band is not None:
                    c_arr = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(c_arr)
                    if c_nodata is not None:
                        c_valid &= c_arr != c_nodata
                    pass_mask = (c_arr > 0.5) & c_valid
                    fail_mask = valid & c_valid & (~pass_mask)
                    valid &= c_valid
                else:
                    pass_mask = np.ones((rows, cols), dtype=bool)
                    fail_mask = np.zeros((rows, cols), dtype=bool)

                weighted_mean = np.tensordot(weights, stack, axes=(0, 0)).astype(np.float32)
                unweighted_std = np.std(stack, axis=0).astype(np.float32)
                p10 = np.percentile(stack, 10, axis=0).astype(np.float32)
                p90 = np.percentile(stack, 90, axis=0).astype(np.float32)

                # Confidence index: 100 means perfect agreement across scenarios.
                conf = (100.0 - np.clip(unweighted_std, 0.0, 100.0)).astype(np.float32)

                weighted_mean = np.where(pass_mask, weighted_mean, 0.0)
                unweighted_std = np.where(pass_mask, unweighted_std, 0.0)
                p10 = np.where(pass_mask, p10, 0.0)
                p90 = np.where(pass_mask, p90, 0.0)
                conf = np.where(pass_mask, conf, 0.0)

                out_mean_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_std_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_p10_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_p90_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_conf_arr = np.full((rows, cols), out_nodata, dtype=np.float32)

                out_mean_arr[valid] = weighted_mean[valid]
                out_std_arr[valid] = unweighted_std[valid]
                out_p10_arr[valid] = p10[valid]
                out_p90_arr[valid] = p90[valid]
                out_conf_arr[valid] = conf[valid]

                out_mean_arr[fail_mask] = 0.0
                out_std_arr[fail_mask] = 0.0
                out_p10_arr[fail_mask] = 0.0
                out_p90_arr[fail_mask] = 0.0
                out_conf_arr[fail_mask] = 0.0

                mean_band.WriteArray(out_mean_arr, xoff, yoff)
                std_band.WriteArray(out_std_arr, xoff, yoff)
                p10_band.WriteArray(out_p10_arr, xoff, yoff)
                p90_band.WriteArray(out_p90_arr, xoff, yoff)
                conf_band.WriteArray(out_conf_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        mean_ds = None
        std_ds = None
        p10_ds = None
        p90_ds = None
        conf_ds = None
        for ds in datasets:
            ds = None

        return {
            self.OUT_MEAN: out_mean,
            self.OUT_STD: out_std,
            self.OUT_P10: out_p10,
            self.OUT_P90: out_p90,
            self.OUT_CONF: out_conf,
        }
