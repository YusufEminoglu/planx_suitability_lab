# Changelog

## [1.3.6] - 2026-05-26

- Maintenance release: refreshed Plugin Hub package with QGIS 4 panel-only dashboard mode.

## [1.3.5] - 2026-05-26

- Keep QGIS 4 dashboard panel-only by hiding the Processing provider.

## [1.3.4] - 2026-05-26

- Fix QGIS 4 / Qt6 dashboard alignment enum compatibility.

All notable changes to **PlanX Suitability Lab** are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

- Fixed QGIS 3.40 compatibility for table-producing algorithms by replacing `parameterAsSink(..., None)` with explicit `QgsCoordinateReferenceSystem()` across Weights/Reporting/XAI modules.
- Fixed missing `QgsCoordinateReferenceSystem` imports in table-producing modules (`weights`, `reporting`, `xai`) that caused runtime `NameError` in QGIS 3.40.
- Fixed `Core: Vector Rasterizer` input handling to use validated vector layer objects, preventing `Could not load source layer for INPUT: invalid value` failures on GeoPackage layers.
- Dashboard UX was streamlined for production use: removed beta/release/issue-oriented wording, simplified quick actions, and centered the interface on guided project execution.
- Reworked user guidance into a clean `Guided Flow` and `System Health` model with actionable next-step suggestions.
- Updated module and report labels to user-facing planning terminology (for example, `Output Integrity Check`, `Planning Narrative Builder`, `Project Evidence Summary`).
- Removed non-essential benchmark/issue helpers from primary UX surface while keeping optional sample workflow tools for onboarding.
- Added smart temporary output naming across core/compose/uncertainty/XAI raster modules: when users keep output as temporary, files are now auto-named as `<input>_<operation>_<timestamp>.tif` for traceable run artifacts.
- Added `vikor_suitability` as a fourth major compose engine (WLC/OWA/TOPSIS/VIKOR) for compromise-based MCDA decision support.
- Added `scenario_robustness_leaderboard` to fuse benchmark, dominance, minimax-regret and portfolio-diversity evidence into one elite robustness rank.
- Added `scenario_governance_audit` to convert robustness/benchmark/minimax/selection evidence into scenario-level governance-risk flags and portfolio status.
- Upgraded `scenario_selection_recommender` to consume optional robustness evidence and switch to a robustness-hardening strategy when needed.
- Extended synthetic pipeline with VIKOR outputs (`suitability_vikor`, delta-vs-WLC), robustness leaderboard artifact, and robust selection wiring.
- Refreshed dashboard visual system (studio theme polish), bilingual button/tab labels, and runbook/changelog helper texts.
- Rebuilt the studio dashboard visual hierarchy with stronger module cards, accent-group styling, and cleaner status presentation.
- Added per-module live registry health chips (`Ready` / `Missing`) plus `Critical` tagging for release-essential modules.
- Added visible-module counter, shortcut help popup, and `Copy Shortcuts` quick action for better operator ergonomics.
- Regenerated `icons/icon.png` as a unique, production-grade PlanX Suitability Lab mark.
- Synced command guide shortcut table with real dashboard keybindings and added status-chip behavior notes.
- Added `critic_weights` objective weighting algorithm (contrast + inter-criterion conflict), with per-criterion diagnostics.
- Added `weight_consensus_audit` to quantify agreement/disagreement across weighting methods using CV-based confidence classes.
- Added `ensemble_suitability` for multi-scenario synthesis with `mean/std/p10/p90/confidence` rasters.
- Extended `scenario_weight_pack` to ingest optional CRITIC tables and included new modules in synthetic smoke pipeline and release-evidence checks.
- Added `opportunity_loss_map` to identify high-suitability areas excluded by hard constraints (score + class outputs).
- Added `scenario_similarity_matrix` for pairwise scenario QA (Pearson, MAE, RMSE, agreement class).
- Added `method_benchmark_leaderboard` to rank MCDA scenario methods by composite performance (mean, high-coverage, p90, stability).
- Added `scenario_portfolio_diversity` to quantify method redundancy/diversification strength and effective-scenario depth.
- Added `risk_opportunity_matrix_map` for strategy zoning from robust suitability and uncertainty (invest / validate / defer classes).
- Added `risk_opportunity_area_stats` for planning-facing area splits of risk-opportunity strategy classes.
- Added `regret_fragility_map` for cross-scenario regret spread mapping (stable/watch/fragile classes).
- Added `minimax_regret_selector` implementing Savage minimax-regret scenario selection under deep uncertainty.
- Added `scenario_dominance_matrix` for pairwise scenario win/loss/tie diagnostics and net-dominance ranking.
- Added `regret_fragility_area_stats` for area shares of stable/watch/fragile regret classes.
- Added `scenario_selection_recommender` to select primary/challenger scenario using benchmark, minimax regret, portfolio diversity and readiness context.
- Added `implementation_wave_planner` to generate four-phase execution waves from priority zones and risk-opportunity classes.
- Added `deployment_readiness_gate` to synthesize scorecard + minimax + wave + fragility diagnostics into GO/CONDITIONAL/HOLD release decisions.
- Added `priority_zoning_from_suitability` for action-oriented implementation zones from suitability, confidence, and constraint-loss.
- Added `policy_sensitivity_frontier` for lambda-sweep decision frontier diagnostics (mean/median/p90 and area-above-threshold metrics).
- Added `action_playbook_generator` to transform zoning/uncertainty diagnostics into an implementation-ready Markdown action plan.
- Added `intervention_budget_phasing` to quantify impact-capture vs budget steps for phased implementation planning.
- Added `release_narrative_builder` to automatically assemble bilingual release narrative paragraphs from diagnostic evidence tables.
- Added `criterion_redundancy_diagnostics` for correlation + VIF-based criterion overlap diagnostics.
- Added `constraint_impact_audit` to quantify suitability/high-suitability loss by each hard-constraint mask and union effect.
- Added `alignment_audit` to verify raster grid consistency (pixel size, extent, dimensions) before MCDA composition.
- Added `priority_transition_matrix` to quantify baseline-to-scenario implementation zone shifts with transition classes.
- Added `spatial_fragmentation_audit` to assess compactness and patch fragmentation of high-suitability areas.
- Extended synthetic pipeline chain with baseline priority zoning plus transition and fragmentation diagnostics.
- Added `scenario_consensus_zone` for cross-scenario agreement mapping (consensus count + consensus class raster outputs).
- Added `consensus_zone_area_stats` for planning-facing area breakdown of consensus classes.
- Added `threshold_coverage_curve` for policy-threshold sweeps (area and percent above threshold).
- Added `scenario_disagreement_attention` to map contested suitability zones with conflict score and attention classes.
- Added `attention_class_area_stats` for area distribution of disagreement attention classes.
- Added `executive_kpi_snapshot` for single-row management KPI extraction from key output rasters.
- Added `policy_gate_recommender` for automated threshold/lambda gate suggestions from curve and frontier diagnostics.
- Added `decision_quadrant_map` to segment areas by suitability/conflict quadrants for execution strategy.
- Added `decision_quadrant_area_stats` for area share by quadrant class.
- Added `intervention_conflict_matrix` to combine priority and conflict into direct execution classes.
- Added `intervention_conflict_area_stats` for area share by intervention class.
- Added `actionability_scorecard` to synthesize KPI, budget, and policy-gate diagnostics into an overall readiness grade.
- Extended synthetic pipeline and readiness scope with consensus diagnostics artifacts.
- Added a new Navigator tab in dashboard with staged publication run-order, gate coverage table, and next-critical execution shortcut.
- Added dashboard Command Palette (`Ctrl+K`) for fast search-and-run across all modules and operational quick actions.
- Added dashboard EN/TR language mode switch, `Ctrl+N` next-critical run shortcut, and `Ctrl+L` language toggle.
- Reworked `Ctrl+N` flow into a persisted guided critical-run sequence instead of registry-missing checks.
- Extended synthetic pipeline outputs and report chains with redundancy + constraint-impact diagnostics.

## [1.3.1] - 2026-05-24

- Fixed Hub scan quality blockers and warnings reported for `1.3.0`.
- Resolved `E741` in dashboard list comprehensions by replacing ambiguous variable names.
- Resolved `E226` arithmetic spacing warnings in diagnostics/readiness counters.
- Removed unused imports (`F401`) in `main_plugin.py` and `decision_quadrant_map.py`.
- Fixed `F841` in `_mcda_utils.py` by releasing dataset references without dead assignment.
- Removed trailing blank-line issues (`W391`) in package init files.
- Added `setup.cfg` flake8 policy to ignore `W503` and `E203` (Black-compatible style).
- Removed hidden `icons/.gitkeep` to clear suspicious hidden-file warning.

## [1.2.3] - 2026-05-24

- Added persistent module favorites (star pinning) in dashboard cards.
- Added `Favorites Only` filter for faster access to preferred workflows.
- Stored favorites with QSettings so user preferences persist across sessions.

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
