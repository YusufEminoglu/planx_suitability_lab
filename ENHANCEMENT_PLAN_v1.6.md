# PlanX Suitability Lab — Enhancement Plan v1.6.0 ("English-Only, Documented, Hardened")

**Audience:** an external implementation agent (DeepSeek). Work through the phases IN ORDER.
**Repository:** `planx_suitability_lab/` inside the `qgis_plugins` monorepo.
**Current version:** 1.5.1 → **Target version:** 1.6.0 (single release at the end).
**Baseline facts (verified 2026-07-10):** 68 Processing algorithms across 6 groups (core 7, weights 7, compose 16, uncertainty 1, xai 3, reporting 34), `dashboard.py` = 1132 lines, `provider.py` registers all algorithms explicitly, tests = `tests/test_site_logic.py` (pure logic) + `tests/headless_integrity.py`.

---

## 0. Non-negotiable ground rules (read before touching anything)

1. **Read the monorepo docs first:** `qgis_plugins/AGENTS.md` and `qgis_plugins/RELEASING.md`. Their conventions (LICENSE present, `experimental=False`, release via `release.ps1`) are mandatory.
2. **No literal `%` in `metadata.txt`** — a bare `%` breaks the QGIS Hub upload (configparser interpolation). Reword any sentence that needs one, and `grep -n "%" metadata.txt` must return nothing before you finish.
3. **No self-praise wording** anywhere in user-facing copy: never write "elite", "best", "ultimate", "world-class". Show quality; don't claim it.
4. **No AI attribution:** never add `Co-Authored-By: Claude` (or DeepSeek, or any AI) trailers to commits.
5. **Never weaken an existing test or gate.** If a test asserts a count (e.g., algorithm count, distinct icons), the count may only go UP. If a test blocks you, fix the code, not the test. If you genuinely must change a test's expectation, document the exact reason in your report (Section R below) — silent loosening is grounds for rejecting the whole delivery.
6. **Security scan:** the QGIS Hub runs Bandit/detect-secrets/Flake8 and hard-blocks Critical findings (especially SHA-1/MD5 usage, B303/B324). Run `bandit -r . -x tests,__pycache__` before declaring done and report the output.
7. **New algorithm registration rule (also applies to renames):** every algorithm must be consistent across FOUR places — `provider.py`, `dashboard.py` (command palette/catalog), `README.md`, and `docs/COMMAND_GUIDE.html`. Any change to one must be mirrored in all four.
8. **Do not bump the version or write the changelog until Phase 6.** Do not release/tag/upload — the maintainer releases manually after review.
9. Work on the current branch; make small, well-scoped commits per phase with messages like `phase-1: remove TR language mode from dashboard`.

---

## Phase 1 — 100% English conversion (the headline requirement)

The plugin must become **entirely English**. The bilingual EN/TR machinery is to be REMOVED, not just defaulted.

### 1.1 `dashboard.py`
- Remove the language combo box (`lang_combo`, lines ~481–486), the `self.lang` setting (`planx_suitability_lab/lang`, line ~324), the `_set_language` slot (~line 895), and the Ctrl+L shortcut (~line 1130) plus its mentions in the shortcut help texts (~lines 933, 988).
- Remove every `if self.lang == ...` branch (~lines 801–809, 845, 961) keeping ONLY the English text. Delete the Turkish strings entirely, including ASCII-transliterated Turkish ("Yuklu katmanlar", "Sistem saglik skoru", "Turkce (Secondary)").
- After removal, `grep -in "lang\b\|Turkce\|TR mode" dashboard.py` should show no language-switch remnants (the word "lang" may survive only if used for something unrelated — justify any survivor in your report).

### 1.2 `processing/reporting/release_narrative_builder.py`
- This algorithm currently generates an EN **and** a TR narrative paragraph (Turkish text around lines 179–187). Remove the Turkish narrative entirely: outputs, parameters, field names, and help text become English-only. If the output table/HTML had an EN/TR pair, it now has a single English narrative.
- Update its entry in `docs/COMMAND_GUIDE.html` (currently says "auto-generates EN/TR ... narrative").

### 1.3 `docs/COMMAND_GUIDE.html`
- Title currently says "(EN/TR)" and there are `<b>TR:</b>` paragraphs (e.g., line ~20). Remove ALL Turkish paragraphs and the "(EN/TR)" tag. Remove the Ctrl+L row from the shortcuts table if present.

