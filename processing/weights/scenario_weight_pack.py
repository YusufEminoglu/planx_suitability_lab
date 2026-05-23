# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
)


class ScenarioWeightPackAlgorithm(QgsProcessingAlgorithm):
    AHP = "AHP"
    PCA = "PCA"
    ENT = "ENT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_weight_pack"

    def displayName(self):
        return "Weights: Scenario Weight Pack (AHP/PCA/Entropy)"

    def group(self):
        return "Weights"

    def groupId(self):
        return "weights"

    def createInstance(self):
        return ScenarioWeightPackAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.AHP, "AHP weight table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.PCA, "PCA weight table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.ENT, "Entropy weight table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario weights table", QgsProcessing.TypeVector))

    def _collect(self, src, method_name):
        out = []
        names = src.fields().names()
        for f in src.getFeatures():
            cid = int(f["criterion_id"]) if "criterion_id" in names else len(out) + 1
            w = float(f["weight"]) if "weight" in names else 0.0
            out.append((method_name, cid, w))
        return out

    def processAlgorithm(self, parameters, context, feedback):
        ahp = self.parameterAsSource(parameters, self.AHP, context)
        pca = self.parameterAsSource(parameters, self.PCA, context)
        ent = self.parameterAsSource(parameters, self.ENT, context)

        rows = self._collect(ahp, "AHP") + self._collect(pca, "PCA") + self._collect(ent, "ENTROPY")
        by_method = defaultdict(float)
        for method, _, w in rows:
            by_method[method] += w

        fields = QgsFields()
        fields.append(QgsField("method", QVariant.String))
        fields.append(QgsField("criterion_id", QVariant.Int))
        fields.append(QgsField("weight_raw", QVariant.Double))
        fields.append(QgsField("weight_norm", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, 1, None)

        for method, cid, w in rows:
            denom = by_method[method] if by_method[method] > 0 else 1.0
            feat = QgsFeature(fields)
            feat["method"] = method
            feat["criterion_id"] = cid
            feat["weight_raw"] = w
            feat["weight_norm"] = float(w / denom)
            sink.addFeature(feat)

        # Optional blended scenario as arithmetic mean of normalized method weights.
        blended = defaultdict(list)
        for method, cid, w in rows:
            denom = by_method[method] if by_method[method] > 0 else 1.0
            blended[cid].append(float(w / denom))
        for cid, vals in blended.items():
            feat = QgsFeature(fields)
            feat["method"] = "BLENDED_AVG"
            feat["criterion_id"] = cid
            feat["weight_raw"] = float(sum(vals) / max(1, len(vals)))
            feat["weight_norm"] = feat["weight_raw"]
            sink.addFeature(feat)

        return {self.OUTPUT: dest}

