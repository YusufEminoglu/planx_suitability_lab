# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime

import processing
from qgis.PyQt.QtCore import QSettings, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import Qgis, QgsApplication, QgsProject


ALGO_GROUPS = [
    (
        "Prepare",
        [
            ("Data Harmonizer", "planx_suitability_lab:data_harmonizer", "Align CRS/extent/resolution and export aligned stack."),
            ("Sample Data Generator (Optional)", "planx_suitability_lab:synthetic_sample_raster", "Create optional sample criteria and hard mask for learning/demo."),
            ("Sample Workflow Runner (Optional)", "planx_suitability_lab:synthetic_pipeline_runner", "Run optional sample workflow end-to-end on generated data."),
        ],
    ),
    (
        "Criteria",
        [
            ("Vector Rasterizer", "planx_suitability_lab:vector_rasterizer", "Rasterize by constant or field value."),
            ("Proximity Builder", "planx_suitability_lab:proximity_builder", "Distance raster from selected target values."),
            ("Normalizer/Reclassifier", "planx_suitability_lab:normalizer_reclassifier", "Min-max and fuzzy transforms."),
            ("Constraint Builder", "planx_suitability_lab:constraint_builder", "Generate hard 0/1 eligibility mask."),
        ],
    ),
    (
        "Weights",
        [
            ("AHP Weights", "planx_suitability_lab:ahp_weights", "Pairwise matrix with CR quality output."),
            ("PCA Weights", "planx_suitability_lab:pca_derived_weights", "Sampled covariance PCA objective weights."),
            ("Entropy Weights", "planx_suitability_lab:entropy_weights", "Sampled entropy-information weights."),
            ("CRITIC Weights", "planx_suitability_lab:critic_weights", "Objective weighting from contrast + inter-criterion conflict."),
            ("Scenario Weight Pack", "planx_suitability_lab:scenario_weight_pack", "Merge AHP/PCA/Entropy scenarios."),
            ("Weight Consensus Audit", "planx_suitability_lab:weight_consensus_audit", "Method-agreement diagnostics with CV-based confidence."),
        ],
    ),
    (
        "Compose",
        [
            ("WLC Suitability", "planx_suitability_lab:wlc_suitability", "Chunk-aware weighted linear combination."),
            ("OWA Suitability", "planx_suitability_lab:owa_suitability", "Chunk-aware ordered weighted averaging."),
            ("TOPSIS Suitability", "planx_suitability_lab:topsis_suitability", "Benefit/cost distance-to-ideal suitability."),
            ("VIKOR Suitability", "planx_suitability_lab:vikor_suitability", "Compromise MCDA balancing group utility and individual regret."),
            ("Ensemble Suitability", "planx_suitability_lab:ensemble_suitability", "Multi-scenario mean, spread and confidence rasters."),
            ("Scenario Consensus Zone", "planx_suitability_lab:scenario_consensus_zone", "Consensus zoning across multiple suitability scenarios."),
            ("Disagreement Attention", "planx_suitability_lab:scenario_disagreement_attention", "Highlights areas where scenarios diverge strongly, especially in high-suitability zones."),
            ("Decision Quadrant Map", "planx_suitability_lab:decision_quadrant_map", "2x2 map from suitability and disagreement to separate quick-win vs contested zones."),
            ("Intervention Conflict Matrix", "planx_suitability_lab:intervention_conflict_matrix", "Priority and conflict fused into action classes like quick-win, resolve-first, and co-design."),
            ("Risk-Opportunity Matrix", "planx_suitability_lab:risk_opportunity_matrix_map", "Combines robust suitability and uncertainty into invest/validate/defer matrix classes."),
            ("Regret Fragility Map", "planx_suitability_lab:regret_fragility_map", "Maps scenario-spread fragility from low-regret stability to high-regret contested cells."),
            ("Opportunity Loss Map", "planx_suitability_lab:opportunity_loss_map", "Highlights high-suitability areas excluded by hard constraints."),
            ("Priority Zoning", "planx_suitability_lab:priority_zoning_from_suitability", "Turns suitability/confidence/loss into action-oriented zoning classes."),
            ("Robust Suitability", "planx_suitability_lab:uncertainty_adjusted_suitability", "Risk-averse score from mean/std."),
            ("Scenario Comparator", "planx_suitability_lab:scenario_comparator", "Delta map and summary stats."),
        ],
    ),
    (
        "Uncertainty + Explain",
        [
            ("Monte Carlo Suitability", "planx_suitability_lab:montecarlo_suitability", "unc_mean/std/p05/p50/p95/stability."),
            ("Global Sensitivity", "planx_suitability_lab:xai_global_sensitivity", "Sampled criterion influence table."),
            ("Local Contribution", "planx_suitability_lab:xai_local_contribution", "Contribution and percentage rasters."),
            ("GeoShapley-lite", "planx_suitability_lab:xai_geoshapley_lite", "Local attribution around sampled baseline."),
        ],
    ),
    (
        "Report",
        [
            ("Output Integrity Check", "planx_suitability_lab:numerical_qa_check", "Checks bounds, percentile ordering and basic raster validity."),
            ("Class Area Stats", "planx_suitability_lab:suitability_class_area_stats", "Coverage by suitability bands."),
            ("Suitability HTML Report", "planx_suitability_lab:suitability_html_report", "Executive report with QA section."),
            ("Scenario Markdown Brief", "planx_suitability_lab:scenario_markdown_brief", "Planner memo output."),
            ("Scenario Similarity Matrix", "planx_suitability_lab:scenario_similarity_matrix", "Pairwise correlation/MAE/RMSE across scenario rasters."),
            ("Scenario Dominance Matrix", "planx_suitability_lab:scenario_dominance_matrix", "Pairwise win/loss/tie dominance and net-dominance rank across scenarios."),
            ("Method Benchmark Leaderboard", "planx_suitability_lab:method_benchmark_leaderboard", "Ranks scenario methods by mean/high-coverage/stability composite score."),
            ("Scenario Robustness Leaderboard", "planx_suitability_lab:scenario_robustness_leaderboard", "Fuses benchmark, dominance, minimax-regret and diversity into one elite robustness rank."),
            ("Scenario Governance Audit", "planx_suitability_lab:scenario_governance_audit", "Audits scenario-level governance risk flags for primary/challenger/minimax tracks."),
            ("Scenario Portfolio Diversity", "planx_suitability_lab:scenario_portfolio_diversity", "Audits scenario redundancy vs diversification strength in one governance table."),
            ("Minimax Regret Selector", "planx_suitability_lab:minimax_regret_selector", "Selects the least-worst-regret scenario under deep uncertainty."),
            ("Raster Alignment Audit", "planx_suitability_lab:alignment_audit", "Checks criterion grid consistency (pixel size, extent, shape) before compose."),
            ("Policy Sensitivity Frontier", "planx_suitability_lab:policy_sensitivity_frontier", "Risk-aversion frontier table over lambda sweep."),
            ("Criterion Redundancy Diagnostics", "planx_suitability_lab:criterion_redundancy_diagnostics", "Correlation + VIF diagnostics to identify overlapping criteria."),
            ("Constraint Impact Audit", "planx_suitability_lab:constraint_impact_audit", "Quantifies suitability and high-suitability loss by each hard constraint."),
            ("Priority Transition Matrix", "planx_suitability_lab:priority_transition_matrix", "Tracks zone-to-zone transition between baseline and scenario priority outputs."),
            ("Spatial Fragmentation Audit", "planx_suitability_lab:spatial_fragmentation_audit", "Measures patch compactness/fragmentation of high-suitability areas."),
            ("Consensus Zone Area Stats", "planx_suitability_lab:consensus_zone_area_stats", "Area distribution by multi-scenario consensus class."),
            ("Threshold Coverage Curve", "planx_suitability_lab:threshold_coverage_curve", "Area-above-threshold curve for policy cutoff tuning."),
            ("Attention Class Area Stats", "planx_suitability_lab:attention_class_area_stats", "Area split for disagreement attention classes."),
            ("Executive KPI Snapshot", "planx_suitability_lab:executive_kpi_snapshot", "One-row management KPI summary from key output rasters."),
            ("Policy Gate Recommender", "planx_suitability_lab:policy_gate_recommender", "Suggests threshold and lambda from coverage and frontier diagnostics."),
            ("Decision Quadrant Area Stats", "planx_suitability_lab:decision_quadrant_area_stats", "Area distribution across decision quadrants."),
            ("Intervention Conflict Area Stats", "planx_suitability_lab:intervention_conflict_area_stats", "Area distribution across intervention conflict classes."),
            ("Risk-Opportunity Area Stats", "planx_suitability_lab:risk_opportunity_area_stats", "Area distribution across invest/validate/defer strategy classes."),
            ("Regret Fragility Area Stats", "planx_suitability_lab:regret_fragility_area_stats", "Area distribution for stable/watch/fragile regret classes."),
            ("Actionability Scorecard", "planx_suitability_lab:actionability_scorecard", "Single-table implementation score from KPI, budget and policy diagnostics."),
            ("Scenario Selection Recommender", "planx_suitability_lab:scenario_selection_recommender", "Recommends primary/challenger scenario using benchmark, minimax regret, portfolio diversity and policy evidence."),
            ("Implementation Wave Planner", "planx_suitability_lab:implementation_wave_planner", "Produces four-phase implementation wave plan from priority zones and risk-opportunity matrix."),
            ("Implementation Decision Gate", "planx_suitability_lab:deployment_readiness_gate", "Automated GO/CONDITIONAL/HOLD decision using scorecard, minimax, wave plan and fragility burden."),
            ("Intervention Budget Phasing", "planx_suitability_lab:intervention_budget_phasing", "Budget-step capture curve from priority zoning and index."),
            ("Action Playbook Generator", "planx_suitability_lab:action_playbook_generator", "Markdown playbook from priority zones and policy diagnostics."),
            ("Planning Narrative Builder", "planx_suitability_lab:release_narrative_builder", "Auto-builds EN/TR planning narrative paragraphs from diagnostics tables."),
            ("Project Evidence Summary", "planx_suitability_lab:beta_evidence_report", "Creates consolidated project evidence summary tables."),
        ],
    ),
]

