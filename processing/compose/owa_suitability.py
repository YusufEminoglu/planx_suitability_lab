# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_weights_csv, smart_output_path


class OWASuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    CRITERIA_WEIGHTS = "CRITERIA_WEIGHTS"
    ORDER_WEIGHTS = "ORDER_WEIGHTS"
    SORT_MODE = "SORT_MODE"
    CONSTRAINT = "CONSTRAINT"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    SORT_OPTIONS = ["Descending (high score first)", "Ascending (low score first)"]

    def name(self):
        return "owa_suitability"

    def displayName(self):
        return "Compose: OWA Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return OWASuitabilityAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Multi-criteria suitability via Ordered Weighted Averaging (OWA).</b></p>\n"
            "<p><b>Inputs:</b> Up to 6 criterion rasters (normalized 0–100); "
            "optional criteria weights CSV; optional order weights CSV; "
            "ordering mode (Descending = optimistic, Ascending = pessimistic); "
            "optional constraint mask (0/1); block size 64–2048.<br>\n"
            "<b>Output:</b> Suitability raster (Float32, 0–100); "
            "constraint-failing cells set to 0; nodata where any input is invalid.<br>\n"
            "<b>Method:</b> Chunk-aware OWA: per cell, criterion values are sorted "
            "by the chosen ordering, criteria weights are reordered accordingly, "
            "then alpha = sorted_criteria_weight × order_weight. "
            "Result = sum(alpha × sorted_value) / sum(alpha). "
            "Order weights control risk attitude: descending favours high-scoring "
            "criteria (optimistic/OR-like), ascending favours low-scoring "
            "(pessimistic/AND-like).<br>\n"
            "<b>Typical use:</b> When trade-off attitude matters — "
            "optimistic for opportunity scanning, pessimistic for conservative "
            "constraint-driven screening.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6, normalized to 0-100)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.CRITERIA_WEIGHTS, "Criteria weights CSV (optional)", defaultValue="", optional=True))
        self.addParameter(QgsProcessingParameterString(self.ORDER_WEIGHTS, "Order weights CSV (optional)", defaultValue="", optional=True))
        self.addParameter(QgsProcessingParameterEnum(self.SORT_MODE, "Ordering mode", options=self.SORT_OPTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_owa"))

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
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        if not layers:
            raise QgsProcessingException("No criterion rasters provided for OWA.")
        n = len(layers)
        criteria_w = np.array(parse_weights_csv(self.parameterAsString(parameters, self.CRITERIA_WEIGHTS, context), n), dtype=np.float32)
        order_w = np.array(parse_weights_csv(self.parameterAsString(parameters, self.ORDER_WEIGHTS, context), n), dtype=np.float32)
        sort_mode = int(self.parameterAsEnum(parameters, self.SORT_MODE, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, layers[0], "owa_suitability")
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)

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
                raise QgsProcessingException("All input rasters must share the same grid dimensions.")
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
                raise QgsProcessingException("Constraint raster must match criterion grid dimensions.")
            c_band = cds.GetRasterBand(1)
            c_nodata = c_band.GetNoDataValue()

        out_nodata = nodatas[0] if nodatas[0] is not None else -9999.0
        out_ds, out_band = self._create_output(template_ds, out, out_nodata)

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
                    arrs.append(np.clip(a, 0.0, 100.0))
                    m = np.isfinite(a)
                    nd = nodatas[j]
                    if nd is not None:
                        m &= a != nd
                    valid &= m

                stack = np.stack(arrs, axis=0)  # (n,rows,cols)
                order_idx = np.argsort(stack, axis=0)
                if sort_mode == 0:
                    order_idx = order_idx[::-1, :, :]
                sorted_vals = np.take_along_axis(stack, order_idx, axis=0)

                cw_grid = np.broadcast_to(criteria_w[:, None, None], stack.shape)
                sorted_cw = np.take_along_axis(cw_grid, order_idx, axis=0)
                alpha = sorted_cw * order_w[:, None, None]
                denom = np.sum(alpha, axis=0)
                num = np.sum(alpha * sorted_vals, axis=0)
                result = np.where(denom > 1e-12, num / denom, 0.0).astype(np.float32)
                result = np.clip(result, 0.0, 100.0)

                if c_band is not None:
                    c_arr = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(c_arr)
                    if c_nodata is not None:
                        c_valid &= c_arr != c_nodata
                    pass_mask = (c_arr > 0.5) & c_valid
                    result = np.where(pass_mask, result, 0.0)
                    valid &= c_valid

                result = np.where(valid, result, out_nodata).astype(np.float32)
                out_band.WriteArray(result, xoff, yoff)
                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        out_ds = None
        for ds in datasets:
            ds = None
        return {self.OUTPUT: out}
