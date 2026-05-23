# Changelog

All notable changes to **PlanX Suitability Lab** are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [1.2.2] - 2026-05-23

- Reworked dashboard into a studio console with module cards and grouped catalog browsing.
- Added module filtering (search + group) and in-dashboard direct run buttons.
- Added recent-runs panel with timestamps and quick log clearing.
- Improved workflow navigation and quick-actions ergonomics.

## [1.2.1] - 2026-05-23

- Rebuilt the dashboard UI as a studio-grade console with cleaner layout, grouped workflow catalog, and improved visual hierarchy.
- Added a fully custom PlanX Suitability Lab icon (PNG) and removed prior duplicate icon usage.
- Updated quick-action UX, readiness labeling, and release changelog helper text in dashboard.

## [1.2.0] - 2026-05-23

- Added suitability class-area statistics algorithm (`suitability_class_area_stats`) for class-based coverage analysis and reporting.
- Integrated class-stat summaries into synthetic pipeline QA and reporting chain.
- Standardized weight and sensitivity table outputs to geometry-free tables for cleaner Processing behavior.

## [1.1.0] - 2026-05-23

- Added uncertainty-adjusted suitability algorithm (`uncertainty_adjusted_suitability`) for risk-averse planning outputs based on uncertainty mean and standard deviation.
- Added scenario markdown brief generator (`scenario_markdown_brief`) for studio and decision memo workflows.
- Expanded synthetic pipeline runner to produce robust suitability and markdown planning brief artifacts.

## [1.0.0] - 2026-05-23

- Promoted plugin from beta track to production-ready release.
- Added chunk-aware computation in core heavy compose workflows for better large-raster behavior.
- Rebuilt WLC as nodata-safe, block-based weighted overlay with hard-constraint policy support.
- Rebuilt OWA as nodata-safe, block-based ordered weighting using both criteria and order weights.
- Added TOPSIS suitability algorithm with benefit/cost impacts and hard-constraint support.
- Upgraded scenario comparator to block-based delta engine with stats summary output.
- Upgraded normalizer with explicit min-max and fuzzy linear/sigmoid/gaussian modes.
- Upgraded harmonizer to export a full aligned raster stack folder plus manifest.
- Expanded rasterizer with field-driven mode and proximity builder with target-value/distance controls.
- Upgraded Monte Carlo to chunk-based execution with full percentile and stability outputs.
- Upgraded AHP output with CR acceptance flag and inconsistency warnings.
- Upgraded PCA/entropy sampling logic for more robust objective weight estimation.
- Expanded synthetic pipeline runner to execute WLC, OWA, TOPSIS, deltas, uncertainty, QA and HTML reporting.
- Upgraded release evidence reporting and dashboard release-readiness UX.
- Documentation refreshed for release usage and operator guidance.
