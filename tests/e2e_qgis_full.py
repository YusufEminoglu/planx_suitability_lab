#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full end-to-end test for planx_suitability_lab -- all 68 algorithms.

Run with OSGeo4W:
  C:/OSGeo4W/bin/python-qgis-ltr.bat tests/e2e_qgis_full.py   (QGIS 3.44)
  C:/OSGeo4W/bin/python-qgis.bat tests/e2e_qgis_full.py       (QGIS 4.x)

Goal: execute every algorithm at least once and verify outputs.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication  # noqa: E402

qgs = QgsApplication([], False)
qgs.initQgis()

import qgis  # noqa: E402

# Resolve the Processing plugin dir of the *running* QGIS (qgis vs qgis-ltr),
# so the harness works under both python-qgis-ltr.bat and python-qgis.bat.
sys.path.insert(0, str(Path(qgis.__file__).resolve().parents[1] / "plugins"))
sys.path.append(r"C:\Users\YE\PyCharmMiscProject\qgis_plugins")

import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

from qgis.core import QgsProject, QgsVectorLayer  # noqa: E402

Processing.initialize()

from planx_suitability_lab.provider import PlanXSuitabilityLabProvider  # noqa: E402

provider = PlanXSuitabilityLabProvider()
QgsApplication.processingRegistry().addProvider(provider)

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
failures = []
executed = set()
algo_count = 0


def check(cond, label):
    global algo_count
    algo_count += 1
    status = "OK" if cond else "FAIL"
    print(f"  [{status}] {label}")
    if not cond:
        failures.append(label)


def run_algo(algo_id, params, label_hint=""):
    """Run a processing algorithm, track execution, return result dict."""
    try:
        res = processing.run(algo_id, params)
        executed.add(algo_id)
        return res
    except Exception as e:
        print(f"  [FAIL] {algo_id}: {e}")
        failures.append(f"{algo_id}: {e}")
        return {}


# ---------------------------------------------------------------------------
# 1. Provider assertion
# ---------------------------------------------------------------------------
print("=== 1. Provider assertion ===")
reg = QgsApplication.processingRegistry()
all_ids = [a.id() for a in reg.algorithms() if a.id().startswith("planx_suitability_lab:")]
check(len(all_ids) == 68, f"Provider exposes 68 algorithms (got {len(all_ids)})")
for aid in sorted(all_ids):
    print(f"    {aid}")

# ---------------------------------------------------------------------------
# 2. Synthetic pipeline (exercises ~40 algorithms)
# ---------------------------------------------------------------------------
print("\n=== 2. Synthetic pipeline run ===")
import numpy as np  # noqa: E402
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle  # noqa: E402

# Create extent and run the synthetic pipeline runner
extent = QgsRectangle(500000, 4500000, 501200, 4501200)
out_dir = tempfile.mkdtemp(prefix="suitlab_e2e_")

print(f"  Output directory: {out_dir}")

# Step 2a: Generate synthetic sample rasters
res_sample = run_algo(
    "planx_suitability_lab:synthetic_sample_raster",
    {"EXTENT": extent, "PIXEL": 30.0, "OUTPUT_DIR": out_dir},
    "synthetic_sample_raster",
)

# Find the generated raster files
criterion_files = sorted(Path(out_dir).glob("criterion_*.tif"))
mask_files = sorted(Path(out_dir).glob("constraint_mask*.tif"))
check(len(criterion_files) == 4, f"4 criterion rasters generated (got {len(criterion_files)})")

