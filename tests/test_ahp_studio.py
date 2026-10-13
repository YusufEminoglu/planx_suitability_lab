#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure-logic unit tests for AHP Studio (ahp_studio.py) scale mappings, math, division guards and chart export.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ahp_studio import (
    AHP_MAX_CRITERIA,
    RI_TABLE,
    ratio_to_index,
    INDEX_TO_RATIO,
    calculate_ahp,
    generate_ahp_infographic,
    THEME_A_MATRIX,
    THEME_B_MATRIX,
    SCALE_DEF,
)


def _ri_table_literal(path: Path, name: str) -> dict:
    """Read an RI dict literal out of a module's source without importing it.

    The copy in processing/_mcda_utils.py cannot be imported from here: it pulls
    in `processing` and GDAL, and its table only exists as a local inside
    ahp_weights_from_json. Reading the literal keeps the drift check honest --
    the count assertion below fails loudly if the shape ever changes.
    """
    literals = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            targets = node.targets
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                literals.append(ast.literal_eval(node.value))
    assert len(literals) == 1, (
        f"expected exactly one `{name}` dict literal in {path.name}, found {len(literals)}")
    return literals[0]


def _cyclic_matrix(n: int, ratio: float = 9.0) -> np.ndarray:
    """Reciprocal, diagonal-1, but intransitive: a 9x cycle all the way round.

    No set of priorities can satisfy w_i / w_(i+1) = 9 for every i around a
    closed cycle, so CR must come out well above the 0.10 threshold.
    """
    m = np.ones((n, n), dtype=float)
    for i in range(n):
        m[i, (i + 1) % n] = ratio
        m[(i + 1) % n, i] = 1.0 / ratio
    return m


def test_ahp_scale_bijective_mapping():
    for idx in range(-8, 9):
        ratio = INDEX_TO_RATIO[idx]
        mapped_idx = ratio_to_index(ratio)
        assert mapped_idx == idx, f"Mismatch for scale index {idx}: ratio {ratio} -> {mapped_idx}"


def test_ahp_zero_division_guards():
    # Verify zero, negative, and extreme ratios do not throw ZeroDivisionError
    assert ratio_to_index(0.0) == 0
    assert ratio_to_index(-1.0) == 0
    assert ratio_to_index(1.0) == 0
    assert ratio_to_index(1e-15) == 8


def test_ahp_equal_weights():
    mat = np.ones((6, 6), dtype=float)
    res = calculate_ahp(mat)
    assert res["cr"] == 0.0
    assert res["cr_ok"] is True
    assert len(res["weights"]) == 6
    for w in res["weights"]:
        assert abs(w - (1.0 / 6.0)) < 1e-4


def test_ahp_theme_a_exact_math():
    res = calculate_ahp(np.array(THEME_A_MATRIX, dtype=float))
    assert abs(res["cr"] - 0.0400) < 0.005 or abs(res["cr"] - 0.0115) < 0.005
    assert res["cr_ok"] is True
    assert len(res["weights"]) == 6
    assert abs(sum(res["weights"]) - 1.0) < 1e-9


def test_ahp_theme_b_exact_math():
    res = calculate_ahp(np.array(THEME_B_MATRIX, dtype=float))
    assert abs(res["cr"] - 0.0199) < 0.005
    assert res["cr_ok"] is True
    assert len(res["weights"]) == 6
    assert abs(sum(res["weights"]) - 1.0) < 1e-9


def test_ahp_inconsistent_matrix_flagged():
    bad = np.array([
        [1.0, 9.0, 0.1111],
        [0.1111, 1.0, 9.0],
        [9.0, 0.1111, 1.0]
    ])
    res = calculate_ahp(bad)
    assert res["cr"] > 0.10
    assert res["cr_ok"] is False


# ---------------------------------------------------------------------------
# RI table: coverage, published values, and the drift guard
# ---------------------------------------------------------------------------
def test_ahp_ri_table_covers_every_supported_criterion_count():
    assert AHP_MAX_CRITERIA == 20
    assert sorted(RI_TABLE) == list(range(1, AHP_MAX_CRITERIA + 1))
    # Saaty's published values are unchanged ...
    assert [RI_TABLE[n] for n in range(3, 16)] == [
        0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49, 1.51, 1.54, 1.56, 1.57, 1.59]
    # ... and n = 16..20 is Alonso & Lamata (2006), i.e. the continuation the
    # criterion ceiling is derived from, not an extrapolation.
    assert [RI_TABLE[n] for n in range(16, 21)] == [
        1.5978, 1.6086, 1.6181, 1.6265, 1.6341]


