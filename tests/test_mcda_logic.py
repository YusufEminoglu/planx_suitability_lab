#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure-logic unit tests for MCDA weight derivation, parsing utilities, and edge cases.

Tests the numerical cores in _mcda_utils.py without QGIS.
Creates temporary synthetic rasters via GDAL for the sampling-based weight functions.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "processing"))
# _mcda_utils does a top-level `import processing` (QGIS Processing framework,
# used only at algorithm call sites). For these pure-logic tests the plugin's
# own light `processing` package is a sufficient stand-in, so make ROOT
# importable too — keeps the tests runnable without a QGIS plugin path.
sys.path.insert(1, str(ROOT))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _make_tif(path, arr, nodata=-9999.0):
    from osgeo import gdal

    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(path, arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0, 1, 0, 0, 0, -1))
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(arr.astype(np.float32))
    band.FlushCache()
    ds = None


def _tmp():
    fd, p = tempfile.mkstemp(prefix="test_mcda_", suffix=".tif")
    os.close(fd)
    return p


# ---------------------------------------------------------------------------
# module under test
# ---------------------------------------------------------------------------
import _mcda_utils as U


# ===================================================================
# 1. ensure_list
# ===================================================================
def test_ensure_list():
    assert U.ensure_list(None) == []
    assert U.ensure_list([1, 2]) == [1, 2]
    assert U.ensure_list((1,)) == [1]
    assert U.ensure_list("single") == ["single"]
    assert U.ensure_list(42) == [42]


# ===================================================================
# 2. slugify_ascii
# ===================================================================
def test_slugify_ascii():
    assert U.slugify_ascii("Hello World") == "hello_world"
    assert U.slugify_ascii("") == "layer"
    assert U.slugify_ascii(None, fallback="fb") == "fb"
    assert U.slugify_ascii("  A B  C  ") == "a_b_c"
    assert U.slugify_ascii("path/to/file.tif") == "path_to_file_tif"
    # Turkish chars stripped
    res = U.slugify_ascii("uygunluk", fallback="x")
    assert "u" in res


# ===================================================================
# 3. infer_layer_label
# ===================================================================
def test_infer_layer_label():
    assert U.infer_layer_label(None, "fb") == "fb"
    assert U.infer_layer_label("/some/path/myraster.tif") == "myraster"
    assert U.infer_layer_label("  ") == "layer"


# ===================================================================
# 4. parse_weights_csv
# ===================================================================
def test_parse_weights_csv():
    # valid
    w = U.parse_weights_csv("0.5, 0.3, 0.2", 3)
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-12
    assert w == [0.5, 0.3, 0.2]

    # empty -> equal weights
    w2 = U.parse_weights_csv("", 4)
    assert len(w2) == 4
    assert all(abs(v - 0.25) < 1e-9 for v in w2)

    # count=0
    assert U.parse_weights_csv("1,2,3", 0) == []

    # wrong count -> ValueError
    try:
        U.parse_weights_csv("0.5,0.5", 3)
        assert False, "should raise"
    except ValueError:
        pass

    # negative -> ValueError
    try:
        U.parse_weights_csv("-0.1, 0.5, 0.6", 3)
        assert False, "should raise"
    except ValueError:
        pass

    # all zero -> equal weights fallback
    w3 = U.parse_weights_csv("0, 0, 0", 3)
    assert all(abs(v - 1.0 / 3) < 1e-9 for v in w3)

    # renormalize non-normalized
    w4 = U.parse_weights_csv("2, 2, 6", 3)
    assert abs(sum(w4) - 1.0) < 1e-12
    assert w4 == [0.2, 0.2, 0.6]