### 1.4 `README.md`
- Remove the "bilingual EN/TR dashboard mode with quick toggle" bullet (line ~103). Replace with an honest English-only feature bullet or drop it.
- The ecosystem-table mention of "Turkish master-plan automation" for the UIP Toolset (line ~131) describes ANOTHER plugin's domain and is in English — leave it.

### 1.5 Sweep the whole plugin
- Run these and fix every hit that is user-facing Turkish (code identifiers are fine only if not user-visible; prefer renaming even those):
  - `grep -rn "[çğıöşüÇĞİÖŞÜ]" --include="*.py" --include="*.html" --include="*.md" --include="*.txt" .` (exclude `__pycache__`)
  - `grep -rin "uygunluk\|katman\|agirlik\|senaryo\|belirsizlik\|olcut\|kriter\|politika\|rapor\|Turkce" --include="*.py" .` — audit every hit (many are transliterated Turkish that the character-class grep misses).
- `metadata.txt`, `CHANGELOG.md`, `CITATION.cff`: verify fully English (they appear to be — confirm and state so).

**Phase 1 exit criteria:** both greps clean (or every survivor justified), dashboard launches with no language UI, release_narrative_builder emits English only.

---

## Phase 2 — Documentation inside the Processing toolbox (biggest current shortcoming)

**Finding:** only 3 of 68 algorithms implement `shortHelpString()`; **zero** implement `helpUrl()`. In the QGIS Processing dialog, 65 algorithms show an empty help panel. This is the largest UX gap in the plugin.

### 2.1 `shortHelpString()` for ALL 68 algorithms
For every algorithm file under `processing/`, add a `shortHelpString()` returning English HTML/text with this exact structure:

```
<one-sentence purpose>

Inputs: <each parameter, one line, with expected range/units — e.g. "normalized 0–100 rasters">
Output: <what is produced, value range, nodata behavior>
Method: <2–4 sentences on the algorithm/math, naming the technique (WLC, OWA with order weights, TOPSIS closeness coefficient, VIKOR Q index, AHP with CR check, Monte Carlo perturbation, etc.)>
Typical use: <1–2 sentences, planning-oriented>
```

- The text must be **specific to each algorithm** — copy-pasted generic boilerplate across algorithms will be rejected. Read each `processAlgorithm` to describe what it actually does (e.g., mention the max-6-raster limit in WLC if it exists, the compactness metric in candidate_site_extractor, FDR/threshold parameters where present).
- Keep each help under ~150 words.

### 2.2 `helpUrl()`
- Add `helpUrl()` to a shared mixin or per-algorithm returning `https://github.com/YusufEminoglu/planx_suitability_lab` (repo root is acceptable; deep anchors optional).
- If you introduce a mixin/base class for this, it must not change any algorithm's `name()`, `displayName()`, `group()`, or parameter definitions.

### 2.3 Consistency audit while you're in every file
As you touch each of the 68 files, record in your report any of these defects (fix the trivial ones, list the risky ones):
- Missing or wrong `groupId()`/`group()` pairing.
- Parameter labels that are unclear, non-English, or missing units.
- Hardcoded temp paths, prints instead of `feedback.pushInfo`, bare `except:`.
- Divisions without zero-guards, nodata handled inconsistently (compare against `processing/_mcda_utils.py` helpers — algorithms that reimplement what `_mcda_utils` already provides should call the helper instead).

**Phase 2 exit criteria:** `grep -rln "shortHelpString" processing | wc -l` returns 68+ (every algorithm file); `grep -rln "helpUrl" processing` covers all algorithms; a table in your report lists every algorithm with a ✅ and any defect found.

---

## Phase 3 — Test expansion (current coverage is far too thin for 68 algorithms)

**Finding:** unit tests cover only candidate-site logic; `headless_integrity.py` is a shallow integrity check. There is no per-algorithm execution test.

