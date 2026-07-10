# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import processing
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterExtent, QgsProcessingParameterFolderDestination, QgsProcessingParameterNumber


class SyntheticPipelineRunnerAlgorithm(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    PIXEL = "PIXEL"
    OUTDIR = "OUTDIR"

    def name(self):
        return "synthetic_pipeline_runner"

    def displayName(self):
        return "Core: Synthetic End-to-End Pipeline Runner"

    def group(self):
        return "Core"

    def groupId(self):
        return "core"

    def shortHelpString(self):
        return (
            "<p><b>Runs the complete PlanX Suitability Lab pipeline end-to-end on synthetic data, "
            "producing every raster, table, and report artifact for workflow verification.</b></p>"
            "<p><b>Inputs:</b> Study extent (bounding box); pixel size in map units (>=1.0, default 30.0).<br>"
            "<b>Output:</b> 70+ files in the output folder: suitability rasters (WLC, OWA, TOPSIS, VIKOR, ensemble), "
            "scenario diagnostics (consensus zones, disagreement attention, decision quadrants, intervention matrix, "
            "risk-opportunity matrix, regret-fragility map), opportunity loss maps, priority zoning, transition and "
            "fragmentation audits, method benchmark and robustness leaderboards, portfolio diversity, minimax regret, "
            "policy sensitivity frontier, budget phasing, governance audit, wave plan, deployment gate, "
            "and three reports (HTML suitability report, scenario markdown brief, beta evidence HTML).<br>"
            "<b>Method:</b> Chain-runs 35+ sub-algorithms in deterministic sequence: synthetic data generation, "
            "four MCDA methods with equal weights, Monte Carlo uncertainty (120 iterations, sigma 0.08), "
            "AHP/PCA/Entropy/CRITIC weight derivation, ensemble synthesis, scenario consensus and disagreement "
            "mapping, priority zoning (baseline + refined), multi-scenario benchmarking and robustness ranking, "
            "budget phasing, and deployment readiness gating.<br>"
            "<b>Typical use:</b> One-click smoke-test verifying every algorithm executes correctly "
            "after installation, environment changes, or dependency updates.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return SyntheticPipelineRunnerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(self.EXTENT, "Study extent"))
        self.addParameter(
            QgsProcessingParameterNumber(self.PIXEL, "Pixel size", type=QgsProcessingParameterNumber.Double, defaultValue=30.0, minValue=1.0)
        )
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTDIR, "Output folder"))

    def processAlgorithm(self, parameters, context, feedback):
        ex = self.parameterAsExtent(parameters, self.EXTENT, context)
        pix = float(self.parameterAsDouble(parameters, self.PIXEL, context))
        outdir = self.parameterAsString(parameters, self.OUTDIR, context)
        os.makedirs(outdir, exist_ok=True)

        syn = processing.run(
            "planx_suitability_lab:synthetic_sample_raster",
            {"EXTENT": ex, "PIXEL": pix, "OUTPUT_DIR": outdir},
            context=context,
            feedback=feedback,
        )
        wlc_out = os.path.join(outdir, "suitability_wlc.tif")
        owa_out = os.path.join(outdir, "suitability_owa.tif")
        topsis_out = os.path.join(outdir, "suitability_topsis.tif")
        vikor_out = os.path.join(outdir, "suitability_vikor.tif")
        delta_out = os.path.join(outdir, "suitability_delta_owa_minus_wlc.tif")
        delta_topsis = os.path.join(outdir, "suitability_delta_topsis_minus_wlc.tif")
        delta_vikor = os.path.join(outdir, "suitability_delta_vikor_minus_wlc.tif")
        mc_mean = os.path.join(outdir, "unc_mean.tif")
        mc_std = os.path.join(outdir, "unc_std.tif")
        mc_p05 = os.path.join(outdir, "unc_p05.tif")
        mc_p50 = os.path.join(outdir, "unc_p50.tif")
        mc_p95 = os.path.join(outdir, "unc_p95.tif")
        mc_stb = os.path.join(outdir, "stability_index.tif")
        robust_out = os.path.join(outdir, "suitability_robust.tif")
        rep = os.path.join(outdir, "suitability_report.html")
        brief = os.path.join(outdir, "scenario_brief.md")
        class_stats = os.path.join(outdir, "suitability_class_stats.gpkg")
        ahp_tbl = os.path.join(outdir, "weights_ahp.gpkg")
        pca_tbl = os.path.join(outdir, "weights_pca.gpkg")
        ent_tbl = os.path.join(outdir, "weights_entropy.gpkg")
        critic_tbl = os.path.join(outdir, "weights_critic.gpkg")
        pack_tbl = os.path.join(outdir, "weights_pack.gpkg")
        audit_tbl = os.path.join(outdir, "weights_consensus_audit.gpkg")
        ens_mean = os.path.join(outdir, "ensemble_mean.tif")
        ens_std = os.path.join(outdir, "ensemble_std.tif")
        ens_p10 = os.path.join(outdir, "ensemble_p10.tif")
        ens_p90 = os.path.join(outdir, "ensemble_p90.tif")
        ens_conf = os.path.join(outdir, "ensemble_confidence.tif")
        consensus_count = os.path.join(outdir, "scenario_consensus_count.tif")
        consensus_zone = os.path.join(outdir, "scenario_consensus_zone.tif")
        disagreement_score = os.path.join(outdir, "scenario_disagreement_score.tif")
        disagreement_class = os.path.join(outdir, "scenario_disagreement_class.tif")
        decision_quadrant = os.path.join(outdir, "decision_quadrant_map.tif")
        intervention_matrix = os.path.join(outdir, "intervention_conflict_matrix.tif")
        risk_matrix = os.path.join(outdir, "risk_opportunity_matrix.tif")
        regret_fragility_score = os.path.join(outdir, "regret_fragility_score.tif")
        regret_fragility_class = os.path.join(outdir, "regret_fragility_class.tif")
        opp_loss = os.path.join(outdir, "opportunity_loss_score.tif")
        opp_cls = os.path.join(outdir, "opportunity_loss_class.tif")
        opp_loss_wlc = os.path.join(outdir, "opportunity_loss_wlc_score.tif")
        opp_cls_wlc = os.path.join(outdir, "opportunity_loss_wlc_class.tif")
        baseline_priority_idx = os.path.join(outdir, "baseline_priority_index.tif")
        baseline_priority_zone = os.path.join(outdir, "baseline_priority_zone.tif")
        sim_tbl = os.path.join(outdir, "scenario_similarity_matrix.gpkg")
        dominance_tbl = os.path.join(outdir, "scenario_dominance_matrix.gpkg")
        benchmark_tbl = os.path.join(outdir, "method_benchmark_leaderboard.gpkg")
        robustness_tbl = os.path.join(outdir, "scenario_robustness_leaderboard.gpkg")
        portfolio_tbl = os.path.join(outdir, "scenario_portfolio_diversity.gpkg")
        minimax_tbl = os.path.join(outdir, "minimax_regret_selector.gpkg")
        alignment_tbl = os.path.join(outdir, "alignment_audit.gpkg")
        redundancy_pairs = os.path.join(outdir, "criterion_redundancy_pairs.gpkg")
        redundancy_criteria = os.path.join(outdir, "criterion_redundancy_criteria.gpkg")
        constraint_audit = os.path.join(outdir, "constraint_impact_audit.gpkg")
        priority_transition = os.path.join(outdir, "priority_transition_matrix.gpkg")
        fragmentation_tbl = os.path.join(outdir, "spatial_fragmentation_audit.gpkg")
        consensus_stats_tbl = os.path.join(outdir, "consensus_zone_area_stats.gpkg")
        attention_stats_tbl = os.path.join(outdir, "attention_class_area_stats.gpkg")
        quadrant_stats_tbl = os.path.join(outdir, "decision_quadrant_area_stats.gpkg")
        intervention_stats_tbl = os.path.join(outdir, "intervention_conflict_area_stats.gpkg")
        risk_stats_tbl = os.path.join(outdir, "risk_opportunity_area_stats.gpkg")
        regret_stats_tbl = os.path.join(outdir, "regret_fragility_area_stats.gpkg")
        threshold_curve_tbl = os.path.join(outdir, "threshold_coverage_curve.gpkg")
        executive_kpi_tbl = os.path.join(outdir, "executive_kpi_snapshot.gpkg")
        policy_gate_tbl = os.path.join(outdir, "policy_gate_recommender.gpkg")
        actionability_tbl = os.path.join(outdir, "actionability_scorecard.gpkg")
        scenario_select_tbl = os.path.join(outdir, "scenario_selection_recommender.gpkg")
        governance_audit_tbl = os.path.join(outdir, "scenario_governance_audit.gpkg")
        wave_plan_tbl = os.path.join(outdir, "implementation_wave_plan.gpkg")
        deploy_gate_tbl = os.path.join(outdir, "deployment_readiness_gate.gpkg")
        frontier_tbl = os.path.join(outdir, "policy_sensitivity_frontier.gpkg")
        budget_tbl = os.path.join(outdir, "intervention_budget_phasing.gpkg")
        priority_idx = os.path.join(outdir, "priority_index.tif")
        priority_zone = os.path.join(outdir, "priority_zone.tif")
        playbook_md = os.path.join(outdir, "action_playbook.md")
        narrative_md = os.path.join(outdir, "release_narrative.md")
        q = os.path.join(outdir, "beta_evidence.html")

        processing.run(
            "planx_suitability_lab:wlc_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "WEIGHTS_CSV": "0.25,0.25,0.25,0.25",
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "OUTPUT": wlc_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:owa_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "CRITERIA_WEIGHTS": "0.25,0.25,0.25,0.25",
                "ORDER_WEIGHTS": "0.4,0.3,0.2,0.1",
                "SORT_MODE": 0,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "OUTPUT": owa_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:topsis_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "WEIGHTS_CSV": "0.25,0.25,0.25,0.25",
                "IMPACTS_CSV": "B,B,B,C",
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": topsis_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:vikor_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "WEIGHTS_CSV": "0.25,0.25,0.25,0.25",
                "IMPACTS_CSV": "B,B,B,C",
                "V": 0.5,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": vikor_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_comparator",
            {"A": wlc_out, "B": owa_out, "OUTPUT": delta_out},
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_comparator",
            {"A": wlc_out, "B": topsis_out, "OUTPUT": delta_topsis},
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_comparator",
            {"A": wlc_out, "B": vikor_out, "OUTPUT": delta_vikor},
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:montecarlo_suitability",
            {
                "INPUT": wlc_out,
                "ITER": 120,
                "SIGMA": 0.08,
                "BLOCK": 256,
                "OUT_MEAN": mc_mean,
                "OUT_STD": mc_std,
                "OUT_P05": mc_p05,
                "OUT_P50": mc_p50,
                "OUT_P95": mc_p95,
                "OUT_STAB": mc_stb,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:ahp_weights",
            {
                "MATRIX_JSON": "[[1,2,3,4],[0.5,1,2,3],[0.3333,0.5,1,2],[0.25,0.3333,0.5,1]]",
                "OUTPUT": ahp_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:pca_derived_weights",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "OUTPUT": pca_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:entropy_weights",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "OUTPUT": ent_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:critic_weights",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "IMPACTS_CSV": "B,B,B,C",
                "OUTPUT": critic_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_weight_pack",
            {
                "AHP": ahp_tbl,
                "PCA": pca_tbl,
                "ENT": ent_tbl,
                "CRIT": critic_tbl,
                "OUTPUT": pack_tbl,
            },
            context=context,
            feedback=feedback,
        )
        audit = processing.run(
            "planx_suitability_lab:weight_consensus_audit",
            {
                "INPUT": pack_tbl,
                "OUTPUT": audit_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:ensemble_suitability",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out],
                "WEIGHTS_CSV": "0.30,0.25,0.25,0.20",
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUT_MEAN": ens_mean,
                "OUT_STD": ens_std,
                "OUT_P10": ens_p10,
                "OUT_P90": ens_p90,
                "OUT_CONF": ens_conf,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:opportunity_loss_map",
            {
                "SUIT": ens_mean,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "MEDIUM": 40.0,
                "HIGH": 70.0,
                "BLOCK": 256,
                "OUT_LOSS": opp_loss,
                "OUT_CLASS": opp_cls,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_consensus_zone",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "MEDIUM": 60.0,
                "HIGH": 75.0,
                "BLOCK": 256,
                "OUT_COUNT": consensus_count,
                "OUT_ZONE": consensus_zone,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_disagreement_attention",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "STD_REF": 18.0,
                "HIGH_MEAN": 70.0,
                "BLOCK": 256,
                "OUT_SCORE": disagreement_score,
                "OUT_CLASS": disagreement_class,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:decision_quadrant_map",
            {
                "SUITABILITY": ens_mean,
                "DISAGREEMENT": disagreement_score,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "SUIT_HIGH": 70.0,
                "DISAGREE_HIGH": 60.0,
                "BLOCK": 256,
                "OUTPUT": decision_quadrant,
            },
            context=context,
            feedback=feedback,
        )
        c_stats = processing.run(
            "planx_suitability_lab:consensus_zone_area_stats",
            {
                "INPUT": consensus_zone,
                "OUTPUT": consensus_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        a_stats = processing.run(
            "planx_suitability_lab:attention_class_area_stats",
            {
                "INPUT": disagreement_class,
                "OUTPUT": attention_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        q_stats = processing.run(
            "planx_suitability_lab:decision_quadrant_area_stats",
            {
                "INPUT": decision_quadrant,
                "OUTPUT": quadrant_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        t_curve = processing.run(
            "planx_suitability_lab:threshold_coverage_curve",
            {
                "INPUT": ens_mean,
                "STEP": 5,
                "OUTPUT": threshold_curve_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:opportunity_loss_map",
            {
                "SUIT": wlc_out,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "MEDIUM": 40.0,
                "HIGH": 70.0,
                "BLOCK": 256,
                "OUT_LOSS": opp_loss_wlc,
                "OUT_CLASS": opp_cls_wlc,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:priority_zoning_from_suitability",
            {
                "SUIT": wlc_out,
                "CONF": mc_stb,
                "OPP": opp_loss_wlc,
                "SUIT_MED": 50.0,
                "SUIT_HIGH": 75.0,
                "CONF_MED": 60.0,
                "CONF_HIGH": 80.0,
                "OPP_HIGH": 70.0,
                "BLOCK": 256,
                "OUT_INDEX": baseline_priority_idx,
                "OUT_ZONE": baseline_priority_zone,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:priority_zoning_from_suitability",
            {
                "SUIT": ens_mean,
                "CONF": ens_conf,
                "OPP": opp_loss,
                "SUIT_MED": 50.0,
                "SUIT_HIGH": 75.0,
                "CONF_MED": 60.0,
                "CONF_HIGH": 80.0,
                "OPP_HIGH": 70.0,
                "BLOCK": 256,
                "OUT_INDEX": priority_idx,
                "OUT_ZONE": priority_zone,
            },
            context=context,
            feedback=feedback,
        )
        p_trans = processing.run(
            "planx_suitability_lab:priority_transition_matrix",
            {
                "FROM_ZONE": baseline_priority_zone,
                "TO_ZONE": priority_zone,
                "OUTPUT": priority_transition,
            },
            context=context,
            feedback=feedback,
        )
        frag = processing.run(
            "planx_suitability_lab:spatial_fragmentation_audit",
            {
                "INPUT": ens_mean,
                "THRESHOLD": 70.0,
                "CONNECTIVITY": 8,
                "OUTPUT": fragmentation_tbl,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:intervention_conflict_matrix",
            {
                "PRIORITY_ZONE": priority_zone,
                "ATTENTION_CLASS": disagreement_class,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "OUTPUT": intervention_matrix,
            },
            context=context,
            feedback=feedback,
        )
        i_stats = processing.run(
            "planx_suitability_lab:intervention_conflict_area_stats",
            {
                "INPUT": intervention_matrix,
                "OUTPUT": intervention_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        sim = processing.run(
            "planx_suitability_lab:scenario_similarity_matrix",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": sim_tbl,
            },
            context=context,
            feedback=feedback,
        )
        dom = processing.run(
            "planx_suitability_lab:scenario_dominance_matrix",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "EPS": 0.5,
                "BLOCK": 256,
                "OUTPUT": dominance_tbl,
            },
            context=context,
            feedback=feedback,
        )
        bench = processing.run(
            "planx_suitability_lab:method_benchmark_leaderboard",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "HIGH_THRESHOLD": 70.0,
                "BLOCK": 256,
                "OUTPUT": benchmark_tbl,
            },
            context=context,
            feedback=feedback,
        )
        portfolio = processing.run(
            "planx_suitability_lab:scenario_portfolio_diversity",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": portfolio_tbl,
            },
            context=context,
            feedback=feedback,
        )
        minimax = processing.run(
            "planx_suitability_lab:minimax_regret_selector",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": minimax_tbl,
            },
            context=context,
            feedback=feedback,
        )
        robust_rank = processing.run(
            "planx_suitability_lab:scenario_robustness_leaderboard",
            {
                "BENCHMARK": benchmark_tbl,
                "DOMINANCE": dominance_tbl,
                "MINIMAX": minimax_tbl,
                "PORTFOLIO": portfolio_tbl,
                "OUTPUT": robustness_tbl,
            },
            context=context,
            feedback=feedback,
        )
        align = processing.run(
            "planx_suitability_lab:alignment_audit",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "SNAP": syn["CRITERION_1"],
                "OUTPUT": alignment_tbl,
            },
            context=context,
            feedback=feedback,
        )
        red = processing.run(
            "planx_suitability_lab:criterion_redundancy_diagnostics",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "MASK": syn["CONSTRAINT_MASK"],
                "MAX_SAMPLES": 120000,
                "BLOCK": 256,
                "OUTPUT_PAIRS": redundancy_pairs,
                "OUTPUT_CRITERIA": redundancy_criteria,
            },
            context=context,
            feedback=feedback,
        )
        c_audit = processing.run(
            "planx_suitability_lab:constraint_impact_audit",
            {
                "SUITABILITY": ens_mean,
                "CONSTRAINTS": [syn["CONSTRAINT_MASK"]],
                "HIGH_THRESHOLD": 70.0,
                "BLOCK": 256,
                "OUTPUT": constraint_audit,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:uncertainty_adjusted_suitability",
            {
                "MEAN": mc_mean,
                "STD": mc_std,
                "RISK": 1.0,
                "OUTPUT": robust_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:risk_opportunity_matrix_map",
            {
                "ROBUST": robust_out,
                "UNC_STD": mc_std,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "ROBUST_HIGH": 70.0,
                "STD_HIGH": 15.0,
                "BLOCK": 256,
                "OUTPUT": risk_matrix,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:regret_fragility_map",
            {
                "INPUT_RASTERS": [wlc_out, owa_out, topsis_out, vikor_out, ens_mean],
                "MASK": syn["CONSTRAINT_MASK"],
                "LOW": 12.0,
                "HIGH": 25.0,
                "BLOCK": 256,
                "OUT_SCORE": regret_fragility_score,
                "OUT_CLASS": regret_fragility_class,
            },
            context=context,
            feedback=feedback,
        )
        regret_stats = processing.run(
            "planx_suitability_lab:regret_fragility_area_stats",
            {
                "INPUT": regret_fragility_class,
                "OUTPUT": regret_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        r_stats = processing.run(
            "planx_suitability_lab:risk_opportunity_area_stats",
            {
                "INPUT": risk_matrix,
                "OUTPUT": risk_stats_tbl,
            },
            context=context,
            feedback=feedback,
        )
        frontier = processing.run(
            "planx_suitability_lab:policy_sensitivity_frontier",
            {
                "MEAN": mc_mean,
                "STD": mc_std,
                "LAMBDAS": "0,0.5,1,1.5,2",
                "OUTPUT": frontier_tbl,
            },
            context=context,
            feedback=feedback,
        )
        kpi = processing.run(
            "planx_suitability_lab:executive_kpi_snapshot",
            {
                "SUITABILITY": ens_mean,
                "ROBUST": robust_out,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "CONSENSUS_ZONE": consensus_zone,
                "ATTENTION_CLASS": disagreement_class,
                "OUTPUT": executive_kpi_tbl,
            },
            context=context,
            feedback=feedback,
        )
        gate = processing.run(
            "planx_suitability_lab:policy_gate_recommender",
            {
                "THRESHOLD_CURVE": threshold_curve_tbl,
                "FRONTIER": frontier_tbl,
                "TARGET_COVERAGE": 25.0,
                "MAX_CRITICAL_CONFLICT": 10.0,
                "OUTPUT": policy_gate_tbl,
            },
            context=context,
            feedback=feedback,
        )
        budget = processing.run(
            "planx_suitability_lab:intervention_budget_phasing",
            {
                "PRIORITY_ZONE": priority_zone,
                "PRIORITY_INDEX": priority_idx,
                "COST_BY_ZONE": "0.6,0.9,1.2,1.5,1.8",
                "STEP": 10,
                "OUTPUT": budget_tbl,
            },
            context=context,
            feedback=feedback,
        )
        scorecard = processing.run(
            "planx_suitability_lab:actionability_scorecard",
            {
                "KPI": executive_kpi_tbl,
                "BUDGET": budget_tbl,
                "GATE": policy_gate_tbl,
                "OUTPUT": actionability_tbl,
            },
            context=context,
            feedback=feedback,
        )
        scenario_pick = processing.run(
            "planx_suitability_lab:scenario_selection_recommender",
            {
                "BENCHMARK": benchmark_tbl,
                "PORTFOLIO": portfolio_tbl,
                "MINIMAX": minimax_tbl,
                "GATE": policy_gate_tbl,
                "SCORECARD": actionability_tbl,
                "ROBUSTNESS": robustness_tbl,
                "OUTPUT": scenario_select_tbl,
            },
            context=context,
            feedback=feedback,
        )
        wave_plan = processing.run(
            "planx_suitability_lab:implementation_wave_planner",
            {
                "PRIORITY_ZONE": priority_zone,
                "RISK_MATRIX": risk_matrix,
                "OUTPUT": wave_plan_tbl,
            },
            context=context,
            feedback=feedback,
        )
        deploy_gate = processing.run(
            "planx_suitability_lab:deployment_readiness_gate",
            {
                "SCORECARD": actionability_tbl,
                "SCENARIO_SELECTION": scenario_select_tbl,
                "MINIMAX": minimax_tbl,
                "WAVE_PLAN": wave_plan_tbl,
                "REGRET_STATS": regret_stats_tbl,
                "OUTPUT": deploy_gate_tbl,
            },
            context=context,
            feedback=feedback,
        )
        gov_audit = processing.run(
            "planx_suitability_lab:scenario_governance_audit",
            {
                "ROBUSTNESS": robustness_tbl,
                "BENCHMARK": benchmark_tbl,
                "MINIMAX": minimax_tbl,
                "SELECTION": scenario_select_tbl,
                "DEPLOYMENT": deploy_gate_tbl,
                "OUTPUT": governance_audit_tbl,
            },
            context=context,
            feedback=feedback,
        )
        playbook = processing.run(
            "planx_suitability_lab:action_playbook_generator",
            {
                "PROJECT": "PlanX Synthetic Smoke Study",
                "PRIORITY_ZONE": priority_zone,
                "PRIORITY_INDEX": priority_idx,
                "FRONTIER": frontier_tbl,
                "SIMILARITY": sim_tbl,
                "NOTES": "Generated from synthetic smoke pipeline for decision-workflow verification. Budget phasing table: "
                + budget["OUTPUT"],
                "OUTPUT": playbook_md,
            },
            context=context,
            feedback=feedback,
        )
        narrative = processing.run(
            "planx_suitability_lab:release_narrative_builder",
            {
                "PROJECT": "PlanX Suitability Lab",
                "VERSION": "1.6.0-draft",
                "HIGHLIGHTS": "Synthetic pipeline auto-generated governance diagnostics, budget phasing and implementation playbook artifacts.",
                "FRONTIER": frontier_tbl,
                "BUDGET": budget_tbl,
                "SIMILARITY": sim_tbl,
                "OUTPUT": narrative_md,
            },
            context=context,
            feedback=feedback,
        )
        qa = processing.run(
            "planx_suitability_lab:numerical_qa_check",
            {
                "SUIT": wlc_out,
                "P05": mc_p05,
                "P50": mc_p50,
                "P95": mc_p95,
            },
            context=context,
            feedback=feedback,
        )
        stats = processing.run(
            "planx_suitability_lab:suitability_class_area_stats",
            {
                "INPUT": robust_out,
                "BREAKS": "20,40,60,80",
                "BLOCK": 512,
                "OUTPUT": class_stats,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:suitability_html_report",
            {
                "PROJECT": "PlanX Synthetic Smoke Study",
                "SUMMARY": "Synthetic run completed with WLC, OWA, TOPSIS, VIKOR, ensemble, scenario-consensus/disagreement/quadrant/intervention mapping, risk-opportunity matrix, regret-fragility mapping, opportunity-loss mapping, scenario similarity/dominance/benchmark/robustness/diversity/minimax audits, policy sensitivity frontier, priority zoning, transition/fragmentation diagnostics, scenario selection + governance audit, implementation wave planning, deployment readiness gating, and actionability scorecard outputs.",
                "WEIGHT_METHOD": "Equal criteria overlay + AHP/PCA/Entropy/CRITIC weight diagnostics + ensemble synthesis",
                "QA_SUMMARY": qa["OUTPUT"]
                + "\n"
                + stats["SUMMARY"]
                + "\nWeight audit table: "
                + audit["OUTPUT"]
                + "\nScenario similarity matrix: "
                + sim["OUTPUT"]
                + "\nScenario dominance matrix: "
                + dom["OUTPUT"]
                + "\nMethod benchmark leaderboard: "
                + bench["OUTPUT"]
                + "\nScenario portfolio diversity: "
                + portfolio["OUTPUT"]
                + "\nScenario robustness leaderboard: "
                + robust_rank["OUTPUT"]
                + "\nMinimax regret selector: "
                + minimax["OUTPUT"]
                + "\nAlignment audit: "
                + align["OUTPUT"]
                + "\nCriterion redundancy (pairs): "
                + red["OUTPUT_PAIRS"]
                + "\nCriterion redundancy (criteria): "
                + red["OUTPUT_CRITERIA"]
                + "\nConstraint impact audit: "
                + c_audit["OUTPUT"]
                + "\nPriority transition matrix: "
                + p_trans["OUTPUT"]
                + "\nSpatial fragmentation audit: "
                + frag["OUTPUT"]
                + "\nConsensus zone area stats: "
                + c_stats["OUTPUT"]
                + "\nAttention class area stats: "
                + a_stats["OUTPUT"]
                + "\nDecision quadrant area stats: "
                + q_stats["OUTPUT"]
                + "\nIntervention conflict area stats: "
                + i_stats["OUTPUT"]
                + "\nRisk-opportunity area stats: "
                + r_stats["OUTPUT"]
                + "\nRegret fragility area stats: "
                + regret_stats["OUTPUT"]
                + "\nDisagreement score raster: "
                + disagreement_score
                + "\nDisagreement class raster: "
                + disagreement_class
                + "\nIntervention conflict matrix raster: "
                + intervention_matrix
                + "\nRisk-opportunity matrix raster: "
                + risk_matrix
                + "\nRegret fragility score raster: "
                + regret_fragility_score
                + "\nRegret fragility class raster: "
                + regret_fragility_class
                + "\nThreshold coverage curve: "
                + t_curve["OUTPUT"]
                + "\nExecutive KPI snapshot: "
                + kpi["OUTPUT"]
                + "\nPolicy gate recommender: "
                + gate["OUTPUT"]
                + "\nActionability scorecard: "
                + scorecard["OUTPUT"]
                + "\nScenario selection recommender: "
                + scenario_pick["OUTPUT"]
                + "\nScenario governance audit: "
                + gov_audit["OUTPUT"]
                + "\nImplementation wave plan: "
                + wave_plan["OUTPUT"]
                + "\nDeployment readiness gate: "
                + deploy_gate["OUTPUT"]
                + "\nPolicy frontier: "
                + frontier["OUTPUT"]
                + "\nBudget phasing: "
                + budget["OUTPUT"]
                + "\nAction playbook: "
                + playbook["OUTPUT"]
                + "\nRelease narrative: "
                + narrative["OUTPUT"],
                "OUTPUT": rep,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_markdown_brief",
            {
                "PROJECT": "PlanX Synthetic Smoke Study",
                "BASELINE": "WLC baseline",
                "SCENARIO": "OWA/TOPSIS/VIKOR + ensemble + scenario consensus/disagreement/quadrant/intervention + risk-opportunity matrix + regret fragility + opportunity-loss + priority zoning + similarity/dominance/robustness/minimax scenario governance + scenario selection + governance audit + implementation wave planning + robust overlay",
                "QA": qa["OUTPUT"]
                + "\n"
                + stats["SUMMARY"]
                + "\nWeight consensus audit: "
                + audit["OUTPUT"]
                + "\nScenario similarity matrix: "
                + sim["OUTPUT"]
                + "\nScenario dominance matrix: "
                + dom["OUTPUT"]
                + "\nMethod benchmark leaderboard: "
                + bench["OUTPUT"]
                + "\nScenario portfolio diversity: "
                + portfolio["OUTPUT"]
                + "\nScenario robustness leaderboard: "
                + robust_rank["OUTPUT"]
                + "\nMinimax regret selector: "
                + minimax["OUTPUT"]
                + "\nAlignment audit: "
                + align["OUTPUT"]
                + "\nCriterion redundancy (pairs): "
                + red["OUTPUT_PAIRS"]
                + "\nCriterion redundancy (criteria): "
                + red["OUTPUT_CRITERIA"]
                + "\nConstraint impact audit: "
                + c_audit["OUTPUT"]
                + "\nPriority transition matrix: "
                + p_trans["OUTPUT"]
                + "\nSpatial fragmentation audit: "
                + frag["OUTPUT"]
                + "\nConsensus zone area stats: "
                + c_stats["OUTPUT"]
                + "\nAttention class area stats: "
                + a_stats["OUTPUT"]
                + "\nDecision quadrant area stats: "
                + q_stats["OUTPUT"]
                + "\nIntervention conflict area stats: "
                + i_stats["OUTPUT"]
                + "\nRisk-opportunity area stats: "
                + r_stats["OUTPUT"]
                + "\nRegret fragility area stats: "
                + regret_stats["OUTPUT"]
                + "\nDisagreement score raster: "
                + disagreement_score
                + "\nDisagreement class raster: "
                + disagreement_class
                + "\nIntervention conflict matrix raster: "
                + intervention_matrix
                + "\nRisk-opportunity matrix raster: "
                + risk_matrix
                + "\nRegret fragility score raster: "
                + regret_fragility_score
                + "\nRegret fragility class raster: "
                + regret_fragility_class
                + "\nThreshold coverage curve: "
                + t_curve["OUTPUT"]
                + "\nExecutive KPI snapshot: "
                + kpi["OUTPUT"]
                + "\nPolicy gate recommender: "
                + gate["OUTPUT"]
                + "\nActionability scorecard: "
                + scorecard["OUTPUT"]
                + "\nScenario selection recommender: "
                + scenario_pick["OUTPUT"]
                + "\nScenario governance audit: "
                + gov_audit["OUTPUT"]
                + "\nImplementation wave plan: "
                + wave_plan["OUTPUT"]
                + "\nDeployment readiness gate: "
                + deploy_gate["OUTPUT"]
                + "\nPolicy frontier: "
                + frontier["OUTPUT"]
                + "\nBudget phasing: "
                + budget["OUTPUT"]
                + "\nAction playbook: "
                + playbook["OUTPUT"]
                + "\nRelease narrative: "
                + narrative["OUTPUT"],
                "NOTES": "Synthetic smoke run for environment verification.",
                "OUTPUT": brief,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:beta_evidence_report",
            {
                "ARTIFACT_DIR": outdir,
                "SUMMARY": "Synthetic pipeline executed: synthetic -> WLC/OWA/TOPSIS/VIKOR -> ensemble -> scenario-consensus/disagreement/quadrant/intervention -> risk-opportunity matrix -> regret fragility -> opportunity-loss -> priority zoning -> transition/fragmentation diagnostics -> scenario similarity -> scenario dominance -> method benchmark -> robustness leaderboard -> portfolio diversity -> minimax regret -> policy frontier -> budget phasing -> KPI/gate/scorecard -> scenario selection -> governance audit -> implementation wave planning -> deployment gate -> action playbook -> Monte Carlo -> AHP/PCA/Entropy/CRITIC -> consensus audit -> QA -> reports.\n\n"
                + qa["OUTPUT"]
                + "\n"
                + stats["SUMMARY"]
                + "\n"
                + "Weight consensus audit: "
                + audit["OUTPUT"]
                + "\n"
                + "Scenario similarity matrix: "
                + sim["OUTPUT"]
                + "\n"
                + "Scenario dominance matrix: "
                + dom["OUTPUT"]
                + "\n"
                + "Method benchmark leaderboard: "
                + bench["OUTPUT"]
                + "\n"
                + "Scenario portfolio diversity: "
                + portfolio["OUTPUT"]
                + "\n"
                + "Scenario robustness leaderboard: "
                + robust_rank["OUTPUT"]
                + "\n"
                + "Minimax regret selector: "
                + minimax["OUTPUT"]
                + "\n"
                + "Alignment audit: "
                + align["OUTPUT"]
                + "\n"
                + "Criterion redundancy (pairs): "
                + red["OUTPUT_PAIRS"]
                + "\n"
                + "Criterion redundancy (criteria): "
                + red["OUTPUT_CRITERIA"]
                + "\n"
                + "Constraint impact audit: "
                + c_audit["OUTPUT"]
                + "\n"
                + "Priority transition matrix: "
                + p_trans["OUTPUT"]
                + "\n"
                + "Spatial fragmentation audit: "
                + frag["OUTPUT"]
                + "\n"
                + "Consensus zone area stats: "
                + c_stats["OUTPUT"]
                + "\n"
                + "Attention class area stats: "
                + a_stats["OUTPUT"]
                + "\n"
                + "Decision quadrant area stats: "
                + q_stats["OUTPUT"]
                + "\n"
                + "Intervention conflict area stats: "
                + i_stats["OUTPUT"]
                + "\n"
                + "Risk-opportunity area stats: "
                + r_stats["OUTPUT"]
                + "\n"
                + "Regret fragility area stats: "
                + regret_stats["OUTPUT"]
                + "\n"
                + "Disagreement score raster: "
                + disagreement_score
                + "\n"
                + "Disagreement class raster: "
                + disagreement_class
                + "\n"
                + "Intervention conflict matrix raster: "
                + intervention_matrix
                + "\n"
                + "Risk-opportunity matrix raster: "
                + risk_matrix
                + "\n"
                + "Regret fragility score raster: "
                + regret_fragility_score
                + "\n"
                + "Regret fragility class raster: "
                + regret_fragility_class
                + "\n"
                + "Threshold coverage curve: "
                + t_curve["OUTPUT"]
                + "\n"
                + "Executive KPI snapshot: "
                + kpi["OUTPUT"]
                + "\n"
                + "Policy gate recommender: "
                + gate["OUTPUT"]
                + "\n"
                + "Actionability scorecard: "
                + scorecard["OUTPUT"]
                + "\n"
                + "Scenario selection recommender: "
                + scenario_pick["OUTPUT"]
                + "\n"
                + "Scenario governance audit: "
                + gov_audit["OUTPUT"]
                + "\n"
                + "Implementation wave plan: "
                + wave_plan["OUTPUT"]
                + "\n"
                + "Deployment readiness gate: "
                + deploy_gate["OUTPUT"]
                + "\n"
                + "Policy frontier: "
                + frontier["OUTPUT"]
                + "\n"
                + "Budget phasing: "
                + budget["OUTPUT"]
                + "\n"
                + "Action playbook: "
                + playbook["OUTPUT"]
                + "\n"
                + "Release narrative: "
                + narrative["OUTPUT"],
                "OUTPUT": q,
            },
            context=context,
            feedback=feedback,
        )
        return {
            "SYNTHETIC_DIR": syn["OUTPUT_DIR"],
            "WLC": wlc_out,
            "OWA": owa_out,
            "TOPSIS": topsis_out,
            "VIKOR": vikor_out,
            "DELTA": delta_out,
            "DELTA_TOPSIS": delta_topsis,
            "DELTA_VIKOR": delta_vikor,
            "UNC_MEAN": mc_mean,
            "UNC_STD": mc_std,
            "UNC_P05": mc_p05,
            "UNC_P50": mc_p50,
            "UNC_P95": mc_p95,
            "STABILITY": mc_stb,
            "ENSEMBLE_MEAN": ens_mean,
            "ENSEMBLE_STD": ens_std,
            "ENSEMBLE_P10": ens_p10,
            "ENSEMBLE_P90": ens_p90,
            "ENSEMBLE_CONF": ens_conf,
            "CONSENSUS_COUNT": consensus_count,
            "CONSENSUS_ZONE": consensus_zone,
            "CONSENSUS_ZONE_STATS": consensus_stats_tbl,
            "DISAGREEMENT_SCORE": disagreement_score,
            "DISAGREEMENT_CLASS": disagreement_class,
            "ATTENTION_CLASS_STATS": attention_stats_tbl,
            "DECISION_QUADRANT": decision_quadrant,
            "DECISION_QUADRANT_STATS": quadrant_stats_tbl,
            "INTERVENTION_CONFLICT_MATRIX": intervention_matrix,
            "INTERVENTION_CONFLICT_STATS": intervention_stats_tbl,
            "RISK_OPPORTUNITY_MATRIX": risk_matrix,
            "RISK_OPPORTUNITY_STATS": risk_stats_tbl,
            "REGRET_FRAGILITY_SCORE": regret_fragility_score,
            "REGRET_FRAGILITY_CLASS": regret_fragility_class,
            "REGRET_FRAGILITY_STATS": regret_stats_tbl,
            "THRESHOLD_COVERAGE_CURVE": threshold_curve_tbl,
            "EXECUTIVE_KPI": executive_kpi_tbl,
            "POLICY_GATE_RECOMMENDER": policy_gate_tbl,
            "ACTIONABILITY_SCORECARD": actionability_tbl,
            "SCENARIO_SELECTION": scenario_select_tbl,
            "SCENARIO_GOVERNANCE_AUDIT": governance_audit_tbl,
            "IMPLEMENTATION_WAVE_PLAN": wave_plan_tbl,
            "DEPLOYMENT_READINESS_GATE": deploy_gate_tbl,
            "OPPORTUNITY_LOSS": opp_loss,
            "OPPORTUNITY_LOSS_CLASS": opp_cls,
            "PRIORITY_INDEX": priority_idx,
            "PRIORITY_ZONE": priority_zone,
            "BASELINE_PRIORITY_INDEX": baseline_priority_idx,
            "BASELINE_PRIORITY_ZONE": baseline_priority_zone,
            "SCENARIO_SIMILARITY": sim_tbl,
            "SCENARIO_DOMINANCE": dominance_tbl,
            "METHOD_BENCHMARK": benchmark_tbl,
            "SCENARIO_ROBUSTNESS": robustness_tbl,
            "SCENARIO_PORTFOLIO_DIVERSITY": portfolio_tbl,
            "MINIMAX_REGRET_SELECTOR": minimax_tbl,
            "ALIGNMENT_AUDIT": alignment_tbl,
            "CRITERION_REDUNDANCY_PAIRS": redundancy_pairs,
            "CRITERION_REDUNDANCY_CRITERIA": redundancy_criteria,
            "CONSTRAINT_IMPACT_AUDIT": constraint_audit,
            "PRIORITY_TRANSITION": priority_transition,
            "SPATIAL_FRAGMENTATION": fragmentation_tbl,
            "POLICY_FRONTIER": frontier_tbl,
            "BUDGET_PHASING": budget_tbl,
            "ACTION_PLAYBOOK": playbook_md,
            "RELEASE_NARRATIVE": narrative_md,
            "WEIGHTS_AHP": ahp_tbl,
            "WEIGHTS_PCA": pca_tbl,
            "WEIGHTS_ENTROPY": ent_tbl,
            "WEIGHTS_CRITIC": critic_tbl,
            "WEIGHTS_PACK": pack_tbl,
            "WEIGHTS_AUDIT": audit_tbl,
            "ROBUST": robust_out,
            "SUITABILITY_REPORT": rep,
            "SCENARIO_BRIEF": brief,
            "QA_SUMMARY": qa["OUTPUT"],
            "CLASS_STATS": class_stats,
            "CLASS_STATS_SUMMARY": stats["SUMMARY"],
            "EVIDENCE_HTML": q,
            self.OUTDIR: outdir,
        }
