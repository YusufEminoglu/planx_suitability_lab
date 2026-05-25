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
