# -*- coding: utf-8 -*-
from __future__ import annotations

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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
)

from .._mcda_utils import critic_weights_from_rasters, ensure_list, parse_impacts_csv


class CriticWeightsAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    IMPACTS_CSV = "IMPACTS_CSV"
    OUTPUT = "OUTPUT"

    def name(self):
        return "critic_weights"

    def displayName(self):
        return "Weights: CRITIC Objective Weights"

    def group(self):
        return "Weights"

    def groupId(self):
        return "weights"

    def createInstance(self):
        return CriticWeightsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, "Criterion rasters", QgsProcessing.TypeRaster))
        self.addParameter(
            QgsProcessingParameterString(
                self.IMPACTS_CSV,
                "Impacts CSV per criterion (B/C or +/-1, optional; default all benefit)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "CRITIC weights table", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        if not layers:
            raise QgsProcessingException("No criterion rasters provided.")
        impacts = parse_impacts_csv(self.parameterAsString(parameters, self.IMPACTS_CSV, context), len(layers))
        weights, sigma, contrast = critic_weights_from_rasters([l.source() for l in layers], impacts=impacts)

        fields = QgsFields()
        fields.append(QgsField("criterion_id", QVariant.Int))
        fields.append(QgsField("weight", QVariant.Double))
        fields.append(QgsField("std_dev", QVariant.Double))
        fields.append(QgsField("contrast", QVariant.Double))
        fields.append(QgsField("critic_score", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        for i, wi in enumerate(weights, start=1):
            sc = float(sigma[i - 1] * contrast[i - 1]) if i - 1 < len(sigma) else 0.0
            f = QgsFeature(fields)
            f["criterion_id"] = i
            f["weight"] = float(wi)
            f["std_dev"] = float(sigma[i - 1]) if i - 1 < len(sigma) else 0.0
            f["contrast"] = float(contrast[i - 1]) if i - 1 < len(contrast) else 0.0
            f["critic_score"] = sc
            sink.addFeature(f)
        return {self.OUTPUT: dest}
