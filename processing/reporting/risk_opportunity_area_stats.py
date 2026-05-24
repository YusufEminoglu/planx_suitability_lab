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


class RiskOpportunityAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "risk_opportunity_area_stats"

    def displayName(self):
        return "Reporting: Risk-Opportunity Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return RiskOpportunityAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Risk-opportunity class raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Risk-opportunity area stats", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open risk-opportunity raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)
        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells in risk-opportunity raster.")

        cls = np.clip(np.rint(arr[valid]), 0, 4).astype(np.int32)
        counts = np.bincount(cls, minlength=5).astype(np.float64)
        total = float(np.sum(counts))
        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        fields = QgsFields()
        fields.append(QgsField("class_id", QVariant.Int))
        fields.append(QgsField("label", QVariant.String))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("pct", QVariant.Double))
        fields.append(QgsField("area", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        labels = {
            0: "UNCLASSIFIED",
            1: "INVEST_NOW",
            2: "VALIDATE_THEN_INVEST",
            3: "LOW_STRATEGIC_VALUE",
            4: "DEFER_AND_MONITOR",
        }
        for cid in range(5):
            c = counts[cid]
            feat = QgsFeature(fields)
            feat["class_id"] = int(cid)
            feat["label"] = labels.get(cid, "UNKNOWN")
            feat["cells"] = int(c)
            feat["pct"] = float(100.0 * (c / total)) if total > 0 else 0.0
            feat["area"] = float(c * cell_area)
            sink.addFeature(feat)

        return {self.OUTPUT: dest}

