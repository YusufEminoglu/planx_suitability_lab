# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QMetaType
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
    QgsCoordinateReferenceSystem,
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

    def shortHelpString(self):
        return (
            "<p><b>Computes area per decision quadrant from a suitability-vs-conflict classification raster.</b></p>"
            "<p><b>Inputs:</b> Decision quadrant class raster (0-4).<br>"
            "<b>Output:</b> Feature sink with 5 rows: quadrant (0-4), label (UNCLASSIFIED, HIGH_SUIT_LOW_CONFLICT, "
            "HIGH_SUIT_HIGH_CONFLICT, LOW_SUIT_LOW_CONFLICT, LOW_SUIT_HIGH_CONFLICT), cells, pct, area.<br>"
            "<b>Method:</b> Reads the raster, rounds to integers clipped [0,4], bins counts per quadrant. "
            "Computes percentage of total valid cells and area from geotransform. "
            "Quadrants partition the study area by suitability level and conflict/disagreement intensity, "
            "highlighting where high suitability coincides with or avoids conflict.<br>"
            "<b>Typical use:</b> Distinguish between uncontested priority areas (ready for action) "
            "and contested high-suitability zones (requiring negotiation).</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return DecisionQuadrantAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Decision quadrant class raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Decision quadrant area stats", QgsProcessing.SourceType.TypeVector))

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
        fields.append(QgsField("quadrant", QMetaType.Type.Int))
        fields.append(QgsField("label", QMetaType.Type.QString))
        fields.append(QgsField("cells", QMetaType.Type.LongLong))
        fields.append(QgsField("pct", QMetaType.Type.Double))
        fields.append(QgsField("area", QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

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
