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
  - `weight_consolidator`, `scenario_weight_pack`
- Compose engines:
  - `wlc_suitability` (chunk-aware weighted linear combination)
  - `owa_suitability` (chunk-aware OWA with criteria + order weights)
  - `topsis_suitability` (benefit/cost impacts + ideal/anti-ideal proximity)
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
  - `numerical_qa_check`
  - `beta_evidence_report` (release readiness evidence report)
- Dashboard:
  - studio-grade workflow pages and grouped algorithm catalog
  - module-card view with search/group filters
  - diagnostics and issue template helpers
  - command guide opener
  - one-click synthetic smoke pipeline runner
  - recent-run log panel with timestamps
  - redesigned visual theme and layout

## Technical Policy

- QGIS native + NumPy only (no mandatory external scientific stack)
- Hard-constraint policy:
  - final suitability = `constraint_mask * score`
- Large-raster resilience:
  - chunk-based processing in heavy modules (WLC/OWA/TOPSIS/Monte Carlo/comparator)

## Notes

- Use aligned 0-100 criteria rasters for best MCDA behavior.
- Run `synthetic_pipeline_runner` first when validating new environments.
- Full command details are available in `docs/COMMAND_GUIDE.html`.
