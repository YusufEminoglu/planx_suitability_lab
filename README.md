# PlanX Suitability Lab

PlanX Suitability Lab is a production-ready raster MCDA plugin for QGIS, designed for land suitability studies with strong reproducibility, uncertainty tracking, and explainability.

## Release Scope (v1.0.0)

- Core preparation:
  - `data_harmonizer` (batch CRS/extent/resolution alignment to output stack + manifest)
  - `vector_rasterizer` (constant burn or field-driven rasterization)
  - `proximity_builder` (target values, distance units, max distance)
  - `normalizer_reclassifier` (min-max and fuzzy linear/sigmoid/gaussian)
  - `constraint_builder` (hard 0/1 mask policy)
  - `synthetic_sample_raster`, `synthetic_pipeline_runner` (smoke and QA automation)
- Weight engines:
  - `ahp_weights` (CR and CR acceptance flag)
  - `pca_derived_weights` (sampled covariance PCA-based weights)
  - `entropy_weights` (sampled entropy-information weights)
  - `critic_weights` (objective CRITIC: contrast + inter-criterion conflict)
  - `weight_consolidator`, `scenario_weight_pack`, `weight_consensus_audit`
- Compose engines:
  - `wlc_suitability` (chunk-aware weighted linear combination)
  - `owa_suitability` (chunk-aware OWA with criteria + order weights)
  - `topsis_suitability` (benefit/cost impacts + ideal/anti-ideal proximity)
  - `vikor_suitability` (compromise MCDA balancing group utility and individual regret)
  - `ensemble_suitability` (multi-scenario mean/std/p10/p90/confidence rasters)
  - `scenario_consensus_zone` (cross-scenario consensus count and consensus-class zoning)
  - `scenario_disagreement_attention` (conflict score/class map where scenarios diverge)
  - `decision_quadrant_map` (suitability x disagreement 2x2 decision map)
  - `intervention_conflict_matrix` (priority and conflict fused to execution classes)
  - `risk_opportunity_matrix_map` (robust suitability x uncertainty strategy matrix)
  - `regret_fragility_map` (cross-scenario regret spread score and fragility classes)
  - `opportunity_loss_map` (detects high-suitability zones excluded by hard constraints)
  - `priority_zoning_from_suitability` (action zoning from suitability/confidence/opportunity-loss)
  - `uncertainty_adjusted_suitability` (robust score from mean-std with risk aversion factor)
  - `scenario_comparator` (delta raster + stats summary)
- Uncertainty:
  - `montecarlo_suitability` with chunk processing and outputs:
    `unc_mean`, `unc_std`, `unc_p05`, `unc_p50`, `unc_p95`, `stability_index`
- Explainability:
  - `xai_global_sensitivity`
  - `xai_local_contribution`
  - `xai_geoshapley_lite`
- Reporting:
  - `suitability_html_report`
  - `scenario_markdown_brief`
  - `suitability_class_area_stats`
  - `scenario_similarity_matrix`
  - `scenario_dominance_matrix`
  - `method_benchmark_leaderboard`
  - `scenario_robustness_leaderboard`
  - `scenario_portfolio_diversity`
  - `minimax_regret_selector`
  - `scenario_governance_audit`
  - `alignment_audit`
  - `policy_sensitivity_frontier`
  - `criterion_redundancy_diagnostics`
  - `constraint_impact_audit`
  - `priority_transition_matrix`
  - `spatial_fragmentation_audit`
  - `consensus_zone_area_stats`
  - `attention_class_area_stats`
  - `threshold_coverage_curve`
  - `executive_kpi_snapshot`
  - `policy_gate_recommender`
  - `decision_quadrant_area_stats`
  - `intervention_conflict_area_stats`
  - `risk_opportunity_area_stats`
  - `regret_fragility_area_stats`
  - `actionability_scorecard`
  - `scenario_selection_recommender`
  - `implementation_wave_planner`
  - `deployment_readiness_gate`
  - `intervention_budget_phasing`
  - `action_playbook_generator`
  - `release_narrative_builder`
  - `numerical_qa_check`
  - `beta_evidence_report` (release readiness evidence report)
- Dashboard:
  - studio-grade workflow pages and grouped algorithm catalog
  - module-card view with search/group filters
  - persistent favorite-module star pinning and favorites-only filter
  - diagnostics and issue template helpers
  - publication runbook copy helper and navigator tab
  - command guide opener
  - command palette for fast module/action launch (`Ctrl+K`)
  - one-click synthetic smoke pipeline runner
  - live per-module `Ready/Missing` registry chips and critical-module tags
  - bilingual EN/TR dashboard mode with quick toggle
  - recent-run log panel with timestamps
  - redesigned visual theme and layout

## Technical Policy

- QGIS native + NumPy only (no mandatory external scientific stack)
- Hard-constraint policy:
  - final suitability = `constraint_mask * score`
- Large-raster resilience:
  - chunk-based processing in heavy modules (WLC/OWA/TOPSIS/VIKOR/Monte Carlo/comparator)

## Notes

- Use aligned 0-100 criteria rasters for best MCDA behavior.
- Run `synthetic_pipeline_runner` first when validating new environments.
- Smart output naming: when an algorithm output is left as temporary, PlanX auto-generates readable file names in the pattern `<input>_<operation>_<timestamp>.tif`.
- Full command details are available in `docs/COMMAND_GUIDE.html`.
- Competitive positioning snapshot is documented in `docs/COMPETITIVE_BENCHMARK_2026-05.md`.
