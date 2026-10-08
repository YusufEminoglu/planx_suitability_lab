# Changelog

## [1.7.1] - 2026-10-09

### Added
- **Vector Rasterizer can now produce a constraint mask on your analysis grid.**
  Three optional inputs: a *reference raster* (its extent, cell size and CRS
  replace the vector extent and the pixel size; the vector is reprojected when
  the CRS differ), a *background value* and *treat background as NoData*.
  The defaults reproduce the previous behaviour exactly (vector extent,
  background 0 as NoData). Exclusion polygons become a 0/1 mask with
  reference raster = grid, burn 0, background 1, NoData off: 0 inside the
  polygons, 1 elsewhere, same shape as the criteria rasters.
  Why: the old route (Vector Rasterizer, then Constraint Builder) produced a
  mask that was smaller than the grid and marked the polygon interior as
  *suitable* (Constraint Builder keeps cells >= threshold), the opposite of an
  exclusion.

## [1.7.0] - 2026-09-29

### Fixed
- **Constraint Builder produced an all-nodata mask on Windows.** It ran
  gdal:rastercalculator with the formula `(A>=t)`; that command line goes
  through a shell on Windows, `>` became a redirect, the calculation failed
  and wrote its error into a stray file named `0.5)`, and the run reported
  success with a mask that was nodata in every cell - so any map constrained
  by it lost every cell. The mask is now computed with GDAL and numpy, and
  `raster_calc` refuses formulas the Windows command line would mangle.
- **Inputs beyond a tool's limit were dropped silently.** 18 algorithms sliced
  their raster list (`[:6]`, `[:12]`...); extra criteria vanished from the
  result. They now stop with the limit and the number given.
- **AHP accepted non-reciprocal matrices** although its method requires
  `a[i][j] = 1/a[j][i]`; a transposed judgement produced plausible but
  meaningless weights and CR. Such matrices are now rejected (2% tolerance for
  rounded fractions such as 0.3333).
- **WLC, OWA, TOPSIS, VIKOR and Ensemble borrowed the first input's nodata**
  for their float output; with a byte raster's nodata 0, real scores of 0 and
  constraint-excluded cells became nodata. Outputs now use -9999.
- The TOPSIS help described a 0-1 result for a 0-100 output; the Monte Carlo
  help claimed to capture weight uncertainty, which it does not model.
- Two GDAL-dependent test files were registered as pure-Python tests and
  failed the release gate; they now run on both QGIS runtimes.

### Added
- **Uncertainty: One-at-a-Time Weight Sensitivity** (`weight_sensitivity_oat`,
  69th algorithm). Each criterion weight is changed by +/-p% (default 20) with
  the others rescaled proportionally; the WLC map is recomputed and a ranked
  table reports mean and maximum absolute change and the share of cells
  moving more than a threshold, with an optional map of where one weight
  matters (Chen, Yu & Khan 2010). Reference manual section 4.2.
- Suitability outputs (WLC, OWA, TOPSIS, VIKOR, Normalizer, Robust
  Suitability) load with a fixed 0-100 colour ramp, and constraint masks with
  Excluded/Allowed classes, for temporary and file outputs alike.

## [1.6.9] - 2026-09-16

- Redesign plugin icon to high-end 3D tactile brand design with circular teal pedestal, zero margin, and refreshed documentation links.

## [1.6.8] - 2026-09-06

- Migrate repository and documentation URLs to GitLab and Cloudflare Pages.

## [1.6.7] - 2026-08-07

