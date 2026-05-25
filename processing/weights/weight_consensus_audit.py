# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from statistics import median

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsCoordinateReferenceSystem,
)


class WeightConsensusAuditAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "weight_consensus_audit"

    def displayName(self):
        return "Weights: Weight Consensus Audit"

    def group(self):
        return "Weights"

    def groupId(self):
        return "weights"

    def createInstance(self):
        return WeightConsensusAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                "Scenario weights table (from scenario_weight_pack)",
                [QgsProcessing.TypeVector],
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Weight consensus audit table", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        src = self.parameterAsSource(parameters, self.INPUT, context)
        if src is None:
            raise QgsProcessingException("Input table is missing.")
        names = src.fields().names()
        if "criterion_id" not in names:
            raise QgsProcessingException("Input table must contain 'criterion_id'.")
        w_field = "weight_norm" if "weight_norm" in names else ("weight" if "weight" in names else None)
        if w_field is None:
            raise QgsProcessingException("Input table must contain 'weight_norm' or 'weight'.")

        by_criterion = defaultdict(list)
        for f in src.getFeatures():
            cid = int(f["criterion_id"])
            by_criterion[cid].append(float(f[w_field]))

        fields = QgsFields()
        fields.append(QgsField("criterion_id", QVariant.Int))
        fields.append(QgsField("method_count", QVariant.Int))
        fields.append(QgsField("w_mean", QVariant.Double))
        fields.append(QgsField("w_median", QVariant.Double))
        fields.append(QgsField("w_min", QVariant.Double))
        fields.append(QgsField("w_max", QVariant.Double))
        fields.append(QgsField("w_range", QVariant.Double))
        fields.append(QgsField("w_std", QVariant.Double))
        fields.append(QgsField("cv_pct", QVariant.Double))
        fields.append(QgsField("agreement", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        for cid in sorted(by_criterion.keys()):
            vals = by_criterion[cid]
            n = len(vals)
            if n == 0:
                continue
            m = sum(vals) / n
            mn = min(vals)
            mx = max(vals)
            wr = mx - mn
            var = sum((v - m) * (v - m) for v in vals) / n
            std = var ** 0.5
            cv = (std / m * 100.0) if m > 1e-12 else 0.0
            if cv <= 10:
                ag = "HIGH"
            elif cv <= 25:
                ag = "MEDIUM"
            else:
                ag = "LOW"

            feat = QgsFeature(fields)
            feat["criterion_id"] = cid
            feat["method_count"] = n
            feat["w_mean"] = float(m)
            feat["w_median"] = float(median(vals))
            feat["w_min"] = float(mn)
            feat["w_max"] = float(mx)
            feat["w_range"] = float(wr)
            feat["w_std"] = float(std)
            feat["cv_pct"] = float(cv)
            feat["agreement"] = ag
            sink.addFeature(feat)

        return {self.OUTPUT: dest}