REQUIRED_IDS = [
    "planx_suitability_lab:data_harmonizer",
    "planx_suitability_lab:wlc_suitability",
    "planx_suitability_lab:owa_suitability",
    "planx_suitability_lab:topsis_suitability",
    "planx_suitability_lab:vikor_suitability",
    "planx_suitability_lab:uncertainty_adjusted_suitability",
    "planx_suitability_lab:ensemble_suitability",
    "planx_suitability_lab:scenario_consensus_zone",
    "planx_suitability_lab:scenario_disagreement_attention",
    "planx_suitability_lab:decision_quadrant_map",
    "planx_suitability_lab:intervention_conflict_matrix",
    "planx_suitability_lab:risk_opportunity_matrix_map",
    "planx_suitability_lab:regret_fragility_map",
    "planx_suitability_lab:opportunity_loss_map",
    "planx_suitability_lab:priority_zoning_from_suitability",
    "planx_suitability_lab:montecarlo_suitability",
    "planx_suitability_lab:xai_global_sensitivity",
    "planx_suitability_lab:critic_weights",
    "planx_suitability_lab:weight_consensus_audit",
    "planx_suitability_lab:scenario_similarity_matrix",
    "planx_suitability_lab:scenario_dominance_matrix",
    "planx_suitability_lab:method_benchmark_leaderboard",
    "planx_suitability_lab:scenario_robustness_leaderboard",
    "planx_suitability_lab:scenario_governance_audit",
    "planx_suitability_lab:scenario_portfolio_diversity",
    "planx_suitability_lab:minimax_regret_selector",
    "planx_suitability_lab:alignment_audit",
    "planx_suitability_lab:policy_sensitivity_frontier",
    "planx_suitability_lab:criterion_redundancy_diagnostics",
    "planx_suitability_lab:constraint_impact_audit",
    "planx_suitability_lab:priority_transition_matrix",
    "planx_suitability_lab:spatial_fragmentation_audit",
    "planx_suitability_lab:consensus_zone_area_stats",
    "planx_suitability_lab:threshold_coverage_curve",
    "planx_suitability_lab:attention_class_area_stats",
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
    "planx_suitability_lab:numerical_qa_check",
    "planx_suitability_lab:suitability_html_report",
    "planx_suitability_lab:scenario_markdown_brief",
]

