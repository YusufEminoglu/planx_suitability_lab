# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import (
    Qgis,
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
        fields.append(QgsField('cr_ok', QVariant.Int))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        cr_ok = 1 if cr <= 0.10 else 0
        if cr_ok == 0:
            feedback.reportError(f'AHP consistency ratio is high (CR={cr:.4f} > 0.10). Consider revising pairwise judgments.')
        for i, wi in enumerate(w, start=1):
            f = QgsFeature(fields)
            f['criterion_id'] = i
            f['weight'] = float(wi)
            f['cr'] = float(cr)
            f['cr_ok'] = cr_ok
            sink.addFeature(f)
        return {self.OUTPUT: dest}
