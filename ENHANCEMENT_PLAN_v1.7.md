# PlanX Suitability Lab — Enhancement Plan v1.7.0 (Real E2E Coverage + Weight Sensitivity)

**Audience:** an external implementation agent. Work through the phases IN ORDER.
**Repository:** `planx_suitability_lab/` inside the `qgis_plugins` monorepo.
**Current version:** 1.6.8 → **Target version:** 1.7.0 (single release at the end).
**Baseline facts (verified against the current tree, not `ENHANCEMENT_PLAN_v1.6.md`'s
already-completed English-only/hardening scope):** 68 Processing algorithms
across 6 groups (Core 7, Weights 7, Compose 16, Uncertainty 1, XAI 3,
Reporting 34, per `REPORT_v1.6.md`'s own count). The Dashboard's 5-tab GUI
(Model Flow/Overview/Modules/Recent Runs/System Health) is documented as of
this session's Track A pass — not this plan's concern.

**One paragraph:** Two independent workstreams. First, a genuine, previously
admitted gap: `REPORT_v1.6.md` states the e2e harness (`tests/e2e_qgis_full.py`)
only actually executes **9 of 68** algorithms end-to-end — most
`processing.run()` calls fail with "Unable to execute algorithm," hypothesised
(not confirmed) to be a raster-parameter-passing issue. A test suite that
silently exercises 13% of what it claims to cover is close to the "tests that
cannot fail" failure mode this project explicitly watches for — Phase 1
investigates the real cause and drives coverage up with verified evidence,
not a second guess. Second, a real algorithmic gap: the sole existing
uncertainty tool (`Uncertainty: Monte Carlo Suitability`) perturbs the
*output* score with Gaussian noise: it answers "how noisy is my result,"
never "which criterion's weight actually drives the result" — a distinct,
well-established MCDA technique (one-at-a-time weight sensitivity) that
this plugin, despite seven dedicated Weights algorithms, does not offer.

---

## 0. Non-negotiable ground rules (read before touching anything)

1. **Read the monorepo docs first:** `qgis_plugins/AGENTS.md` and
   `qgis_plugins/RELEASING.md`. LICENSE present, `experimental=False`,
   release via `release.ps1` are mandatory conventions.
2. **No literal `%` in `metadata.txt`** — `grep -n "%" metadata.txt` must
   return nothing before you finish.
3. **No self-praise wording** anywhere in user-facing copy: never "elite",
   "best", "ultimate", "world-class." (Ground truth: `REPORT_v1.6.md`
   §7.4 records that the *previous* plan itself had to remove a literal
   "ELITE" tier label found mid-implementation — check for recurrences,
   don't assume the sweep was exhaustive.)
4. **No AI attribution:** never add `Co-Authored-By:` (or any AI) trailers
   to commits.
5. **Never weaken an existing test or gate.** The 68-algorithm provider
   count pin may only go up (to 69, once the new algorithm lands). If a
   test blocks you, fix the code, not the test.
6. **New algorithm registration rule (also applies to renames):** every
   algorithm must stay consistent across the same FOUR places the last plan
   established: `provider.py`, `dashboard.py` (command palette/catalog —
   `REPORT_v1.6.md` §7.6 records a real bug where a shipped algorithm was
   registered in the provider but missing from the dashboard catalog; verify
   the new algorithm lands in both), `README.md`, and
   `docs/COMMAND_GUIDE.html`.
7. **Security scan:** run `bandit -r . -x tests,__pycache__`. Use `-f csv`
   or `-f json` output — `REPORT_v1.6.md` §7 does not record this Bandit
   Windows-terminal Unicode crash for this plugin, but it is a documented
   issue in the sibling `planx_urban_resilience` plugin; check before
   assuming the default text formatter is safe here too.
8. **Do not bump the version or write the changelog until Phase 3. Do not
   release/tag/upload** — the maintainer releases manually after review.
9. Work on the current branch; small, well-scoped commits per phase, e.g.
   `phase-1: fix e2e raster parameter passing, verify real execution count`.

---

## Phase 1 — Make the e2e harness actually execute what it claims to

**What.** `REPORT_v1.6.md`'s own §7.2 admits real coverage is 9/68, not the
claimed target, with an unconfirmed hypothesis about
`QgsProcessingParameterRasterLayer` needing a `QgsRasterLayer` object
rather than a file-path string. **Confirm or refute that hypothesis first**
by running one failing algorithm manually with both a string path and an
explicit `QgsRasterLayer(path, name)` object and comparing the actual
exception — do not assume the old report's guess was correct and build on
top of an unverified premise.

Once the real cause is confirmed, fix `tests/e2e_qgis_full.py` systematically
— not by patching each of the ~59 uncovered calls ad hoc, but by adding a
small helper (e.g. `_raster_param(path)`) that produces whatever input shape
`processing.run()` actually needs for a raster parameter in this QGIS
version, used consistently everywhere the harness currently passes a bare
path string. Apply the same scrutiny to vector inputs and any other
parameter type the harness constructs, in case the raster issue is one
instance of a broader pattern rather than the only one.

**Target:** report the real before/after execution count for all 68
algorithms — this plan does not pre-commit to a specific number (68/68 may
not be reachable if some algorithms have parameter combinations that are
inherently untestable without real project data), but the report must state
the honest final count and, for every algorithm still not executed, the
specific reason why, not a generic "skipped."

---

## Phase 2 — One-at-a-Time Weight Sensitivity Analysis

**What.** A new algorithm, `processing/uncertainty/weight_sensitivity.py`
(`name()`: `weight_sensitivity_oat`, `displayName()`:
`"Uncertainty: One-at-a-Time Weight Sensitivity"`), grouped with the
existing `Uncertainty: Monte Carlo Suitability` tool. Given the same
weighted-composite inputs a WLC/OWA run would take (criterion rasters +
their base weights), perturb **one weight at a time** by a configurable
percentage (default ±20%, renormalising the remaining weights
proportionally so they still sum to 1.0 — state the renormalisation rule
explicitly in the help text, since it materially affects the result and a
silent choice here would be exactly the kind of undocumented behavior this
project's own conventions warn against), recompute the composite suitability
raster for each perturbed case, and output:
- a per-criterion **sensitivity ranking** (e.g., mean absolute change in the
  composite score, or a rank-correlation measure against the baseline —
  pick one well-established, cite it, and justify the choice in the manual's
  Mathematical Formulation section rather than presenting an ad hoc metric
  as if it were standard),
- an optional raster stack or table of the perturbed outputs for a chosen
  criterion, so a user can see *where* on the map that criterion's weight
  matters most, not just a single scalar sensitivity score.

**Design notes.**
- Reuse the existing composite-scoring code path (WLC's own weighted-sum
  computation) rather than reimplementing it — check whether it is
  factored into a callable function or embedded directly in
  `processAlgorithm`; `REPORT_v1.6.md`'s own shortcomings register (S4)
  notes the compose algorithms' numerical cores were *not* refactored out
  of `processAlgorithm` in the last plan specifically because doing so
  risked changing outputs without bit-identical verification — if that is
  still true, do not silently refactor it as a side effect of this phase;
  either verify bit-identical output before reuse, or duplicate the
  computation deliberately and say so in the report.
- This is genuinely different from the existing Monte Carlo tool: Monte
  Carlo answers "how much does random noise change my result"; this
  answers "how much does *my own uncertainty about the right weights*
  change my result" — make sure the manual's "When to use vs. the Monte
  Carlo tool" framing states this distinction clearly, matching the
  cross-referencing convention already used elsewhere in this plugin's
  docs (e.g. the Dashboard's Model Flow descriptions).

---

## Phase 3 — Documentation, registration, version bump

Only after Phases 1–2 are done and tested:
- Register the new algorithm across all four required places (ground rule 6).
- Write its `shortHelpString()`/`helpUrl()` and manual entry to the same
  standard the last plan established for the other 68 (the last plan's
  Phase 2 added `shortHelpString`/`helpUrl` to all 68 algorithms — match
  that bar, don't regress it for the one new addition).
- Update `README.md`'s algorithm count (68 → 69) and `docs/COMMAND_GUIDE.html`.
- Update `CHANGELOG.md` with a new `## [1.7.0]` entry documenting both the
  real e2e-coverage fix (with the honest before/after numbers from Phase 1)
  and the new algorithm.
- Bump `metadata.txt`'s `version=1.7.0`; confirm the `%` gate is clean.
- Do **not** tag, run `release.ps1`, or upload.

---

## Known shortcomings register (fix or explicitly defer with reason)

| # | Shortcoming | Severity | Phase |
|---|---|---|---|
| S1 | Root cause of the e2e raster-parameter failure is unconfirmed in the prior report ("Investigation indicates...") — must be verified before building a fix on top of it | High | 1 |
| S2 | Renormalisation rule for the untouched weights in weight-sensitivity perturbation must be explicit and documented, not an implicit default | Medium | 2 |
| S3 | Reuse vs. duplication of the WLC composite-scoring core, given the prior plan's explicit S4 deferral of refactoring it — verify bit-identical output before reusing, or duplicate deliberately | Medium | 2 |
| S4 | Carried from `REPORT_v1.6.md` S4: numerical cores for compose algorithms (WLC/OWA/TOPSIS/VIKOR) remain embedded in `processAlgorithm` — still not addressed by this plan; re-defer explicitly rather than silently dropping it a second time | Low | — |
| S5 | Carried from `REPORT_v1.6.md` S8: full e2e coverage was already a known partial item before this plan — Phase 1 is this plan's attempt to close it; if it cannot reach 68/68, the report must say exactly which algorithms remain untested and why, not round up | High | 1 |

---

## R. Required response format

Deliver a single file `REPORT_v1.7.md` in the plugin root:

```markdown
# Implementation Report v1.7.0
## 1. Phase status
Phase 1: DONE|PARTIAL — <one line, with the real X/68 execution count>
Phase 2: DONE|PARTIAL — <one line>
Phase 3: DONE|PARTIAL — <one line>
## 2. Shortcomings register outcomes
S1–S5, plus any NEW shortcomings discovered, numbered S6+
## 3. E2E coverage table
| algorithm id | executed before | executed after | reason if still not executed |
(68 rows)
## 4. New algorithm summary
name/displayName/inputs/outputs/sensitivity metric used + citation
## 5. Test evidence
### 5.1 pure test output (verbatim, complete)
### 5.2 e2e QGIS 3.44 LTR output (verbatim, complete)
### 5.3 e2e QGIS 4.x output (verbatim, complete)
## 6. Gate outputs
bandit / `%`-in-metadata grep (verbatim)
## 7. Deviations from this plan
## 8. Commit list
(hash + message, one per line)
```

**Honesty over completeness:** a PARTIAL with truthful evidence is
acceptable; a DONE that the reviewer's re-run contradicts invalidates the
delivery. Rounding the Phase 1 coverage number up is exactly the kind of
misrepresentation this plan exists to correct — do not repeat it.
