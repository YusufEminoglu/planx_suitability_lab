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

    def createInstance(self):
        return InterventionConflictAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Intervention conflict class raster (0..6)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Intervention conflict area stats", QgsProcessing.TypeVector))

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
        fields.append(QgsField("class_id", QVariant.Int))
        fields.append(QgsField("label", QVariant.String))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("pct", QVariant.Double))
        fields.append(QgsField("area", QVariant.Double))
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
