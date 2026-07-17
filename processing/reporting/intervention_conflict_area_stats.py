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


class InterventionConflictAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "intervention_conflict_area_stats"

    def displayName(self):
        return "Reporting: Intervention Conflict Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Computes area per intervention conflict class from a multi-dimensional conflict raster.</b></p>"
            "<p><b>Inputs:</b> Intervention conflict class raster (0-6).<br>"
            "<b>Output:</b> Feature sink with 7 rows: class_id (0-6), label (HOLD, QUICK_WIN, DELIBERATE_DESIGN, "
            "RESOLVE_FIRST, MONITOR, CO_DESIGN, RE_SCREEN), cells, pct, area.<br>"
            "<b>Method:</b> Reads the raster, rounds to integers clipped [0,6], bins counts per class. "
            "Computes percentage and area per intervention conflict type. "
            "Classes range from immediate action (QUICK_WIN) through deliberative processes to re-screening, "
            "encoding both suitability potential and implementation feasibility.<br>"
            "<b>Typical use:</b> Categorize the study area into intervention strategies for phased implementation planning.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return InterventionConflictAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Intervention conflict class raster (0..6)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Intervention conflict area stats", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open intervention conflict raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)

        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells in intervention conflict raster.")

        cls = np.clip(np.rint(arr[valid]), 0, 6).astype(np.int32)
        counts = np.bincount(cls, minlength=7).astype(np.float64)
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
            0: "HOLD",
            1: "QUICK_WIN",
            2: "DELIBERATE_DESIGN",
            3: "RESOLVE_FIRST",
            4: "MONITOR",
            5: "CO_DESIGN",
            6: "RE_SCREEN",
        }
        for cid in range(7):
            c = counts[cid]
            f = QgsFeature(fields)
            f["class_id"] = int(cid)
            f["label"] = labels.get(cid, "UNKNOWN")
            f["cells"] = int(c)
            f["pct"] = float(100.0 * (c / total)) if total > 0 else 0.0
            f["area"] = float(c * cell_area)
            sink.addFeature(f)

        return {self.OUTPUT: dest}
