# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
from typing import List, Sequence, Tuple

import numpy as np
import processing
from osgeo import gdal


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def parse_weights_csv(text: str, count: int) -> List[float]:
    if count <= 0:
        return []
    if not text:
        return [1.0 / count] * count
    vals = [float(v.strip()) for v in text.split(",") if v.strip()]
    if len(vals) != count:
        raise ValueError(f"Expected {count} weights, got {len(vals)}")
    if any(v < 0 for v in vals):
        raise ValueError("Weights cannot be negative.")
    s = sum(vals)
    if s <= 0:
        return [1.0 / count] * count
    return [v / s for v in vals]


def parse_impacts_csv(text: str, count: int) -> List[int]:
    if count <= 0:
        return []
    if not text:
        return [1] * count
    raw = [v.strip().upper() for v in text.split(",") if v.strip()]
    if len(raw) != count:
        raise ValueError(f"Expected {count} impacts, got {len(raw)}")
    out = []
    for token in raw:
        if token in ("B", "BENEFIT", "+1", "1", "+"):
            out.append(1)
        elif token in ("C", "COST", "-1", "-"):
            out.append(-1)
        else:
            raise ValueError(f"Unknown impact token: {token}")
    return out


def temp_tif(prefix: str = "planx_suit_") -> str:
    fd, p = tempfile.mkstemp(prefix=prefix, suffix=".tif")
    os.close(fd)
    return p


def copy_raster(src: str, dst: str):
    processing.run(
        "gdal:translate",
        {
            "INPUT": src,
            "TARGET_CRS": None,
            "NODATA": None,
            "COPY_SUBDATASETS": False,
            "OPTIONS": "",
            "EXTRA": "",
            "DATA_TYPE": 0,
            "OUTPUT": dst,
        },
    )


def raster_calc(inputs: List[str], formula: str, out_path: str):
    letters = ["A", "B", "C", "D", "E", "F"]
    params = {
        "INPUT_A": None,
        "BAND_A": 1,
        "INPUT_B": None,
        "BAND_B": 1,
        "INPUT_C": None,
        "BAND_C": 1,
        "INPUT_D": None,
        "BAND_D": 1,
        "INPUT_E": None,
        "BAND_E": 1,
        "INPUT_F": None,
        "BAND_F": 1,
        "FORMULA": formula,
        "NO_DATA": -9999,
        "RTYPE": 5,
        "EXTRA": "",
        "OPTIONS": "",
        "OUTPUT": out_path,
    }
    for i, path in enumerate(inputs[:6]):
        params[f"INPUT_{letters[i]}"] = path
    processing.run("gdal:rastercalculator", params)


def ahp_weights_from_json(matrix_json: str) -> Tuple[List[float], float]:
    m = np.array(json.loads(matrix_json), dtype=float)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError("AHP matrix must be square")
    n = m.shape[0]
    if n == 0:
        raise ValueError("AHP matrix cannot be empty")
    if np.any(m <= 0):
        raise ValueError("AHP matrix values must be positive.")

    vals, vecs = np.linalg.eig(m)
    max_idx = int(np.argmax(vals.real))
    lam = float(vals[max_idx].real)
    w = np.abs(vecs[:, max_idx].real)
    if w.sum() == 0:
        w = np.ones(n, dtype=float)
    w = w / w.sum()

    ri_map = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
    ri = ri_map.get(n, 1.49)
    ci = (lam - n) / max(1.0, n - 1)
    cr = 0.0 if ri == 0 else ci / ri
    return w.tolist(), float(cr)


def _open_raster_bands(rasters: Sequence[str]):
    datasets = []
    bands = []
    nodatas = []
    xsize = None
    ysize = None
    for p in rasters:
        ds = gdal.Open(p, gdal.GA_ReadOnly)
        if ds is None:
            raise ValueError(f"Cannot open raster: {p}")
        band = ds.GetRasterBand(1)
        if xsize is None:
            xsize = ds.RasterXSize
            ysize = ds.RasterYSize
        elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
            raise ValueError("All rasters must have the same grid dimensions.")
        datasets.append(ds)
        bands.append(band)
        nodatas.append(band.GetNoDataValue())
    return datasets, bands, nodatas, xsize, ysize


