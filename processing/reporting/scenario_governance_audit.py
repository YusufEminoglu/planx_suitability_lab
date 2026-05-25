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


class ScenarioGovernanceAuditAlgorithm(QgsProcessingAlgorithm):
    ROBUSTNESS = "ROBUSTNESS"
    BENCHMARK = "BENCHMARK"
    MINIMAX = "MINIMAX"
    SELECTION = "SELECTION"
    DEPLOYMENT = "DEPLOYMENT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_governance_audit"

    def displayName(self):
        return "Reporting: Scenario Governance Audit"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ScenarioGovernanceAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.ROBUSTNESS, "Scenario robustness leaderboard table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.BENCHMARK, "Method benchmark leaderboard table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.MINIMAX, "Minimax regret selector table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.SELECTION, "Scenario selection recommender table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.DEPLOYMENT,
                "Optional deployment readiness gate table",
                [QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario governance audit", QgsProcessing.TypeVector))

    @staticmethod
    def _rows(src):
        return [f for f in src.getFeatures(QgsFeatureRequest())]

    @staticmethod
    def _first(src):
        if src is None:
            return None
        for f in src.getFeatures(QgsFeatureRequest()):
            return f
        return None

    def processAlgorithm(self, parameters, context, feedback):
        robustness_src = self.parameterAsSource(parameters, self.ROBUSTNESS, context)
        benchmark_src = self.parameterAsSource(parameters, self.BENCHMARK, context)
        minimax_src = self.parameterAsSource(parameters, self.MINIMAX, context)
        selection_src = self.parameterAsSource(parameters, self.SELECTION, context)
        deploy_src = self.parameterAsSource(parameters, self.DEPLOYMENT, context)
        if robustness_src is None or benchmark_src is None or minimax_src is None or selection_src is None:
            raise QgsProcessingException("Could not read one or more required input tables.")

        robustness_rows = self._rows(robustness_src)
        benchmark_rows = self._rows(benchmark_src)
        minimax_rows = self._rows(minimax_src)
        sel = self._first(selection_src)
        dep = self._first(deploy_src)

        if not robustness_rows or not benchmark_rows or not minimax_rows:
            raise QgsProcessingException("Robustness, benchmark and minimax tables must be non-empty.")
        if sel is None:
            raise QgsProcessingException("Scenario selection table is empty.")

        rb = {}
        for f in robustness_rows:
            try:
                s = str(f["scenario"])
                rb[s] = {
                    "robustness": float(f["robustness"]),
                    "tier": str(f["tier"]),
                    "rb_rank": int(f["rank"]),
                }
            except Exception:
                continue
        if not rb:
            raise QgsProcessingException("Robustness table missing required scenario fields.")

        bm = {}
        for f in benchmark_rows:
            try:
                s = str(f["scenario"])
                bm[s] = {
                    "composite": float(f["composite"]),
                    "stability": float(f["stability"]),
                    "std_score": float(f["std_score"]),
                }
            except Exception:
                continue

        mm = {}
        mm_selected = None
        for f in minimax_rows:
            try:
                s = str(f["scenario"])
                mm[s] = {
                    "max_regret": float(f["max_regret"]),
                    "mm_rank": int(f["rank"]),
                }
                if str(f["selected"]).upper() == "YES":
                    mm_selected = s
            except Exception:
                continue
        if not mm:
            raise QgsProcessingException("Minimax table missing required scenario fields.")

        primary = str(sel["primary_scn"]) if "primary_scn" in sel.fields().names() else ""
        challenger = str(sel["challenger_scn"]) if "challenger_scn" in sel.fields().names() else ""
        minimax_sel = str(sel["minimax_scn"]) if "minimax_scn" in sel.fields().names() else (mm_selected or "")
        strategy = str(sel["strategy"]) if "strategy" in sel.fields().names() else ""

        deploy_decision = ""
        if dep is not None and "decision" in dep.fields().names():
            deploy_decision = str(dep["decision"])

        scenarios = sorted(set(rb.keys()) | set(mm.keys()) | set(bm.keys()))
        if not scenarios:
            raise QgsProcessingException("No scenario names could be extracted from input tables.")

        fields = QgsFields()
        fields.append(QgsField("row_type", QVariant.String))
        fields.append(QgsField("scenario", QVariant.String))
        fields.append(QgsField("role", QVariant.String))
        fields.append(QgsField("robustness", QVariant.Double))
        fields.append(QgsField("composite", QVariant.Double))
        fields.append(QgsField("stability", QVariant.Double))
        fields.append(QgsField("max_regret", QVariant.Double))
        fields.append(QgsField("risk_score", QVariant.Double))
        fields.append(QgsField("risk_level", QVariant.String))
        fields.append(QgsField("flag_regret", QVariant.Int))
        fields.append(QgsField("flag_robust", QVariant.Int))
        fields.append(QgsField("flag_vol", QVariant.Int))
        fields.append(QgsField("notes", QVariant.String))
        fields.append(QgsField("strategy", QVariant.String))
        fields.append(QgsField("deploy_dec", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        scenario_risks = []
        for s in scenarios:
            rb_s = rb.get(s, {})
            bm_s = bm.get(s, {})
            mm_s = mm.get(s, {})
            robust = float(rb_s.get("robustness", 50.0))
            composite = float(bm_s.get("composite", 50.0))
            stability = float(bm_s.get("stability", max(0.0, 100.0 - float(bm_s.get("std_score", 30.0)))))
            regret = float(mm_s.get("max_regret", 50.0))

            # Lower risk is better. Components normalized to [0,100].
            risk_score = (0.40 * (100.0 - robust)) + (0.25 * regret) + (0.20 * max(0.0, 100.0 - stability)) + (0.15 * max(0.0, 100.0 - composite))
            risk_score = float(max(0.0, min(100.0, risk_score)))

            flag_regret = 1 if regret > 24.0 else 0
            flag_robust = 1 if robust < 62.0 else 0
            flag_vol = 1 if stability < 68.0 else 0
            n_flags = flag_regret + flag_robust + flag_vol

            if risk_score >= 62.0 or n_flags >= 2:
                risk_level = "HIGH"
                note = "Needs hardening before broad deployment."
            elif risk_score >= 42.0:
                risk_level = "MEDIUM"
                note = "Deploy with controls and challenger tracking."
            else:
                risk_level = "LOW"
                note = "Operationally stable for deployment track."

            role_tags = []
            if s == primary:
                role_tags.append("PRIMARY")
            if s == challenger:
                role_tags.append("CHALLENGER")
            if s == minimax_sel:
                role_tags.append("MINIMAX")
            role = "|".join(role_tags) if role_tags else "CANDIDATE"

            f = QgsFeature(fields)
            f["row_type"] = "SCENARIO"
            f["scenario"] = s
            f["role"] = role
            f["robustness"] = robust
            f["composite"] = composite
            f["stability"] = stability
            f["max_regret"] = regret
            f["risk_score"] = risk_score
            f["risk_level"] = risk_level
            f["flag_regret"] = int(flag_regret)
            f["flag_robust"] = int(flag_robust)
            f["flag_vol"] = int(flag_vol)
            f["notes"] = note
            f["strategy"] = strategy
            f["deploy_dec"] = deploy_decision
            sink.addFeature(f)
            scenario_risks.append((s, risk_score, risk_level, role))

        avg_risk = float(sum(v[1] for v in scenario_risks) / max(1, len(scenario_risks)))
        max_row = sorted(scenario_risks, key=lambda x: -x[1])[0]
        primary_risk = next((r for r in scenario_risks if r[0] == primary), max_row)
        high_count = sum(1 for _, _, lvl, _ in scenario_risks if lvl == "HIGH")

        if primary_risk[1] >= 62.0:
            overall = "UNSAFE_PRIMARY"
            overall_note = "Primary scenario remains high-risk. Keep deployment gate conservative."
        elif high_count >= 2:
            overall = "FRAGILE_PORTFOLIO"
            overall_note = "Multiple high-risk scenarios indicate fragile scenario governance."
        elif avg_risk <= 35.0:
            overall = "ROBUST_PORTFOLIO"
            overall_note = "Portfolio risk is low and governance profile is stable."
        else:
            overall = "CONTROLLED_PORTFOLIO"
            overall_note = "Portfolio is acceptable with monitoring controls."

        sf = QgsFeature(fields)
        sf["row_type"] = "SUMMARY"
        sf["scenario"] = "__SUMMARY__"
        sf["role"] = f"PRIMARY={primary}"
        sf["robustness"] = -1.0
        sf["composite"] = -1.0
        sf["stability"] = -1.0
        sf["max_regret"] = float(max_row[1])
        sf["risk_score"] = avg_risk
        sf["risk_level"] = overall
        sf["flag_regret"] = int(high_count)
        sf["flag_robust"] = 0
        sf["flag_vol"] = 0
        sf["notes"] = overall_note
        sf["strategy"] = strategy
        sf["deploy_dec"] = deploy_decision
        sink.addFeature(sf)

        feedback.pushInfo(
            f"Governance audit: primary={primary} risk={primary_risk[1]:.2f} overall={overall} avg={avg_risk:.2f} high_count={high_count}"
        )
        return {self.OUTPUT: dest}

