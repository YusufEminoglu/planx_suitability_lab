# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterMultipleLayers, QgsProcessingParameterString, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination

from .._mcda_utils import ensure_list, parse_weights_csv, raster_calc


class WLCSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    WEIGHTS_CSV = 'WEIGHTS_CSV'
    CONSTRAINT = 'CONSTRAINT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'wlc_suitability'

    def displayName(self):
        return 'Compose: WLC Suitability'

    def group(self):
        return 'Compose'

    def groupId(self):
        return 'compose'

    def createInstance(self):
        return WLCSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Criterion rasters (max 6)', QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, 'Weights CSV (e.g. 0.4,0.3,0.3)', defaultValue=''))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, 'Constraint mask raster (0/1)', optional=True))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Suitability WLC output'))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        if not layers:
            raise Exception('No criterion rasters provided')
        weights = parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), len(layers))
        letters = ['A', 'B', 'C', 'D', 'E', 'F']
        terms = [f'({weights[i]:.12f}*{letters[i]})' for i in range(len(layers))]
        formula = 'maximum(0,minimum(100,(' + '+'.join(terms) + ')))'
        c = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        if c is not None:
            layers_with_c = [l.source() for l in layers] + [c.source()]
            c_letter = letters[len(layers)]
            # Hard-constraint policy: any cell > 0.5 is pass (1), otherwise fail (0).
            formula = f'({formula})*(( {c_letter} > 0.5 )*1)'
            raster_calc(layers_with_c, formula, self.parameterAsOutputLayer(parameters, self.OUTPUT, context))
        else:
            raster_calc([l.source() for l in layers], formula, self.parameterAsOutputLayer(parameters, self.OUTPUT, context))
        return {self.OUTPUT: self.parameterAsOutputLayer(parameters, self.OUTPUT, context)}