# ===================================================================
# 5. parse_impacts_csv
# ===================================================================
def test_parse_impacts_csv():
    # empty -> all benefit
    assert U.parse_impacts_csv("", 3) == [1, 1, 1]

    # explicit
    assert U.parse_impacts_csv("B, C, +1", 3) == [1, -1, 1]
    assert U.parse_impacts_csv("benefit, COST, -1, +", 4) == [1, -1, -1, 1]

    # count=0
    assert U.parse_impacts_csv("x,y", 0) == []

    # unknown token -> ValueError
    try:
        U.parse_impacts_csv("X", 1)
        assert False, "should raise"
    except ValueError:
        pass

    # wrong count
    try:
        U.parse_impacts_csv("B,C", 3)
        assert False, "should raise"
    except ValueError:
        pass


# ===================================================================
# 6. AHP weight derivation (known matrix)
# ===================================================================
def test_ahp_weights():
    # Textbook 3x3 consistent matrix: criterion 2 wins over 1, etc.
    mat = [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]
    w, cr = U.ahp_weights_from_json(json.dumps(mat))
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-9
    # Expected: w1 > w2 > w3  (approx 0.571, 0.286, 0.143 for perfect consistency)
    assert w[0] > w[1] > w[2]
    assert abs(w[0] - 4.0 / 7.0) < 0.01
    assert cr < 0.01  # nearly perfect consistency

    # Inconsistent matrix (should give CR > 0)
    mat2 = [[1, 3, 5], [1.0 / 3, 1, 3], [1.0 / 5, 1.0 / 3, 1]]
    w2, cr2 = U.ahp_weights_from_json(json.dumps(mat2))
    assert len(w2) == 3
    assert abs(sum(w2) - 1.0) < 1e-9
    assert cr2 > 0.01  # moderate inconsistency

    # 2x2 matrix (CR = 0 always)
    mat3 = [[1, 2], [0.5, 1]]
    w3, cr3 = U.ahp_weights_from_json(json.dumps(mat3))
    assert len(w3) == 2
    assert abs(cr3) < 1e-9

    # Non-square -> ValueError
    try:
        U.ahp_weights_from_json(json.dumps([[1, 2]]))
        assert False
    except ValueError:
        pass

    # Empty -> ValueError
    try:
        U.ahp_weights_from_json(json.dumps([]))
        assert False
    except ValueError:
        pass

    # Negative values -> ValueError
    try:
        U.ahp_weights_from_json(json.dumps([[-1, 1], [1, 1]]))
        assert False
    except ValueError:
        pass


def test_ahp_consistency_ratio_matches_textbook_value():
    # [[1,3,5],[1/3,1,3],[1/5,1/3,1]]: lambda_max ~ 3.0385, CI ~ 0.0193,
    # RI(3) = 0.58, so CR ~ 0.033 - pins the arithmetic, not just "CR > 0"
    mat = [[1, 3, 5], [1.0 / 3, 1, 3], [1.0 / 5, 1.0 / 3, 1]]
    w, cr = U.ahp_weights_from_json(json.dumps(mat))
    assert abs(cr - 0.0332) < 0.001, cr
    assert abs(w[0] - 0.637) < 0.002 and abs(w[1] - 0.258) < 0.002, w


def test_ahp_rejects_non_reciprocal_matrices():
    # a transposed judgement: 3 where 1/3 belongs
    for bad in ([[1, 3, 5], [3, 1, 3], [0.2, 1.0 / 3, 1]],
                [[2, 1], [1, 1]]):                     # diagonal not 1
        try:
            U.ahp_weights_from_json(json.dumps(bad))
            assert False, f"accepted {bad}"
        except ValueError as exc:
            assert "reciprocal" in str(exc) or "diagonal" in str(exc), exc
    # rounded fractions are fine: 3 * 0.3333 = 0.9999
    w, cr = U.ahp_weights_from_json(json.dumps([[1, 2, 3], [0.5, 1, 2], [0.3333, 0.5, 1]]))
    assert abs(sum(w) - 1.0) < 1e-9 and cr >= 0.0


