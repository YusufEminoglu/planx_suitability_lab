# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)


class ProximityBuilderAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    VALUES = 'VALUES'
    UNITS = 'UNITS'
    MAX_DISTANCE = 'MAX_DISTANCE'
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
        self.addParameter(QgsProcessingParameterString(self.VALUES, 'Target pixel values (comma-separated)', defaultValue='1'))
        self.addParameter(QgsProcessingParameterEnum(self.UNITS, 'Distance units', options=['Georeferenced', 'Pixels'], defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_DISTANCE,
                'Maximum distance (0 for unlimited)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Proximity raster'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        values = self.parameterAsString(parameters, self.VALUES, context).strip() or '1'
        units = int(self.parameterAsEnum(parameters, self.UNITS, context))
        maxd = float(self.parameterAsDouble(parameters, self.MAX_DISTANCE, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        processing.run('gdal:proximity', {
            'INPUT': rl.source(),
            'BAND': 1,
            'VALUES': values,
            'UNITS': units,
            'MAX_DISTANCE': maxd,
            'REPLACE': 0,
            'NODATA': 0,
            'OPTIONS': '',
            'EXTRA': '',
            'DATA_TYPE': 5,
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
