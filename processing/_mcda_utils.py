# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
from typing import List, Tuple

import numpy as np
import processing
from qgis.core import QgsRasterLayer


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def parse_weights_csv(text: str, count: int) -> List[float]:
    if not text:
        return [1.0 / max(1, count)] * count
    vals = [float(v.strip()) for v in text.split(',') if v.strip()]
    if len(vals) != count:
        raise ValueError(f'Expected {count} weights, got {len(vals)}')
    s = sum(vals)
    if s == 0:
        return [1.0 / max(1, count)] * count
    return [v / s for v in vals]


def temp_tif(prefix: str = 'planx_suit_') -> str:
    fd, p = tempfile.mkstemp(prefix=prefix, suffix='.tif')
    os.close(fd)
    return p


def copy_raster(src: str, dst: str):
    processing.run('gdal:translate', {
        'INPUT': src,
        'TARGET_CRS': None,
        'NODATA': None,
        'COPY_SUBDATASETS': False,
        'OPTIONS': '',
        'EXTRA': '',
        'DATA_TYPE': 0,
        'OUTPUT': dst,
    })


def raster_calc(inputs: List[str], formula: str, out_path: str):
    letters = ['A', 'B', 'C', 'D', 'E', 'F']
    params = {
        'INPUT_A': None, 'BAND_A': 1,
        'INPUT_B': None, 'BAND_B': 1,
        'INPUT_C': None, 'BAND_C': 1,
        'INPUT_D': None, 'BAND_D': 1,
        'INPUT_E': None, 'BAND_E': 1,
        'INPUT_F': None, 'BAND_F': 1,
        'FORMULA': formula,
        'NO_DATA': -9999,
        'RTYPE': 5,
        'EXTRA': '',
        'OPTIONS': '',
        'OUTPUT': out_path,
    }
    for i, path in enumerate(inputs[:6]):
        params[f'INPUT_{letters[i]}'] = path
    processing.run('gdal:rastercalculator', params)


def ahp_weights_from_json(matrix_json: str) -> Tuple[List[float], float]:
    m = np.array(json.loads(matrix_json), dtype=float)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError('AHP matrix must be square')
    vals, vecs = np.linalg.eig(m)
    max_idx = int(np.argmax(vals.real))
    lam = float(vals[max_idx].real)
    w = np.abs(vecs[:, max_idx].real)
    if w.sum() == 0:
        w = np.ones(m.shape[0])
    w = w / w.sum()
    n = m.shape[0]
    ri_map = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
    ri = ri_map.get(n, 1.49)
    ci = (lam - n) / max(1.0, n - 1)
    cr = 0.0 if ri == 0 else ci / ri
    return w.tolist(), float(cr)


def pca_proxy_weights_from_rasters(rasters: List[str]) -> List[float]:
    # Lightweight proxy using per-raster variance over sampled block values.
    vars_ = []
    for p in rasters:
        rl = QgsRasterLayer(p, 'r')
        dp = rl.dataProvider()
        ext = rl.extent()
        cols = min(128, rl.width())
        rows = min(128, rl.height())
        block = dp.block(1, ext, cols, rows)
        arr = np.array(block.data(), dtype=float)
        arr = arr[np.isfinite(arr)]
        vars_.append(float(np.var(arr)) if arr.size else 0.0)
    s = sum(vars_)
    if s == 0:
        return [1.0 / max(1, len(rasters))] * len(rasters)
    return [v / s for v in vars_]


def entropy_weights_from_rasters(rasters: List[str]) -> List[float]:
    ent = []
    for p in rasters:
        rl = QgsRasterLayer(p, 'r')
        dp = rl.dataProvider()
        ext = rl.extent()
        cols = min(128, rl.width())
        rows = min(128, rl.height())
        block = dp.block(1, ext, cols, rows)
        arr = np.array(block.data(), dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            ent.append(0.0)
            continue
        arr = arr - arr.min()
        if arr.max() > 0:
            arr = arr / arr.max()
        pvals = arr + 1e-12
        pvals = pvals / pvals.sum()
        e = -np.sum(pvals * np.log(pvals)) / np.log(max(2, pvals.size))
        ent.append(float(1 - e))
    s = sum(ent)
    if s == 0:
        return [1.0 / max(1, len(rasters))] * len(rasters)
    return [v / s for v in ent]