def test_limit_layers_refuses_instead_of_truncating():
    assert U.limit_layers(["a", "b"], 6) == ["a", "b"]
    assert U.limit_layers(list("abcdef"), 6) == list("abcdef")
    try:
        U.limit_layers(list("abcdefg"), 6, "criterion rasters")
        assert False, "seven layers were accepted by a six-layer tool"
    except ValueError as exc:
        assert "at most 6 criterion rasters; 7 were given" in str(exc), exc


def test_threshold_mask_and_raster_calc_guard():
    from processing.core.constraint_builder import threshold_mask, MASK_NODATA
    arr = np.array([[0.2, 0.5, 0.9], [np.nan, -9999.0, 0.49]])
    got = threshold_mask(arr, 0.5, nodata=-9999.0)
    assert got.tolist() == [[0, 1, 1], [MASK_NODATA, MASK_NODATA, 0]], got.tolist()
    # a formula the Windows shell would mangle is refused, not silently run
    try:
        U.raster_calc(["x.tif"], "(A>=0.5)", "out.tif")
        assert False, "raster_calc accepted a '>' formula"
    except ValueError as exc:
        assert ">" in str(exc), exc


# ===================================================================
# 7. Entropy weights with synthetic rasters
# ===================================================================
def test_entropy_weights():
    # Three criteria: high-variance, medium, constant
    n = 48
    arr1 = np.random.default_rng(1).uniform(0, 100, (n, n)).astype(np.float32)  # high variance
    arr2 = np.full((n, n), 50.0, dtype=np.float32)  # constant -> low weight
    arr3 = np.tile(np.linspace(0, 100, n), (n, 1)).astype(np.float32)  # medium gradient

    p1, p2, p3 = _tmp(), _tmp(), _tmp()
    _make_tif(p1, arr1)
    _make_tif(p2, arr2)
    _make_tif(p3, arr3)

    w = U.entropy_weights_from_rasters([p1, p2, p3])
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-9
    # constant raster must have lowest weight
    assert w[1] < w[0]
    assert w[1] < w[2]

    for p in [p1, p2, p3]:
        os.unlink(p)

    # empty rasters
    assert U.entropy_weights_from_rasters([]) == []


# ===================================================================
# 8. PCA proxy weights
# ===================================================================
def test_pca_weights():
    n = 40
    rng = np.random.default_rng(2)
    # Two correlated criteria, one uncorrelated
    base = rng.uniform(0, 100, (n, n)).astype(np.float32)
    arr1 = base + rng.uniform(-5, 5, (n, n)).astype(np.float32)
    arr2 = base + rng.uniform(-5, 5, (n, n)).astype(np.float32)  # highly correlated with arr1
    arr3 = rng.uniform(0, 100, (n, n)).astype(np.float32)  # independent

    p1, p2, p3 = _tmp(), _tmp(), _tmp()
    _make_tif(p1, arr1)
    _make_tif(p2, arr2)
    _make_tif(p3, arr3)

    w = U.pca_proxy_weights_from_rasters([p1, p2, p3])
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-9
    # All weights should be positive
    assert all(v > 0 for v in w)

    for p in [p1, p2, p3]:
        os.unlink(p)

    assert U.pca_proxy_weights_from_rasters([]) == []

    # Very small raster (less than 3 valid samples -> equal weights)
    tiny = np.full((3, 3), 10.0, dtype=np.float32)
    pt = _tmp()
    _make_tif(pt, tiny)
    w_tiny = U.pca_proxy_weights_from_rasters([pt])
    assert len(w_tiny) == 1
    assert abs(w_tiny[0] - 1.0) < 1e-9
    os.unlink(pt)


