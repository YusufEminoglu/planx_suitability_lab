# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import Qgis, QgsFeature, QgsFields, QgsField, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterMultipleLayers, QgsProcessingParameterFeatureSink, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QVariant

from .._mcda_utils import ensure_list, entropy_weights_from_rasters


class EntropyWeightsAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'entropy_weights'

    def displayName(self):
        return 'Weights: Entropy Weights'

    def group(self):
        return 'Weights'

    def groupId(self):
        return 'weights'

    def shortHelpString(self):
        return (
            "<p><b>Compute objective criterion weights using Shannon information entropy - "
            "criteria with greater value contrast receive higher weight.</b></p>"
            "<p><b>Inputs:</b> Criterion rasters - same extent and cell size required; "
            "values are sampled from a regular grid of up to ~8000 cells.<br>"
            "<b>Output:</b> A table with criterion_id and weight (0-1, summing to 1). "
            "Higher weight means the criterion has more discriminating power; "
            "a near-constant raster gets a weight close to zero.<br>"
            "<b>Method:</b> Normalises each raster to [0,1] via min-max scaling, then computes "
            "proportional values across all sampled cells. Shannon entropy is calculated per criterion; "
            "the degree of diversification d = 1 - e (where e is normalised entropy) forms the raw weight. "
            "Criteria with concentrated, distinctive values produce low entropy and thus high weight; "
            "uniform criteria are down-weighted.<br>"
            "<b>Typical use:</b> Assign weights purely from the information content of spatial data, "
            "ideal when all criteria are considered equally important a priori and the analyst wants "
            "discriminating power to drive the weighting.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return EntropyWeightsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Criterion rasters', QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'Entropy weights table', QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        weights = entropy_weights_from_rasters([l.source() for l in layers])
        fields = QgsFields()
        fields.append(QgsField('criterion_id', QVariant.Int))
        fields.append(QgsField('weight', QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        for i, wi in enumerate(weights, start=1):
            f = QgsFeature(fields)
            f['criterion_id'] = i
            f['weight'] = float(wi)
            sink.addFeature(f)
        return {self.OUTPUT: dest}
