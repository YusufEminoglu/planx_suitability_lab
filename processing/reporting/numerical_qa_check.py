# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterRasterLayer,
)


class NumericalQACheckAlgorithm(QgsProcessingAlgorithm):
    SUIT = "SUIT"
    P05 = "P05"
    P50 = "P50"
    P95 = "P95"
    OUTPUT = "OUTPUT"

    def name(self):
        return "numerical_qa_check"

    def displayName(self):
        return "Reporting: Numerical QA Check"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return NumericalQACheckAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUIT, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.P05, "Uncertainty p05 raster"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.P50, "Uncertainty p50 raster"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.P95, "Uncertainty p95 raster"))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT, "QA Summary"))

    def _arr(self, layer):
        ds = gdal.Open(layer.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Raster read failed during QA check.")
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()
        mask = np.isfinite(arr)
        if nodata is not None:
            mask &= arr != nodata
        return arr, mask

    def processAlgorithm(self, parameters, context, feedback):
        suit = self.parameterAsRasterLayer(parameters, self.SUIT, context)
        p05 = self.parameterAsRasterLayer(parameters, self.P05, context)
        p50 = self.parameterAsRasterLayer(parameters, self.P50, context)
        p95 = self.parameterAsRasterLayer(parameters, self.P95, context)

        s, sm = self._arr(suit)
        a, am = self._arr(p05)
        b, bm = self._arr(p50)
        c, cm = self._arr(p95)
        m = sm & am & bm & cm
        if not np.any(m):
            raise QgsProcessingException("No overlapping valid cells for QA check.")

        smin = float(np.nanmin(s[m]))
        smax = float(np.nanmax(s[m]))
        bounded = (smin >= 0.0) and (smax <= 100.0)
        monotonic_ok = bool(np.all((a[m] <= b[m]) & (b[m] <= c[m])))
        msg = (
            "PlanX Suitability Lab QA\n"
            f"- suitability_min: {smin:.4f}\n"
            f"- suitability_max: {smax:.4f}\n"
            f"- suitability_bounded_0_100: {'PASS' if bounded else 'FAIL'}\n"
            f"- percentile_order_p05_p50_p95: {'PASS' if monotonic_ok else 'FAIL'}\n"
        )
        feedback.pushInfo(msg)
        return {self.OUTPUT: msg}