# ===================================================================
# 9. CRITIC weights
# ===================================================================
def test_critic_weights():
    n = 40
    rng = np.random.default_rng(3)
    arr1 = rng.uniform(0, 100, (n, n)).astype(np.float32)  # high variance
    arr2 = np.tile(np.linspace(0, 100, n), (n, 1)).astype(np.float32)  # gradient
    arr3 = np.full((n, n), 50.0, dtype=np.float32)  # constant

    p1, p2, p3 = _tmp(), _tmp(), _tmp()
    _make_tif(p1, arr1)
    _make_tif(p2, arr2)
    _make_tif(p3, arr3)

    w, sigma, contrast = U.critic_weights_from_rasters([p1, p2, p3], impacts=[1, 1, 1])
    assert len(w) == 3
    assert abs(sum(w) - 1.0) < 1e-9
    # constant raster gets near-zero std -> near-zero weight
    assert w[2] < 0.1

    for p in [p1, p2, p3]:
        os.unlink(p)

    w_empty, s_empty, c_empty = U.critic_weights_from_rasters([])
    assert w_empty == []
    assert s_empty.size == 0
    assert c_empty.size == 0


# ===================================================================
# 10. Edge cases and zero-division guards
# ===================================================================
def test_edge_cases():
    # Entropy with all constant rasters
    n = 20
    arr = np.full((n, n), 50.0, dtype=np.float32)
    p = _tmp()
    _make_tif(p, arr)

    # Single constant raster -> entropy gives 1.0 weight
    w_e = U.entropy_weights_from_rasters([p])
    assert len(w_e) == 1
    assert abs(w_e[0] - 1.0) < 1e-9

    # CRITIC with all constant -> equal weights
    w_c, _, _ = U.critic_weights_from_rasters([p])
    assert len(w_c) == 1
    assert abs(w_c[0] - 1.0) < 1e-9

    # PCA with single constant -> weight 1
    w_p = U.pca_proxy_weights_from_rasters([p])
    assert len(w_p) == 1
    assert abs(w_p[0] - 1.0) < 1e-9

    # Two constant rasters -> equal weights
    p2 = _tmp()
    _make_tif(p2, arr)
    w2 = U.entropy_weights_from_rasters([p, p2])
    assert len(w2) == 2
    assert abs(w2[0] - 0.5) < 1e-9
    assert abs(w2[1] - 0.5) < 1e-9

    for pp in [p, p2]:
        os.unlink(pp)


# ===================================================================
# 11. smart_output_path
# ===================================================================
def test_smart_output_path():
    # Temporary placeholder
    p1 = U.smart_output_path("TEMPORARY_OUTPUT", None, "test_op", ".tif")
    assert "test_op" in p1
    assert p1.endswith(".tif")

    # Empty string -> temp
    p2 = U.smart_output_path("", None, "op2")
    assert "op2" in p2

    # Explicit path -> returned unchanged
    p3 = U.smart_output_path("/out/myraster.tif", None, "op3")
    assert p3 == "/out/myraster.tif"

    # memory: prefix
    p4 = U.smart_output_path("memory:xyz", None, "op4")
    assert "op4" in p4


# ===================================================================
# 12. Weight math edge cases
# ===================================================================
def test_weight_math():
    # parse_weights with trailing comma
    w = U.parse_weights_csv("0.25, 0.25, 0.25, 0.25", 4)
    assert abs(sum(w) - 1.0) < 1e-9

    # parse_impacts with whitespace
    assert U.parse_impacts_csv("  B  , c , BENEFIT ", 3) == [1, -1, 1]

    # Ensure non-normalized weights sum to 1 after parsing
    w2 = U.parse_weights_csv("10, 20, 30, 40", 4)
    assert abs(sum(w2) - 1.0) < 1e-9
    assert w2 == [0.1, 0.2, 0.3, 0.4]


# ===================================================================
# runner
# ===================================================================
if __name__ == "__main__":
    import traceback

    tests = [
        fn
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    passed = 0
    failed = 0
    assertions_total = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
            print(f"PASS {test_fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {test_fn.__name__}")
            traceback.print_exc()

    print(f"\n{tests.__len__()} test functions: {passed} passed, {failed} failed")

    # Count approximate assertions
    src = Path(__file__).read_text()
    assertion_count = src.count("assert ")
    print(f"~{assertion_count} assertions")

    sys.exit(0 if failed == 0 else 1)
