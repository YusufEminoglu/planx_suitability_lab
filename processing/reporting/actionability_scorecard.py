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
    QgsCoordinateReferenceSystem,
)


from contextlib import suppress


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


class ActionabilityScorecardAlgorithm(QgsProcessingAlgorithm):
    KPI = "KPI"
    BUDGET = "BUDGET"
    GATE = "GATE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "actionability_scorecard"

    def displayName(self):
        return "Reporting: Actionability Scorecard"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Produces an overall readiness score (A-D) from KPI, budget, and policy-gate diagnostics.</b></p>"
            "<p><b>Inputs:</b> Executive KPI snapshot table, Intervention budget phasing table, "
            "Policy gate recommender table.<br>"
            "<b>Output:</b> Feature sink with one row: overall score (0-100), grade (A>=85, B>=75, C>=65, D<65), "
            "readiness (PUBLICATION_READY, NEAR_READY, REVISE_REQUIRED, REWORK_REQUIRED), "
            "sub-scores (robustness, consensus, implementability, delivery, policy_align), policy_mode, budget_ref, capture_ref.<br>"
            "<b>Method:</b> Computes five sub-scores: robustness (mean_robust - 0.5*confidence_gap), "
            "consensus (0.7*high + 0.3*unanimous), implementability (0.65*eligible + 0.35*consensus - 0.35*conflict_penalty), "
            "delivery (impact capture at ~50% budget), and policy_alignment (100 - 2*threshold_gap - 1.5*lambda_gap). "
            "Overall = weighted sum (0.26/0.20/0.24/0.16/0.14) times a policy-mode factor (1.0/0.97/0.93).<br>"
            "<b>Typical use:</b> Gate-check before publication: is the analysis mature enough for stakeholder release?</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ActionabilityScorecardAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.KPI, "Executive KPI snapshot table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.BUDGET, "Intervention budget phasing table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.GATE, "Policy gate recommender table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Actionability scorecard", QgsProcessing.SourceType.TypeVector))

    @staticmethod
    def _first(src):
        for f in src.getFeatures(QgsFeatureRequest()):
            return f
        return None

    @staticmethod
    def _closest_budget_capture(budget_src, target_budget_pct: float):
        best_diff = None
        best_capture = None
        best_budget = None
        for f in budget_src.getFeatures(QgsFeatureRequest()):
            with suppress(Exception):
                b = float(f["budget_pct"])
                c = float(f["impact_capture_pct"])
                d = abs(b - target_budget_pct)
                if best_diff is None or d < best_diff:
                    best_diff = d
                    best_capture = c
                    best_budget = b
        if best_capture is None:
            return 0.0, 0.0
        return float(best_budget), float(best_capture)

    def processAlgorithm(self, parameters, context, feedback):
        kpi_src = self.parameterAsSource(parameters, self.KPI, context)
        budget_src = self.parameterAsSource(parameters, self.BUDGET, context)
        gate_src = self.parameterAsSource(parameters, self.GATE, context)
        if kpi_src is None or budget_src is None or gate_src is None:
            raise QgsProcessingException("Could not read one or more input tables.")

        kpi = self._first(kpi_src)
        gate = self._first(gate_src)
        if kpi is None:
            raise QgsProcessingException("Executive KPI table is empty.")
        if gate is None:
            raise QgsProcessingException("Policy gate table is empty.")

        try:
            mean_robust = float(kpi["mean_robust"])
            eligible_pct = float(kpi["eligible_pct"])
            consensus_high_pct = float(kpi["consensus_high_pct"])
            consensus_unanim_pct = float(kpi["consensus_unanim_pct"])
            high_conflict_pct = float(kpi["high_conflict_pct"])
            critical_conflict_pct = float(kpi["critical_conflict_pct"])
            confidence_gap = float(kpi["confidence_gap"])
        except Exception as exc:
            raise QgsProcessingException(f"KPI table missing expected fields: {exc}")

        try:
            target_cov = float(gate["target_cov_pct"])
            threshold_cov = float(gate["threshold_cov_pct"])
            lambda_area60 = float(gate["lambda_area60_pct"])
            policy_mode = str(gate["policy_mode"])
        except Exception as exc:
            raise QgsProcessingException(f"Policy gate table missing expected fields: {exc}")

        budget_at_50, capture_at_50 = self._closest_budget_capture(budget_src, 50.0)

        # Subscores
        robustness = _clamp(mean_robust - 0.5 * confidence_gap)
        consensus = _clamp(0.7 * consensus_high_pct + 0.3 * consensus_unanim_pct)
        conflict_penalty = _clamp(0.6 * high_conflict_pct + 1.4 * critical_conflict_pct)
        implementability = _clamp(0.65 * eligible_pct + 0.35 * consensus - 0.35 * conflict_penalty)
        delivery = _clamp(capture_at_50)
        policy_alignment = _clamp(100.0 - 2.0 * abs(threshold_cov - target_cov) - 1.5 * abs(lambda_area60 - target_cov))

        if policy_mode.upper() == "STRICT":
            policy_factor = 1.0
        elif policy_mode.upper() == "BALANCED":
            policy_factor = 0.97
        else:
            policy_factor = 0.93

        overall = _clamp(
            (0.26 * robustness + 0.2 * consensus + 0.24 * implementability + 0.16 * delivery + 0.14 * policy_alignment)
            * policy_factor
        )

        if overall >= 85:
            grade = "A"
            readiness = "PUBLICATION_READY"
        elif overall >= 75:
            grade = "B"
            readiness = "NEAR_READY"
        elif overall >= 65:
            grade = "C"
            readiness = "REVISE_REQUIRED"
        else:
            grade = "D"
            readiness = "REWORK_REQUIRED"

        fields = QgsFields()
        fields.append(QgsField("overall", QVariant.Double))
        fields.append(QgsField("grade", QVariant.String))
        fields.append(QgsField("readiness", QVariant.String))
        fields.append(QgsField("robustness", QVariant.Double))
        fields.append(QgsField("consensus", QVariant.Double))
        fields.append(QgsField("implement", QVariant.Double))
        fields.append(QgsField("delivery", QVariant.Double))
        fields.append(QgsField("policy_align", QVariant.Double))
        fields.append(QgsField("policy_mode", QVariant.String))
        fields.append(QgsField("budget_ref", QVariant.Double))
        fields.append(QgsField("capture_ref", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        feat = QgsFeature(fields)
        feat["overall"] = overall
        feat["grade"] = grade
        feat["readiness"] = readiness
        feat["robustness"] = robustness
        feat["consensus"] = consensus
        feat["implement"] = implementability
        feat["delivery"] = delivery
        feat["policy_align"] = policy_alignment
        feat["policy_mode"] = policy_mode
        feat["budget_ref"] = budget_at_50
        feat["capture_ref"] = capture_at_50
        sink.addFeature(feat)
        return {self.OUTPUT: dest}
