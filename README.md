# PlanX Suitability Lab

PlanX Suitability Lab is a raster-first MCDA plugin for QGIS focused on land suitability workflows.

## Beta v0.1.0 scope

- Core: data harmonizer, vector rasterizer, proximity builder, normalizer/reclassifier, hard constraint mask builder, synthetic sample raster pack, synthetic pipeline runner
- Weights: AHP, PCA-derived (variance proxy), Entropy, weight consolidator, scenario weight pack (AHP/PCA/Entropy + blended average)
- Compose: WLC suitability, OWA suitability, scenario comparator
- Uncertainty: Monte Carlo suitability summary outputs (`unc_mean`, `unc_std`, `unc_p05`, `unc_p50`, `unc_p95`, `stability_index`)
- Explainability: sampled global sensitivity table, local contribution rasters (+ percent shares), GeoShapley-lite approximation with sampled baseline
- Reporting: suitability HTML report, beta evidence HTML report
- QA: numerical acceptance checker (bounds + percentile order)
- Dashboard: guided flow tabs (`Prepare -> Criteria -> Weights -> Compose -> Uncertainty -> Explain -> Report`) and beta diagnostics helpers
- Documentation UX: detailed EN/TR HTML command guide with dashboard access and keyboard shortcuts (`Ctrl+R`, `Ctrl+D`, `Ctrl+I`, `Ctrl+H`)

## Technical defaults

- Processing-first architecture with dashboard launcher
- QGIS native + NumPy only
- Hard-constraint policy: final suitability = `constraint_mask * weighted_score`
- Memory-aware uncertainty processing via chunked Monte Carlo blocks for larger rasters

## Notes

This beta targets reproducibility and explainability. Some advanced statistical implementations are lightweight proxies in v0.1.0 and are designed to be strengthened in subsequent versions.
