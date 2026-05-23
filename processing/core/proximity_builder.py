# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination


class ProximityBuilderAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'proximity_builder'

    def displayName(self):
        return 'Core: Proximity Builder'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def createInstance(self):
        return ProximityBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input raster'))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Proximity raster'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        processing.run('gdal:proximity', {
            'INPUT': rl.source(),
            'BAND': 1,
            'VALUES': '1',
            'UNITS': 0,
            'MAX_DISTANCE': 0,
            'REPLACE': 0,
            'NODATA': 0,
            'OPTIONS': '',
            'EXTRA': '',
            'DATA_TYPE': 5,
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