### 3.1 Pure-logic unit tests (no QGIS required) — `tests/test_mcda_logic.py` (new)
Target the numerical cores that can be tested with numpy arrays alone. Minimum set (aim for ~60+ assertions total):
- `_mcda_utils.py`: every public helper — weight parsing (valid, malformed, wrong count, negative, non-normalized → renormalization behavior), list handling, output-path logic.
- Weighting math: AHP weight derivation + consistency ratio on a known 3×3 matrix with published result; entropy weights on a hand-computable 3-criterion table; CRITIC on the same; PCA weights sanity (sum to 1, non-negative handling as designed).
- Composition math: WLC on tiny 3×3 arrays with known weights → exact expected array; OWA ordering behavior (optimistic vs pessimistic order weights change the result in the correct direction); TOPSIS closeness ∈ [0,1] and rank order on a textbook example; VIKOR Q on the same example.
- Edge cases: all-nodata input, constant raster (zero variance — entropy/CRITIC must not divide by zero), single criterion, weights summing to ≠ 1.
- If the math lives inside `processAlgorithm` and can't be imported without QGIS, **refactor the numerical core into module-level pure functions** (e.g., `_compute(...)`) that `processAlgorithm` calls — behavior must be bit-identical; do not change any algorithm's outputs.

### 3.2 Real-QGIS end-to-end test — extend/replace `tests/headless_integrity.py` with `tests/e2e_qgis_full.py` (new)
- Pattern: script file executed via OSGeo4W `python-qgis-ltr.bat` (QGIS 3.44) and `python-qgis.bat` (QGIS 4). **Script files only — multiline `python -c` silently fails.** A working recipe exists at `qgis_plugins/scratch/suitlab_e2e_qgis.py`; study and extend it.
- The e2e must: initialize QGIS, register the provider, **assert the provider exposes exactly 68 algorithms** (pin the number — update the pin only when adding algorithms), then build a synthetic pipeline using the plugin's own `synthetic_sample_raster` / `synthetic_pipeline_runner` and execute a representative chain covering EVERY group: harmonize → normalize → constraint → each weighting algo → WLC + OWA + TOPSIS + VIKOR + ensemble → montecarlo → all 3 xai algos → at least 10 reporting algos including suitability_html_report and release_narrative_builder (verify its output is English-only programmatically: assert no Turkish substrings like "uygunluk", "agirlik", "belirsizlik" in the output).
- Every executed algorithm must be checked for: success flag, output exists, output value range sane (e.g., suitability ∈ [0,100], weights sum ≈ 1).
- Target: **every one of the 68 algorithms executed at least once** in e2e. If a few are genuinely impossible to drive synthetically, list them with reasons in the report — the accepted floor is 60/68 executed.
- If QGIS teardown segfaults after the run (known platform issue), end the harness with `os._exit(0)` after printing the PASS/FAIL summary — but only AFTER all assertions have run.

### 3.3 Dashboard smoke test
- Add a headless-safe check (inside e2e, guarded) that imports `dashboard.py`, instantiates the widget class without showing it, and asserts (a) no `lang` attribute/setting remains, (b) the command catalog lists 68 entries matching the provider.

**Phase 3 exit criteria:** unit tests pass with plain `python -m pytest tests/test_mcda_logic.py -q`; e2e passes on BOTH QGIS 3.44 and 4.x with the 68-pin intact; full console output of all three runs pasted in the report.

---

## Phase 4 — Dashboard quality pass

`dashboard.py` is a 1132-line monolith and the plugin's storefront.

- After the Phase-1 language removal, do a cleanup pass: dead code, unused imports, duplicated HTML fragments.
- Verify the command palette (Ctrl+K) catalog matches the provider's 68 algorithms exactly — add a private `_catalog_matches_provider()` used by the Phase-3.3 smoke test.
- All dashboard copy proof-read as natural English (it currently contains ASCII-transliterated Turkish remnants in some labels — Phase 1 grep should have caught these; double-check headings, tooltips, popup texts, the diagnostics/issue templates).
- Qt6/QGIS-4 compatibility: no `QAction` imported from `QtWidgets` (must be QtGui-compatible pattern used elsewhere in the ecosystem), no deprecated `exec_()`, enum access via fully-qualified `Qt.AlignmentFlag...` style (already partially done — make it consistent).
- Do NOT redesign the UI or add new panels/settings. Smarter defaults over new knobs.

**Phase 4 exit criteria:** dashboard opens in both QGIS 3.44 and 4.x without console warnings from this plugin; catalog-vs-provider assertion passes.

---

## Phase 5 — Docs & metadata truthfulness pass

