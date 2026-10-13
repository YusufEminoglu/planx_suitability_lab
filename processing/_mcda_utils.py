# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import unicodedata
from datetime import datetime
from typing import List, Sequence, Tuple

import numpy as np
import processing
from osgeo import gdal


from contextlib import suppress


# --------------------------------------------------------------------------
# Output styling. Raster outputs are always files that QGIS opens after the
# run, so a renderer set during processAlgorithm could never reach them; a
# layer post-processor styles the layer QGIS actually loads. QGIS keeps only a
# raw pointer to it, so each one is kept alive here.
# --------------------------------------------------------------------------
_STYLE_PROCESSORS: list = []

#: 0-100 suitability ramp, light yellow (low) to dark green (high): sequential,
#: colour-blind safe, and fixed to the score's own range so two runs compare.
SCORE_RAMP = ("#ffffcc", "#c2e699", "#78c679", "#31a354", "#006837")


def _apply_score_style(layer, minimum: float = 0.0, maximum: float = 100.0) -> None:
    from qgis.core import (QgsColorRampShader, QgsRasterShader,
                           QgsSingleBandPseudoColorRenderer)
    from qgis.PyQt.QtGui import QColor
    ramp = QgsColorRampShader(minimum, maximum)
    ramp.setColorRampType(QgsColorRampShader.Type.Interpolated)
    step = (maximum - minimum) / (len(SCORE_RAMP) - 1)
    ramp.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(minimum + i * step, QColor(color), f"{minimum + i * step:g}")
        for i, color in enumerate(SCORE_RAMP)])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    renderer.setClassificationMin(minimum)
    renderer.setClassificationMax(maximum)
    layer.setRenderer(renderer)


def _apply_mask_style(layer) -> None:
    from qgis.core import QgsPalettedRasterRenderer
    from qgis.PyQt.QtGui import QColor
    classes = [QgsPalettedRasterRenderer.Class(0, QColor("#bdbdbd"), "Excluded (0)"),
               QgsPalettedRasterRenderer.Class(1, QColor("#1a9850"), "Allowed (1)")]
    layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))


def style_raster_output(context, output_path: str, kind: str = "score") -> bool:
    """Style ``output_path`` when QGIS loads it: ``score`` (0-100 ramp) or
    ``mask`` (0/1 classes). Returns True when a style was scheduled."""
    from qgis.core import QgsProcessingLayerPostProcessorInterface
    if not output_path or not context.willLoadLayerOnCompletion(output_path):
        return False
    apply = _apply_mask_style if kind == "mask" else _apply_score_style

    class _Style(QgsProcessingLayerPostProcessorInterface):
        def postProcessLayer(self, layer, ctx, feedback):
            if layer is None or not hasattr(layer, "dataProvider"):
                return
            try:
                apply(layer)
                layer.triggerRepaint()
            except Exception as exc:  # noqa: BLE001 - styling never fails a run
                if feedback is not None:
                    feedback.reportError(f"Could not style the output: {exc}", False)

    processor = _Style()
    _STYLE_PROCESSORS.append(processor)
    context.layerToLoadOnCompletionDetails(output_path).setPostProcessor(processor)
    return True


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def limit_layers(layers, cap: int, what: str = "criterion rasters"):
    """Return ``layers`` unchanged, or refuse when there are more than ``cap``.

    The tools used to slice the list silently (``[:6]``), so a seventh
    criterion vanished from the result without a word. Raising names the
    limit instead of producing a map that ignores part of the input.
    """
    layers = list(layers)
    if len(layers) > cap:
        raise ValueError(
            f"This tool accepts at most {cap} {what}; {len(layers)} were given. "
            f"Remove or pre-combine {len(layers) - cap} of them - they would "
            f"otherwise be left out of the result.")
    return layers


def validate_ahp_matrix(m, tolerance: float = 0.02) -> None:
    """Check the reciprocity the AHP method assumes.

    The diagonal must be 1 and ``m[i][j] * m[j][i]`` must be 1. The relative
    tolerance admits rounded fractions such as 0.3333 for 1/3 (product
    0.9999) but not a transposed or mistyped judgement.
    """
    n = m.shape[0]
    for i in range(n):
        if abs(m[i, i] - 1.0) > tolerance:
            raise ValueError(f"AHP matrix diagonal must be 1; element [{i}][{i}] is {m[i, i]:g}.")
    for i in range(n):
        for j in range(i + 1, n):
            product = m[i, j] * m[j, i]
            if abs(product - 1.0) > tolerance:
                raise ValueError(
                    f"AHP matrix is not reciprocal: [{i}][{j}] = {m[i, j]:g} but "
                    f"[{j}][{i}] = {m[j, i]:g} (expected {1.0 / m[i, j]:.4g}). "
                    f"Each judgement below the diagonal must be the inverse of the one above it.")


def infer_layer_label(layer_or_path, fallback: str = "layer") -> str:
    """Best-effort label extraction for naming outputs."""
    if layer_or_path is None:
        return fallback
    # QGIS layer-like object
    with suppress(Exception):
        nm = layer_or_path.name()
        if isinstance(nm, str) and nm.strip():
            return nm.strip()
    # String/path
    try:
        s = str(layer_or_path).strip()
        if not s:
            return fallback
        base = os.path.basename(s)
        stem, _ = os.path.splitext(base)
        return stem or fallback
    except Exception:
        return fallback


