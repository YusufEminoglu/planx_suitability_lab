# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination

from .._mcda_utils import raster_calc


class OWASuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'owa_suitability'

    def displayName(self):
        return 'Compose: OWA Suitability (risk-aware transform)'

    def group(self):
        return 'Compose'

    def groupId(self):
        return 'compose'

    def createInstance(self):
        return OWASuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input suitability raster'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'OWA output'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        raster_calc([rl.source()], 'pow((A/100.0),0.8)*100.0', out)
        return {self.OUTPUT: out}
