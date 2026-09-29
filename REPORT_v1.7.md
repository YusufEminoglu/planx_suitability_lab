# Implementation Report v1.7.0

Delivers `ENHANCEMENT_PLAN_v1.7.md` plus the defects a correctness audit of
the MCDA cores found on the way. Committed locally; not tagged or uploaded.

## 1. Phase status

- Phase 1: DONE (already, before this pass). The plan's premise was stale: the
  e2e had reached 68/68 executed in July 2026. It now executes **69/69** on
  QGIS 3.44 and 4.2. The real coverage gap was elsewhere. The harness *ran*
  Constraint Builder but never read its output, which was nodata everywhere
  on Windows (S6). Two GDAL-dependent test files were registered as
  pure-Python and failed the gate (S7).
- Phase 2: DONE: `weight_sensitivity_oat`, see section 4.
- Phase 3: DONE: provider, dashboard catalog and governance group, README,
  COMMAND_GUIDE, manual section 4.2, counts 68 to 69, CHANGELOG, metadata
  1.7.0, CITATION.

## 2. Shortcomings register

| # | Outcome |
|---|---|
| S1 | Resolved in July: the old "raster parameter" hypothesis was wrong (invented parameter keys). No further action. |
| S2 | The renormalisation rule is stated in the help text and in manual Eq. (44a): `w_j' = w_j (1 - w_i')/(1 - w_i)`. |
| S3 | Reuse, verified: `_mcda_utils.wlc_score` is a new function. The e2e checks that the WLC tool's output raster equals it (atol 1e-4), so the sensitivity tool perturbs the model WLC publishes. WLC's own `processAlgorithm` was not refactored. |
| S4 | Re-deferred explicitly: the compose cores (OWA/TOPSIS/VIKOR) remain in `processAlgorithm`. The audit read them and found the maths correct (Jiang and Eastman OWA, standard TOPSIS, Opricovic and Tzeng VIKOR). |
| S5 | 69/69 executed. The coverage number was not the problem; the unread outputs were (S6). |
| S6 | New: Constraint Builder produced an all-nodata mask on Windows (`>` in a gdal_calc formula became a shell redirect) while reporting success. Fixed with GDAL/numpy. The e2e now reads the mask; against the old code it fails. |
| S7 | New: `test_mcda_logic.py` and `test_site_logic.py` need GDAL but were registered as pure tests; `pf verify` failed on a clean tree. They are now in `tests_qgis` (both runtimes). |
| S8 | New: 18 algorithms dropped inputs past a fixed cap without a word. They now refuse, naming the limit. |
| S9 | New: AHP accepted non-reciprocal matrices. Now validated. |
| S10 | New: float outputs of five compose tools borrowed the first input's nodata (often 0), erasing real zero scores. Outputs now use -9999. |
| S11 | New: outputs loaded unstyled. Scores now load with a fixed 0-100 ramp and masks with two classes, via a layer post-processor (rasters are files, so styling during the run cannot reach them). |
| S12 | Open: Monte Carlo's outputs follow from the input score and sigma alone. Its help text and the manual now say so and point to OAT; the method itself is unchanged. |
| S13 | Open: `xai_global_sensitivity` is a weight x spread proxy, not a variance-based global analysis. Its help already says "proxy"; unchanged. |

## 3. E2E coverage

69/69 algorithms executed on both runtimes (`Executed: 69/69 algorithms`).
New value checks on top of execution: the constraint mask matches the
threshold, WLC output equals `wlc_score`, OAT mean-absolute-change and change
raster match numpy, and styled outputs carry their renderer when loaded.

## 4. New algorithm

`weight_sensitivity_oat` / "Uncertainty: One-at-a-Time Weight Sensitivity".
Inputs: 2-12 criterion rasters (0-100), weights CSV, perturbation % (default
20), change threshold (default 5 points), optional constraint, optional focus
criterion. Outputs: a ranked table (weight, weight_up, weight_down, mac_up,
mac_down, mac, max_abs_change, share_changed_pct, rank) and an optional change
raster. Metric: mean absolute change of the composite per perturbed weight,
following Chen, Y., Yu, J. and Khan, S. (2010), Environmental Modelling and
Software 25(12): 1582-1591, doi:10.1016/j.envsoft.2010.06.001 (DOI checked
against Crossref).

## 5. Test evidence

- Pure (plain python): `headless_integrity.py` PASS.
- QGIS 3.44 and 4.2: `test_mcda_logic.py` 18 functions passed, including the
  AHP textbook CR 0.0332, the reciprocity refusal, the cap refusal, the OAT
  renormalisation and the exact identity dS = d(x1 - x2). `test_site_logic.py`:
  15 checks. `e2e_qgis_full.py`: PASS, 69/69.
- Mutation checks: the reciprocity, cap and constraint-mask tests fail against
  the previous code.

## 6. Gates

`pf verify planx_suitability_lab`: validate 0 warnings, Hub security scan
CLEAN, Qt6 no errors, all suites green on both runtimes. No `%` in metadata.
