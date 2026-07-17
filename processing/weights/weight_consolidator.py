# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import Qgis, QgsFeature, QgsFields, QgsField, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink, QgsCoordinateReferenceSystem
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

    def shortHelpString(self):
        return (
            "<p><b>Normalise a weight table so all weights sum to 1, selecting which weight set activates "
            "for downstream scoring.</b></p>"
            "<p><b>Inputs:</b> Weight table - any vector layer containing criterion_id and weight columns.<br>"
            "<b>Output:</b> A table with criterion_id and normalised weight (0-1, summing to 1). "
            "Zero-division is guarded; an all-zero or empty input produces a safely normalised output.<br>"
            "<b>Method:</b> Reads all features, sums the raw weight values, then divides each weight by the total. "
            "If the sum is zero, a divisor of 1.0 is substituted to avoid division errors. "
            "This is a pass-through activation step: it does not alter relative proportions - "
            "it only ensures weights are ready for weighted overlay or TOPSIS combination.<br>"
            "<b>Typical use:</b> After generating weights with AHP, PCA, Entropy, or CRITIC, "
            "run this algorithm to activate the chosen weight set before feeding it into MCDA scoring.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return WeightConsolidatorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, 'Weight table', [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'Consolidated weights table', QgsProcessing.SourceType.TypeVector))

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
