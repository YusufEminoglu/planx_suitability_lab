# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination

from .._mcda_utils import raster_calc


class NormalizerAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'normalizer_reclassifier'

    def displayName(self):
        return 'Core: Normalizer/Reclassifier (0-100 clamp)'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def createInstance(self):
        return NormalizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input raster'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Normalized raster'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        raster_calc([rl.source()], 'maximum(minimum(A,100),0)', out)
        return {self.OUTPUT: out}
