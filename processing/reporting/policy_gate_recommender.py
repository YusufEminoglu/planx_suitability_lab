# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
)


class PolicyGateRecommenderAlgorithm(QgsProcessingAlgorithm):
    THRESHOLD_CURVE = "THRESHOLD_CURVE"
    FRONTIER = "FRONTIER"
    TARGET_COVERAGE = "TARGET_COVERAGE"
    MAX_CRITICAL_CONFLICT = "MAX_CRITICAL_CONFLICT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "policy_gate_recommender"

    def displayName(self):
        return "Reporting: Policy Gate Recommender"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return PolicyGateRecommenderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.THRESHOLD_CURVE, "Threshold coverage curve table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.FRONTIER, "Policy sensitivity frontier table", [QgsProcessing.TypeVector]))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TARGET_COVERAGE,
                "Target area coverage percent",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=25.0,
                minValue=1.0,
                maxValue=95.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_CRITICAL_CONFLICT,
                "Max acceptable critical conflict percent (guideline)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=10.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Policy gate recommendation", QgsProcessing.TypeVector))

    @staticmethod
    def _rows(src):
        return [f for f in src.getFeatures(QgsFeatureRequest())]

    def processAlgorithm(self, parameters, context, feedback):
        curve_src = self.parameterAsSource(parameters, self.THRESHOLD_CURVE, context)
        front_src = self.parameterAsSource(parameters, self.FRONTIER, context)
        if curve_src is None or front_src is None:
            raise QgsProcessingException("Could not read threshold/frontier tables.")

        target_cov = float(self.parameterAsDouble(parameters, self.TARGET_COVERAGE, context))
        max_conf = float(self.parameterAsDouble(parameters, self.MAX_CRITICAL_CONFLICT, context))

        curve = self._rows(curve_src)
        frontier = self._rows(front_src)
        if not curve:
            raise QgsProcessingException("Threshold coverage curve table is empty.")
        if not frontier:
            raise QgsProcessingException("Policy frontier table is empty.")

        # Threshold suggestion: choose threshold whose pct_ge is closest to target coverage.
        best_thr = None
        best_thr_cov = None
        best_thr_gap = None
        for f in curve:
            try:
                t = float(f["threshold"])
                cov = float(f["pct_ge"])
            except Exception:
                continue
            gap = abs(cov - target_cov)
            if best_thr is None or gap < best_thr_gap:
                best_thr = t
                best_thr_cov = cov
                best_thr_gap = gap
        if best_thr is None:
            raise QgsProcessingException("Threshold curve table does not contain threshold/pct_ge fields.")

        # Lambda suggestion: maximize mean_score while preserving area_ge_60_pct near target.
        best_lam = None
        best_mean = None
        best_area60 = None
        best_score = None
        for f in frontier:
            try:
                lam = float(f["lambda"])
                m = float(f["mean_score"])
                a60 = float(f["area_ge_60_pct"])
            except Exception:
                continue
            # Multi-objective surrogate: prioritize high mean and closeness to target coverage.
            score = m - 0.35 * abs(a60 - target_cov)
            if best_lam is None or score > best_score:
                best_lam = lam
                best_mean = m
                best_area60 = a60
                best_score = score
        if best_lam is None:
            raise QgsProcessingException("Policy frontier table does not contain lambda/mean_score/area_ge_60_pct fields.")

        # Conflict guidance is consumed as a policy flag (actual conflict ratio should come from attention stats).
        policy_flag = "STRICT" if max_conf <= 7.5 else ("BALANCED" if max_conf <= 15.0 else "PERMISSIVE")
        note = (
            f"Threshold tuned to target coverage {target_cov:.1f}%. "
            f"Lambda optimized by mean-vs-coverage tradeoff. "
            f"Conflict guideline mode: {policy_flag}."
        )

        fields = QgsFields()
        fields.append(QgsField("target_cov_pct", QVariant.Double))
        fields.append(QgsField("rec_threshold", QVariant.Double))
        fields.append(QgsField("threshold_cov_pct", QVariant.Double))
        fields.append(QgsField("rec_lambda", QVariant.Double))
        fields.append(QgsField("lambda_mean", QVariant.Double))
        fields.append(QgsField("lambda_area60_pct", QVariant.Double))
        fields.append(QgsField("max_critical_conf", QVariant.Double))
        fields.append(QgsField("policy_mode", QVariant.String))
        fields.append(QgsField("note", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        out = QgsFeature(fields)
        out["target_cov_pct"] = target_cov
        out["rec_threshold"] = float(best_thr)
        out["threshold_cov_pct"] = float(best_thr_cov)
        out["rec_lambda"] = float(best_lam)
        out["lambda_mean"] = float(best_mean)
        out["lambda_area60_pct"] = float(best_area60)
        out["max_critical_conf"] = max_conf
        out["policy_mode"] = policy_flag
        out["note"] = note
        sink.addFeature(out)
        return {self.OUTPUT: dest}
