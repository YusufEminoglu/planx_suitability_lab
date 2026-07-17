#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure-logic tests for candidate_site_extractor (no QGIS required).

Stubs qgis/processing/osgeo so the module imports, then exercises the
numpy-only labeling and ranking core.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


class _Anything:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Anything()

    def __getattr__(self, item):
        return _Anything()


def _install_stubs() -> None:
    _stub("processing", run=lambda *a, **k: {})
    _stub("osgeo", gdal=_Anything())
    sys.modules["osgeo.gdal"] = _Anything()
    qgis = _stub("qgis")
    core_attrs = {
        n: _Anything
        for n in (
            "Qgis",
            "QgsFeature",
            "QgsField",
            "QgsFields",
            "QgsGeometry",
            "QgsProcessing",
            "QgsProcessingAlgorithm",
            "QgsProcessingException",
            "QgsProcessingParameterFeatureSink",
            "QgsProcessingParameterNumber",
            "QgsProcessingParameterRasterLayer",
            "QgsVectorLayer",
        )
    }
    qgis.core = _stub("qgis.core", **core_attrs)
    qgis.PyQt = _stub("qgis.PyQt")
    qgis.PyQt.QtCore = _stub("qgis.PyQt.QtCore", QVariant=_Anything, QMetaType=_Anything)


def _load_module():
    _install_stubs()
    import importlib.util

    path = ROOT / "processing" / "compose" / "candidate_site_extractor.py"
    spec = importlib.util.spec_from_file_location("cse_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run() -> int:
    mod = _load_module()
    failures: list[str] = []
    total = [0]

    def check(cond: bool, label: str) -> None:
        total[0] += 1
        print(f"  [{'OK' if cond else 'FAIL'}] {label}")
        if not cond:
            failures.append(label)

    # Grid: two separate orthogonal patches + one diagonal-only pair.
    mask = np.zeros((8, 8), dtype=bool)
    mask[0:2, 0:3] = True          # patch A: 6 cells
    mask[5:8, 5:8] = True          # patch B: 9 cells
    mask[3, 0] = True              # patch C part 1
    mask[4, 1] = True              # patch C part 2 (diagonal neighbor only)

    labels8, n8 = mod.label_components(mask, connectivity=8)
    check(n8 == 3, f"8-connectivity finds 3 patches (got {n8})")
    labels4, n4 = mod.label_components(mask, connectivity=4)
    check(n4 == 4, f"4-connectivity splits diagonal pair into 4 patches (got {n4})")
    check(int((labels8 > 0).sum()) == int(mask.sum()), "all masked cells labeled")
    check(int((labels8[~mask]).sum()) == 0, "background stays 0")

    # Values: patch B has higher mean than patch A.
    values = np.zeros((8, 8), dtype=np.float32)
    values[0:2, 0:3] = 80.0
    values[5:8, 5:8] = 95.0
    values[3, 0] = 99.0
    values[4, 1] = 99.0

    # cell = 100m x 100m = 1 ha per cell.
    sites = mod.rank_sites(labels8, n8, values, cell_area_m2=10000.0, min_area_ha=0.0, top_n=0)
    check(len(sites) == 3, f"no filter keeps 3 sites (got {len(sites)})")
    check(sites[0]["mean"] == 99.0 and sites[0]["cells"] == 2, "rank 1 = highest mean patch")
    check(sites[1]["mean"] == 95.0 and sites[1]["cells"] == 9, "rank 2 = 95-mean patch")
    check(sites[2]["mean"] == 80.0, "rank 3 = lowest mean patch")
    check(abs(sites[1]["area_ha"] - 9.0) < 1e-9, "area_ha = cells * cell_area / 10000")

    # Min-area filter: 3 ha removes the 2-cell diagonal patch.
    sites_min = mod.rank_sites(labels8, n8, values, 10000.0, min_area_ha=3.0, top_n=0)
    check(len(sites_min) == 2 and sites_min[0]["mean"] == 95.0, "min-area filter drops small patch")

    # top_n cap.
    sites_top = mod.rank_sites(labels8, n8, values, 10000.0, min_area_ha=0.0, top_n=1)
    check(len(sites_top) == 1 and sites_top[0]["mean"] == 99.0, "top_n=1 keeps best site only")

    # Tie-break: equal means -> larger area first; determinism across runs.
    values_tie = np.where(mask, 50.0, 0.0).astype(np.float32)
    t1 = mod.rank_sites(labels8, n8, values_tie, 10000.0, 0.0, 0)
    t2 = mod.rank_sites(labels8, n8, values_tie, 10000.0, 0.0, 0)
    check(t1 == t2, "ranking is deterministic")
    check(t1[0]["cells"] == 9, "equal means tie-break by larger area")

    # Empty mask -> no sites.
    empty_labels, empty_n = mod.label_components(np.zeros((4, 4), dtype=bool), 8)
    check(empty_n == 0, "empty mask yields zero components")
    check(mod.rank_sites(empty_labels, empty_n, np.zeros((4, 4), dtype=np.float32), 1.0, 0.0, 0) == [], "empty mask yields no sites")

    if failures:
        print(f"SITE LOGIC: FAIL ({len(failures)} failures)")
        return 1
    print(f"SITE LOGIC: PASS ({total[0]} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