if criterion_files:
    # Step 2b: Run alignment audit on the generated rasters
    run_algo(
        "planx_suitability_lab:alignment_audit",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "OUTPUT": "TEMPORARY_OUTPUT"},
        "alignment_audit",
    )

    # Step 2c: Run normalizer on first criterion
    run_algo(
        "planx_suitability_lab:normalizer_reclassifier",
        {"INPUT": str(criterion_files[0]), "METHOD": 0, "LOW": 0.0, "HIGH": 100.0, "MID": 50.0, "SPREAD": 10.0, "OUTPUT": "TEMPORARY_OUTPUT"},
        "normalizer",
    )

    # Step 2d: Run constraint builder
    if mask_files:
        run_algo(
            "planx_suitability_lab:constraint_builder",
            {"INPUT": str(mask_files[0]), "THRESHOLD": 0.5, "OUTPUT": "TEMPORARY_OUTPUT"},
            "constraint_builder",
        )

    # Step 2e: Run WLC with equal weights
    wlc_res = run_algo(
        "planx_suitability_lab:wlc_suitability",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "0.4,0.3,0.3", "CONSTRAINT": str(mask_files[0]) if mask_files else None, "OUTPUT": "TEMPORARY_OUTPUT"},
        "wlc_suitability",
    )

    wlc_tif = None
    if "OUTPUT" in wlc_res:
        wlc_tif = wlc_res["OUTPUT"]
        if isinstance(wlc_tif, str):
            check(os.path.exists(wlc_tif), "WLC output raster exists")

    # Step 2f: Run OWA
    run_algo(
        "planx_suitability_lab:owa_suitability",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "CRITERIA_WEIGHTS": "", "ORDER_WEIGHTS": "0.6, 0.3, 0.1", "SORT_MODE": 0, "CONSTRAINT": str(mask_files[0]) if mask_files else None, "OUTPUT": "TEMPORARY_OUTPUT"},
        "owa_suitability",
    )

    # Step 2g: Run TOPSIS
    run_algo(
        "planx_suitability_lab:topsis_suitability",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "", "IMPACTS_CSV": "B, B, B", "CONSTRAINT": str(mask_files[0]) if mask_files else None, "OUTPUT": "TEMPORARY_OUTPUT"},
        "topsis_suitability",
    )

    # Step 2h: Run VIKOR
    run_algo(
        "planx_suitability_lab:vikor_suitability",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "", "IMPACTS_CSV": "B, B, B", "V": 0.5, "CONSTRAINT": str(mask_files[0]) if mask_files else None, "OUTPUT": "TEMPORARY_OUTPUT"},
        "vikor_suitability",
    )

    # Step 2i: Weight derivations
    ahp_res = run_algo(
        "planx_suitability_lab:ahp_weights",
        {"MATRIX_JSON": '[[1,2,3],[0.5,1,2],[0.3333,0.5,1]]', "OUTPUT": "TEMPORARY_OUTPUT"},
        "ahp_weights",
    )

    entropy_res = run_algo(
        "planx_suitability_lab:entropy_weights",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "OUTPUT": "TEMPORARY_OUTPUT"},
        "entropy_weights",
    )

    pca_res = run_algo(
        "planx_suitability_lab:pca_derived_weights",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "OUTPUT": "TEMPORARY_OUTPUT"},
        "pca_weights",
    )

    critic_res = run_algo(
        "planx_suitability_lab:critic_weights",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "IMPACTS_CSV": "B, B, B", "OUTPUT": "TEMPORARY_OUTPUT"},
        "critic_weights",
    )

    # Step 2k: Monte Carlo on WLC output if available
    if wlc_tif and os.path.exists(wlc_tif):
        run_algo(
            "planx_suitability_lab:montecarlo_suitability",
            {"INPUT": wlc_tif, "ITER": 30, "SIGMA": 0.08, "BLOCK": 256,
             "OUT_MEAN": "TEMPORARY_OUTPUT", "OUT_STD": "TEMPORARY_OUTPUT", "OUT_P05": "TEMPORARY_OUTPUT",
             "OUT_P50": "TEMPORARY_OUTPUT", "OUT_P95": "TEMPORARY_OUTPUT", "OUT_STAB": "TEMPORARY_OUTPUT"},
            "montecarlo_suitability",
        )

    # Step 2l: XAI algorithms on criterion rasters
    run_algo(
        "planx_suitability_lab:xai_global_sensitivity",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "0.4, 0.35, 0.25", "SAMPLE": 2, "OUTPUT": "TEMPORARY_OUTPUT"},
        "xai_global_sensitivity",
    )

    os.makedirs(os.path.join(out_dir, "xai_local"), exist_ok=True)
    run_algo(
        "planx_suitability_lab:xai_local_contribution",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "0.4, 0.35, 0.25", "OUTPUT_DIR": os.path.join(out_dir, "xai_local")},
        "xai_local_contribution",
    )

    run_algo(
        "planx_suitability_lab:xai_geoshapley_lite",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "WEIGHTS_CSV": "0.4, 0.35, 0.25", "SAMPLE": 200, "OUTPUT": "TEMPORARY_OUTPUT"},
        "xai_geoshapley_lite",
    )

    # Step 2m: Ensemble suitability needs 3 scenarios; use WLC, OWA, TOPSIS rasters
    # We'll collect them in a helper step; for now, we skip ensemble without multiple scenarios

