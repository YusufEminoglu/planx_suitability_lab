# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from qgis.core import (
    QgsFeature,
    QgsFields,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
)
from qgis.PyQt.QtCore import QVariant

from .._mcda_utils import ahp_weights_from_json


class AHPWeightsAlgorithm(QgsProcessingAlgorithm):
    MATRIX_JSON = 'MATRIX_JSON'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'ahp_weights'

    def displayName(self):
        return 'Weights: AHP Weights'

    def group(self):
        return 'Weights'

    def groupId(self):
        return 'weights'

    def createInstance(self):
        return AHPWeightsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.MATRIX_JSON, 'Pairwise matrix JSON', multiLine=True, defaultValue='[[1,2,3],[0.5,1,2],[0.3333,0.5,1]]'))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'AHP weights table', QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        txt = self.parameterAsString(parameters, self.MATRIX_JSON, context)
        w, cr = ahp_weights_from_json(txt)
        fields = QgsFields()
        fields.append(QgsField('criterion_id', QVariant.Int))
        fields.append(QgsField('weight', QVariant.Double))
        fields.append(QgsField('cr', QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, 1, None)
        for i, wi in enumerate(w, start=1):
            f = QgsFeature(fields)
            f['criterion_id'] = i
            f['weight'] = float(wi)
            f['cr'] = float(cr)
            sink.addFeature(f)
        return {self.OUTPUT: dest}
