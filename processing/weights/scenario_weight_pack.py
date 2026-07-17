# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsCoordinateReferenceSystem,
)


class ScenarioWeightPackAlgorithm(QgsProcessingAlgorithm):
    AHP = "AHP"
    PCA = "PCA"
    ENT = "ENT"
    CRIT = "CRIT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_weight_pack"

    def displayName(self):
        return "Weights: Scenario Weight Pack (AHP/PCA/Entropy/CRITIC)"

    def group(self):
        return "Weights"

    def groupId(self):
        return "weights"

    def shortHelpString(self):
        return (
            "<p><b>Merge AHP, PCA, Entropy, and CRITIC weight tables into a unified scenario pack "
            "and add a blended-average ensemble scenario.</b></p>"
            "<p><b>Inputs:</b> AHP, PCA, and Entropy weight tables (required); "
            "CRITIC weight table (optional). Each must contain criterion_id and weight columns.<br>"
            "<b>Output:</b> A combined table with columns method, criterion_id, weight_raw, and weight_norm. "
            "Each method's weights are independently normalised to sum to 1. "
            "An additional BLENDED_AVG method provides the per-criterion arithmetic mean "
            "of the normalised weights across all supplied methods.<br>"
            "<b>Method:</b> Collects all rows, grouping by method. Within each method weights are normalised "
            "to sum to 1. The blended scenario computes the per-criterion mean of these normalised values, "
            "creating a simple ensemble that balances subjective (AHP) and objective (PCA, Entropy, CRITIC) "
            "approaches without requiring further user judgment.<br>"
            "<b>Typical use:</b> Prepare a multi-scenario weight set for sensitivity analysis, "
            "consensus auditing, or comparison of how different weighting philosophies affect "
            "the final suitability ranking.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ScenarioWeightPackAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.AHP, "AHP weight table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.PCA, "PCA weight table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.ENT, "Entropy weight table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.CRIT,
                "CRITIC weight table (optional)",
                [QgsProcessing.SourceType.TypeVector],
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario weights table", QgsProcessing.SourceType.TypeVector))

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
        crit = self.parameterAsSource(parameters, self.CRIT, context)

        rows = self._collect(ahp, "AHP") + self._collect(pca, "PCA") + self._collect(ent, "ENTROPY")
        if crit is not None:
            rows += self._collect(crit, "CRITIC")
        by_method = defaultdict(float)
        for method, _, w in rows:
            by_method[method] += w

        fields = QgsFields()
        fields.append(QgsField("method", QVariant.String))
        fields.append(QgsField("criterion_id", QVariant.Int))
        fields.append(QgsField("weight_raw", QVariant.Double))
        fields.append(QgsField("weight_norm", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

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
