<div align="center">

<img src="icons/icon.png" width="96" alt="PlanX Suitability Lab icon"/>

# PlanX Suitability Lab

**Raster MCDA suitability lab for QGIS — AHP/PCA/Entropy weighting, WLC/OWA composition, Monte Carlo uncertainty, explainable analytics.**

[![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-93b023?logo=qgis&logoColor=white)](https://plugins.qgis.org/plugins/planx_suitability_lab/)
[![Version](https://img.shields.io/github/v/tag/YusufEminoglu/planx_suitability_lab?label=version&color=blue)](https://github.com/YusufEminoglu/planx_suitability_lab/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0-orange)](LICENSE)
[![QGIS Plugin Hub](https://img.shields.io/badge/QGIS%20Hub-install-589632?logo=qgis&logoColor=white)](https://plugins.qgis.org/plugins/planx_suitability_lab/)

</div>

---

PlanX Suitability Lab is a production-ready raster MCDA plugin for QGIS, designed for land suitability studies with strong reproducibility, uncertainty tracking, and explainability.

## Module catalog

- Core preparation:
  - `data_harmonizer` (batch CRS/extent/resolution alignment to output stack + manifest)
  - `vector_rasterizer` (constant burn or field-driven rasterization)
  - `proximity_builder` (target values, distance units, max distance)
  - `normalizer_reclassifier` (min-max and fuzzy linear/sigmoid/gaussian)
  - `constraint_builder` (hard 0/1 mask policy)
  - `synthetic_sample_raster`, `synthetic_pipeline_runner` (optional sample data/workflow for onboarding)
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
  - `candidate_site_extractor` (ranked candidate site polygons from contiguous high-suitability patches)
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
  - `beta_evidence_report` (project evidence summary)
- Dashboard:
  - production workflow pages: Overview, Workflow, Guided Flow, Modules, Quick Actions, Recent Runs, System Health
  - module-card view with search/group filters
  - persistent favorite-module star pinning and favorites-only filter
  - workflow checklist and project-status copy helpers
  - command guide opener
  - command palette for fast module/action launch (`Ctrl+K`)
  - optional sample workflow runner for onboarding
  - live per-module `Ready/Missing` registry chips
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
- For real projects, start with `data_harmonizer` and continue from the dashboard `Guided Flow` tab.
- Smart output naming: when an algorithm output is left as temporary, PlanX auto-generates readable file names in the pattern `<input>_<operation>_<timestamp>.tif`.
- Full command details are available in `docs/COMMAND_GUIDE.html`.

## 🧩 Part of the PlanX ecosystem

This plugin is one of 15 open-source QGIS plugins for urban planning by the same author:

| Planning & analysis | CAD & production | 3D & visualization |
|---|---|---|
| [PlanX](https://github.com/YusufEminoglu/PlanX) — spatial-planning suite | [PlanX CAD Toolset](https://github.com/YusufEminoglu/PlanX-CAD) — drafting-grade CAD | [PlanX 3D City](https://github.com/YusufEminoglu/planx_3d_city) — Three.js city viewer |
| [GeoStats Lab](https://github.com/YusufEminoglu/planx_geostats) — spatial statistics | [EasyFillet](https://github.com/YusufEminoglu/EasyFillet) — tangent-arc fillet | [3D OSM Model](https://github.com/YusufEminoglu/osm_3d_model) — OSM → 3D city in browser |
| [Suitability Lab](https://github.com/YusufEminoglu/planx_suitability_lab) — raster MCDA | [Settlement Toolset](https://github.com/YusufEminoglu/PlanX-Settlement) — 9-stage settlement plans | [OSM Quick 3D](https://github.com/YusufEminoglu/osm_quick_3d) — OSM → native QGIS 3D |
| [DataCube Lab](https://github.com/YusufEminoglu/planx_datacube) — spatiotemporal cubes | [UIP Toolset](https://github.com/YusufEminoglu/PlanX-UIP) — Turkish master-plan automation | [Urban Procedural 3D](https://github.com/YusufEminoglu/planx_urban_procedural_3d) — parametric zoning lab |
| [Urban Resilience](https://github.com/YusufEminoglu/planx_urban_resilience) — 28 resilience tools | [ParcelFlux](https://github.com/YusufEminoglu/parcelflux) — parcel subdivision | [CartoLab](https://github.com/YusufEminoglu/planx_cartolab) — publication cartography |

## 📜 License & author

GPL-3.0 © [Yusuf Eminoğlu](https://github.com/YusufEminoglu) — bug reports and feature requests welcome in [Issues](https://github.com/YusufEminoglu/planx_suitability_lab/issues).
