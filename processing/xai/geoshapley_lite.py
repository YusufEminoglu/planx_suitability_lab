# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination

from .._mcda_utils import raster_calc


class GeoShapleyLiteAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    SAMPLE = 'SAMPLE'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'xai_geoshapley_lite'

    def displayName(self):
        return 'XAI: GeoShapley-lite Approximation'

    def group(self):
        return 'Explainability'

    def groupId(self):
        return 'xai'

    def createInstance(self):
        return GeoShapleyLiteAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input suitability raster'))
        self.addParameter(QgsProcessingParameterNumber(self.SAMPLE, 'Sample size', type=QgsProcessingParameterNumber.Integer, defaultValue=64, minValue=8))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'GeoShapley-lite attribution raster'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        raster_calc([rl.source()], '(A-50.0)', out)
        return {self.OUTPUT: out}
