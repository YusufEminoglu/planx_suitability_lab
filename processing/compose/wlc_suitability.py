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

from .._mcda_utils import ensure_list, parse_weights_csv, smart_output_path, limit_layers, style_raster_output


class WLCSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    CONSTRAINT = "CONSTRAINT"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "wlc_suitability"

    def displayName(self):
        return "Compose: WLC Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return WLCSuitabilityAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Multi-criteria suitability via Weighted Linear Combination (WLC).</b></p>\n"
            "<p><b>Inputs:</b> Up to 20 criterion rasters (normalized 0–100); "
            "criteria weights as CSV (e.g. 0.4,0.3,0.3); "
            "optional binary constraint mask (0/1, cells >0.5 pass); "
            "block size 64–2048 pixels.<br>\n"
            "<b>Output:</b> Suitability raster (Float32, 0–100); "
            "constraint-failing cells set to 0; "
            "nodata where any criterion is invalid.<br>\n"
            "<b>Method:</b> Chunk-aware weighted sum per block: "
            "each criterion is read, validated, stacked, "
            "and multiplied by its weight. The constraint mask zeroes "
            "excluded areas. Result clipped to 0–100. "
            "Simplest compensatory MCDA technique.<br>\n"
            "<b>Typical use:</b> Baseline land-suitability scoring "
            "when criteria are independent. Combine with constraint "
            "layers (protected areas, water) to exclude infeasible zones.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (normalized to 0-100)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, "Weights CSV (e.g. 0.4,0.3,0.3)", defaultValue=""))
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_wlc"))

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
        layers = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 20, "criterion rasters")
        if not layers:
            raise QgsProcessingException("No criterion rasters provided.")
        n = len(layers)
        weights = np.array(parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), n), dtype=np.float32)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, layers[0], "wlc_suitability")
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
            band = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
                template_ds = ds
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All criterion rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(band)
            nodatas.append(band.GetNoDataValue())

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

        # A fixed value outside the 0-100 score range: borrowing the first
        # input's nodata (often 0 for byte rasters) turned real scores of 0
        # and constraint-excluded cells into nodata.
        out_nodata = -9999.0
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

                stack = np.stack(arrs, axis=0)
                result = np.sum(stack * weights[:, None, None], axis=0).astype(np.float32)
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
        style_raster_output(context, out, "score")
        return {self.OUTPUT: out}