GOVERNANCE_GROUPS = {
    "Core Engine": [
        "planx_suitability_lab:data_harmonizer",
        "planx_suitability_lab:wlc_suitability",
        "planx_suitability_lab:owa_suitability",
        "planx_suitability_lab:topsis_suitability",
        "planx_suitability_lab:vikor_suitability",
    ],
    "Reliability": [
        "planx_suitability_lab:critic_weights",
        "planx_suitability_lab:weight_consensus_audit",
        "planx_suitability_lab:scenario_similarity_matrix",
        "planx_suitability_lab:scenario_dominance_matrix",
        "planx_suitability_lab:method_benchmark_leaderboard",
        "planx_suitability_lab:scenario_robustness_leaderboard",
        "planx_suitability_lab:scenario_governance_audit",
        "planx_suitability_lab:scenario_portfolio_diversity",
        "planx_suitability_lab:alignment_audit",
        "planx_suitability_lab:montecarlo_suitability",
        "planx_suitability_lab:xai_global_sensitivity",
        "planx_suitability_lab:criterion_redundancy_diagnostics",
        "planx_suitability_lab:constraint_impact_audit",
        "planx_suitability_lab:priority_transition_matrix",
        "planx_suitability_lab:spatial_fragmentation_audit",
    ],
    "Decision Ops": [
        "planx_suitability_lab:ensemble_suitability",
        "planx_suitability_lab:scenario_consensus_zone",
        "planx_suitability_lab:scenario_disagreement_attention",
        "planx_suitability_lab:decision_quadrant_map",
        "planx_suitability_lab:intervention_conflict_matrix",
        "planx_suitability_lab:risk_opportunity_matrix_map",
        "planx_suitability_lab:regret_fragility_map",
        "planx_suitability_lab:opportunity_loss_map",
        "planx_suitability_lab:priority_zoning_from_suitability",
        "planx_suitability_lab:policy_sensitivity_frontier",
        "planx_suitability_lab:intervention_budget_phasing",
        "planx_suitability_lab:action_playbook_generator",
    ],
    "Reporting": [
        "planx_suitability_lab:numerical_qa_check",
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
        "planx_suitability_lab:scenario_robustness_leaderboard",
        "planx_suitability_lab:scenario_governance_audit",
        "planx_suitability_lab:minimax_regret_selector",
        "planx_suitability_lab:scenario_selection_recommender",
        "planx_suitability_lab:implementation_wave_planner",
        "planx_suitability_lab:deployment_readiness_gate",
        "planx_suitability_lab:suitability_html_report",
        "planx_suitability_lab:scenario_markdown_brief",
        "planx_suitability_lab:release_narrative_builder",
        "planx_suitability_lab:beta_evidence_report",
    ],
}

GROUP_ACCENT = {
    "Prepare": "#2f7aa8",
    "Criteria": "#357a5f",
    "Weights": "#7359a8",
    "Compose": "#2f6f88",
    "Uncertainty + Explain": "#8a5f36",
    "Report": "#7a4a5f",
}

CRITICAL_RUN_SEQUENCE = [
    "planx_suitability_lab:data_harmonizer",
    "planx_suitability_lab:alignment_audit",
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
    "planx_suitability_lab:priority_zoning_from_suitability",
    "planx_suitability_lab:montecarlo_suitability",
    "planx_suitability_lab:weight_consensus_audit",
    "planx_suitability_lab:criterion_redundancy_diagnostics",
    "planx_suitability_lab:constraint_impact_audit",
    "planx_suitability_lab:method_benchmark_leaderboard",
    "planx_suitability_lab:scenario_dominance_matrix",
    "planx_suitability_lab:scenario_robustness_leaderboard",
    "planx_suitability_lab:scenario_governance_audit",
    "planx_suitability_lab:scenario_portfolio_diversity",
    "planx_suitability_lab:minimax_regret_selector",
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
    "planx_suitability_lab:implementation_wave_planner",
    "planx_suitability_lab:deployment_readiness_gate",
    "planx_suitability_lab:policy_sensitivity_frontier",
    "planx_suitability_lab:intervention_budget_phasing",
    "planx_suitability_lab:action_playbook_generator",
    "planx_suitability_lab:numerical_qa_check",
    "planx_suitability_lab:suitability_html_report",
    "planx_suitability_lab:release_narrative_builder",
    "planx_suitability_lab:beta_evidence_report",
]


def _processing_provider_enabled() -> bool:
    return int(getattr(Qgis, "QGIS_VERSION_INT", 0)) < 40000


