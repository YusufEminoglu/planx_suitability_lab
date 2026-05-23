# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination

from .._mcda_utils import raster_calc


class ScenarioComparatorAlgorithm(QgsProcessingAlgorithm):
    A = 'A'
    B = 'B'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'scenario_comparator'

    def displayName(self):
        return 'Compose: Scenario Comparator (delta)'

    def group(self):
        return 'Compose'

    def groupId(self):
        return 'compose'

    def createInstance(self):
        return ScenarioComparatorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.A, 'Baseline suitability'))
        self.addParameter(QgsProcessingParameterRasterLayer(self.B, 'Scenario suitability'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Delta raster (B-A)'))

    def processAlgorithm(self, parameters, context, feedback):
        a = self.parameterAsRasterLayer(parameters, self.A, context)
        b = self.parameterAsRasterLayer(parameters, self.B, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        raster_calc([a.source(), b.source()], 'B-A', out)
        return {self.OUTPUT: out}