def _sample_matrix_from_rasters(rasters: Sequence[str], target_samples: int = 6000) -> np.ndarray:
    if not rasters:
        return np.empty((0, 0), dtype=np.float64)
    datasets, bands, nodatas, xsize, ysize = _open_raster_bands(rasters)
    total_cells = max(1, xsize * ysize)
    stride = int(np.sqrt(total_cells / max(1, target_samples)))
    stride = max(1, stride)

    cols = np.arange(0, xsize, stride, dtype=int)
    rows = np.arange(0, ysize, stride, dtype=int)
    matrix = []
    for y in rows:
        for x in cols:
            vals = []
            valid = True
            for j, b in enumerate(bands):
                v = float(b.ReadAsArray(x, y, 1, 1)[0, 0])
                if not np.isfinite(v):
                    valid = False
                    break
                nd = nodatas[j]
                if nd is not None and v == nd:
                    valid = False
                    break
                vals.append(v)
            if valid:
                matrix.append(vals)
    for ds in datasets:
        ds = None
    if not matrix:
        return np.empty((0, len(rasters)), dtype=np.float64)
    return np.array(matrix, dtype=np.float64)


def pca_proxy_weights_from_rasters(rasters: List[str]) -> List[float]:
    n = len(rasters)
    if n == 0:
        return []
    X = _sample_matrix_from_rasters(rasters, target_samples=8000)
    if X.shape[0] < 3:
        return [1.0 / n] * n
    # Standardize criteria before covariance PCA.
    mu = np.mean(X, axis=0)
    sd = np.std(X, axis=0)
    sd = np.where(sd <= 1e-12, 1.0, sd)
    Z = (X - mu) / sd

    cov = np.cov(Z, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    idx = np.argsort(vals)[::-1]
    vals = vals[idx]
    vecs = vecs[:, idx]
    if vals[0] <= 1e-12:
        return [1.0 / n] * n
    # Use absolute loadings of PC1, weighted by explained variance ratio of PC1.
    load = np.abs(vecs[:, 0])
    evr1 = float(vals[0] / max(1e-12, np.sum(np.maximum(vals, 0))))
    load = load * max(evr1, 1e-6)
    s = float(np.sum(load))
    if s <= 1e-12:
        return [1.0 / n] * n
    return (load / s).tolist()


def entropy_weights_from_rasters(rasters: List[str]) -> List[float]:
    n = len(rasters)
    if n == 0:
        return []
    X = _sample_matrix_from_rasters(rasters, target_samples=8000)
    if X.shape[0] == 0:
        return [1.0 / n] * n
    # Normalize each criterion to [0,1]
    mins = np.min(X, axis=0)
    maxs = np.max(X, axis=0)
    den = np.where((maxs - mins) <= 1e-12, 1.0, (maxs - mins))
    Z = (X - mins) / den
    Z = np.clip(Z, 0.0, 1.0)

    # Entropy on proportional values.
    P = Z + 1e-12
    P = P / np.sum(P, axis=0, keepdims=True)
    m = max(2, P.shape[0])
    e = -np.sum(P * np.log(P), axis=0) / np.log(m)
    d = 1.0 - e
    d = np.where(np.isfinite(d), d, 0.0)
    s = float(np.sum(d))
    if s <= 1e-12:
        return [1.0 / n] * n
    return (d / s).tolist()


def critic_weights_from_rasters(rasters: List[str], impacts: List[int] | None = None) -> Tuple[List[float], np.ndarray, np.ndarray]:
    """
    CRITIC objective weighting.
    Returns:
      - normalized weights
      - per-criterion standard deviation on normalized values
      - per-criterion contrast sum (sum(1-corr))
    """
    n = len(rasters)
    if n == 0:
        return [], np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    X = _sample_matrix_from_rasters(rasters, target_samples=10000)
    if X.shape[0] < 3:
        w = np.array([1.0 / n] * n, dtype=np.float64)
        return w.tolist(), np.zeros(n, dtype=np.float64), np.ones(n, dtype=np.float64)

    if impacts is None or len(impacts) != n:
        impacts = [1] * n

    mins = np.min(X, axis=0)
    maxs = np.max(X, axis=0)
    den = np.where((maxs - mins) <= 1e-12, 1.0, (maxs - mins))
    Z = np.empty_like(X, dtype=np.float64)
    for j in range(n):
        if impacts[j] >= 0:
            Z[:, j] = (X[:, j] - mins[j]) / den[j]
        else:
            Z[:, j] = (maxs[j] - X[:, j]) / den[j]
    Z = np.clip(Z, 0.0, 1.0)

    sigma = np.std(Z, axis=0)
    corr = np.corrcoef(Z, rowvar=False)
    corr = np.where(np.isfinite(corr), corr, 0.0)
    np.fill_diagonal(corr, 1.0)
    contrast = np.sum(1.0 - corr, axis=1)
    scores = sigma * contrast
    scores = np.where(np.isfinite(scores), scores, 0.0)
    s = float(np.sum(scores))
    if s <= 1e-12:
        w = np.array([1.0 / n] * n, dtype=np.float64)
        return w.tolist(), sigma, contrast
    w = scores / s
    return w.tolist(), sigma, contrast