class SuitabilityDashboard(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QSettings()
        self.lang = self.settings.value("planx_suitability_lab/lang", "EN", type=str) or "EN"
        self.run_cursor = int(self.settings.value("planx_suitability_lab/run_cursor", 0, type=int) or 0)
        self.recent_runs = []
        self.card_widgets = []
        self.favorites = set(self.settings.value("planx_suitability_lab/favorites", [], type=list) or [])
        self.setWindowTitle("PlanX Suitability Lab - Production Console / Uretim Konsolu")
        self.resize(1320, 860)
        self._apply_style()
        self._build_ui()
        self._refresh()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QDialog { background: #ecf3f4; font-family: "Segoe UI"; }
            QFrame#heroCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #10384a, stop:0.45 #1b5f77, stop:1 #2d7f8f);
                border-radius: 16px;
                border: 1px solid #285f73;
            }
            QLabel#heroTitle { color: #ffffff; font-family: "Segoe UI Semibold"; font-size: 26px; font-weight: 700; letter-spacing: 0.2px; }
            QLabel#heroSub { color: #d8edf5; font-size: 13px; }
            QLabel#statusChip {
                color: #0f2d3a;
                background: #f8d37a;
                border: 1px solid #e8bf58;
                border-radius: 11px;
                padding: 4px 10px;
                font-weight: 700;
            }
            QLabel#cardCount {
                color: #2b4d57;
                font-size: 11px;
                padding: 0 4px;
            }
            QTabWidget::pane { border: 1px solid #cfdee2; border-radius: 12px; background: #ffffff; top: -1px; }
            QTabBar::tab {
                background: #dce9ec;
                color: #183844;
                border: 1px solid #c4d6dc;
                padding: 8px 13px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 3px;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: 700; border-color: #9bbac4; }
            QTextBrowser {
                background: #ffffff;
                border: 1px solid #d4e1e5;
                border-radius: 11px;
                padding: 9px;
                color: #17313a;
            }
            QPushButton {
                background: #236e83;
                color: #ffffff;
                border: 1px solid #1b5c6e;
                border-radius: 9px;
                padding: 7px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2d819a; }
            QPushButton#ghost {
                background: #ffffff;
                color: #1f6074;
                border: 1px solid #b4ccd3;
            }
            QPushButton#ghost:hover { background: #f2f8f9; }
            QPushButton#favBtn {
                background: #ffffff;
                color: #1f6f88;
                border: 1px solid #a2c4cf;
                border-radius: 7px;
                padding: 2px 7px;
                font-weight: 700;
            }
            QPushButton#favBtn:checked {
                background: #e2f3fb;
                color: #0f4d63;
                border: 1px solid #7cb1c3;
            }
            QComboBox, QLineEdit {
                background: #ffffff;
                border: 1px solid #c9d9de;
                border-radius: 7px;
                padding: 6px;
                color: #17323a;
            }
            QFrame[classCard="true"] { background: #fbfefe; border: 1px solid #d3e3e7; border-radius: 13px; }
            QFrame[classCard="true"]:hover {
                background: #f2fafc;
                border: 1px solid #a8cfdb;
            }
            QLabel[classTitle="true"] { color: #173741; font-weight: 700; font-size: 13px; }
            QLabel[classMeta="true"] { color: #4a6871; font-size: 11px; }
            QLabel[classChip="ok"] {
                color: #0d4430;
                background: #b8e9cf;
                border: 1px solid #92d8b1;
                border-radius: 9px;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel[classChip="warn"] {
                color: #734700;
                background: #ffe2ab;
                border: 1px solid #f0cb86;
                border-radius: 9px;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            """
        )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        ttl_box = QVBoxLayout()
        title = QLabel("PlanX Suitability Lab")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Raster MCDA workflow: prepare, score, compare, explain, report | Raster MCDA akisi: hazirla, puanla, karsilastir, acikla, raporla")
        subtitle.setObjectName("heroSub")
        ttl_box.addWidget(title)
        ttl_box.addWidget(subtitle)
        hero_layout.addLayout(ttl_box, 1)
        status_col = QVBoxLayout()
        status_col.setSpacing(6)
        self.status_chip = QLabel("System Status: checking...")
        self.status_chip.setObjectName("statusChip")
        status_col.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignRight)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English (Primary)", "EN")
        self.lang_combo.addItem("Turkce (Secondary)", "TR")
        self.lang_combo.setCurrentIndex(0 if self.lang == "EN" else 1)
        self.lang_combo.currentIndexChanged.connect(self._set_language)
        status_col.addWidget(self.lang_combo, 0, Qt.AlignmentFlag.AlignRight)
        hero_layout.addLayout(status_col, 0)
        root.addWidget(hero)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.overview = QTextBrowser()
        self.tabs.addTab(self.overview, "Overview / Genel")

        workflow_tab = QWidget()
        wf = QVBoxLayout(workflow_tab)
        wf.setContentsMargins(10, 10, 10, 10)
        top = QHBoxLayout()
        self.workflow_combo = QComboBox()
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                self.workflow_combo.addItem(f"{group} - {title_txt}", (aid, desc))
        top.addWidget(self.workflow_combo, 1)
        run_sel = QPushButton("Run Selected / Seciliyi Calistir")
        run_sel.clicked.connect(self._run_selected)
        top.addWidget(run_sel)
        wf.addLayout(top)
        self.workflow_desc = QTextBrowser()
        self.workflow_desc.setMaximumHeight(95)
        wf.addWidget(self.workflow_desc)
        self.workflow_map = QTextBrowser()
        wf.addWidget(self.workflow_map, 1)
        self.workflow_combo.currentIndexChanged.connect(self._update_selected_desc)
        self.tabs.addTab(workflow_tab, "Workflow / Akis")

        navigator_tab = QWidget()
        nl = QVBoxLayout(navigator_tab)
        nl.setContentsMargins(10, 10, 10, 10)
        nav_btns = QHBoxLayout()
        run_next = QPushButton("Run Next Suggested Step / Sonraki Onerilen Adim")
        run_next.clicked.connect(self._run_next_critical)
        nav_btns.addWidget(run_next)
        copy_runbook = QPushButton("Copy Workflow Checklist / Akis Kontrol Listesi")
        copy_runbook.setObjectName("ghost")
        copy_runbook.clicked.connect(self._copy_runbook)
        nav_btns.addWidget(copy_runbook)
        nav_btns.addStretch(1)
        nl.addLayout(nav_btns)
        self.navigator = QTextBrowser()
        nl.addWidget(self.navigator, 1)
        self.tabs.addTab(navigator_tab, "Guided Flow / Rehberli Akis")

        modules_tab = QWidget()
        ml = QVBoxLayout(modules_tab)
        ml.setContentsMargins(10, 10, 10, 10)
        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter modules / Modulleri filtrele (name, group, id)...")
        self.search.textChanged.connect(self._filter_cards)
        filter_row.addWidget(self.search, 1)
        self.group_filter = QComboBox()
        self.group_filter.addItem("All Groups / Tum Gruplar", "")
        for g, _ in ALGO_GROUPS:
            self.group_filter.addItem(g, g)
        self.group_filter.currentIndexChanged.connect(self._filter_cards)
        filter_row.addWidget(self.group_filter)
        self.fav_only = QPushButton("Favorites Only / Favoriler")
        self.fav_only.setObjectName("ghost")
        self.fav_only.setCheckable(True)
        self.fav_only.toggled.connect(self._filter_cards)
        filter_row.addWidget(self.fav_only)
        self.card_count = QLabel("Visible: 0/0")
        self.card_count.setObjectName("cardCount")
        filter_row.addWidget(self.card_count, 0, Qt.AlignmentFlag.AlignRight)
        ml.addLayout(filter_row)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        cards_host = QWidget()
        self.cards_grid = QGridLayout(cards_host)
        self.cards_grid.setContentsMargins(4, 4, 4, 4)
        self.cards_grid.setHorizontalSpacing(10)
        self.cards_grid.setVerticalSpacing(10)
        self.cards_scroll.setWidget(cards_host)
        ml.addWidget(self.cards_scroll, 1)
        self.tabs.addTab(modules_tab, "Modules / Moduller")

        quick_tab = QWidget()
        ql = QGridLayout(quick_tab)
        ql.setContentsMargins(12, 12, 12, 12)
        ql.setHorizontalSpacing(10)
        ql.setVerticalSpacing(10)
        quick_buttons = [
            ("Run Suggested Next Step / Onerilen Sonraki Adim", self._run_next_critical, False),
            ("Generate Project Evidence / Proje Ozet Kaniti", self._run_release_evidence, False),
            ("Open Command Palette / Komut Paleti", self._open_command_palette, False),
            ("Open Command Guide", self._open_command_guide, True),
            ("Show Shortcut Help / Kisayol Yardimi", self._show_shortcuts, True),
            ("Copy Project Status", self._copy_diagnostics, True),
            ("Copy Shortcuts", self._copy_shortcuts, True),
            ("Copy Workflow Checklist", self._copy_runbook, True),
            ("Run Sample Workflow (Optional)", self._run_synthetic_pipeline, True),
        ]
        for i, (txt, fn, ghost) in enumerate(quick_buttons):
            b = QPushButton(txt)
            if ghost:
                b.setObjectName("ghost")
            b.clicked.connect(fn)
            ql.addWidget(b, i // 2, i % 2)
        self.tabs.addTab(quick_tab, "Quick Actions / Hizli")

        runlog_tab = QWidget()
        rl = QVBoxLayout(runlog_tab)
        rl.setContentsMargins(10, 10, 10, 10)
        self.runlog = QTextBrowser()
        rl.addWidget(self.runlog, 1)
        clear_log = QPushButton("Clear Run Log / Gunlugu Temizle")
        clear_log.setObjectName("ghost")
        clear_log.clicked.connect(self._clear_runlog)
        rl.addWidget(clear_log, 0, Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(runlog_tab, "Recent Runs / Son Calismalar")

        self.readiness = QTextBrowser()
        self.tabs.addTab(self.readiness, "System Health / Sistem Durumu")

        footer = QHBoxLayout()
        refresh = QPushButton("Refresh / Yenile")
        refresh.clicked.connect(self._refresh)
        footer.addWidget(refresh)
        hint = QLabel("Shortcuts: Ctrl+K palette | Ctrl+R refresh | Ctrl+D status | Ctrl+H help | Ctrl+G guide | Ctrl+P sample(optional) | Ctrl+N next-step | Ctrl+L EN/TR")
        hint.setStyleSheet("color:#35545f;")
        footer.addWidget(hint, 1)
        root.addLayout(footer)

        self._build_cards()

    def _build_cards(self):
        for w in self.card_widgets:
            w.setParent(None)
        self.card_widgets = []
        idx = 0
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                card = QFrame()
                card.setProperty("classCard", "true")
                card.setStyleSheet(f"border-left: 3px solid {GROUP_ACCENT.get(group, '#2f6f88')};")
                v = QVBoxLayout(card)
                v.setContentsMargins(10, 10, 10, 10)

                header = QHBoxLayout()
                t = QLabel(title_txt)
                t.setProperty("classTitle", "true")
                header.addWidget(t, 1)
                status_lbl = QLabel("Checking")
                status_lbl.setProperty("classChip", "warn")
                header.addWidget(status_lbl, 0, Qt.AlignmentFlag.AlignRight)

                m = QLabel(f"{group} | {aid}")
                m.setProperty("classMeta", "true")
                d = QLabel(desc)
                d.setWordWrap(True)
                d.setStyleSheet("color:#294e58; font-size:12px;")

                fav = QPushButton("Fav")
                fav.setObjectName("favBtn")
                fav.setCheckable(True)
                fav.setChecked(aid in self.favorites)
                fav.clicked.connect(lambda checked, x=aid: self._toggle_favorite(x, checked))

                run = QPushButton("Run")
                run.clicked.connect(lambda _, x=aid, n=title_txt: self._run_algorithm(x, n))

                v.addLayout(header)
                v.addWidget(m)
                v.addWidget(d, 1)

                br = QHBoxLayout()
                br.addWidget(fav, 0, Qt.AlignmentFlag.AlignLeft)
                br.addStretch(1)
                br.addWidget(run, 0, Qt.AlignmentFlag.AlignRight)
                v.addLayout(br)

                card.meta = (group.lower(), title_txt.lower(), aid.lower(), desc.lower())
                card.algo_id = aid
                card.status_lbl = status_lbl
                r = idx // 3
                c = idx % 3
                self.cards_grid.addWidget(card, r, c)
                self.card_widgets.append(card)
                idx += 1

    def _filter_cards(self):
        q = (self.search.text() or "").strip().lower()
        group = self.group_filter.currentData() or ""
        g = group.lower().strip()
        fav_only = self.fav_only.isChecked()
        for card in self.card_widgets:
            mg, mt, ma, md = card.meta
            ok_q = (q in mg) or (q in mt) or (q in ma) or (q in md) if q else True
            ok_g = (mg == g) if g else True
            ok_f = (card.algo_id in self.favorites) if fav_only else True
            card.setVisible(ok_q and ok_g and ok_f)
        visible_count = len([c for c in self.card_widgets if c.isVisible()])
        self.card_count.setText(f"Visible: {visible_count}/{len(self.card_widgets)}")

    def _toggle_favorite(self, algo_id, checked):
        if checked:
            self.favorites.add(algo_id)
        else:
            self.favorites.discard(algo_id)
        self.settings.setValue("planx_suitability_lab/favorites", sorted(self.favorites))
        self._filter_cards()

    def _build_workflow_html(self):
        parts = ["<h2>Operational Map</h2>"]
        for group, items in ALGO_GROUPS:
            parts.append(f"<h3>{group}</h3><ul>")
            for title_txt, aid, desc in items:
                parts.append(f"<li><b>{title_txt}</b> (<code>{aid}</code>)<br>{desc}</li>")
            parts.append("</ul>")
        return "".join(parts)

    def _update_selected_desc(self):
        data = self.workflow_combo.currentData()
        if not data:
            self.workflow_desc.setHtml("")
            return
        aid, desc = data
        self.workflow_desc.setHtml(f"<b>{aid}</b><br>{desc}")

    def _track_run(self, algo_id, label):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.recent_runs.insert(0, f"[{ts}] {label} ({algo_id})")
        self.recent_runs = self.recent_runs[:30]
        self._refresh_runlog()

    def _refresh_runlog(self):
        if not self.recent_runs:
            self.runlog.setHtml("<h3>Recent Runs</h3><p>No runs yet.</p>")
            return
        html = "<h3>Recent Runs</h3><ul>" + "".join(f"<li>{line}</li>" for line in self.recent_runs) + "</ul>"
        self.runlog.setHtml(html)

    def _clear_runlog(self):
        self.recent_runs = []
        self._refresh_runlog()

    def _run_algorithm(self, algo_id, label):
        if not _processing_provider_enabled():
            QMessageBox.information(
                self,
                "PlanX Suitability Lab",
                "Processing tools are hidden in QGIS 4. Use this dashboard as a panel-only overview.",
            )
            return
        processing.execAlgorithmDialog(algo_id)
        self._track_run(algo_id, label)

    def _run_selected(self):
        data = self.workflow_combo.currentData()
        if not data:
            return
        aid, _ = data
        label = self.workflow_combo.currentText()
        self._run_algorithm(aid, label)

    def _refresh(self):
        layers = list(QgsProject.instance().mapLayers().values())
        vectors = [layer for layer in layers if hasattr(layer, "featureCount")]
        rasters = [layer for layer in layers if not hasattr(layer, "featureCount")]
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]
        gov_rows = []
        gov_ok = 0
        gov_total = 0
        for gname, ids in GOVERNANCE_GROUPS.items():
            found = len([aid for aid in ids if reg.algorithmById(aid) is not None])
            total = len(ids)
            gov_ok += found
            gov_total += total
            pct = (100.0 * found / total) if total > 0 else 0.0
            gov_rows.append((gname, found, total, pct))
        gov_score = (100.0 * gov_ok / gov_total) if gov_total > 0 else 0.0

        for card in self.card_widgets:
            is_ready = reg.algorithmById(card.algo_id) is not None
            card.status_lbl.setText("Ready" if is_ready else "Missing")
            card.status_lbl.setProperty("classChip", "ok" if is_ready else "warn")
            card.status_lbl.style().unpolish(card.status_lbl)
            card.status_lbl.style().polish(card.status_lbl)

        ready = len(missing) == 0
        status = "READY" if ready else "ATTENTION"
        self.status_chip.setText(f"System Status: {status}")
        if ready:
            self.status_chip.setStyleSheet("color:#0f2d3a;background:#9fdfbf;border:1px solid #6fc995;border-radius:11px;padding:4px 10px;font-weight:700;")
        else:
            self.status_chip.setStyleSheet("color:#0f2d3a;background:#f8d37a;border:1px solid #e8bf58;border-radius:11px;padding:4px 10px;font-weight:700;")

        self.overview.setHtml(
            "<h2>Overview</h2>"
            + (
                "<p><b>EN:</b> Production raster MCDA workflow with hard constraints, uncertainty, explainability, and reporting.</p>"
                "<p><b>TR:</b> Ikincil dil destegi etkin. Turkce yardim ve kisayollar arayuzde gorunur.</p>"
                if self.lang == "EN"
                else "<p><b>TR:</b> Sert kisit, belirsizlik, aciklanabilirlik ve raporlama iceren uretim-hazir raster MCDA platformu.</p>"
                "<p><b>EN:</b> Secondary English text remains visible for mixed-language teams.</p>"
            )
            + f"<p><b>{'Loaded layers' if self.lang == 'EN' else 'Yuklu katmanlar'}:</b> {len(layers)} (vector: {len(vectors)}, raster: {len(rasters)})</p>"
            + f"<p><b>{'System health score' if self.lang == 'EN' else 'Sistem saglik skoru'}:</b> {gov_score:.1f}% ({gov_ok}/{gov_total} checks)</p>"
            + (
                "<p><b>Tip:</b> Start with <code>Data Harmonizer</code>, then continue from <code>Guided Flow</code>.</p>"
                if self.lang == "EN"
                else "<p><b>Ipucu:</b> Once <code>Data Harmonizer</code> calistirin, sonra <code>Rehberli Akis</code> sekmesini takip edin.</p>"
            )
        )
        self.workflow_map.setHtml(self._build_workflow_html())
        self._update_selected_desc()
        self._refresh_runlog()
        self._filter_cards()

        gov_table = [
            "<table style='border-collapse:collapse;width:100%'>",
            "<tr><th style='text-align:left;border:1px solid #d7e3e6;padding:6px'>Gate</th><th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Coverage</th><th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Score</th></tr>",
        ]
        for gname, found, total, pct in gov_rows:
            gov_table.append(
                f"<tr><td style='border:1px solid #d7e3e6;padding:6px'>{gname}</td><td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{found}/{total}</td><td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{pct:.1f}%</td></tr>"
            )
        gov_table.append("</table>")

        self.readiness.setHtml(
            "<h2>System Health</h2>"
            f"<p><b>Available algorithms:</b> {len(REQUIRED_IDS) - len(missing)}/{len(REQUIRED_IDS)}</p>"
            f"<p><b>Coverage score:</b> {gov_score:.1f}% ({gov_ok}/{gov_total})</p>"
            f"<p><b>Missing modules:</b> {', '.join(missing) if missing else 'None'}</p>"
            "<h3>Workflow Coverage</h3>"
            + "".join(gov_table)
            + "<h3>What this means</h3>"
            "<ul>"
            "<li>Prepare/Criteria/Weights/Compose/Report pipeline modules are registered.</li>"
            "<li>You can run modules from Workflow, Modules, or Command Palette.</li>"
            "<li>If modules are missing, restart QGIS and refresh this panel.</li>"
            "</ul>"
        )
        self.navigator.setHtml(self._build_navigator_html(gov_rows, missing))

    def _build_navigator_html(self, gov_rows, missing):
        if self.lang == "TR":
            title = "Rehberli Proje Akisi"
            lead = "Asagidaki sira, yerlesilebilirlik calismasini sistemli ve tekrar edilebilir sekilde yurutur."
            missing_label = "Eksik moduller"
            next_step = "Sonraki adim"
            all_good = "Tum temel moduller aktif. Rehberli akisla devam edebilirsiniz."
        else:
            title = "Guided Project Flow"
            lead = "Follow this sequence to run a complete, production suitability workflow in a consistent way."
            missing_label = "Missing modules"
            next_step = "Next best action"
            all_good = "Core modules are active. Continue with the guided flow."

        flow = [
            "1) Prepare: Data Harmonizer + Alignment Audit to standardize all criteria rasters.",
            "2) Criteria: Rasterize vectors, build proximity layers, normalize scores, and create hard constraints.",
            "3) Weights: Run AHP/PCA/Entropy/CRITIC and review consensus before selecting scenarios.",
            "4) Compose: Build WLC/OWA/TOPSIS/VIKOR, then inspect consensus, disagreement, and priority zoning.",
            "5) Explain + Report: Monte Carlo, sensitivity, KPI tables, HTML report, and planning narrative.",
        ]

        gates = [
            "<table style='border-collapse:collapse;width:100%'>",
            "<tr><th style='text-align:left;border:1px solid #d7e3e6;padding:6px'>Gate</th><th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Coverage</th><th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Score</th></tr>",
        ]
        for gname, found, total, pct in gov_rows:
            gates.append(
                f"<tr><td style='border:1px solid #d7e3e6;padding:6px'>{gname}</td><td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{found}/{total}</td><td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{pct:.1f}%</td></tr>"
            )
        gates.append("</table>")

        next_action = all_good if not missing else f"{next_step}: <code>{missing[0]}</code>"
        miss_text = ", ".join(missing) if missing else "None"
        seq_id = CRITICAL_RUN_SEQUENCE[self.run_cursor % len(CRITICAL_RUN_SEQUENCE)]
        seq_hint = f"Suggested next run: <code>{seq_id}</code>"

        html = (
            f"<h2>{title}</h2>"
            f"<p>{lead}</p>"
            "<ol>"
            + "".join(f"<li>{row}</li>" for row in flow)
            + "</ol>"
            f"<p><b>{missing_label}:</b> {miss_text}</p>"
            f"<p><b>{next_action}</b></p>"
            f"<p><b>{seq_hint}</b></p>"
            "<h3>Module Coverage</h3>"
            + "".join(gates)
        )
        return html

    def _set_language(self, *_):
        data = self.lang_combo.currentData() or "EN"
        self.lang = str(data)
        self.settings.setValue("planx_suitability_lab/lang", self.lang)
        self._refresh()

    def _copy_diagnostics(self):
        layers = list(QgsProject.instance().mapLayers().values())
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]
        gate_lines = []
        for gname, ids in GOVERNANCE_GROUPS.items():
            found = len([aid for aid in ids if reg.algorithmById(aid) is not None])
            gate_lines.append(f"- {gname}: {found}/{len(ids)}")
        txt = (
            "PlanX Suitability Lab - Project Status\n"
            "=====================================\n"
            f"Loaded layers: {len(layers)}\n"
            f"Required registry coverage: {len(REQUIRED_IDS) - len(missing)}/{len(REQUIRED_IDS)}\n"
            f"Missing algorithms: {', '.join(missing) if missing else 'None'}\n"
            "Module coverage by workflow group:\n"
            + "\n".join(gate_lines)
            + "\n"
        )
        QApplication.clipboard().setText(txt)

    def _copy_shortcuts(self):
        txt = (
            "PlanX Suitability Lab Shortcuts\n"
            "===============================\n"
            "Ctrl+K : Open command palette\n"
            "Ctrl+R : Refresh dashboard checks\n"
            "Ctrl+D : Copy project status\n"
            "Ctrl+I : Copy workflow checklist\n"
            "Ctrl+H : Show shortcut help\n"
            "Ctrl+G : Open command guide\n"
            "Ctrl+P : Run sample workflow (optional)\n"
            "Ctrl+N : Run next suggested step\n"
            "Ctrl+L : Toggle language EN/TR\n"
        )
        QApplication.clipboard().setText(txt)

    def _copy_runbook(self):
        txt = (
            "PlanX Suitability Lab - Workflow Checklist\n"
            "==========================================\n"
            "1. Prepare: Harmonize all rasters and run alignment audit.\n"
            "2. Criteria: Rasterize vectors, create proximity rasters, normalize criteria, build hard constraints.\n"
            "3. Weights: Compute AHP/PCA/Entropy/CRITIC and review consensus table.\n"
            "4. Compose: Generate WLC/OWA/TOPSIS/VIKOR and compare scenarios.\n"
            "5. Explain: Run Monte Carlo and sensitivity/contribution modules.\n"
            "6. Report: Produce class stats, KPI snapshot, HTML report, and planning narrative.\n"
        )
        QApplication.clipboard().setText(txt)

    def _open_command_guide(self):
        guide_path = os.path.join(os.path.dirname(__file__), "docs", "COMMAND_GUIDE.html")
        if os.path.exists(guide_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))

    def _show_shortcuts(self):
        popup = QDialog(self)
        popup.setWindowTitle("Shortcut Help")
        popup.resize(520, 350)
        layout = QVBoxLayout(popup)
        browser = QTextBrowser()
        if self.lang == "TR":
            browser.setHtml(
                "<h2>Kisayollar (TR/EN)</h2>"
                "<ul>"
                "<li><b>Ctrl+K</b> - Komut paletini ac</li>"
                "<li><b>Ctrl+R</b> - Panel kontrollerini yenile</li>"
                "<li><b>Ctrl+D</b> - Proje durumunu kopyala</li>"
                "<li><b>Ctrl+I</b> - Akis kontrol listesini kopyala</li>"
                "<li><b>Ctrl+H</b> - Bu yardimi ac</li>"
                "<li><b>Ctrl+G</b> - Komut rehberini ac</li>"
                "<li><b>Ctrl+P</b> - Ornek akis (opsiyonel) calistir</li>"
                "<li><b>Ctrl+N</b> - Sonraki onerilen adimi calistir</li>"
                "<li><b>Ctrl+L</b> - EN/TR dil degistir</li>"
                "</ul>"
            )
        else:
            browser.setHtml(
                "<h2>Dashboard Shortcuts</h2>"
                "<ul>"
                "<li><b>Ctrl+K</b> - Open command palette</li>"
                "<li><b>Ctrl+R</b> - Refresh dashboard checks</li>"
                "<li><b>Ctrl+D</b> - Copy project status</li>"
                "<li><b>Ctrl+I</b> - Copy workflow checklist</li>"
                "<li><b>Ctrl+H</b> - Show this shortcut help</li>"
                "<li><b>Ctrl+G</b> - Open full command guide</li>"
                "<li><b>Ctrl+P</b> - Run sample workflow (optional)</li>"
                "<li><b>Ctrl+N</b> - Run next suggested step</li>"
                "<li><b>Ctrl+L</b> - Toggle EN/TR language</li>"
                "</ul>"
            )
        layout.addWidget(browser, 1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(popup.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
        popup.exec()

    def _open_command_palette(self):
        popup = QDialog(self)
        popup.setWindowTitle("Command Palette")
        popup.resize(760, 520)
        layout = QVBoxLayout(popup)

        query = QLineEdit()
        query.setPlaceholderText("Type to filter commands, modules, actions, or shortcuts...")
        layout.addWidget(query)

        listing = QListWidget()
        layout.addWidget(listing, 1)

        commands = [
            ("Run Sample Workflow (Optional)", "__action__:run_synthetic", "Optional end-to-end run on sample data", self._run_synthetic_pipeline),
            ("Run Next Suggested Step", "__action__:next_critical", "Guided project workflow execution", self._run_next_critical),
            ("Generate Project Evidence", "__action__:release_evidence", "Open consolidated project evidence dialog", self._run_release_evidence),
            ("Open Command Guide", "__action__:command_guide", "Open detailed command usage guide", self._open_command_guide),
            ("Show Shortcut Help", "__action__:shortcut_help", "Open shortcuts quick help", self._show_shortcuts),
            ("Copy Project Status", "__action__:copy_diag", "Copy layer and module coverage status", self._copy_diagnostics),
            ("Copy Workflow Checklist", "__action__:copy_runbook", "Copy step-by-step production workflow checklist", self._copy_runbook),
        ]
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                label = f"{title_txt} [{group}]"
                commands.append((label, aid, desc, lambda x=aid, n=title_txt: self._run_algorithm(x, n)))

        def refill():
            q = (query.text() or "").strip().lower()
            listing.clear()
            for label, cmd_id, desc, fn in commands:
                hay = f"{label} {cmd_id} {desc}".lower()
                if q and q not in hay:
                    continue
                item_text = f"{label}  |  {cmd_id}\n{desc}"
                item = listing.addItem(item_text)
                _ = item

        def run_current():
            row = listing.currentRow()
            if row < 0:
                return
            q = (query.text() or "").strip().lower()
            filtered = []
            for entry in commands:
                hay = f"{entry[0]} {entry[1]} {entry[2]}".lower()
                if q and q not in hay:
                    continue
                filtered.append(entry)
            if row >= len(filtered):
                return
            _, _, _, fn = filtered[row]
            popup.accept()
            fn()

        query.textChanged.connect(lambda *_: refill())
        listing.itemDoubleClicked.connect(lambda *_: run_current())

        btn_row = QHBoxLayout()
        run_btn = QPushButton("Run Selected")
        run_btn.clicked.connect(run_current)
        btn_row.addWidget(run_btn)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost")
        close_btn.clicked.connect(popup.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        refill()
        if listing.count() > 0:
            listing.setCurrentRow(0)
        query.setFocus()
        popup.exec()

    def _run_synthetic_pipeline(self):
        self._run_algorithm("planx_suitability_lab:synthetic_pipeline_runner", "Sample Workflow Runner")

    def _run_release_evidence(self):
        self._run_algorithm("planx_suitability_lab:beta_evidence_report", "Project Evidence Summary")

    def _run_next_critical(self):
        reg = QgsApplication.processingRegistry()
        if not CRITICAL_RUN_SEQUENCE:
            self._run_synthetic_pipeline()
            return
        max_len = len(CRITICAL_RUN_SEQUENCE)
        for _ in range(max_len):
            aid = CRITICAL_RUN_SEQUENCE[self.run_cursor % max_len]
            self.run_cursor = (self.run_cursor + 1) % max_len
            self.settings.setValue("planx_suitability_lab/run_cursor", self.run_cursor)
            if reg.algorithmById(aid) is not None:
                self._run_algorithm(aid, aid.split(":")[-1])
                self._refresh()
                return
        self._run_synthetic_pipeline()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_K:
            self._open_command_palette()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_R:
            self._refresh()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_D:
            self._copy_diagnostics()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_I:
            self._copy_runbook()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_H:
            self._show_shortcuts()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_G:
            self._open_command_guide()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_P:
            self._run_synthetic_pipeline()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_N:
            self._run_next_critical()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_L:
            self.lang_combo.setCurrentIndex(1 if self.lang_combo.currentIndex() == 0 else 0)
            return
        super().keyPressEvent(event)
