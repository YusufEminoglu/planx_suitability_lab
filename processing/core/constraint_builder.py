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

MASK_NODATA = 255


def threshold_mask(values, threshold, nodata=None):
    """1 where ``values >= threshold``, 0 below it, MASK_NODATA where the input
    is nodata or not finite. Pure numpy, so it is testable without GDAL."""
    arr = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(arr)
    if nodata is not None:
        valid &= arr != nodata
    out = np.where(arr >= threshold, 1, 0).astype(np.uint8)
    out[~valid] = MASK_NODATA
    return out


class ConstraintBuilderAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    THRESHOLD = 'THRESHOLD'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'constraint_builder'

    def displayName(self):
        return 'Core: Constraint Builder (0/1 mask)'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def shortHelpString(self):
        return (
            "<p><b>Creates a binary exclusion mask (0/1) from a criterion raster by thresholding: "
            "cells meeting or exceeding the threshold become 1, others become 0.</b></p>"
            "<p><b>Inputs:</b> Input criterion raster (single-band); threshold value (default 50.0) "
            "- cells with value >= threshold are marked as 1 (valid/suitable).<br>"
            "<b>Output:</b> Single-band binary GeoTIFF (values 0 or 1) matching the input grid geometry "
            "(same extent, resolution, projection). Value 1 = suitable, 0 = excluded.<br>"
            "<b>Method:</b> Compares band 1 of the input with the threshold block by block. "
            "The output is a strict binary Byte mask with no intermediate values; input "
            "nodata stays nodata (255), which the compose tools treat as excluded.<br>"
            "<b>Typical use:</b> Building Boolean constraint layers for weighted overlay - for example, "
            "excluding slopes steeper than a buildable maximum, masking out protected areas, or limiting "
            "analysis to parcels above a minimum suitability threshold.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ConstraintBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input criterion raster'))
        self.addParameter(QgsProcessingParameterNumber(self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Constraint mask'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        t = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, rl, "constraint_builder")
        # Computed here rather than through gdal:rastercalculator: on Windows
        # its command line goes through a shell, the ">" in "(A>=t)" became a
        # redirect, the calculation failed and the "mask" was entirely nodata
        # while the run reported success.
        src = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if src is None:
            raise QgsProcessingException(f"Cannot open raster: {rl.name()}")
        band = src.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        xsize, ysize = src.RasterXSize, src.RasterYSize
        dst = gdal.GetDriverByName("GTiff").Create(
            out, xsize, ysize, 1, gdal.GDT_Byte, options=["COMPRESS=LZW", "TILED=YES"])
        if dst is None:
            raise QgsProcessingException(f"Cannot create output raster: {out}")
        dst.SetGeoTransform(src.GetGeoTransform())
        dst.SetProjection(src.GetProjection())
        out_band = dst.GetRasterBand(1)
        out_band.SetNoDataValue(MASK_NODATA)
        block = 512
        total = max(1, ((ysize + block - 1) // block))
        for step, yoff in enumerate(range(0, ysize, block)):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            arr = band.ReadAsArray(0, yoff, xsize, rows)
            out_band.WriteArray(threshold_mask(arr, t, nodata), 0, yoff)
            feedback.setProgress(int(100 * (step + 1) / total))
        out_band.FlushCache()
        out_band = None
        dst = None
        src = None
        return {self.OUTPUT: out}
