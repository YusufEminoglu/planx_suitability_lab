# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)


class ThresholdCoverageCurveAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    STEP = "STEP"
    OUTPUT = "OUTPUT"

    def name(self):
        return "threshold_coverage_curve"

    def displayName(self):
        return "Reporting: Threshold Coverage Curve"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ThresholdCoverageCurveAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STEP,
                "Threshold step",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=5,
                minValue=1,
                maxValue=25,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Threshold coverage table", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        step = int(self.parameterAsInt(parameters, self.STEP, context))
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open input suitability raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)
        arr = np.clip(arr, 0.0, 100.0)
        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        vals = arr[valid]
        if vals.size == 0:
            raise QgsProcessingException("No valid cells in suitability raster.")

        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0
        total = float(vals.size)

        fields = QgsFields()
        fields.append(QgsField("threshold", QVariant.Double))
        fields.append(QgsField("cells_ge", QVariant.LongLong))
        fields.append(QgsField("pct_ge", QVariant.Double))
        fields.append(QgsField("area_ge", QVariant.Double))
        fields.append(QgsField("delta_pct_prev", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        prev_pct = None
        thresholds = list(range(0, 101, step))
        if thresholds[-1] != 100:
            thresholds.append(100)
        for i, t in enumerate(thresholds):
            ge = float(np.sum(vals >= float(t)))
            pct = 100.0 * (ge / total)
            delta = 0.0 if prev_pct is None else float(pct - prev_pct)
            prev_pct = pct

            feat = QgsFeature(fields)
            feat["threshold"] = float(t)
            feat["cells_ge"] = int(ge)
            feat["pct_ge"] = float(pct)
            feat["area_ge"] = float(ge * cell_area)
            feat["delta_pct_prev"] = float(delta)
            sink.addFeature(feat)
            feedback.setProgress(int(((i + 1) / max(1, len(thresholds))) * 100))

        return {self.OUTPUT: dest}