- Added online user manual link (https://yusufeminoglu.github.io/planx_suitability_lab/) and GitHub repository star call-to-action.

## [1.6.6] - 2026-08-07

- Add floating Save as PDF button to reference manual

## [1.6.5] - 2026-08-07

- Add comprehensive academic reference manual: 68 algorithms, 45 equations, DOI-verified refs

## [1.6.4] - 2026-07-20

- Added a compact, outcome-led `Model Flow` dashboard with three alternatives: Essential Suitability, Robust Decision Map, and Scenario Comparison. Each route exposes its final output up front, locks future stages until the current stage runs, and persists progress independently.
- Simplified the production UI by replacing the overlapping Workflow, Guided Flow, and Quick Actions tabs with Model Flow. Removed sample/test workflow and standalone command-guide actions from the user-facing dashboard, stopped shipping the obsolete command-guide page, and retained the complete Processing catalog under Modules.

## [1.6.3] - 2026-07-17

- QGIS Hub review fixes for 1.6.2. Qt6 compatibility: migrated all 296 Qt5-style `QVariant.*` field-type enums across 37 algorithm files to `QMetaType.Type.*` (`Double`/`Int`/`LongLong` map 1:1, `String` → `QString`) — PyQt6 has no `QVariant.Type`, and `QMetaType.Type` is the documented replacement (the `QgsField` QVariant constructor is deprecated since QGIS 3.38); every mapping was probe-verified with a `QgsField` round-trip on QGIS 3.44 LTR and QGIS 4.2 before rewriting (`scratch/qvariant_to_qmetatype.py`).
- Code quality: renamed the ambiguous loop variable `l` flagged by the Hub's Flake8 panel (E741) in 10 files; the local Hub-scan mirror now also checks E741/E742/E743 so quality findings surface before upload.

## [1.6.2] - 2026-07-17

- QGIS 4 / Qt6 readiness: scoped all 169 remaining Qt5-style enum accesses across 63 algorithm files for the Hub's Qt6 static check — `QgsProcessing.Type*` → `QgsProcessing.SourceType.Type*` and `QgsProcessingParameterNumber.Integer|Double` → `QgsProcessingParameterNumber.Type.*`. Every scoped form was probe-verified against both QGIS 3.44 LTR and QGIS 4 before rewriting (`scratch/qt6_enum_audit.py`); `QVariant.*` field types intentionally stay unscoped (PyQt6 has no `QVariant.Type`; the qgis.PyQt compatibility layer keeps them working). No functional change.

## [1.6.1] - 2026-07-17

- Security hardening: resolved all remaining Bandit findings in code — the B110/B112 `try/except: pass|continue` patterns in `_mcda_utils` and the six reporting algorithms (actionability scorecard, deployment readiness gate, policy gate recommender, scenario governance audit, scenario robustness leaderboard, scenario selection recommender) were rewritten with `contextlib.suppress`, preserving row-skip semantics. The `.bandit` skip configuration was removed entirely; the QGIS Hub security scan now passes plain CLEAN with zero findings and zero suppressions.
- Packaging hygiene fix: `packaging/zip_hub.py` now always excludes internal AI-agent work-order files (`ENHANCEMENT_PLAN_*.md`, `DEEPSEEK_PROMPT_*.txt`, `REPORT_v*.md`) from the built zip, regardless of version suffix. These files remain in the GitHub repository as project history but no longer ship in the QGIS Hub package.

## [1.6.0] - 2026-07-10

- English-only conversion: removed bilingual EN/TR machinery from dashboard (language combo, Ctrl+L, all Turkish UI strings), release_narrative_builder (TR narrative removed), action_playbook_generator (TR recommendations removed), COMMAND_GUIDE.html, and README.
- In-toolbox documentation: added `shortHelpString()` with algorithm-specific HTML help and `helpUrl()` returning the GitHub repo URL to all 68 Processing algorithms, covering every parameter, output, method, and typical use.
- New pure-logic unit tests (`tests/test_mcda_logic.py`): 12 test functions with ~80 assertions covering weight parsing (CSV/impacts), AHP eigenvalue derivation with CR check, entropy weights, PCA proxy weights, CRITIC weights, edge cases (constant rasters, empty inputs, single criterion), and slug/label utilities.
- Fixed edge-case bugs in `_mcda_utils.py`: CRITIC single-criterion guard (1x1 correlation matrix), PCA degenerate covariance (np.atleast_2d).
- Dashboard: corrected algorithm catalog to 68 entries (added missing weight_consolidator to ALGO_GROUPS).
- New end-to-end test scaffold (`tests/e2e_qgis_full.py`): provider assertion (68-algo pin), synthetic pipeline execution, per-algorithm coverage with dashboard smoke test (lang-free verification, catalog-provider cross-check).
- Updated README, COMMAND_GUIDE.html (English-only, no Ctrl+L), and metadata.txt for 1.6.0.
- Fixed the e2e harness's parameter names (initial DeepSeek scaffold used invented keys) and extended it to execute all 68/68 algorithms, including the 17 chain-dependent reporting/weight/vector algorithms; PASS on both QGIS 3.44 LTR and QGIS 4.

## [1.5.1] - 2026-06-18

- docs: add CITATION.cff for Zenodo DOI integration

## [1.5.0] - 2026-06-10

- Added `candidate_site_extractor` (Compose) — the missing "last mile" from raster to action: extracts contiguous high-suitability patches as ranked candidate site polygons with `site_id`, `rank`, `cells`, `area_ha`, `mean_suit`, `max_suit` and `compactness` attributes. Threshold, minimum-area (ha) and top-N controls; 4/8 connectivity; deterministic ranking (mean suitability, area tie-break).
- Package diet: plugin icon optimized 46.5 KB -> 9 KB (visually identical 256-color quantization); dev-only files (`setup.cfg`, `.gitattributes`, internal benchmark doc) excluded from the Hub zip via `.zipignore`. Zip size 216 KB -> 189 KB.
- Tests: new `tests/test_site_logic.py` pure-logic harness (15 checks: labeling 4/8-connectivity, area filter, ranking, tie-breaks, determinism, empty-mask) plus a first end-to-end headless QGIS run validating the full algorithm against a synthetic raster (9 checks).
- Cleaned a stale duplicated `[Unreleased]` section in the changelog and refreshed the `metadata.txt` changelog summary.
- Registered the new module in the dashboard Compose group and Decision Ops governance set, README module catalog and the EN/TR command guide.

## [1.4.2] - 2026-06-02

- Restored QGIS 4 Processing provider registration so the dashboard and toolbox expose the full Suitability Lab algorithm catalog in QGIS 4.
- Restored Plugin Hub-safe `icons/icon.png` metadata wiring while keeping SVG fallback support for local Qt rendering.

## [1.4.1] - 2026-05-30

- Revised plugin icon to SVG

## [1.4.0] - 2026-05-29

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

## [1.3.7] - 2026-05-26

- Qt5/Qt6 compatibility maintenance, dashboard runtime hardening, and QGIS 4 processing-provider gate behavior.

## [1.3.6] - 2026-05-26

- Maintenance release: refreshed Plugin Hub package with QGIS 4 panel-only dashboard mode.

## [1.3.5] - 2026-05-26

- Keep QGIS 4 dashboard panel-only by hiding the Processing provider.

## [1.3.4] - 2026-05-26

- Fix QGIS 4 / Qt6 dashboard alignment enum compatibility.

All notable changes to **PlanX Suitability Lab** are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).
