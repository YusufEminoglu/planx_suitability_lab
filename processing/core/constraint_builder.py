# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination

from .._mcda_utils import raster_calc, smart_output_path


class ConstraintBuilderAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    THRESHOLD = 'THRESHOLD'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'constraint_builder'

    def displayName(self):
        return 'Core: Constraint Builder (0/1 mask)'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def createInstance(self):
        return ConstraintBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input criterion raster'))
        self.addParameter(QgsProcessingParameterNumber(self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Constraint mask'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        t = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, rl, "constraint_builder")
        raster_calc([rl.source()], f'(A>={t})', out)
        return {self.OUTPUT: out}
