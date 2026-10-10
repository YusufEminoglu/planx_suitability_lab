# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import processing
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
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
            ("Sample Workflow Runner (Optional)", "planx_suitability_lab:synthetic_pipeline_runner", "Run an optional end-to-end learning workflow on generated data."),
        ],
    ),
    (
        "Criteria",
        [
            ("Vector Rasterizer", "planx_suitability_lab:vector_rasterizer", "Rasterize by constant or field value; with a reference raster it can build a 0/1 constraint mask on your grid."),
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
            ("Weight Consolidator", "planx_suitability_lab:weight_consolidator", "Normalise and activate a weight set for downstream scoring."),
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
            ("Candidate Site Extractor", "planx_suitability_lab:candidate_site_extractor", "Extracts ranked candidate site polygons from contiguous high-suitability patches."),
            ("Robust Suitability", "planx_suitability_lab:uncertainty_adjusted_suitability", "Risk-averse score from mean/std."),
            ("Scenario Comparator", "planx_suitability_lab:scenario_comparator", "Delta map and summary stats."),
        ],
    ),
    (
        "Uncertainty + Explain",
        [
            ("Monte Carlo Suitability", "planx_suitability_lab:montecarlo_suitability", "unc_mean/std/p05/p50/p95/stability."),
            ("Weight Sensitivity (OAT)", "planx_suitability_lab:weight_sensitivity_oat", "Which criterion weight moves the WLC map, and where."),
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
            ("Scenario Robustness Leaderboard", "planx_suitability_lab:scenario_robustness_leaderboard", "Fuses benchmark, dominance, minimax-regret and diversity into one robustness rank."),
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
    "planx_suitability_lab:weight_sensitivity_oat",
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
        "planx_suitability_lab:weight_sensitivity_oat",
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
        "planx_suitability_lab:candidate_site_extractor",
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

MODEL_FLOWS = [
    {
        "id": "essential",
        "title": "Essential Suitability",
        "summary": "A compact, transparent route for one defensible suitability map.",
        "outcome": "Final output: a 0-100 WLC suitability raster and ranked candidate-site polygons.",
        "steps": [
            ("Prepare the grid", "planx_suitability_lab:data_harmonizer", "Align every criterion to one CRS, extent and cell size."),
            ("Score the criteria", "planx_suitability_lab:normalizer_reclassifier", "Convert each criterion to a comparable 0-100 score. Repeat this stage for every criterion."),
            ("Set the weights", "planx_suitability_lab:ahp_weights", "Create transparent expert weights and verify the consistency ratio."),
            ("Build the suitability map", "planx_suitability_lab:wlc_suitability", "Combine criteria, weights and the optional hard-constraint mask."),
            ("Extract final sites", "planx_suitability_lab:candidate_site_extractor", "Turn high-scoring contiguous cells into ranked candidate polygons."),
        ],
    },
    {
        "id": "robust",
        "title": "Robust Decision Map",
        "summary": "A risk-aware route when weights or evidence are uncertain.",
        "outcome": "Final output: a conservative suitability raster and implementation-priority zones.",
        "steps": [
            ("Prepare the grid", "planx_suitability_lab:data_harmonizer", "Align the criterion stack before any comparison."),
            ("Score the criteria", "planx_suitability_lab:normalizer_reclassifier", "Convert every criterion to a comparable 0-100 score; repeat as needed."),
            ("Build the baseline", "planx_suitability_lab:wlc_suitability", "Create the suitability raster that will be stress-tested."),
            ("Test uncertainty", "planx_suitability_lab:montecarlo_suitability", "Simulate score variation and produce mean, spread and stability rasters."),
            ("Create the robust score", "planx_suitability_lab:uncertainty_adjusted_suitability", "Penalize unstable locations according to risk appetite."),
            ("Create priority zones", "planx_suitability_lab:priority_zoning_from_suitability", "Translate robust suitability into action-oriented final zones."),
        ],
    },
    {
        "id": "scenario",
        "title": "Scenario Comparison",
        "summary": "A compact comparison route once two or more completed suitability rasters are ready.",
        "outcome": "Final output: a decision-quadrant map separating quick wins from contested areas.",
        "steps": [
            ("Synthesize scenarios", "planx_suitability_lab:ensemble_suitability", "Create cross-scenario mean, spread and confidence surfaces."),
            ("Map disagreement", "planx_suitability_lab:scenario_disagreement_attention", "Locate high-value areas where scenarios conflict."),
            ("Create the final decision map", "planx_suitability_lab:decision_quadrant_map", "Separate quick wins, contested priorities and low-priority areas."),
        ],
    },
]


def _processing_provider_enabled() -> bool:
    return QgsApplication.processingRegistry().providerById("planx_suitability_lab") is not None


IS_QGIS4 = int(getattr(Qgis, "QGIS_VERSION_INT", 0)) >= 40000
DASHBOARD_SIZE = (1240, 820) if IS_QGIS4 else (1320, 860)
DEFAULT_CARD_COLUMNS = 2 if IS_QGIS4 else 3


class SuitabilityDashboard(QDockWidget):
    """
    Main PlanX Suitability Lab production console docked on the right side of QGIS.
    Dockable anywhere (RightDockWidgetArea by default), movable, floatable and tab-dockable.
    """

    def __init__(self, iface=None, parent=None):
        super().__init__("PlanX Suitability Lab — Production Console", parent)
        self.iface = iface
        self.setObjectName("PlanX_Suitability_Lab_Dock")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.settings = QSettings()
        self.recent_runs = []
        self.card_widgets = []
        self.model_step_widgets = []
        self._current_card_columns = DEFAULT_CARD_COLUMNS
        self.favorites = set(self.settings.value("planx_suitability_lab/favorites", [], type=list) or [])
        self.setMinimumWidth(380)

        self._central_widget = QWidget(self)
        self._central_widget.setObjectName("dashboardCentralWidget")
        self.setWidget(self._central_widget)

        self._apply_style()
        self._build_ui()
        self._refresh()

    def _apply_style(self):
        hero_radius = 12 if IS_QGIS4 else 16
        pane_radius = 10 if IS_QGIS4 else 12
        tab_radius = 7 if IS_QGIS4 else 8
        card_radius = 10 if IS_QGIS4 else 13
        button_radius = 8 if IS_QGIS4 else 9
        title_size = 18 if IS_QGIS4 else 20
        self.setStyleSheet(
            """
            QDockWidget { background: #ecf3f4; font-family: "Segoe UI"; }
            QDockWidget::title {
                background: #10384a;
                color: #ffffff;
                font-family: "Segoe UI Semibold", "Segoe UI";
                font-weight: 700;
                padding: 6px 10px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QWidget#dashboardCentralWidget { background: #ecf3f4; font-family: "Segoe UI"; }
            QDialog { background: #ecf3f4; font-family: "Segoe UI"; }
            QFrame#heroCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #10384a, stop:0.45 #1b5f77, stop:1 #2d7f8f);
                border-radius: %(hero_radius)dpx;
                border: 1px solid #285f73;
            }
            QLabel#heroTitle { color: #ffffff; font-family: "Segoe UI Semibold"; font-size: %(title_size)dpx; font-weight: 700; letter-spacing: 0.2px; }
            QLabel#heroSub { color: #d8edf5; font-size: 13px; }
            QLabel#statusChip {
                color: #0f2d3a;
                background: #f8d37a;
                border: 1px solid #e8bf58;
                border-radius: %(tab_radius)dpx;
                padding: 4px 10px;
                font-weight: 700;
            }
            QLabel#cardCount {
                color: #2b4d57;
                font-size: 11px;
                padding: 0 4px;
            }
            QTabWidget::pane { border: 1px solid #cfdee2; border-radius: %(pane_radius)dpx; background: #ffffff; top: -1px; }
            QTabBar::tab {
                background: #dce9ec;
                color: #183844;
                border: 1px solid #c4d6dc;
                padding: 8px 13px;
                border-top-left-radius: %(tab_radius)dpx;
                border-top-right-radius: %(tab_radius)dpx;
                margin-right: 3px;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: 700; border-color: #9bbac4; }
            QTextBrowser {
                background: #ffffff;
                border: 1px solid #d4e1e5;
                border-radius: %(pane_radius)dpx;
                padding: 9px;
                color: #17313a;
            }
            QPushButton {
                background: #236e83;
                color: #ffffff;
                border: 1px solid #1b5c6e;
                border-radius: %(button_radius)dpx;
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
                border-radius: %(tab_radius)dpx;
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
                border-radius: %(tab_radius)dpx;
                padding: 6px;
                color: #17323a;
            }
            QFrame[classCard="true"] { background: #fbfefe; border: 1px solid #d3e3e7; border-radius: %(card_radius)dpx; }
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
                border-radius: %(tab_radius)dpx;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel[classChip="warn"] {
                color: #734700;
                background: #ffe2ab;
                border: 1px solid #f0cb86;
                border-radius: %(tab_radius)dpx;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            """
            % {
                "button_radius": button_radius,
                "card_radius": card_radius,
                "hero_radius": hero_radius,
                "pane_radius": pane_radius,
                "tab_radius": tab_radius,
                "title_size": title_size,
            }
        )

    def _build_ui(self):
        root_margin = 10 if IS_QGIS4 else 14
        root_spacing = 10 if IS_QGIS4 else 12
        section_margin = 8 if IS_QGIS4 else 10
        grid_spacing = 8 if IS_QGIS4 else 10
        root = QVBoxLayout(self._central_widget)
        root.setContentsMargins(root_margin, root_margin, root_margin, root_margin)
        root.setSpacing(root_spacing)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        ttl_box = QVBoxLayout()
        title = QLabel("PlanX Suitability Lab")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Raster MCDA workflow: prepare, score, compare, explain, report")
        subtitle.setObjectName("heroSub")
        ttl_box.addWidget(title)
        ttl_box.addWidget(subtitle)
        hero_layout.addLayout(ttl_box, 1)
        status_col = QVBoxLayout()
        status_col.setSpacing(4 if IS_QGIS4 else 6)
        self.status_chip = QLabel("System Status: checking...")
        self.status_chip.setObjectName("statusChip")
        status_col.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignRight)
        hero_layout.addLayout(status_col, 0)
        root.addWidget(hero)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        model_tab = QWidget()
        model_layout = QVBoxLayout(model_tab)
        model_layout.setContentsMargins(section_margin, section_margin, section_margin, section_margin)
        model_head = QHBoxLayout()
        model_label = QLabel("Choose a model")
        model_label.setProperty("classTitle", True)
        model_head.addWidget(model_label)
        self.model_flow_combo = QComboBox()
        for model in MODEL_FLOWS:
            self.model_flow_combo.addItem(model["title"], model["id"])
        saved_model = self.settings.value("planx_suitability_lab/model_flow", MODEL_FLOWS[0]["id"])
        saved_index = self.model_flow_combo.findData(saved_model)
        self.model_flow_combo.setCurrentIndex(max(0, saved_index))
        self.model_flow_combo.currentIndexChanged.connect(self._model_flow_changed)
        model_head.addWidget(self.model_flow_combo, 1)
        self.model_progress = QLabel()
        self.model_progress.setObjectName("cardCount")
        model_head.addWidget(self.model_progress)
        reset_model = QPushButton("Reset flow")
        reset_model.setObjectName("ghost")
        reset_model.clicked.connect(self._reset_model_flow)
        model_head.addWidget(reset_model)
        model_layout.addLayout(model_head)

        self.model_summary = QLabel()
        self.model_summary.setWordWrap(True)
        self.model_summary.setStyleSheet("color:#35545f;padding:2px 4px;")
        model_layout.addWidget(self.model_summary)
        self.model_outcome = QLabel()
        self.model_outcome.setWordWrap(True)
        self.model_outcome.setStyleSheet("background:#e5f4ed;color:#174b36;border:1px solid #b7dcc9;border-radius:8px;padding:9px;font-weight:700;")
        model_layout.addWidget(self.model_outcome)

        model_scroll = QScrollArea()
        model_scroll.setWidgetResizable(True)
        self.model_steps_host = QWidget()
        self.model_steps_layout = QVBoxLayout(self.model_steps_host)
        self.model_steps_layout.setContentsMargins(4, 4, 4, 4)
        self.model_steps_layout.setSpacing(grid_spacing)
        model_scroll.setWidget(self.model_steps_host)
        model_layout.addWidget(model_scroll, 1)
        self.tabs.addTab(model_tab, "Model Flow")

        self.overview = QTextBrowser()
        self.tabs.addTab(self.overview, "Overview")

        modules_tab = QWidget()
        ml = QVBoxLayout(modules_tab)
        ml.setContentsMargins(section_margin, section_margin, section_margin, section_margin)
        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter modules (name, group, id)...")
        self.search.textChanged.connect(self._filter_cards)
        filter_row.addWidget(self.search, 1)
        self.group_filter = QComboBox()
        self.group_filter.addItem("All Groups", "")
        for g, _ in ALGO_GROUPS:
            self.group_filter.addItem(g, g)
        self.group_filter.currentIndexChanged.connect(self._filter_cards)
        filter_row.addWidget(self.group_filter)
        self.fav_only = QPushButton("Favorites Only")
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
        self.cards_grid.setHorizontalSpacing(grid_spacing)
        self.cards_grid.setVerticalSpacing(grid_spacing)
        self.cards_scroll.setWidget(cards_host)
        ml.addWidget(self.cards_scroll, 1)
        self.tabs.addTab(modules_tab, "Modules")

        runlog_tab = QWidget()
        rl = QVBoxLayout(runlog_tab)
        rl.setContentsMargins(section_margin, section_margin, section_margin, section_margin)
        self.runlog = QTextBrowser()
        rl.addWidget(self.runlog, 1)
        clear_log = QPushButton("Clear Run Log")
        clear_log.setObjectName("ghost")
        clear_log.clicked.connect(self._clear_runlog)
        rl.addWidget(clear_log, 0, Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(runlog_tab, "Recent Runs")

        self.readiness = QTextBrowser()
        self.tabs.addTab(self.readiness, "System Health")

        footer = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh)
        footer.addWidget(refresh)
        btn_ahp = QPushButton("✨ AHP Studio")
        btn_ahp.setToolTip("Open Interactive AHP Weight & Consistency (CR) Studio")
        btn_ahp.setStyleSheet("background: #1b7e5a; color: white; font-weight: bold;")
        btn_ahp.clicked.connect(self._open_ahp_studio)
        footer.addWidget(btn_ahp)
        hint = QLabel("Shortcuts: Ctrl+N current model stage | Ctrl+K module search | Ctrl+R refresh | Ctrl+D status | Ctrl+H help")
        hint.setStyleSheet("color:#35545f;")
        footer.addWidget(hint, 1)
        root.addLayout(footer)

        self._build_cards()
        self._render_model_flow()

    def _current_model(self):
        model_id = self.model_flow_combo.currentData()
        return next((model for model in MODEL_FLOWS if model["id"] == model_id), MODEL_FLOWS[0])

    def _model_progress_index(self, model):
        key = f"planx_suitability_lab/model_progress/{model['id']}"
        value = int(self.settings.value(key, 0, type=int) or 0)
        return max(0, min(value, len(model["steps"])))

    def _model_flow_changed(self):
        model = self._current_model()
        self.settings.setValue("planx_suitability_lab/model_flow", model["id"])
        self._render_model_flow()

    def _render_model_flow(self):
        while self.model_steps_layout.count():
            item = self.model_steps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.model_step_widgets = []

        model = self._current_model()
        cursor = self._model_progress_index(model)
        total = len(model["steps"])
        self.model_summary.setText(model["summary"])
        self.model_outcome.setText(model["outcome"])
        self.model_progress.setText(f"Progress: {cursor}/{total}")

        reg = QgsApplication.processingRegistry()
        for index, (title_txt, algo_id, desc) in enumerate(model["steps"]):
            card = QFrame()
            card.setProperty("classCard", True)
            row = QHBoxLayout(card)
            row.setContentsMargins(12, 9, 12, 9)

            step_no = QLabel(str(index + 1))
            step_no.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_no.setFixedSize(30, 30)
            if index < cursor:
                step_no.setStyleSheet("background:#9fdfbf;color:#174b36;border-radius:15px;font-weight:700;")
                state = "Complete"
            elif index == cursor:
                step_no.setStyleSheet("background:#236e83;color:white;border-radius:15px;font-weight:700;")
                state = "Current stage"
            else:
                step_no.setStyleSheet("background:#dce9ec;color:#4a6871;border-radius:15px;font-weight:700;")
                state = "Upcoming"
            row.addWidget(step_no)

            copy = QVBoxLayout()
            stage_title = QLabel(f"{title_txt}  |  {state}")
            stage_title.setProperty("classTitle", True)
            stage_desc = QLabel(desc)
            stage_desc.setWordWrap(True)
            stage_desc.setProperty("classMeta", True)
            copy.addWidget(stage_title)
            copy.addWidget(stage_desc)
            row.addLayout(copy, 1)

            run_btn = QPushButton("Run again" if index < cursor else "Run stage")
            available = reg.algorithmById(algo_id) is not None
            run_btn.setEnabled(available and index <= cursor)
            if index > cursor:
                run_btn.setText("Locked")
                run_btn.setObjectName("ghost")
            elif not available:
                run_btn.setText("Missing")
                run_btn.setObjectName("ghost")
            run_btn.clicked.connect(
                lambda _checked=False, mid=model["id"], pos=index: self._run_model_stage(mid, pos)
            )
            row.addWidget(run_btn)
            self.model_steps_layout.addWidget(card)
            self.model_step_widgets.append(card)
        self.model_steps_layout.addStretch(1)

    def _run_model_stage(self, model_id, index):
        model = next((item for item in MODEL_FLOWS if item["id"] == model_id), None)
        if model is None or index >= len(model["steps"]):
            return
        title_txt, algo_id, _ = model["steps"][index]
        if not self._run_algorithm(algo_id, title_txt):
            return
        cursor = self._model_progress_index(model)
        if index == cursor:
            self.settings.setValue(f"planx_suitability_lab/model_progress/{model_id}", cursor + 1)
        self._render_model_flow()

    def _run_current_model_stage(self):
        model = self._current_model()
        cursor = self._model_progress_index(model)
        if cursor >= len(model["steps"]):
            QMessageBox.information(self, "PlanX Suitability Lab", model["outcome"])
            return
        self._run_model_stage(model["id"], cursor)

    def _reset_model_flow(self):
        model = self._current_model()
        self.settings.setValue(f"planx_suitability_lab/model_progress/{model['id']}", 0)
        self._render_model_flow()

    def _build_cards(self):
        for w in self.card_widgets:
            w.setParent(None)
        self.card_widgets = []
        columns = self._cards_column_count()
        self._current_card_columns = columns
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
                r = idx // columns
                c = idx % columns
                self.cards_grid.addWidget(card, r, c)
                self.card_widgets.append(card)
                idx += 1

    def _cards_column_count(self):
        if not hasattr(self, "cards_scroll"):
            return DEFAULT_CARD_COLUMNS
        viewport = self.cards_scroll.viewport()
        width = viewport.width() if viewport is not None else 0
        if width <= 0:
            width = max(1, self.width() - 120)
        target_card_width = 420 if IS_QGIS4 else 360
        max_columns = 2 if IS_QGIS4 else 3
        columns = max(1, min(max_columns, width // target_card_width))
        return columns or 1

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

    def _open_ahp_studio(self):
        try:
            from .ahp_studio import open_ahp_studio
            open_ahp_studio(self.iface, self)
            self._track_run("planx_suitability_lab:ahp_weights", "AHP Interactive Studio")
            return True
        except Exception as exc:
            QMessageBox.warning(self, "AHP Studio Error", f"Failed to open AHP Studio: {exc}")
            return False

    def _run_algorithm(self, algo_id, label):
        if algo_id == "planx_suitability_lab:ahp_weights":
            return self._open_ahp_studio()

        reg = QgsApplication.processingRegistry()
        if not _processing_provider_enabled() or reg.algorithmById(algo_id) is None:
            QMessageBox.information(
                self,
                "PlanX Suitability Lab",
                "Processing provider is not registered yet. Reload the plugin or refresh the Processing toolbox, then try again.",
            )
            return False
        result = processing.execAlgorithmDialog(algo_id)
        if not result:
            return False
        self._track_run(algo_id, label)
        return True

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
            "<p>Production raster MCDA workflow with hard constraints, uncertainty, explainability, and reporting.</p>"
            + f"<p><b>Loaded layers:</b> {len(layers)} (vector: {len(vectors)}, raster: {len(rasters)})</p>"
            + f"<p><b>System health score:</b> {gov_score:.1f}% ({gov_ok}/{gov_total} checks)</p>"
            + "<p><b>Tip:</b> Choose a goal in <code>Model Flow</code>; the first stage and final output are shown together.</p>"
        )
        self._refresh_runlog()
        self._filter_cards()
        self._render_model_flow()

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
            "<li>You can run guided stages from Model Flow or any individual tool from Modules.</li>"
            "<li>If modules are missing, restart QGIS and refresh this panel.</li>"
            "</ul>"
        )

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

    def _show_shortcuts(self):
        popup = QDialog(self)
        popup.setWindowTitle("Shortcut Help")
        popup.resize(520, 350)
        layout = QVBoxLayout(popup)
        browser = QTextBrowser()
        browser.setHtml(
            "<h2>Dashboard Shortcuts</h2>"
            "<ul>"
            "<li><b>Ctrl+K</b> - Open command palette</li>"
            "<li><b>Ctrl+R</b> - Refresh dashboard checks</li>"
            "<li><b>Ctrl+D</b> - Copy project status</li>"
            "<li><b>Ctrl+H</b> - Show this shortcut help</li>"
            "<li><b>Ctrl+N</b> - Run the current Model Flow stage</li>"
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
            ("Run Current Model Stage", "__action__:model_stage", "Continue the selected compact model flow", self._run_current_model_stage),
            ("Generate Project Evidence", "__action__:release_evidence", "Open consolidated project evidence dialog", self._run_release_evidence),
            ("Show Shortcut Help", "__action__:shortcut_help", "Open shortcuts quick help", self._show_shortcuts),
            ("Copy Project Status", "__action__:copy_diag", "Copy layer and module coverage status", self._copy_diagnostics),
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

    def _run_release_evidence(self):
        self._run_algorithm("planx_suitability_lab:beta_evidence_report", "Project Evidence Summary")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "cards_grid"):
            return
        desired_columns = self._cards_column_count()
        if desired_columns == self._current_card_columns:
            return
        self._build_cards()
        self._refresh()

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
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_H:
            self._show_shortcuts()
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_N:
            self._run_current_model_stage()
            return
        super().keyPressEvent(event)


def open_dashboard(iface=None, parent=None) -> SuitabilityDashboard:
    """
    Opens PlanX Suitability Lab production console docked on the right side of QGIS.
    If already opened, brings it to front and focuses it.
    """
    if iface is not None:
        main_win = iface.mainWindow()
        dock = main_win.findChild(QDockWidget, "PlanX_Suitability_Lab_Dock")
        if dock is None:
            dock = SuitabilityDashboard(iface, main_win)
            iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            ahp_dock = main_win.findChild(QDockWidget, "PlanX_AHP_Studio_Dock")
            if ahp_dock is not None:
                iface.tabifyDockWidget(dock, ahp_dock)
        dock.show()
        dock.raise_()
        dock.activateWindow()
        return dock
    else:
        dock = SuitabilityDashboard(iface, parent)
        dock.show()
        return dock
