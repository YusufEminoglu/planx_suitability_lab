# Changelog

All notable changes to **PlanX Suitability Lab** are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [0.3.0] - 2026-05-23

- Initial beta release of Processing-first raster MCDA architecture with dashboard launcher.
- Added core preparation modules: harmonizer, rasterizer, proximity builder, normalizer/reclassifier, hard-constraint mask builder.
- Added weighting modules: AHP (CR output), PCA-derived weights, entropy weights, and a weight consolidator.
- Added composition modules: WLC (bounded 0-100 + hard mask), OWA transform, and scenario comparator.
- Upgraded Monte Carlo uncertainty to NumPy-based simulation with reproducible random seed and outputs:
  `unc_mean`, `unc_std`, `unc_p05`, `unc_p50`, `unc_p95`, `stability_index`.
- Added explainability and reporting modules: global sensitivity, local contribution, GeoShapley-lite, and HTML report generator.
- Added EN/TR command guide at `docs/COMMAND_GUIDE.html` and dashboard keyboard shortcuts:
  `Ctrl+R`, `Ctrl+D`, `Ctrl+I`, `Ctrl+H`.
- Added synthetic sample raster pack generator for fast end-to-end smoke setup.
- Added numerical QA checker for suitability bounds and Monte Carlo percentile order checks.
- Added scenario weight pack to merge AHP/PCA/Entropy outputs and emit a blended-average scenario.
- Added synthetic end-to-end pipeline runner (synthetic -> WLC -> Monte Carlo -> evidence report).
- Added beta evidence HTML report and dashboard quick actions for pipeline/evidence runs.
- Upgraded global sensitivity from placeholder values to sampled statistical importance using criterion std and active weights.
- Upgraded GeoShapley-lite to multi-criterion weighted attribution with sampled global baseline.
- Upgraded local contributions with percent-share rasters and total absolute contribution denominator.
- Refactored Monte Carlo to block/chunk processing for more predictable memory behavior on larger rasters.
- Rebuilt normalizer/reclassifier with explicit methods: min-max benefit/cost, fuzzy linear benefit/cost, fuzzy sigmoid benefit/cost, fuzzy gaussian benefit.
- Rebuilt OWA composition as true multi-raster OWA with criteria weights + order weights + optional hard mask.
- Expanded data harmonizer to batch-align all input rasters into an output folder with manifest and preview output.
- Expanded synthetic pipeline runner to execute WLC + OWA + scenario delta + Monte Carlo + numerical QA + reports in one flow.
