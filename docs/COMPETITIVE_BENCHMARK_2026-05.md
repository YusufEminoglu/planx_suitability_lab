# PlanX Suitability Lab - Competitive Benchmark (2026-05-24)

## Why this matters
- This note maps current QGIS/Python MCDA capabilities so PlanX can target clear technical superiority.

## QGIS plugin landscape (official repository)
- **Easy AHP**: classic AHP + WLC workflow, long-running plugin line.  
  Source: <https://plugins.qgis.org/plugins/EasyAHP/>
- **SSAM**: sustainability-focused geographic MCDA plugin, active QGIS 4 line.  
  Source: <https://plugins.qgis.org/plugins/SSAM/>
- **Imagine Sustainability**: MCDA sustainability plugin based on `pyrepo-mcda`, active QGIS 4 line.  
  Source: <https://plugins.qgis.org/plugins/ImagineSustainability/>
- **MCDA search snapshot** shows mixed maturity (stable + experimental + deprecated ecosystem).  
  Source: <https://plugins.qgis.org/search/?q=mcda>

## Python MCDA ecosystem (PyPI)
- **pymcdm 1.4.0 (released Jan 31, 2026)**: broad MCDA library line, references AHP and many methods.  
  Source: <https://pypi.org/project/pymcdm/>
- **AHPy 2.1 (released Sep 18, 2025)**: dedicated AHP implementation.  
  Source: <https://pypi.org/project/AHPy/>
- **scikit-criteria 0.9 (released Aug 3, 2025)**: broad MCDA stack with multiple methods.  
  Source: <https://pypi.org/project/scikit-criteria/>
- **pyDecision (active 2026)**: very broad MCDA catalog including AHP/Fuzzy AHP and many ranking families.  
  Source: <https://pypi.org/project/pydecision/>
- **pyrepo-mcda docs**: exposes weighting/sensitivity and multiple MCDA utility modules.  
  Source: <https://pyrepo-mcda.readthedocs.io/en/latest/autoapi/pyrepo_mcda/index.html>

## Gaps PlanX must dominate
- Native QGIS **raster-first production pipeline** with chunk-safe processing and hard-constraint policy.
- **Cross-method weight reliability** (not only raw weights): consensus diagnostics and disagreement analytics.
- **Scenario ensemble intelligence**: not just one output map, but uncertainty/confidence-aware synthesis.
- **Operational UX**: studio dashboard, module readiness checks, rapid smoke pipeline, and audit-ready reports.

## Implemented in this cycle
- `critic_weights` (objective CRITIC weighting).
- `weight_consensus_audit` (method agreement diagnostics).
- `ensemble_suitability` (mean/std/p10/p90/confidence synthesis).
- Dashboard/readiness catalog + synthetic pipeline wiring updated accordingly.
- `opportunity_loss_map` (constraint-excluded potential diagnostics).
- `scenario_similarity_matrix` (cross-scenario agreement QA).
- `priority_zoning_from_suitability` (direct implementation zoning for planning action).
- `policy_sensitivity_frontier` (risk-aversion breakpoint analysis for policy choice).
- `action_playbook_generator` (decision-to-action bridge producing structured intervention playbooks).
- `intervention_budget_phasing` (budget-step impact capture planning layer).
- `release_narrative_builder` (evidence-driven release communication automation in English).
