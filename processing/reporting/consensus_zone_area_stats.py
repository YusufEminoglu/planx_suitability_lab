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


class ConsensusZoneAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "consensus_zone_area_stats"

    def displayName(self):
        return "Reporting: Consensus Zone Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Computes area per consensus zone class from a scenario agreement raster.</b></p>"
            "<p><b>Inputs:</b> Consensus zone raster (0-4).<br>"
            "<b>Output:</b> Feature sink with 5 rows: zone (0-4), label (LOW_OR_NONE, MEDIUM_CONSENSUS, "
            "HIGH_MEDIUM_CONSENSUS, HIGH_CONSENSUS, NEAR_UNANIMOUS), cells, pct, area.<br>"
            "<b>Method:</b> Reads the raster, rounds values to integers clipped [0,4], and bins counts. "
            "Computes percentage of total valid cells and area from geotransform per zone. "
            "Higher zone values indicate greater agreement among scenarios.<br>"
            "<b>Typical use:</b> Quantify how much of the study area enjoys strong multi-scenario agreement, "
            "supporting confidence in priority area delineation.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ConsensusZoneAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Consensus zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Consensus zone area stats", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open consensus zone raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)

        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        if not np.any(valid):
            raise QgsProcessingException("No valid cells found in consensus zone raster.")

        zone = np.clip(np.rint(arr[valid]), 0, 4).astype(np.int32)
        counts = np.bincount(zone, minlength=5).astype(np.float64)
        total = float(np.sum(counts))
        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        fields = QgsFields()
        fields.append(QgsField("zone", QMetaType.Type.Int))
        fields.append(QgsField("label", QMetaType.Type.QString))
        fields.append(QgsField("cells", QMetaType.Type.LongLong))
        fields.append(QgsField("pct", QMetaType.Type.Double))
        fields.append(QgsField("area", QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        labels = {
            0: "LOW_OR_NONE",
            1: "MEDIUM_CONSENSUS",
            2: "HIGH_MEDIUM_CONSENSUS",
            3: "HIGH_CONSENSUS",
            4: "NEAR_UNANIMOUS",
        }

        for z in range(5):
            c = counts[z]
            feat = QgsFeature(fields)
            feat["zone"] = int(z)
            feat["label"] = labels.get(z, "UNKNOWN")
            feat["cells"] = int(c)
            feat["pct"] = float(100.0 * (c / total)) if total > 0 else 0.0
            feat["area"] = float(c * cell_area)
            sink.addFeature(feat)

        return {self.OUTPUT: dest}
