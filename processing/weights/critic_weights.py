# -*- coding: utf-8 -*-
from __future__ import annotations

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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
    QgsCoordinateReferenceSystem,
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

    def shortHelpString(self):
        return (
            "<p><b>Compute objective weights via CRITIC (CRiteria Importance Through Intercriteria Correlation), "
            "combining contrast intensity and inter-criterion conflict into a single score.</b></p>"
            "<p><b>Inputs:</b> Criterion rasters - same extent and cell size required. "
            "Impacts string - a comma-separated list of direction signs per criterion "
            "(B/benefit/+1 or C/cost/-1); defaults to all benefit if empty.<br>"
            "<b>Output:</b> A table with criterion_id, weight (0-1, summing to 1), std_dev, contrast, "
            "and critic_score (= std_dev * contrast).<br>"
            "<b>Method:</b> Normalises each raster to [0,1] respecting benefit/cost direction, "
            "then computes standard deviation (contrast intensity) and the sum of 1-correlation "
            "with all other criteria (inter-criterion conflict) for each criterion. "
            "The CRITIC score = std_dev * conflict; weights are normalised scores. "
            "Criteria that are both high-variance and uncorrelated with others receive the largest weights, "
            "penalising redundant layers.<br>"
            "<b>Typical use:</b> Objective weighting that automatically penalises redundant criteria "
            "and rewards independent, high-contrast indicators - well-suited for suitability modelling "
            "with many overlapping environmental layers.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return CriticWeightsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, "Criterion rasters", QgsProcessing.SourceType.TypeRaster))
        self.addParameter(
            QgsProcessingParameterString(
                self.IMPACTS_CSV,
                "Impacts CSV per criterion (B/C or +/-1, optional; default all benefit)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "CRITIC weights table", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        if not layers:
            raise QgsProcessingException("No criterion rasters provided.")
        impacts = parse_impacts_csv(self.parameterAsString(parameters, self.IMPACTS_CSV, context), len(layers))
        weights, sigma, contrast = critic_weights_from_rasters([lyr.source() for lyr in layers], impacts=impacts)

        fields = QgsFields()
        fields.append(QgsField("criterion_id", QMetaType.Type.Int))
        fields.append(QgsField("weight", QMetaType.Type.Double))
        fields.append(QgsField("std_dev", QMetaType.Type.Double))
        fields.append(QgsField("contrast", QMetaType.Type.Double))
        fields.append(QgsField("critic_score", QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

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
