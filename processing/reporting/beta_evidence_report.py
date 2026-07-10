# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime

from qgis.core import (
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)


class BetaEvidenceReportAlgorithm(QgsProcessingAlgorithm):
    SUMMARY = "SUMMARY"
    ARTIFACT_DIR = "ARTIFACT_DIR"
    OUTPUT = "OUTPUT"

    def name(self):
        return "beta_evidence_report"

    def displayName(self):
        return "Reporting: Release Readiness Evidence (HTML)"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Produces a release-readiness evidence report checking algorithm registry and output artifacts.</b></p>"
            "<p><b>Inputs:</b> Execution summary notes (multiline), "
            "Optional output directory for artifact existence checks.<br>"
            "<b>Output:</b> HTML file with overall status (READY/NOT READY), algorithm registry checks "
            "(PASS/FAIL for required algorithms), artifact file checks (PASS/MISSING for expected outputs), "
            "and summary notes.<br>"
            "<b>Method:</b> Iterates a hardcoded list of required algorithm IDs and checks each against the "
            "QGIS processing registry. If an artifact directory is provided, checks expected output files "
            "(TIFF, GPKG, HTML, MD) for existence. "
            "Overall status is READY only if all registry checks pass AND all artifacts are found.<br>"
            "<b>Typical use:</b> Pre-release quality gate: confirm the complete analysis pipeline is registered "
            "and all expected deliverables were produced.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return BetaEvidenceReportAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.SUMMARY,
                "Execution summary notes",
                multiLine=True,
                defaultValue="Release readiness evidence summary for suitability workflow.",
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.ARTIFACT_DIR,
                "Optional output directory for artifact existence checks",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "HTML release evidence report", fileFilter="HTML files (*.html)"))

    def processAlgorithm(self, parameters, context, feedback):
        txt = self.parameterAsString(parameters, self.SUMMARY, context)
        artifact_dir = (self.parameterAsString(parameters, self.ARTIFACT_DIR, context) or "").strip()
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        reg = QgsApplication.processingRegistry()
        required = [
            "planx_suitability_lab:data_harmonizer",
            "planx_suitability_lab:proximity_builder",
            "planx_suitability_lab:ahp_weights",
            "planx_suitability_lab:critic_weights",
            "planx_suitability_lab:wlc_suitability",
            "planx_suitability_lab:owa_suitability",
            "planx_suitability_lab:topsis_suitability",
            "planx_suitability_lab:vikor_suitability",
            "planx_suitability_lab:ensemble_suitability",
            "planx_suitability_lab:scenario_consensus_zone",
            "planx_suitability_lab:scenario_disagreement_attention",
            "planx_suitability_lab:decision_quadrant_map",
            "planx_suitability_lab:intervention_conflict_matrix",
            "planx_suitability_lab:risk_opportunity_matrix_map",
            "planx_suitability_lab:regret_fragility_map",
            "planx_suitability_lab:opportunity_loss_map",
            "planx_suitability_lab:priority_zoning_from_suitability",
            "planx_suitability_lab:uncertainty_adjusted_suitability",
            "planx_suitability_lab:montecarlo_suitability",
            "planx_suitability_lab:xai_global_sensitivity",
            "planx_suitability_lab:weight_consensus_audit",
            "planx_suitability_lab:scenario_similarity_matrix",
            "planx_suitability_lab:scenario_dominance_matrix",
            "planx_suitability_lab:method_benchmark_leaderboard",
            "planx_suitability_lab:scenario_robustness_leaderboard",
            "planx_suitability_lab:scenario_portfolio_diversity",
            "planx_suitability_lab:minimax_regret_selector",
            "planx_suitability_lab:alignment_audit",
            "planx_suitability_lab:policy_sensitivity_frontier",
            "planx_suitability_lab:criterion_redundancy_diagnostics",
            "planx_suitability_lab:constraint_impact_audit",
            "planx_suitability_lab:priority_transition_matrix",
            "planx_suitability_lab:spatial_fragmentation_audit",
            "planx_suitability_lab:consensus_zone_area_stats",
            "planx_suitability_lab:attention_class_area_stats",
            "planx_suitability_lab:threshold_coverage_curve",
            "planx_suitability_lab:executive_kpi_snapshot",
            "planx_suitability_lab:policy_gate_recommender",
            "planx_suitability_lab:decision_quadrant_area_stats",
            "planx_suitability_lab:intervention_conflict_area_stats",
            "planx_suitability_lab:risk_opportunity_area_stats",
            "planx_suitability_lab:regret_fragility_area_stats",
            "planx_suitability_lab:actionability_scorecard",
            "planx_suitability_lab:scenario_selection_recommender",
            "planx_suitability_lab:scenario_governance_audit",
            "planx_suitability_lab:implementation_wave_planner",
            "planx_suitability_lab:deployment_readiness_gate",
            "planx_suitability_lab:intervention_budget_phasing",
            "planx_suitability_lab:action_playbook_generator",
            "planx_suitability_lab:release_narrative_builder",
            "planx_suitability_lab:suitability_html_report",
            "planx_suitability_lab:scenario_markdown_brief",
            "planx_suitability_lab:suitability_class_area_stats",
            "planx_suitability_lab:numerical_qa_check",
        ]
        rows = []
        ok = 0
        for aid in required:
            exists = reg.algorithmById(aid) is not None
            if exists:
                ok += 1
            rows.append(f"<tr><td>{aid}</td><td>{'PASS' if exists else 'FAIL'}</td></tr>")

        artifacts_html = "<p>Artifact checks skipped (no directory provided).</p>"
        artifact_ok = True
        artifact_status_line = "Skipped"
        if artifact_dir:
            expected = [
                "suitability_wlc.tif",
                "suitability_owa.tif",
                "suitability_topsis.tif",
                "suitability_vikor.tif",
                "ensemble_mean.tif",
                "ensemble_confidence.tif",
                "scenario_similarity_matrix.gpkg",
                "scenario_dominance_matrix.gpkg",
                "method_benchmark_leaderboard.gpkg",
                "scenario_robustness_leaderboard.gpkg",
                "scenario_portfolio_diversity.gpkg",
                "minimax_regret_selector.gpkg",
                "risk_opportunity_matrix.tif",
                "regret_fragility_score.tif",
                "regret_fragility_class.tif",
                "risk_opportunity_area_stats.gpkg",
                "regret_fragility_area_stats.gpkg",
                "scenario_selection_recommender.gpkg",
                "scenario_governance_audit.gpkg",
                "implementation_wave_plan.gpkg",
                "deployment_readiness_gate.gpkg",
                "policy_sensitivity_frontier.gpkg",
                "actionability_scorecard.gpkg",
                "suitability_report.html",
                "scenario_brief.md",
            ]
            a_rows = []
            found = 0
            valid_dir = os.path.isdir(artifact_dir)
            for fn in expected:
                p = os.path.join(artifact_dir, fn)
                ex = valid_dir and os.path.exists(p)
                if ex:
                    found += 1
                a_rows.append(f"<tr><td>{fn}</td><td>{'PASS' if ex else 'MISSING'}</td></tr>")
            artifact_ok = valid_dir and (found == len(expected))
            artifact_status_line = f"{found}/{len(expected)} found" if valid_dir else "INVALID DIRECTORY"
            artifacts_html = (
                f"<p><b>Directory:</b> {artifact_dir}</p>"
                f"<p><b>Artifact status:</b> {'PASS' if artifact_ok else 'FAIL'} ({artifact_status_line})</p>"
                "<table><thead><tr><th>Artifact</th><th>Check</th></tr></thead><tbody>"
                + "".join(a_rows)
                + "</tbody></table>"
            )

        status = "READY" if (ok == len(required) and artifact_ok) else "NOT READY"
        html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>PlanX Release Evidence</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:22px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #dbe7e4;padding:8px}}th{{background:#edf6f4}}</style>
</head><body>
<h1>PlanX Suitability Lab - Release Readiness Evidence</h1>
<p><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><b>Status:</b> {status} ({ok}/{len(required)} required algorithms registered, artifacts: {artifact_status_line})</p>
<h2>Registry checks</h2>
<table><thead><tr><th>Algorithm</th><th>Check</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Artifact checks</h2>
{artifacts_html}
<h2>Summary</h2><pre>{txt}</pre>
</body></html>"""
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        return {self.OUTPUT: out}
