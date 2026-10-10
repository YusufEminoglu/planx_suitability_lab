#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure-logic unit tests for AHP Studio (ahp_studio.py) scale mappings, math and chart export.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ahp_studio import (
    ratio_to_index,
    INDEX_TO_RATIO,
    calculate_ahp,
    generate_ahp_infographic,
    TEMA_A_MATRIX,
    TEMA_B_MATRIX,
    SCALE_DEF,
)


def test_ahp_scale_bijective_mapping():
    for idx in range(-8, 9):
        ratio = INDEX_TO_RATIO[idx]
        mapped_idx = ratio_to_index(ratio)
        assert mapped_idx == idx, f"Mismatch for scale index {idx}: ratio {ratio} -> {mapped_idx}"


def test_ahp_tema_a_exact_math():
    res = calculate_ahp(np.array(TEMA_A_MATRIX, dtype=float))
    assert abs(res["cr"] - 0.0115) < 0.001
    assert res["cr_ok"] is True
    assert len(res["weights"]) == 6
    assert abs(sum(res["weights"]) - 1.0) < 1e-9


def test_ahp_tema_b_exact_math():
    res = calculate_ahp(np.array(TEMA_B_MATRIX, dtype=float))
    assert abs(res["cr"] - 0.0199) < 0.001
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


def test_ahp_infographic_export_bytes_and_file(tmp_path: Path):
    names = ["Eğim", "Taşkın", "Diri Fay", "Yol", "Bina", "Tarım"]
    mat = np.array(TEMA_A_MATRIX, dtype=float)
    res = calculate_ahp(mat)

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
        scenario_title="Tema A (Afet Odaklı)",
        output_path=None,
        dpi=150,
    )
    assert raw_bytes is not None
    assert len(raw_bytes) > 10000
    assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    # 2. Test disk file save
    out_file = str(tmp_path / "test_export_ahp.png")
    generate_ahp_infographic(
        criteria_names=names,
        weights=res["weights"],
        cr=res["cr"],
        ci=res["ci"],
        ri=res["ri"],
        lambda_max=res["lambda_max"],
        cr_ok=res["cr_ok"],
        matrix=mat,
        scenario_title="Tema A Test",
        output_path=out_file,
        dpi=150,
    )
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000


if __name__ == "__main__":
    test_ahp_scale_bijective_mapping()
    test_ahp_tema_a_exact_math()
    test_ahp_tema_b_exact_math()
    test_ahp_inconsistent_matrix_flagged()
    import tempfile
    test_ahp_infographic_export_bytes_and_file(Path(tempfile.gettempdir()))
    print("All AHP Studio tests passed successfully!")