def slugify_ascii(text: str, fallback: str = "layer", max_len: int = 64) -> str:
    src = (text or "").strip()
    if not src:
        src = fallback
    # Turkish and unicode friendly normalization to ascii-ish ids
    src = unicodedata.normalize("NFKD", src)
    src = src.encode("ascii", "ignore").decode("ascii")
    out = []
    prev_us = False
    for ch in src:
        if ch.isalnum():
            out.append(ch.lower())
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    name = "".join(out).strip("_")
    if not name:
        name = fallback
    if len(name) > max_len:
        name = name[:max_len].rstrip("_")
    return name or fallback


def smart_output_path(raw_output: str, layer_or_path, operation_tag: str, ext: str = ".tif") -> str:
    """
    If user selected temporary output, create a deterministic readable name:
      <input>_<operation>_<timestamp>.ext
    Otherwise return user-provided output unchanged.
    """
    out = (raw_output or "").strip()
    upper = out.upper()
    is_temp = (not out) or (upper in ("TEMPORARY_OUTPUT", "CREATE TEMPORARY LAYER")) or out.startswith("memory:")
    if not is_temp:
        return out
    label = slugify_ascii(infer_layer_label(layer_or_path, fallback="layer"), fallback="layer")
    op = slugify_ascii(operation_tag or "result", fallback="result", max_len=48)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{label}_{op}_{ts}{ext}"
    return os.path.join(tempfile.gettempdir(), fname)


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


def oat_perturbed_weights(weights, index: int, fraction: float) -> np.ndarray:
    """One-at-a-time weight perturbation (Chen, Yu & Khan, 2010).

    ``w_i' = clip(w_i * (1 + fraction), 0, 1)``; every other weight is scaled
    by ``(1 - w_i') / (1 - w_i)`` so the set keeps its proportions and still
    sums to 1. A criterion that already carries all the weight (``w_i = 1``)
    cannot be perturbed and is returned unchanged.
    """
    w = np.asarray(weights, dtype=np.float64)
    wi = float(w[index])
    if wi >= 1.0 - 1e-12:
        return w.copy()
    new_wi = min(1.0, max(0.0, wi * (1.0 + fraction)))
    scale = (1.0 - new_wi) / (1.0 - wi)
    out = w * scale
    out[index] = new_wi
    return out


def wlc_score(stack, weights) -> np.ndarray:
    """Weighted linear combination exactly as Compose: WLC Suitability computes
    it: criteria clipped to 0-100, weighted sum, result clipped to 0-100."""
    clipped = np.clip(np.asarray(stack, dtype=np.float32), 0.0, 100.0)
    w = np.asarray(weights, dtype=np.float32)
    return np.clip(np.sum(clipped * w[:, None, None], axis=0), 0.0, 100.0).astype(np.float32)


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
    # gdal:rastercalculator passes FORMULA on a command line that goes through
    # a shell on Windows: ">" and "<" become redirects, "|", "&" and "^" are
    # operators. The run still "succeeds" and writes an all-nodata raster.
    unsafe = sorted(set(formula) & set("<>|&^"))
    if unsafe:
        raise ValueError(
            f"raster_calc formula {formula!r} contains {''.join(unsafe)}, which the "
            f"Windows command line mangles; compute it with numpy instead.")
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
    validate_ahp_matrix(m)

    vals, vecs = np.linalg.eig(m)
    max_idx = int(np.argmax(vals.real))
    lam = float(vals[max_idx].real)
    w = np.abs(vecs[:, max_idx].real)
    if w.sum() == 0:
        w = np.ones(n, dtype=float)
    w = w / w.sum()

    # Kept identical to RI_TABLE in ahp_studio.py (n = 16..20 from Alonso &
    # Lamata 2006, doi:10.1142/S0218488506004114); tests/test_ahp_studio.py
    # asserts the two never drift apart.
    ri_map = {
        1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
        8: 1.41, 9: 1.45, 10: 1.49, 11: 1.51, 12: 1.54, 13: 1.56, 14: 1.57, 15: 1.59,
        16: 1.5978, 17: 1.6086, 18: 1.6181, 19: 1.6265, 20: 1.6341,
    }
    ri = ri_map.get(n)
    if ri is None:
        # Past n = 20 no RI is published, and the 1.98 * (n - 2) / n
        # approximation inflates it. CR = CI / RI, so an inflated RI understates
        # CR and would report a genuinely inconsistent matrix as consistent.
        # Refuse the input instead of returning a number that is not one.
        raise ValueError(
            f"AHP supports at most {max(ri_map)} criteria; got {n}. No random "
            "consistency index is published beyond that, so CR cannot be "
            "evaluated for this matrix.")
    # lambda_max >= n for a positive reciprocal matrix; float noise can put it
    # a hair below, which must not report a negative consistency ratio
    ci = max(0.0, (lam - n) / max(1.0, n - 1))
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
    for idx in range(len(datasets)):
        datasets[idx] = None
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
    cov = np.atleast_2d(cov)
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
    if n == 1:
        corr = np.array([[1.0]], dtype=np.float64)
    else:
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