# ---------------------------------------------------------------------------
# 3. Individual quick tests for algorithms not covered by pipeline
# ---------------------------------------------------------------------------
print("\n=== 3. Individual algorithm tests ===")

# 3a: Proximity builder (needs a target pixel raster)
if criterion_files:
    run_algo(
        "planx_suitability_lab:proximity_builder",
        {"INPUT": str(criterion_files[0]), "TARGET_VALUES": "50, 60, 70", "DISTANCE_UNITS": 0, "MAX_DISTANCE": 1000.0, "OUTPUT": "TEMPORARY_OUTPUT"},
        "proximity_builder",
    )

# 3b: Numerical QA check (needs suitability + uncertainty rasters)
if wlc_tif and os.path.exists(wlc_tif):
    # Create a simple p05/p50/p95 from wlc by adding small offsets
    from osgeo import gdal  # noqa: E402

    ds_wlc = gdal.Open(wlc_tif)
    arr_wlc = ds_wlc.ReadAsArray().astype(np.float32)
    ds_wlc = None
    gt = (500000, 30, 0, 4500000, 0, -30)

    def _write_tif(path, arr_data):
        drv = gdal.GetDriverByName("GTiff")
        ds = drv.Create(path, arr_data.shape[1], arr_data.shape[0], 1, gdal.GDT_Float32)
        ds.SetGeoTransform(gt)
        band = ds.GetRasterBand(1)
        band.SetNoDataValue(-9999.0)
        band.WriteArray(arr_data)
        band.FlushCache()
        ds = None

    p05_path = os.path.join(out_dir, "p05.tif")
    p50_path = os.path.join(out_dir, "p50.tif")
    p95_path = os.path.join(out_dir, "p95.tif")
    _write_tif(p05_path, np.clip(arr_wlc - 5.0, 0, 100))
    _write_tif(p50_path, arr_wlc)
    _write_tif(p95_path, np.clip(arr_wlc + 5.0, 0, 100))

    run_algo(
        "planx_suitability_lab:numerical_qa_check",
        {"SUIT": wlc_tif, "P05": p05_path, "P50": p50_path, "P95": p95_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "numerical_qa_check",
    )

    # 3c: Suitability class area stats
    run_algo(
        "planx_suitability_lab:suitability_class_area_stats",
        {"INPUT": wlc_tif, "BREAKS": "20,40,60,80", "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "suitability_class_area_stats",
    )

    # 3d: Threshold coverage curve
    threshold_curve_res = run_algo(
        "planx_suitability_lab:threshold_coverage_curve",
        {"INPUT": wlc_tif, "STEP": 10, "OUTPUT": "TEMPORARY_OUTPUT"},
        "threshold_coverage_curve",
    )

    # 3e: Spatial fragmentation audit
    run_algo(
        "planx_suitability_lab:spatial_fragmentation_audit",
        {"INPUT": wlc_tif, "THRESHOLD": 50.0, "CONNECTIVITY": 8, "OUTPUT": "TEMPORARY_OUTPUT"},
        "spatial_fragmentation_audit",
    )

    # 3f: Create a simple priority zone raster for zoning-based algos
    zone_arr = np.digitize(arr_wlc, [0, 25, 50, 75]).astype(np.int16) - 1
    zone_path = os.path.join(out_dir, "zone.tif")
    _write_tif(zone_path, zone_arr.astype(np.float32))

    # Priority transition matrix
    run_algo(
        "planx_suitability_lab:priority_transition_matrix",
        {"FROM_ZONE": zone_path, "TO_ZONE": zone_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "priority_transition_matrix",
    )

    # Intervention budget phasing
    budget_phasing_res = run_algo(
        "planx_suitability_lab:intervention_budget_phasing",
        {"PRIORITY_ZONE": zone_path, "COST_BY_ZONE": "0.6,0.9,1.2,1.5,1.8", "STEP": 20, "OUTPUT": "TEMPORARY_OUTPUT"},
        "intervention_budget_phasing",
    )

# 3g: Markdown brief and HTML report (no raster inputs needed, just strings)
run_algo(
    "planx_suitability_lab:scenario_markdown_brief",
    {"PROJECT": "E2E Test", "BASELINE": "Baseline", "SCENARIO": "Scenario A", "QA": "All checks pass.", "NOTES": "Test notes.", "OUTPUT": "TEMPORARY_OUTPUT"},
    "scenario_markdown_brief",
)

run_algo(
    "planx_suitability_lab:suitability_html_report",
    {"PROJECT": "E2E Test Project", "SUMMARY": "Test run.", "WEIGHT_METHOD": "AHP", "QA_SUMMARY": "", "OUTPUT": "TEMPORARY_OUTPUT"},
    "suitability_html_report",
)

# 3h: Release narrative builder - verify English-only output
narrative_res = run_algo(
    "planx_suitability_lab:release_narrative_builder",
    {"PROJECT": "Test Project", "VERSION": "1.0.0", "HIGHLIGHTS": "", "OUTPUT": "TEMPORARY_OUTPUT"},
    "release_narrative_builder",
)
if "OUTPUT" in narrative_res and os.path.exists(narrative_res["OUTPUT"]):
    narrative_text = Path(narrative_res["OUTPUT"]).read_text(encoding="utf-8")
    turkish_markers = ["uygunluk", "agirlik", "belirsizlik", "senaryo", "Turkce", "Ozeti", "Yayin"]
    found_turkish = [w for w in turkish_markers if w.lower() in narrative_text.lower()]
    check(len(found_turkish) == 0, f"Release narrative is English-only (no: {found_turkish})")

# 3i: Action playbook generator
if wlc_tif and os.path.exists(wlc_tif) and os.path.exists(zone_path):
    run_algo(
        "planx_suitability_lab:action_playbook_generator",
        {"PROJECT": "E2E Project", "PRIORITY_ZONE": zone_path, "NOTES": "", "OUTPUT": "TEMPORARY_OUTPUT"},
        "action_playbook_generator",
    )

# ---------------------------------------------------------------------------
# 4. Scenario-based algorithms (need multiple suitability rasters)
# ---------------------------------------------------------------------------
print("\n=== 4. Multi-scenario algorithms ===")
if wlc_tif and os.path.exists(wlc_tif):
    # Create two additional "scenario" rasters from WLC with small variations
    rng = np.random.default_rng(99)
    scenario2 = np.clip(arr_wlc + rng.uniform(-3, 3, arr_wlc.shape).astype(np.float32), 0, 100)
    scenario3 = np.clip(arr_wlc + rng.uniform(-5, 5, arr_wlc.shape).astype(np.float32), 0, 100)

    s2_path = os.path.join(out_dir, "scenario2.tif")
    s3_path = os.path.join(out_dir, "scenario3.tif")
    _write_tif(s2_path, scenario2)
    _write_tif(s3_path, scenario3)

    scenario_rasters = [wlc_tif, s2_path, s3_path]

    # Ensemble suitability
    run_algo(
        "planx_suitability_lab:ensemble_suitability",
        {"INPUT_RASTERS": scenario_rasters, "WEIGHTS_CSV": "0.4,0.3,0.3",
         "OUT_MEAN": "TEMPORARY_OUTPUT", "OUT_STD": "TEMPORARY_OUTPUT", "OUT_P10": "TEMPORARY_OUTPUT",
         "OUT_P90": "TEMPORARY_OUTPUT", "OUT_CONF": "TEMPORARY_OUTPUT"},
        "ensemble_suitability",
    )

    # Scenario consensus zone
    run_algo(
        "planx_suitability_lab:scenario_consensus_zone",
        {"INPUT_RASTERS": scenario_rasters, "OUT_COUNT": "TEMPORARY_OUTPUT", "OUT_ZONE": "TEMPORARY_OUTPUT"},
        "scenario_consensus_zone",
    )

    # Scenario disagreement attention
    run_algo(
        "planx_suitability_lab:scenario_disagreement_attention",
        {"INPUT_RASTERS": scenario_rasters, "OUT_SCORE": "TEMPORARY_OUTPUT", "OUT_CLASS": "TEMPORARY_OUTPUT"},
        "scenario_disagreement_attention",
    )

    # Scenario similarity matrix
    run_algo(
        "planx_suitability_lab:scenario_similarity_matrix",
        {"INPUT_RASTERS": scenario_rasters, "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "scenario_similarity_matrix",
    )

    # Scenario dominance matrix
    dominance_res = run_algo(
        "planx_suitability_lab:scenario_dominance_matrix",
        {"INPUT_RASTERS": scenario_rasters, "EPS": 0.5, "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "scenario_dominance_matrix",
    )

    # Method benchmark leaderboard
    benchmark_res = run_algo(
        "planx_suitability_lab:method_benchmark_leaderboard",
        {"INPUT_RASTERS": scenario_rasters, "HIGH_THRESHOLD": 70.0, "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "method_benchmark_leaderboard",
    )

    # Minimax regret selector
    minimax_res = run_algo(
        "planx_suitability_lab:minimax_regret_selector",
        {"INPUT_RASTERS": scenario_rasters, "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "minimax_regret_selector",
    )

    # Scenario portfolio diversity
    portfolio_res = run_algo(
        "planx_suitability_lab:scenario_portfolio_diversity",
        {"INPUT_RASTERS": scenario_rasters, "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "scenario_portfolio_diversity",
    )

    # Decision quadrant map (needs suitability + disagreement)
    # Use wlc_tif as suitability, zone as proxy for disagreement
    z2_path = os.path.join(out_dir, "disag_proxy.tif")
    _write_tif(z2_path, np.clip(np.abs(arr_wlc - 50.0), 0, 100))
    run_algo(
        "planx_suitability_lab:decision_quadrant_map",
        {"SUITABILITY": wlc_tif, "DISAGREEMENT": z2_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "decision_quadrant_map",
    )

    # Risk-opportunity matrix map
    z3_path = os.path.join(out_dir, "unc_proxy.tif")
    _write_tif(z3_path, np.full_like(arr_wlc, 15.0))
    risk_matrix_res = run_algo(
        "planx_suitability_lab:risk_opportunity_matrix_map",
        {"ROBUST": wlc_tif, "UNC_STD": z3_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "risk_opportunity_matrix_map",
    )

    # Regret fragility map
    run_algo(
        "planx_suitability_lab:regret_fragility_map",
        {"INPUT_RASTERS": scenario_rasters, "OUT_SCORE": "TEMPORARY_OUTPUT", "OUT_CLASS": "TEMPORARY_OUTPUT"},
        "regret_fragility_map",
    )

    # Opportunity loss map
    if mask_files:
        run_algo(
            "planx_suitability_lab:opportunity_loss_map",
            {"SUIT": wlc_tif, "CONSTRAINT": str(mask_files[0]), "OUT_LOSS": "TEMPORARY_OUTPUT", "OUT_CLASS": "TEMPORARY_OUTPUT"},
            "opportunity_loss_map",
        )

    # Priority zoning from suitability
    run_algo(
        "planx_suitability_lab:priority_zoning_from_suitability",
        {"SUIT": wlc_tif, "CONF": z3_path, "OPP": z2_path, "OUT_INDEX": "TEMPORARY_OUTPUT", "OUT_ZONE": "TEMPORARY_OUTPUT"},
        "priority_zoning_from_suitability",
    )

    # Uncertainty adjusted suitability
    run_algo(
        "planx_suitability_lab:uncertainty_adjusted_suitability",
        {"MEAN": wlc_tif, "STD": z3_path, "RISK": 1.0, "OUTPUT": "TEMPORARY_OUTPUT"},
        "uncertainty_adjusted_suitability",
    )

    # Scenario comparator
    run_algo(
        "planx_suitability_lab:scenario_comparator",
        {"A": wlc_tif, "B": s2_path, "OUTPUT": "TEMPORARY_OUTPUT", "STATS": "TEMPORARY_OUTPUT"},
        "scenario_comparator",
    )

    # Policy sensitivity frontier
    frontier_res = run_algo(
        "planx_suitability_lab:policy_sensitivity_frontier",
        {"MEAN": wlc_tif, "STD": z3_path, "LAMBDAS": "0,0.5,1.0,2.0", "OUTPUT": "TEMPORARY_OUTPUT"},
        "policy_sensitivity_frontier",
    )

    # Criterion redundancy diagnostics
    run_algo(
        "planx_suitability_lab:criterion_redundancy_diagnostics",
        {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "MAX_SAMPLES": 10000, "BLOCK": 256,
         "OUTPUT_PAIRS": "TEMPORARY_OUTPUT", "OUTPUT_CRITERIA": "TEMPORARY_OUTPUT"},
        "criterion_redundancy_diagnostics",
    )

# ---------------------------------------------------------------------------
# 5. Area stats algorithms (need classification rasters)
# ---------------------------------------------------------------------------
print("\n=== 5. Area stats algorithms ===")
if wlc_tif and os.path.exists(wlc_tif):
    # Create proxy classification rasters
    cls_arr = np.digitize(arr_wlc, [0, 25, 50, 75]).astype(np.float32)
    cls_path = os.path.join(out_dir, "cls.tif")
    _write_tif(cls_path, cls_arr)

    # Consensus zone area stats
    run_algo(
        "planx_suitability_lab:consensus_zone_area_stats",
        {"INPUT": cls_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "consensus_zone_area_stats",
    )

    # Attention class area stats
    run_algo(
        "planx_suitability_lab:attention_class_area_stats",
        {"INPUT": cls_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "attention_class_area_stats",
    )

    # Decision quadrant area stats
    run_algo(
        "planx_suitability_lab:decision_quadrant_area_stats",
        {"INPUT": cls_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "decision_quadrant_area_stats",
    )

    # Intervention conflict area stats (needs 0-6 class raster)
    cls6_arr = np.clip(cls_arr, 0, 6).astype(np.float32)
    cls6_path = os.path.join(out_dir, "cls6.tif")
    _write_tif(cls6_path, cls6_arr)
    run_algo(
        "planx_suitability_lab:intervention_conflict_area_stats",
        {"INPUT": cls6_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "intervention_conflict_area_stats",
    )

    # Risk opportunity area stats
    run_algo(
        "planx_suitability_lab:risk_opportunity_area_stats",
        {"INPUT": cls_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "risk_opportunity_area_stats",
    )

    # Regret fragility area stats
    cls2_arr = np.clip(cls_arr, 0, 2).astype(np.float32)
    cls2_path = os.path.join(out_dir, "cls2.tif")
    _write_tif(cls2_path, cls2_arr)
    regret_stats_res = run_algo(
        "planx_suitability_lab:regret_fragility_area_stats",
        {"INPUT": cls2_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "regret_fragility_area_stats",
    )

    # Executive KPI snapshot
    kpi_res = run_algo(
        "planx_suitability_lab:executive_kpi_snapshot",
        {"SUITABILITY": wlc_tif, "ROBUST": wlc_tif, "CONSTRAINT": str(mask_files[0]) if mask_files else wlc_tif,
         "CONSENSUS_ZONE": cls_path, "ATTENTION_CLASS": cls_path, "OUTPUT": "TEMPORARY_OUTPUT"},
        "executive_kpi_snapshot",
    )

# ---------------------------------------------------------------------------
# 6. Upstream-table-consuming reporting algorithms (real chains, using tables
#    produced by earlier steps in this script)
# ---------------------------------------------------------------------------
print("\n=== 6. Cross-table reporting algorithms ===")

# synthetic_pipeline_runner: standalone, generates its own sample data end-to-end
run_algo(
    "planx_suitability_lab:synthetic_pipeline_runner",
    {"EXTENT": extent, "PIXEL": 30.0, "OUTDIR": os.path.join(out_dir, "pipeline_run")},
    "synthetic_pipeline_runner",
)

policy_gate_res = run_algo(
    "planx_suitability_lab:policy_gate_recommender",
    {"THRESHOLD_CURVE": threshold_curve_res.get("OUTPUT"), "FRONTIER": frontier_res.get("OUTPUT"),
     "TARGET_COVERAGE": 40.0, "MAX_CRITICAL_CONFLICT": 20.0, "OUTPUT": "TEMPORARY_OUTPUT"},
    "policy_gate_recommender",
)

scorecard_res = run_algo(
    "planx_suitability_lab:actionability_scorecard",
    {"KPI": kpi_res.get("OUTPUT"), "BUDGET": budget_phasing_res.get("OUTPUT"),
     "GATE": policy_gate_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "actionability_scorecard",
)

wave_plan_res = run_algo(
    "planx_suitability_lab:implementation_wave_planner",
    {"PRIORITY_ZONE": zone_path, "RISK_MATRIX": risk_matrix_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "implementation_wave_planner",
)

run_algo(
    "planx_suitability_lab:intervention_conflict_matrix",
    {"PRIORITY_ZONE": zone_path, "ATTENTION_CLASS": cls_path,
     "CONSTRAINT": str(mask_files[0]) if mask_files else None, "OUTPUT": "TEMPORARY_OUTPUT"},
    "intervention_conflict_matrix",
)

robustness_res = run_algo(
    "planx_suitability_lab:scenario_robustness_leaderboard",
    {"BENCHMARK": benchmark_res.get("OUTPUT"), "DOMINANCE": dominance_res.get("OUTPUT"),
     "MINIMAX": minimax_res.get("OUTPUT"), "PORTFOLIO": portfolio_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "scenario_robustness_leaderboard",
)

selection_res = run_algo(
    "planx_suitability_lab:scenario_selection_recommender",
    {"BENCHMARK": benchmark_res.get("OUTPUT"), "PORTFOLIO": portfolio_res.get("OUTPUT"),
     "MINIMAX": minimax_res.get("OUTPUT"), "GATE": policy_gate_res.get("OUTPUT"),
     "SCORECARD": scorecard_res.get("OUTPUT"), "ROBUSTNESS": robustness_res.get("OUTPUT"),
     "OUTPUT": "TEMPORARY_OUTPUT"},
    "scenario_selection_recommender",
)

deployment_res = run_algo(
    "planx_suitability_lab:deployment_readiness_gate",
    {"SCORECARD": scorecard_res.get("OUTPUT"), "SCENARIO_SELECTION": selection_res.get("OUTPUT"),
     "MINIMAX": minimax_res.get("OUTPUT"), "WAVE_PLAN": wave_plan_res.get("OUTPUT"),
     "REGRET_STATS": regret_stats_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "deployment_readiness_gate",
)

run_algo(
    "planx_suitability_lab:scenario_governance_audit",
    {"ROBUSTNESS": robustness_res.get("OUTPUT"), "BENCHMARK": benchmark_res.get("OUTPUT"),
     "MINIMAX": minimax_res.get("OUTPUT"), "SELECTION": selection_res.get("OUTPUT"),
     "DEPLOYMENT": deployment_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "scenario_governance_audit",
)

run_algo(
    "planx_suitability_lab:weight_consensus_audit",
    {"INPUT": ahp_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "weight_consensus_audit",
)

weight_pack_res = run_algo(
    "planx_suitability_lab:scenario_weight_pack",
    {"AHP": ahp_res.get("OUTPUT"), "PCA": pca_res.get("OUTPUT"), "ENT": entropy_res.get("OUTPUT"),
     "CRIT": critic_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "scenario_weight_pack",
)

run_algo(
    "planx_suitability_lab:weight_consolidator",
    {"INPUT": ahp_res.get("OUTPUT"), "OUTPUT": "TEMPORARY_OUTPUT"},
    "weight_consolidator",
)

site_res = run_algo(
    "planx_suitability_lab:candidate_site_extractor",
    {"SUIT": wlc_tif, "THRESHOLD": 60.0, "MIN_AREA_HA": 0.1, "TOP_N": 10, "CONNECTIVITY": 8, "OUTPUT": "TEMPORARY_OUTPUT"},
    "candidate_site_extractor",
)

if site_res.get("OUTPUT"):
    run_algo(
        "planx_suitability_lab:vector_rasterizer",
        {"INPUT": site_res.get("OUTPUT"), "FIELD": "mean_suit", "BURN": 1.0, "PIXEL": 30.0, "OUTPUT": "TEMPORARY_OUTPUT"},
        "vector_rasterizer",
    )

run_algo(
    "planx_suitability_lab:data_harmonizer",
    {"INPUT_RASTERS": [str(p) for p in criterion_files[:3]], "SNAP_RASTER": str(criterion_files[0]),
     "TARGET_RES": 30.0, "RESAMPLING": 0,
     "OUTPUT_RASTER": "TEMPORARY_OUTPUT", "OUTPUT_DIR": os.path.join(out_dir, "harmonized"),
     "OUTPUT_MANIFEST": os.path.join(out_dir, "harmonized_manifest.json")},
    "data_harmonizer",
)

if mask_files:
    run_algo(
        "planx_suitability_lab:constraint_impact_audit",
        {"SUITABILITY": wlc_tif, "CONSTRAINTS": [str(mask_files[0])], "HIGH_THRESHOLD": 70.0,
         "BLOCK": 256, "OUTPUT": "TEMPORARY_OUTPUT"},
        "constraint_impact_audit",
    )

run_algo(
    "planx_suitability_lab:beta_evidence_report",
    {"SUMMARY": "E2E synthetic run evidence.", "ARTIFACT_DIR": out_dir, "OUTPUT": os.path.join(out_dir, "beta_evidence.html")},
    "beta_evidence_report",
)

# ---------------------------------------------------------------------------
# 7. Dashboard smoke test
# ---------------------------------------------------------------------------
print("\n=== 7. Dashboard smoke test ===")
try:
    from planx_suitability_lab.dashboard import SuitabilityDashboard, ALGO_GROUPS

    # Verify no lang attribute remains
    dash_catalog_count = sum(len(items) for _, items in ALGO_GROUPS)
    check(dash_catalog_count == 68, f"Dashboard catalog has 68 entries (got {dash_catalog_count})")

    # Verify no 'lang' related remnants in the class
    import inspect
    src = inspect.getsource(SuitabilityDashboard)
    has_lang_combo = "lang_combo" in src
    has_set_language = "_set_language" in src
    has_lang_attr = "self.lang =" in src
    check(not has_lang_combo, "No lang_combo in dashboard")
    check(not has_set_language, "No _set_language in dashboard")
    check(not has_lang_attr, "No self.lang setting in dashboard")

    # Verify dashboard class can be inspected (no import-time errors)
    check(True, "Dashboard module imports successfully")

    # Catalog matches provider
    dash_ids = set()
    for group, items in ALGO_GROUPS:
        for title, aid, desc in items:
            dash_ids.add(aid)
    provider_ids = set(all_ids)
    missing_from_dash = provider_ids - dash_ids
    extra_in_dash = dash_ids - provider_ids
    check(len(missing_from_dash) == 0, f"All provider IDs in dashboard catalog (missing: {missing_from_dash})")
    check(len(extra_in_dash) == 0, f"No extra IDs in dashboard (extra: {extra_in_dash})")
except Exception as e:
    check(False, f"Dashboard smoke test error: {e}")
    traceback.print_exc()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"Executed: {len(executed)}/{len(all_ids)} algorithms")
print(f"Total checks: {algo_count}")

not_executed = sorted(set(all_ids) - executed)
if not_executed:
    print(f"Not executed ({len(not_executed)}):")
    for aid in not_executed:
        print(f"  - {aid}")

if failures:
    print(f"\nFAILURES ({len(failures)}):")
    for f in failures[:30]:
        print(f"  - {f}")
    print(f"\nE2E FULL: FAIL ({len(failures)} failures)")
    # Print summary then exit with os._exit to avoid segfault
    import os as _os
    _os._exit(1)
else:
    print("\nE2E FULL: PASS")
    import os as _os
    _os._exit(0)
