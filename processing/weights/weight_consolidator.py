# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import Qgis, QgsFeature, QgsFields, QgsField, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink
from qgis.PyQt.QtCore import QVariant


class WeightConsolidatorAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'weight_consolidator'

    def displayName(self):
        return 'Weights: Consolidator'

    def group(self):
        return 'Weights'

    def groupId(self):
        return 'weights'

    def createInstance(self):
        return WeightConsolidatorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, 'Weight table', [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'Consolidated weights table', QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        src = self.parameterAsSource(parameters, self.INPUT, context)
        fields = QgsFields()
        fields.append(QgsField('criterion_id', QVariant.Int))
        fields.append(QgsField('weight', QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        total = 0.0
        rows = []
        for f in src.getFeatures():
            w = float(f['weight']) if 'weight' in src.fields().names() else 0.0
            cid = int(f['criterion_id']) if 'criterion_id' in src.fields().names() else len(rows) + 1
            rows.append((cid, w))
            total += w
        total = total or 1.0
        for cid, w in rows:
            out = QgsFeature(fields)
            out['criterion_id'] = cid
            out['weight'] = float(w / total)
            sink.addFeature(out)
        return {self.OUTPUT: dest}