- `README.md`: update feature list to reflect Phase 1 (English-only) and Phase 2 (in-toolbox help for all algorithms); verify the stated algorithm count says **68** everywhere it appears; keep tone factual (rule 3).
- `docs/COMMAND_GUIDE.html`: after Phase 1 stripping, ensure every one of the 68 commands still has an entry; add the ~1-line purpose from each new `shortHelpString` so the guide and toolbox help agree.
- `metadata.txt`: description/about proof-read; tags still accurate; **no `%`** (rule 2); `experimental=False` intact.
- `CHANGELOG.md`: add the 1.6.0 section LAST (in Phase 6), covering: English-only conversion, help strings for all 68 algorithms, new unit + full e2e test suites, dashboard cleanup. English, factual, no superlatives.

---

## Phase 6 — Version bump & final gate (do this only when Phases 1–5 are green)

1. Bump `metadata.txt` version to `1.6.0` and add the changelog entry there too (English, no `%`).
2. Run the FULL gate and paste all outputs in the report:
   - `python -m pytest tests/ -q` (pure logic)
   - e2e script on QGIS 3.44 (`python-qgis-ltr.bat`) — full output
   - e2e script on QGIS 4.x (`python-qgis.bat`) — full output
   - `bandit -r . -x tests,__pycache__` — must show no Critical findings
   - `python -m flake8 --max-line-length=140 --extend-ignore=E203,W503 .` (or the monorepo's configured lint) — report count; fix what you introduced
   - `grep -rn "[çğıöşüÇĞİÖŞÜ]"` and the transliterated-Turkish grep from 1.5 — clean
   - `grep -n "%" metadata.txt` — empty
3. Commit; **do not tag, do not run release.ps1, do not upload** — the maintainer does the release after reviewing your report.

---

## Known shortcomings register (fix or explicitly defer with reason)

| # | Shortcoming | Severity | Phase |
|---|---|---|---|
| S1 | 65/68 algorithms have no `shortHelpString`; 68/68 lack `helpUrl` | High | 2 |
| S2 | Bilingual EN/TR machinery contradicts English-only requirement (dashboard, release_narrative_builder, COMMAND_GUIDE, README) | High | 1 |
| S3 | No per-algorithm execution tests; unit tests cover 1 of 68 algorithms | High | 3 |
| S4 | Numerical cores embedded in `processAlgorithm` → untestable without QGIS | Medium | 3.1 |
| S5 | `dashboard.py` monolith with transliterated-Turkish remnants and possible dead code | Medium | 1, 4 |
| S6 | No programmatic guarantee dashboard catalog == provider registration | Medium | 3.3, 4 |
| S7 | `docs/COMMAND_GUIDE.html` partially bilingual and may lag current algorithm set | Medium | 1.3, 5 |
| S8 | No algorithm-count pin in e2e (regression risk when editing provider.py) | Medium | 3.2 |
| S9 | Potential zero-division/constant-raster edge cases in entropy/CRITIC/normalizer (unverified) | Medium | 3.1 |
| S10 | WLC hard "max 6 rasters" label — verify whether limit is enforced/needed; document it in help either way | Low | 2 |

---

## R. Required response format (your report back to the reviewer)

Deliver a single file `REPORT_v1.6.md` in the plugin root, structured EXACTLY like this — the reviewer will machine-check parts of it:

```markdown
# Implementation Report v1.6.0
## 1. Phase status
Phase 1: DONE|PARTIAL — <one line>
... (all 6 phases)
## 2. Shortcomings register outcomes
S1: FIXED|DEFERRED — <evidence: file/grep/test>
... (S1–S10, plus any NEW shortcomings you discovered, numbered S11+)
## 3. Algorithm help table
| algorithm id | shortHelpString | helpUrl | defects found | defects fixed |
(68 rows, one per algorithm)
## 4. Test evidence
### 4.1 pytest output (verbatim, complete)
### 4.2 e2e QGIS 3.44 output (verbatim, complete)
### 4.3 e2e QGIS 4.x output (verbatim, complete)
### 4.4 executed-algorithm coverage: N/68, list of any not executed + reason
## 5. Gate outputs
bandit / flake8 / Turkish greps / metadata % grep (verbatim)
## 6. Changed-test justifications
(empty if none; otherwise every test whose expectation changed, old vs new, why)
## 7. Deviations from this plan
(every place you did something differently and why)
## 8. Commit list
(hash + message, one per line)
```

**Honesty over completeness:** a PARTIAL with truthful evidence is acceptable; a DONE that the reviewer's re-run contradicts invalidates the delivery.
