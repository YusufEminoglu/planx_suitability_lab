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
    QgsProcessingParameterRasterLayer,
)


class DecisionQuadrantAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "decision_quadrant_area_stats"

    def displayName(self):
        return "Reporting: Decision Quadrant Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return DecisionQuadrantAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Decision quadrant class raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Decision quadrant area stats", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open decision quadrant raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)
        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells in decision quadrant raster.")

        cls = np.clip(np.rint(arr[valid]), 0, 4).astype(np.int32)
        counts = np.bincount(cls, minlength=5).astype(np.float64)
        total = float(np.sum(counts))
        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        fields = QgsFields()
        fields.append(QgsField("quadrant", QVariant.Int))
        fields.append(QgsField("label", QVariant.String))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("pct", QVariant.Double))
        fields.append(QgsField("area", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        labels = {
            0: "UNCLASSIFIED",
            1: "HIGH_SUIT_LOW_CONFLICT",
            2: "HIGH_SUIT_HIGH_CONFLICT",
            3: "LOW_SUIT_LOW_CONFLICT",
            4: "LOW_SUIT_HIGH_CONFLICT",
        }
        for q in range(5):
            c = counts[q]
            feat = QgsFeature(fields)
            feat["quadrant"] = int(q)
            feat["label"] = labels.get(q, "UNKNOWN")
            feat["cells"] = int(c)
            feat["pct"] = float(100.0 * (c / total)) if total > 0 else 0.0
            feat["area"] = float(c * cell_area)
            sink.addFeature(feat)

        return {self.OUTPUT: dest}
