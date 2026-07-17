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

    def shortHelpString(self):
        return (
            "<p><b>Creates a binary exclusion mask (0/1) from a criterion raster by thresholding: "
            "cells meeting or exceeding the threshold become 1, others become 0.</b></p>"
            "<p><b>Inputs:</b> Input criterion raster (single-band); threshold value (default 50.0) "
            "- cells with value >= threshold are marked as 1 (valid/suitable).<br>"
            "<b>Output:</b> Single-band binary GeoTIFF (values 0 or 1) matching the input grid geometry "
            "(same extent, resolution, projection). Value 1 = suitable, 0 = excluded.<br>"
            "<b>Method:</b> Applies the Boolean expression (A >= threshold) via the plugin's "
            "raster_calc utility on band 1 of the input. The output is a strict binary mask "
            "with no intermediate values. Nodata propagation depends on the raster_calc implementation.<br>"
            "<b>Typical use:</b> Building Boolean constraint layers for weighted overlay - for example, "
            "excluding slopes steeper than a buildable maximum, masking out protected areas, or limiting "
            "analysis to parcels above a minimum suitability threshold.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ConstraintBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input criterion raster'))
        self.addParameter(QgsProcessingParameterNumber(self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Constraint mask'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        t = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, rl, "constraint_builder")
        raster_calc([rl.source()], f'(A>={t})', out)
        return {self.OUTPUT: out}
