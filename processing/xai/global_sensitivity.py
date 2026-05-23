# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsFeature, QgsFields, QgsField, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterMultipleLayers, QgsProcessingParameterFeatureSink
from qgis.PyQt.QtCore import QVariant

from .._mcda_utils import ensure_list


class GlobalSensitivityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'xai_global_sensitivity'

    def displayName(self):
        return 'XAI: Global Sensitivity'

    def group(self):
        return 'Explainability'

    def groupId(self):
        return 'xai'

    def createInstance(self):
        return GlobalSensitivityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Criterion rasters', QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'xai_global_table', QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        fields = QgsFields()
        fields.append(QgsField('criterion', QVariant.String))
        fields.append(QgsField('importance', QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, 1, None)
        n = max(1, len(layers))
        for i, l in enumerate(layers, start=1):
            f = QgsFeature(fields)
            f['criterion'] = l.name()
            f['importance'] = 1.0 / n
            sink.addFeature(f)
        return {self.OUTPUT: dest}
