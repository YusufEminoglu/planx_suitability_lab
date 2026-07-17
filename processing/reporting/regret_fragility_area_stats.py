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


class RegretFragilityAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "regret_fragility_area_stats"

    def displayName(self):
        return "Reporting: Regret Fragility Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Computes area per regret fragility class (stable, watch, fragile).</b></p>"
            "<p><b>Inputs:</b> Regret fragility class raster (0-2).<br>"
            "<b>Output:</b> Feature sink with 3 rows: class_id (0-2), label (STABLE_LOW_REGRET, "
            "WATCH_MEDIUM_REGRET, FRAGILE_HIGH_REGRET), cells, pct, area.<br>"
            "<b>Method:</b> Reads the raster, rounds to integers clipped [0,2], bins counts per class. "
            "Computes percentage and area. "
            "STABLE_LOW_REGRET zones are resilient to scenario changes; FRAGILE_HIGH_REGRET zones are sensitive "
            "and could trigger large opportunity losses if the wrong scenario is chosen.<br>"
            "<b>Typical use:</b> Identify where planning decisions are most sensitive to scenario choice, "
            "helping focus robustness-improvement efforts on fragile areas.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return RegretFragilityAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Regret fragility class raster (0..2)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Regret fragility area stats", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open regret fragility class raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)
        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells in regret fragility class raster.")

        cls = np.clip(np.rint(arr[valid]), 0, 2).astype(np.int32)
        counts = np.bincount(cls, minlength=3).astype(np.float64)
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
            0: "STABLE_LOW_REGRET",
            1: "WATCH_MEDIUM_REGRET",
            2: "FRAGILE_HIGH_REGRET",
        }
        for cid in range(3):
            c = counts[cid]
            feat = QgsFeature(fields)
            feat["class_id"] = int(cid)
            feat["label"] = labels.get(cid, "UNKNOWN")
            feat["cells"] = int(c)
            feat["pct"] = float(100.0 * (c / total)) if total > 0 else 0.0
            feat["area"] = float(c * cell_area)
            sink.addFeature(feat)

        return {self.OUTPUT: dest}

