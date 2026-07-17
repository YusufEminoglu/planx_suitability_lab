# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.PyQt.QtCore import QMetaType
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
    QgsCoordinateReferenceSystem,
)


from contextlib import suppress


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

    def shortHelpString(self):
        return (
            "<p><b>Recommends a suitability threshold and risk-aversion lambda based on coverage and frontier data.</b></p>"
            "<p><b>Inputs:</b> Threshold coverage curve table, Policy sensitivity frontier table, "
            "Target area coverage percent (1-95, default 25), "
            "Max acceptable critical conflict percent (0-100, default 10).<br>"
            "<b>Output:</b> Feature sink with one row: target_cov_pct, rec_threshold (closest to target coverage), "
            "threshold_cov_pct, rec_lambda (optimized for mean-vs-coverage tradeoff), lambda_mean, lambda_area60_pct, "
            "max_critical_conf, policy_mode (STRICT <=7.5, BALANCED <=15, PERMISSIVE), note.<br>"
            "<b>Method:</b> From the coverage curve, selects the threshold whose pct_ge is closest to the target coverage. "
            "From the frontier, selects the lambda maximizing mean_score - 0.35*|area60 - target_cov|. "
            "Policy mode is derived from the max acceptable critical conflict guideline.<br>"
            "<b>Typical use:</b> Automate initial threshold and lambda settings for a planning run, "
            "reducing manual trial-and-error.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return PolicyGateRecommenderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.THRESHOLD_CURVE, "Threshold coverage curve table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.FRONTIER, "Policy sensitivity frontier table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TARGET_COVERAGE,
                "Target area coverage percent",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=25.0,
                minValue=1.0,
                maxValue=95.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_CRITICAL_CONFLICT,
                "Max acceptable critical conflict percent (guideline)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=10.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Policy gate recommendation", QgsProcessing.SourceType.TypeVector))

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
            with suppress(Exception):
                t = float(f["threshold"])
                cov = float(f["pct_ge"])
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
            with suppress(Exception):
                lam = float(f["lambda"])
                m = float(f["mean_score"])
                a60 = float(f["area_ge_60_pct"])
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
        fields.append(QgsField("target_cov_pct", QMetaType.Type.Double))
        fields.append(QgsField("rec_threshold", QMetaType.Type.Double))
        fields.append(QgsField("threshold_cov_pct", QMetaType.Type.Double))
        fields.append(QgsField("rec_lambda", QMetaType.Type.Double))
        fields.append(QgsField("lambda_mean", QMetaType.Type.Double))
        fields.append(QgsField("lambda_area60_pct", QMetaType.Type.Double))
        fields.append(QgsField("max_critical_conf", QMetaType.Type.Double))
        fields.append(QgsField("policy_mode", QMetaType.Type.QString))
        fields.append(QgsField("note", QMetaType.Type.QString))
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
