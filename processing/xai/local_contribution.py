# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterMultipleLayers, QgsProcessingParameterString, QgsProcessingParameterFolderDestination

from .._mcda_utils import ensure_list, parse_weights_csv, raster_calc


class LocalContributionAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    WEIGHTS_CSV = 'WEIGHTS_CSV'
    OUTPUT_DIR = 'OUTPUT_DIR'

    def name(self):
        return 'xai_local_contribution'

    def displayName(self):
        return 'XAI: Local Contribution Decomposition'

    def group(self):
        return 'Explainability'

    def groupId(self):
        return 'xai'

    def createInstance(self):
        return LocalContributionAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Criterion rasters (max 6)'))
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, 'Weights CSV', defaultValue=''))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_DIR, 'Output folder for xai_local_contribution_*'))

    def processAlgorithm(self, parameters, context, feedback):
        import os

        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        out_dir = self.parameterAsString(parameters, self.OUTPUT_DIR, context)
        weights = parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), len(layers))
        for i, l in enumerate(layers):
            out = os.path.join(out_dir, f'xai_local_contribution_{i+1}.tif')
            raster_calc([l.source()], f'A*{weights[i]:.12f}', out)
        return {self.OUTPUT_DIR: out_dir}