def test_ahp_ri_tables_do_not_drift():
    studio = _ri_table_literal(ROOT / "ahp_studio.py", "RI_TABLE")
    utils = _ri_table_literal(ROOT / "processing" / "_mcda_utils.py", "ri_map")
    assert studio == utils


def test_ahp_ri_is_strictly_increasing_where_it_is_used():
    # RI must grow with n: CR = CI / RI would otherwise make a larger matrix
    # look more consistent than a smaller one at the same CI.
    nonzero = [RI_TABLE[n] for n in range(3, AHP_MAX_CRITERIA + 1)]
    assert all(b > a for a, b in zip(nonzero, nonzero[1:]))


def test_ahp_twenty_criteria_divides_ci_by_the_published_ri():
    res = calculate_ahp(np.ones((20, 20), dtype=float))
    assert res["cr_evaluable"] is True
    assert res["ri"] == 1.6341
    assert res["cr"] == 0.0 and res["cr_ok"] is True

    # The discriminating property: CR is CI over the *published* RI. The
    # 1.98 * (n - 2) / n approximation would divide by 1.782 and report a CR
    # about 9% smaller -- enough to pass a matrix with true CR = 0.105.
    res = calculate_ahp(_cyclic_matrix(20))
    assert res["cr"] > 0.10 and res["cr_ok"] is False
    assert abs(res["cr"] - res["ci"] / RI_TABLE[20]) < 1e-12


def test_ahp_beyond_the_table_is_not_reported_consistent():
    # n = 21 has no published RI. Extrapolating one understates CR, so the
    # result must say it could not be evaluated rather than "consistent".
    res = calculate_ahp(_cyclic_matrix(AHP_MAX_CRITERIA + 1))
    assert res["cr_evaluable"] is False
    assert res["cr_ok"] is False
    assert res["ri"] == 0.0
    assert len(res["weights"]) == AHP_MAX_CRITERIA + 1


def test_ahp_infographic_export_bytes_and_file(tmp_path: Path):
    names = ["Slope", "Flood (HAND)", "Active Fault", "Road Access", "Urban Built-up", "Agriculture Buffer"]
    mat = np.array(THEME_A_MATRIX, dtype=float)
    res = calculate_ahp(mat)

    chart_types = ["infographic", "bar", "radar", "donut", "heatmap", "pareto"]
    for c_type in chart_types:
        # 1. Test in-memory byte generation (used for clipboard)
        raw_bytes = generate_ahp_infographic(
            criteria_names=names,
            weights=res["weights"],
            cr=res["cr"],
            ci=res["ci"],
            ri=res["ri"],
            lambda_max=res["lambda_max"],
            cr_ok=res["cr_ok"],
            matrix=mat,
            scenario_title="Theme A (Hazard Priority)",
            output_path=None,
            dpi=150,
            chart_type=c_type,
        )
        assert raw_bytes is not None, f"Failed byte generation for chart {c_type}"
        assert len(raw_bytes) > 5000, f"Byte size too small for chart {c_type}"
        assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic bytes for chart {c_type}"

        # 2. Test disk file save
        out_file = str(tmp_path / f"test_export_{c_type}.png")
        generate_ahp_infographic(
            criteria_names=names,
            weights=res["weights"],
            cr=res["cr"],
            ci=res["ci"],
            ri=res["ri"],
            lambda_max=res["lambda_max"],
            cr_ok=res["cr_ok"],
            matrix=mat,
            scenario_title="Theme A Test",
            output_path=out_file,
            dpi=150,
            chart_type=c_type,
        )
        assert os.path.exists(out_file), f"Output file missing for {c_type}"
        assert os.path.getsize(out_file) > 5000, f"File size too small for {c_type}"


if __name__ == "__main__":
    test_ahp_scale_bijective_mapping()
    test_ahp_zero_division_guards()
    test_ahp_equal_weights()
    test_ahp_theme_a_exact_math()
    test_ahp_theme_b_exact_math()
    test_ahp_inconsistent_matrix_flagged()
    test_ahp_ri_table_covers_every_supported_criterion_count()
    test_ahp_ri_tables_do_not_drift()
    test_ahp_ri_is_strictly_increasing_where_it_is_used()
    test_ahp_twenty_criteria_divides_ci_by_the_published_ri()
    test_ahp_beyond_the_table_is_not_reported_consistent()
    import tempfile
    test_ahp_infographic_export_bytes_and_file(Path(tempfile.gettempdir()))
    print("All AHP Studio tests passed successfully (including all 6 publication chart renderers)!")
