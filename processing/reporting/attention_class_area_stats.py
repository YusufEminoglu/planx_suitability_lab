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


class AttentionClassAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "attention_class_area_stats"

    def displayName(self):
        return "Reporting: Attention Class Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Computes area per disagreement attention class from a multi-scenario conflict raster.</b></p>"
            "<p><b>Inputs:</b> Attention class raster (0-4).<br>"
            "<b>Output:</b> Feature sink with 5 rows: class_id (0-4), label (LOW, WATCH, REVIEW, "
            "HIGH_CONFLICT, CRITICAL_CONFLICT), cells, pct, area.<br>"
            "<b>Method:</b> Reads the raster, rounds values to integers clipped [0,4], and bins counts. "
            "Computes percentage of total valid cells and area from geotransform per class. "
            "Higher class values indicate more severe disagreement between scenarios requiring planner attention.<br>"
            "<b>Typical use:</b> Identify how much of the study area suffers from scenario disagreement, "
            "helping planners decide where additional data or stakeholder input is needed before commitment.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return AttentionClassAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Attention class raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Attention class area stats", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open attention class raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)

        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells found in attention class raster.")

        cls = np.clip(np.rint(arr[valid]), 0, 4).astype(np.int32)
        counts = np.bincount(cls, minlength=5).astype(np.float64)
        total = float(np.sum(counts))
        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        fields = QgsFields()
        fields.append(QgsField("class_id", QMetaType.Type.Int))
        fields.append(QgsField("label", QMetaType.Type.QString))
        fields.append(QgsField("cells", QMetaType.Type.LongLong))
        fields.append(QgsField("pct", QMetaType.Type.Double))
        fields.append(QgsField("area", QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        labels = {
            0: "LOW",
            1: "WATCH",
            2: "REVIEW",
            3: "HIGH_CONFLICT",
            4: "CRITICAL_CONFLICT",
        }
        for c in range(5):
            ct = counts[c]
            f = QgsFeature(fields)
            f["class_id"] = int(c)
            f["label"] = labels.get(c, "UNKNOWN")
            f["cells"] = int(ct)
            f["pct"] = float(100.0 * (ct / total)) if total > 0 else 0.0
            f["area"] = float(ct * cell_area)
            sink.addFeature(f)
        return {self.OUTPUT: dest}
