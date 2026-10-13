# -*- coding: utf-8 -*-
"""
PlanX Suitability Lab - Interactive AHP Studio (Dockable Panel)
================================================================
A visual, pedagogical Analytic Hierarchy Process (AHP) weighting panel for QGIS:
1. Dockable in QGIS (defaults to RightDockWidgetArea), movable and floatable.
2. Interactive pairwise comparison cards with horizontal clickable scale boxes (9..1..9).
3. Smooth range slider sync and active criterion badge highlighting.
4. Zero-churn, in-place live weight distribution cards (%) with rank badges.
5. Publication-grade downloadable AHP infographic charts (300 DPI PNG & Clipboard).
6. Quality Gate: principal eigenvalue (lambda_max), CI, and Consistency Ratio (CR <= 0.10).
7. Preset planning scenarios (Theme A: Hazard Priority, Theme B: Access Priority, Equal 1/N).
8. Direct WLC Suitability tool integration and in-memory AHP vector table creation.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from typing import List, Tuple, Optional, Dict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qgis.PyQt.QtCore import Qt, QMetaType
from qgis.PyQt.QtGui import QColor, QFont, QImage
from qgis.PyQt.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)
import processing


# Saaty's published random consistency index (RI) for n = 1..15. The n = 16..20
# values continue it with Alonso & Lamata (2006), "Consistency in the analytic
# hierarchy process: a new approach", Int. J. Uncertainty, Fuzziness and
# Knowledge-Based Systems 14(4): 445-459, doi:10.1142/S0218488506004114 — the
# standard continuation of Saaty's table, and the reason the criterion ceiling
# below is 20 rather than an arbitrary UI number.
RI_TABLE = {
    1: 0.0,
    2: 0.0,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.54,
    13: 1.56,
    14: 1.57,
    15: 1.59,
    16: 1.5978,
    17: 1.6086,
    18: 1.6181,
    19: 1.6265,
    20: 1.6341,
}

# Hard ceiling on AHP criteria. It is set by the RI table above and by nothing
# else: past n = 20 no RI is published, and the 1.98 * (n - 2) / n approximation
# circulating in the literature inflates it (1.79 where the trend gives ~1.64 at
# n = 21). Since CR = CI / RI, an inflated RI *understates* CR, so a genuinely
# inconsistent matrix would be reported as consistent. Every entry point caps
# here instead of extrapolating.
AHP_MAX_CRITERIA = max(RI_TABLE)

DEFAULT_CRITERIA_LABELS = [
    ("score_01_egim_yuzde", "Slope (% Topography)"),
    ("score_04_hand_su_mesafe", "Flood Safety (HAND)"),
    ("score_06_diri_fay_mesafe", "Earthquake Safety (Active Fault)"),
    ("score_11_yol_mesafe", "Transport Accessibility (Road)"),
    ("score_13_bina_mesafe", "Urban Proximity (Built-up)"),
    ("score_10_tarim_mesafe", "Agricultural Belt Buffer"),
]

THEME_A_MATRIX = [
    [1.0, 0.5, 0.3333, 3.0, 3.0, 2.0],
    [2.0, 1.0, 0.5, 4.0, 4.0, 3.0],
    [3.0, 2.0, 1.0, 5.0, 5.0, 4.0],
    [0.3333, 0.25, 0.2, 1.0, 1.0, 1.0],
    [0.3333, 0.25, 0.2, 1.0, 1.0, 1.0],
    [0.5, 0.3333, 0.25, 1.0, 1.0, 1.0],
]

THEME_B_MATRIX = [
    [1.0, 2.0, 3.0, 0.3333, 0.3333, 0.5],
    [0.5, 1.0, 2.0, 0.3333, 0.3333, 0.5],
    [0.3333, 0.5, 1.0, 0.25, 0.25, 0.3333],
    [3.0, 3.0, 4.0, 1.0, 1.0, 2.0],
    [3.0, 3.0, 4.0, 1.0, 1.0, 2.0],
    [2.0, 2.0, 3.0, 0.5, 0.5, 1.0],
]

SCALE_DEF = [
    (-8, 9.0, "Absolute Importance (9x)"),
    (-7, 8.0, "Very Strong to Extreme (8x)"),
    (-6, 7.0, "Very Strong Importance (7x)"),
    (-5, 6.0, "Strong to Very Strong (6x)"),
    (-4, 5.0, "Strong Importance (5x)"),
    (-3, 4.0, "Moderate to Strong (4x)"),
    (-2, 3.0, "Moderate Importance (3x)"),
    (-1, 2.0, "Equal to Moderate (2x)"),
    (0, 1.0, "Equal Importance (1x)"),
    (1, 1.0 / 2.0, "Equal to Moderate (2x)"),
    (2, 1.0 / 3.0, "Moderate Importance (3x)"),
    (3, 1.0 / 4.0, "Moderate to Strong (4x)"),
    (4, 1.0 / 5.0, "Strong Importance (5x)"),
    (5, 1.0 / 6.0, "Strong to Very Strong (6x)"),
    (6, 1.0 / 7.0, "Very Strong Importance (7x)"),
    (7, 1.0 / 8.0, "Very Strong to Extreme (8x)"),
    (8, 1.0 / 9.0, "Absolute Importance (9x)"),
]

INDEX_TO_RATIO = {idx: ratio for idx, ratio, _ in SCALE_DEF}
INDEX_TO_TERM = {idx: term for idx, _, term in SCALE_DEF}


def ratio_to_index(ratio: float) -> int:
    """Safely maps a ratio into a scale index (-8 to +8) with zero-division guards."""
    if ratio <= 0.0 or abs(ratio - 1.0) < 0.05:
        return 0
    if ratio > 1.0:
        val = int(round(ratio))
        val = max(2, min(9, val))
        return -(val - 1)
    else:
        try:
            inv = int(round(1.0 / ratio))
            inv = max(2, min(9, inv))
            return inv - 1
        except (ZeroDivisionError, OverflowError):
            return 0


def calculate_ahp(matrix: np.ndarray) -> dict:
    """Calculates AHP weights, lambda_max, CI, RI, and CR from a reciprocal matrix."""
    n = matrix.shape[0]
    if n == 0:
        return {"weights": [], "lambda_max": 0.0, "ci": 0.0, "ri": 0.0, "cr": 0.0,
                "cr_ok": True, "cr_evaluable": True}
    if n == 1:
        return {"weights": [1.0], "lambda_max": 1.0, "ci": 0.0, "ri": 0.0, "cr": 0.0,
                "cr_ok": True, "cr_evaluable": True}
    if n == 2:
        w1 = matrix[0, 1] / (1.0 + matrix[0, 1])
        return {"weights": [w1, 1.0 - w1], "lambda_max": 2.0, "ci": 0.0, "ri": 0.0,
                "cr": 0.0, "cr_ok": True, "cr_evaluable": True}

    vals, vecs = np.linalg.eig(matrix)
    max_idx = int(np.argmax(vals.real))
    lam = float(vals[max_idx].real)
    w = np.abs(vecs[:, max_idx].real)
    if w.sum() == 0:
        w = np.ones(n, dtype=float)
    weights = (w / w.sum()).tolist()
    ri = RI_TABLE.get(n)
    ci = max(0.0, (lam - n) / max(1.0, n - 1))
    if ri is None:
        # Only a hand-built matrix can get past AHP_MAX_CRITERIA, since every
        # entry point caps there. Fail closed rather than extrapolate: an
        # inflated RI understates CR and would pass an inconsistent matrix.
        return {
            "weights": weights,
            "lambda_max": lam,
            "ci": ci,
            "ri": 0.0,
            "cr": 0.0,
            "cr_ok": False,
            "cr_evaluable": False,
        }
    cr = 0.0 if ri == 0 else ci / ri
    return {
        "weights": weights,
        "lambda_max": lam,
        "ci": ci,
        "ri": ri,
        "cr": cr,
        "cr_ok": (cr <= 0.10),
        "cr_evaluable": True,
    }


def generate_ahp_infographic(
    criteria_names: List[str],
    weights: List[float],
    cr: float,
    ci: float,
    ri: float,
    lambda_max: float,
    cr_ok: bool,
    matrix: np.ndarray,
    scenario_title: str = "Custom Scenario",
    output_path: Optional[str] = None,
    dpi: int = 300,
    chart_type: str = "infographic",
) -> Optional[bytes]:
    """
    Renders an English publication-grade, academic AHP infographic or specialized chart (300/600 DPI)
    suitable for posters, synthesis reports, and presentations.

    Supported chart_type:
    - 'infographic': All-in-one Executive Summary (Weights Bar + Consistency Card + Reciprocal Matrix Table)
    - 'bar': Dedicated Priority Ranking Bar Chart (Weights, %, Equal Share Benchmark, Rank Badges)
    - 'radar': Multi-Criteria Polar Radar / Spider Web Profile (360-degree polygon, vertex weight markers)
    - 'donut': Proportional Donut & Composition Slices (Scenario in center, percentage callouts)
    - 'heatmap': Saaty Reciprocal Comparison Matrix Heatmap (Log-scale intensity, numeric cells)
    - 'pareto': Pareto Analysis & Cumulative 80/20 Distribution Curve
    """
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Segoe UI", "Arial", "Helvetica"]

    n = len(criteria_names)
    weights_arr = np.array(weights, dtype=float)

    if chart_type == "bar":
        fig, ax = plt.subplots(figsize=(10.5, max(5.0, n * 0.45)), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")

        pairs = sorted(zip(criteria_names, weights_arr), key=lambda x: x[1])
        s_names = [p[0] for p in pairs]
        s_weights = [p[1] for p in pairs]
        y_pos = np.arange(n)

        colors = plt.cm.viridis(np.linspace(0.35, 0.85, n))
        bars = ax.barh(y_pos, s_weights, height=0.55, color=colors, edgecolor="#0f172a", linewidth=0.8, alpha=0.92)

        max_w = max(s_weights) if s_weights else 0.5
        mean_w = 1.0 / n if n > 0 else 0.0
        ax.axvline(mean_w, color="#ef4444", linestyle="--", linewidth=1.2, alpha=0.75, label=f"Equal Share Benchmark ({mean_w*100:.1f}%)")

        for idx, (bar, w) in enumerate(zip(bars, s_weights)):
            rank = n - idx
            label = f" #{rank} | {w*100:4.1f}% (w={w:.4f})"
            ax.text(w + (max_w * 0.02), bar.get_y() + bar.get_height() / 2.0, label, va="center", ha="left", fontsize=9.5, fontweight="bold", color="#0f172a")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(s_names, fontsize=10, fontweight="bold", color="#1e293b")
        ax.set_xlabel("Eigenvector Weight Share", fontsize=10.5, fontweight="bold", color="#334155")
        ax.set_xlim(0, max_w * 1.45)
        ax.grid(axis="x", linestyle="--", alpha=0.5, color="#cbd5e1")
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#94a3b8")
        ax.spines["bottom"].set_color("#94a3b8")

        status_txt = f"CR = {cr:.4f} ({'Consistent <= 0.10' if cr_ok else 'Inconsistent > 0.10'})"
        ax.set_title(f"AHP Criterion Weights & Priority Ranking\nScenario: {scenario_title}  |  {status_txt}", fontsize=11.5, fontweight="bold", color="#0f172a", pad=12)
        ax.legend(loc="lower right", frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=8.5)

        fig.text(0.12, 0.02, "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset", fontsize=8, color="#64748b")
        plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    elif chart_type == "radar":
        fig = plt.figure(figsize=(9, 9), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")
        ax = fig.add_subplot(111, polar=True)

        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        r_weights = weights_arr.tolist()
        angles += angles[:1]
        r_weights += r_weights[:1]

        ax.plot(angles, r_weights, color="#0f766e", linewidth=2.4, linestyle="solid")
        ax.fill(angles, r_weights, color="#14b8a6", alpha=0.35)
        ax.scatter(angles[:-1], weights_arr, color="#0f766e", s=45, zorder=5)

        ax.set_xticks(angles[:-1])
        label_texts = [f"{name}\n({w*100:.1f}%)" for name, w in zip(criteria_names, weights_arr)]
        ax.set_xticklabels(label_texts, fontsize=9.5, fontweight="bold", color="#1e293b")

        max_val = max(weights_arr) if len(weights_arr) else 0.5
        ax.set_ylim(0, max_val * 1.25)
        ax.grid(color="#cbd5e1", linestyle="--", linewidth=0.8)
        ax.spines["polar"].set_color("#94a3b8")

        status_txt = f"CR: {cr:.4f} ({'Consistent' if cr_ok else 'Inconsistent'})"
        ax.set_title(f"AHP Multi-Criteria Radar Profile\nScenario: {scenario_title}  •  {status_txt}", fontsize=12, fontweight="bold", color="#0f172a", pad=24)

        fig.text(0.5, 0.03, "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset", ha="center", fontsize=8.5, color="#64748b")
        plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    elif chart_type == "donut":
        fig, ax = plt.subplots(figsize=(9.5, 7.5), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")

        pairs = sorted(zip(criteria_names, weights_arr), key=lambda x: x[1], reverse=True)
        s_names = [p[0] for p in pairs]
        s_weights = [p[1] for p in pairs]

        colors = plt.cm.Spectral(np.linspace(0.15, 0.85, n))
        wedges, texts, autotexts = ax.pie(
            s_weights,
            labels=s_names,
            autopct="%1.1f%%",
            pctdistance=0.76,
            startangle=140,
            colors=colors,
            wedgeprops=dict(width=0.42, edgecolor="#ffffff", linewidth=2),
            textprops=dict(color="#1e293b", fontsize=9.5, fontweight="bold"),
        )
        for at in autotexts:
            at.set_fontsize(8.5)
            at.set_fontweight("bold")
            at.set_color("#0f172a")

        ax.text(0, 0.08, f"{scenario_title}", ha="center", va="center", fontsize=10.5, fontweight="bold", color="#0f172a")
        ax.text(0, -0.06, f"Criteria: {n}\nCR: {cr:.4f}", ha="center", va="center", fontsize=9, color="#475569")

        status_txt = "Consistent (CR <= 0.10)" if cr_ok else "Inconsistent (CR > 0.10)"
        ax.set_title(f"AHP Weight Proportional Composition\nStatus: {status_txt}", fontsize=12, fontweight="bold", color="#0f172a", pad=12)
        fig.text(0.5, 0.03, "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset", ha="center", fontsize=8.5, color="#64748b")
        plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    elif chart_type == "heatmap":
        fig, ax = plt.subplots(figsize=(max(8.0, n * 0.8), max(7.0, n * 0.7)), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")

        safe_mat = np.where(matrix <= 1e-5, 1.0, matrix)
        log_matrix = np.log2(np.clip(safe_mat, 1.0/9.0, 9.0))
        cax = ax.matshow(log_matrix, cmap="coolwarm", vmin=-3.17, vmax=3.17, alpha=0.88)

        cbar = fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_ticks([-3.17, -2.0, -1.0, 0, 1.0, 2.0, 3.17])
        cbar.set_ticklabels(["1/9 (Min)", "1/4", "1/2", "1 (Equal)", "2", "4", "9 (Max)"])
        cbar.ax.tick_params(labelsize=8)
        cbar.set_label("Saaty Preference Scale Relative to Diagonal", fontsize=9, fontweight="bold", color="#334155")

        short_names = [nm[:12] + ".." if len(nm) > 12 else nm for nm in criteria_names]
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(short_names, rotation=35, ha="left", fontsize=9, fontweight="bold", color="#1e293b")
        ax.set_yticklabels(short_names, fontsize=9, fontweight="bold", color="#1e293b")

        for i in range(n):
            for j in range(n):
                val = matrix[i, j]
                if abs(val - 1.0) < 1e-4:
                    txt = "1"
                elif val <= 1e-5:
                    txt = "0"
                elif val >= 1.0:
                    txt = f"{val:.1f}".rstrip("0").rstrip(".")
                else:
                    inv = int(round(1.0 / max(val, 1e-5)))
                    txt = f"1/{inv}"
                log_v = log_matrix[i, j]
                t_color = "#ffffff" if abs(log_v) > 2.0 else "#0f172a"
                ax.text(j, i, txt, ha="center", va="center", fontsize=8.5, fontweight="bold", color=t_color)

        ax.set_title(f"Saaty Pairwise Comparison Matrix Heatmap ({n}x{n})\nCR: {cr:.4f} ({'Consistent' if cr_ok else 'Inconsistent'})", fontsize=11.5, fontweight="bold", color="#0f172a", pad=18)
        fig.text(0.5, 0.02, "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset", ha="center", fontsize=8, color="#64748b")
        plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    elif chart_type == "pareto":
        fig, ax1 = plt.subplots(figsize=(10.5, 6.2), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")

        pairs = sorted(zip(criteria_names, weights_arr), key=lambda x: x[1], reverse=True)
        s_names = [p[0] for p in pairs]
        s_weights = [p[1] for p in pairs]
        cum_weights = np.cumsum(s_weights) * 100.0
        x_pos = np.arange(n)

        colors = plt.cm.viridis(np.linspace(0.40, 0.85, n))
        bars = ax1.bar(x_pos, [w * 100 for w in s_weights], color=colors, edgecolor="#0f172a", linewidth=0.8, width=0.55, label="Individual Criterion Weight (%)")
        ax1.set_ylabel("Individual Weight (%)", fontsize=10, fontweight="bold", color="#0f766e")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(s_names, rotation=25, ha="right", fontsize=9, fontweight="bold", color="#1e293b")
        ax1.set_ylim(0, max([w * 100 for w in s_weights]) * 1.25)
        ax1.grid(axis="y", linestyle="--", alpha=0.4, color="#cbd5e1")

        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2.0, h + 0.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#0f172a")

        ax2 = ax1.twinx()
        ax2.plot(x_pos, cum_weights, color="#dc2626", linewidth=2.4, marker="o", markersize=6, label="Cumulative Share (%)")
        ax2.axhline(80.0, color="#f59e0b", linestyle=":", linewidth=1.5, label="80% Pareto Dominance Threshold")
        ax2.set_ylabel("Cumulative Share (%)", fontsize=10, fontweight="bold", color="#dc2626")
        ax2.set_ylim(0, 105)

        for x, c in zip(x_pos, cum_weights):
            ax2.text(x, c + 2.0, f"{c:.0f}%", ha="center", va="bottom", fontsize=8, color="#dc2626", fontweight="bold")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="center right", frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=8.5)

        ax1.set_title(f"AHP Pareto Analysis & Cumulative Weight Distribution\nScenario: {scenario_title}  |  CR: {cr:.4f}", fontsize=11.5, fontweight="bold", color="#0f172a", pad=12)
        fig.text(0.12, 0.02, "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset", fontsize=8, color="#64748b")
        plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    else:
        # Default 'infographic' multi-panel report
        fig = plt.figure(figsize=(13, 7.6), dpi=dpi)
        fig.patch.set_facecolor("#ffffff")

        fig.suptitle(
            "PlanX Suitability Lab — Analytic Hierarchy Process (AHP) Weight & Consistency Report",
            fontsize=13.5,
            fontweight="bold",
            color="#0f172a",
            y=0.965,
        )
        fig.text(
            0.5,
            0.925,
            f"Scenario: {scenario_title}  |  Method: Saaty (1980) Eigenvector Method  |  Criteria Count: {len(criteria_names)}",
            ha="center",
            fontsize=10,
            color="#475569",
        )

        gs = fig.add_gridspec(
            2,
            2,
            width_ratios=[1.3, 1.1],
            height_ratios=[0.85, 1.15],
            left=0.22,
            right=0.94,
            top=0.86,
            bottom=0.10,
            wspace=0.32,
            hspace=0.28,
        )

        # 1. Bar Chart (Left Column)
        ax_bar = fig.add_subplot(gs[:, 0])
        pairs = list(zip(criteria_names, weights_arr))
        pairs_sorted = sorted(pairs, key=lambda x: x[1])
        sorted_names = [p[0] for p in pairs_sorted]
        sorted_weights = [p[1] for p in pairs_sorted]
        y_pos = np.arange(len(sorted_names))

        colors = plt.cm.viridis(np.linspace(0.40, 0.82, len(sorted_names)))
        bars = ax_bar.barh(y_pos, sorted_weights, height=0.55, color=colors, edgecolor="#0f172a", linewidth=0.7, alpha=0.9)

        max_w = max(sorted_weights) if sorted_weights else 0.5
        for bar, w in zip(bars, sorted_weights):
            pct_text = f" {w*100:4.1f}% ({w:.4f})"
            ax_bar.text(
                w + (max_w * 0.02),
                bar.get_y() + bar.get_height() / 2.0,
                pct_text,
                va="center",
                ha="left",
                fontsize=9.5,
                fontweight="bold",
                color="#0f172a",
            )

        ax_bar.set_yticks(y_pos)
        ax_bar.set_yticklabels(sorted_names, fontsize=10, fontweight="bold", color="#1e293b")
        ax_bar.set_xlabel("Eigenvector Weight Share", fontsize=10, fontweight="bold", color="#334155")
        ax_bar.set_xlim(0, max_w * 1.38)
        ax_bar.grid(axis="x", linestyle="--", alpha=0.45, color="#cbd5e1")
        ax_bar.set_axisbelow(True)
        ax_bar.spines["top"].set_visible(False)
        ax_bar.spines["right"].set_visible(False)
        ax_bar.spines["left"].set_color("#94a3b8")
        ax_bar.spines["bottom"].set_color("#94a3b8")
        ax_bar.set_title("Criterion Weights & Priority Ranking", fontsize=11, fontweight="bold", color="#1e293b", pad=12)

        # 2. Consistency Summary Card (Top Right)
        ax_card = fig.add_subplot(gs[0, 1])
        ax_card.axis("off")

        status_bg = "#f0fdf4" if cr_ok else "#fef2f2"
        status_border = "#16a34a" if cr_ok else "#dc2626"
        badge_str = "[ CONSISTENT  (CR <= 0.10) ]" if cr_ok else "[ INCONSISTENT (CR > 0.10) ]"

        bbox = dict(boxstyle="round,pad=0.7", facecolor=status_bg, edgecolor=status_border, linewidth=1.5)
        card_info = (
            f"Saaty Consistency Check: {badge_str}\n"
            f"--------------------------------------------------\n"
            f"CR (Consistency Ratio)  : {cr:.4f}  (Threshold: <= 0.1000)\n"
            f"lambda max (Eigenvalue) : {lambda_max:.4f}\n"
            f"CI (Consistency Index) : {ci:.4f}\n"
            f"RI (Random Index)       : {ri:.2f}  (n = {len(criteria_names)})\n\n"
            f"{'-> Judgments are consistent. Reliable for WLC analysis.' if cr_ok else '-> WARNING: Consistency threshold exceeded! Revise comparisons.'}"
        )
        ax_card.text(
            0.02,
            0.95,
            card_info,
            va="top",
            ha="left",
            fontsize=9.0,
            color="#0f172a",
            bbox=bbox,
            family="monospace",
        )

        # 3. Saaty Reciprocal Matrix (Bottom Right)
        ax_mat = fig.add_subplot(gs[1, 1])
        ax_mat.axis("off")

        short_headers = [f"C{i+1}" for i in range(n)]
        cell_data = []
        for i in range(n):
            row = []
            for j in range(n):
                val = matrix[i, j]
                if abs(val - 1.0) < 1e-4:
                    txt = "1"
                elif val <= 1e-5:
                    txt = "0"
                elif val >= 1.0:
                    txt = f"{val:.1f}".rstrip("0").rstrip(".")
                else:
                    inv = int(round(1.0 / max(val, 1e-5)))
                    txt = f"1/{inv}"
                row.append(txt)
            cell_data.append(row)

        table = ax_mat.table(
            cellText=cell_data,
            rowLabels=short_headers,
            colLabels=short_headers,
            cellLoc="center",
            loc="upper center",
            bbox=[0.05, 0.26, 0.90, 0.68],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)

        for (i, j), cell in table.get_celld().items():
            if i == 0 or j == -1:
                cell.set_facecolor("#e2e8f0")
                cell.set_text_props(weight="bold", color="#1e293b")
            elif i - 1 == j:
                cell.set_facecolor("#cbd5e1")
            else:
                cell.set_facecolor("#ffffff")
            cell.set_edgecolor("#94a3b8")
            cell.set_linewidth(0.6)

        ax_mat.set_title(f"Saaty Reciprocal Comparison Matrix ({n}x{n})", fontsize=10.5, fontweight="bold", color="#1e293b", pad=10)

        legend_items = [f"C{i+1}: {criteria_names[i]}" for i in range(n)]
        legend_line1 = "  |  ".join(legend_items[:3])
        legend_line2 = "  |  ".join(legend_items[3:]) if n > 3 else ""
        legend_str = legend_line1 + ("\n" + legend_line2 if legend_line2 else "")
        ax_mat.text(
            0.5,
            0.05,
            legend_str,
            ha="center",
            va="center",
            fontsize=8.0,
            color="#475569",
            style="italic",
        )

        fig.text(
            0.22,
            0.03,
            "PlanX Suitability Lab  •  Multi-Criteria Decision Analysis (MCDA) Toolset",
            fontsize=8.5,
            color="#64748b",
        )

    if output_path:
        fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor())
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()


class PairCardWidget(QFrame):
    """
    Pairwise comparison card:
    Header: [ Criterion A ] vs [ Criterion B ] with visual chip highlighting.
    Body: Row of clickable boxes [9..1..9] and synchronized slider.
    Footer: Dynamic verbal badge explaining the chosen Saaty preference.
    """

    def __init__(self, r: int, c: int, name_a: str, name_b: str, initial_ratio: float, parent_panel: AHPStudioDockWidget):
        super().__init__()
        self.r = r
        self.c = c
        self.name_a = name_a
        self.name_b = name_b
        self.panel = parent_panel

        self.setStyleSheet(
            "PairCardWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 2px; }"
            "PairCardWidget:hover { border: 1px solid #cbd5e1; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Header: [ Criterion A ]  VS  [ Criterion B ]
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.chip_a = QLabel(self.name_a)
        self.chip_a.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip_a.setFixedHeight(30)
        header_layout.addWidget(self.chip_a, 1)

        vs_lbl = QLabel("VS")
        vs_lbl.setStyleSheet("color: #94a3b8; font-weight: 900; font-style: italic; font-size: 11px;")
        header_layout.addWidget(vs_lbl, 0)

        self.chip_b = QLabel(self.name_b)
        self.chip_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip_b.setFixedHeight(30)
        header_layout.addWidget(self.chip_b, 1)

        layout.addLayout(header_layout)

        # 2. Horizontal Button Boxes (-8 to +8, total 17 buttons)
        boxes_layout = QHBoxLayout()
        boxes_layout.setSpacing(2)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons_map: Dict[int, QPushButton] = {}

        btn_labels = [
            (-8, "9"), (-7, "8"), (-6, "7"), (-5, "6"), (-4, "5"), (-3, "4"), (-2, "3"), (-1, "2"),
            (0, "1"),
            (1, "2"), (2, "3"), (3, "4"), (4, "5"), (5, "6"), (6, "7"), (7, "8"), (8, "9")
        ]

        for idx, text in btn_labels:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedSize(22, 24)
            weight_font = "bold" if text in ("1", "3", "5", "7", "9") else "normal"
            btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold if weight_font == "bold" else QFont.Weight.Normal))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.button_group.addButton(btn, idx)
            self.buttons_map[idx] = btn
            boxes_layout.addWidget(btn)

        layout.addLayout(boxes_layout)

        # 3. Synchronized Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-8, 8)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(2)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.setStyleSheet(
            """
            QSlider::groove:horizontal { height: 5px; background: #cbd5e1; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #0284c7; border-radius: 2px; }
            QSlider::handle:horizontal { background: #0369a1; border: 2px solid #ffffff; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #075985; }
            """
        )
        layout.addWidget(self.slider)

        # 4. Dynamic Verbal Badge
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        self.badge_lbl = QLabel()
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_lbl.setFixedHeight(24)
        badge_row.addWidget(self.badge_lbl)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        self.button_group.idClicked.connect(self._on_button_clicked)
        self.slider.valueChanged.connect(self._on_slider_moved)

        init_idx = ratio_to_index(initial_ratio)
        self.set_scale_index(init_idx, emit=False)

    def set_scale_index(self, idx: int, emit: bool = True):
        idx = max(-8, min(8, idx))
        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)

        btn = self.buttons_map.get(idx)
        if btn:
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)

        self._update_appearance(idx)

        if emit:
            ratio = INDEX_TO_RATIO.get(idx, 1.0)
            self.panel.on_card_value_changed(self.r, self.c, ratio)

    def _on_button_clicked(self, idx: int):
        self.set_scale_index(idx, emit=True)

    def _on_slider_moved(self, val: int):
        self.set_scale_index(val, emit=True)

    def _update_appearance(self, idx: int):
        term = INDEX_TO_TERM.get(idx, "Equal Importance")

        for b_idx, btn in self.buttons_map.items():
            if b_idx == idx:
                if idx < 0:
                    btn.setStyleSheet("background: #0f766e; color: white; border: 1px solid #115e59; border-radius: 3px; font-weight: bold;")
                elif idx > 0:
                    btn.setStyleSheet("background: #0284c7; color: white; border: 1px solid #0369a1; border-radius: 3px; font-weight: bold;")
                else:
                    btn.setStyleSheet("background: #475569; color: white; border: 1px solid #334155; border-radius: 3px; font-weight: bold;")
            else:
                btn.setStyleSheet("background: #ffffff; color: #475569; border: 1px solid #cbd5e1; border-radius: 3px;")

        if idx < 0:
            self.chip_a.setStyleSheet(
                "background: #0f766e; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 3px 8px; border: 1px solid #115e59; font-size: 11px;"
            )
            self.chip_b.setStyleSheet(
                "background: #f8fafc; color: #64748b; font-weight: normal; border-radius: 6px; padding: 3px 8px; border: 1px solid #e2e8f0; font-size: 11px;"
            )
            self.badge_lbl.setText(f"🛡️ {self.name_a} preferred: {term}")
            self.badge_lbl.setStyleSheet(
                "background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; border-radius: 12px; padding: 2px 10px; font-weight: bold; font-size: 10px;"
            )
        elif idx > 0:
            self.chip_a.setStyleSheet(
                "background: #f8fafc; color: #64748b; font-weight: normal; border-radius: 6px; padding: 3px 8px; border: 1px solid #e2e8f0; font-size: 11px;"
            )
            self.chip_b.setStyleSheet(
                "background: #0284c7; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 3px 8px; border: 1px solid #0369a1; font-size: 11px;"
            )
            self.badge_lbl.setText(f"🌊 {self.name_b} preferred: {term}")
            self.badge_lbl.setStyleSheet(
                "background: #f0f9ff; color: #075985; border: 1px solid #bae6fd; border-radius: 12px; padding: 2px 10px; font-weight: bold; font-size: 10px;"
            )
        else:
            self.chip_a.setStyleSheet(
                "background: #f1f5f9; color: #334155; font-weight: bold; border-radius: 6px; padding: 3px 8px; border: 1px solid #cbd5e1; font-size: 11px;"
            )
            self.chip_b.setStyleSheet(
                "background: #f1f5f9; color: #334155; font-weight: bold; border-radius: 6px; padding: 3px 8px; border: 1px solid #cbd5e1; font-size: 11px;"
            )
            self.badge_lbl.setText("⚖️ Equal Importance (1x)")
            self.badge_lbl.setStyleSheet(
                "background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 12px; padding: 2px 10px; font-weight: bold; font-size: 10px;"
            )


class CriterionWeightWidget(QFrame):
    """
    Sleek, modern criterion weight display card:
    Row 1: [Rank #1] [Criterion Name] ... [ 36.7% (0.3666)]
    Row 2: Full-width modern progress bar with dual-color gradient
    Updated in-place with ZERO DOM/widget churn.
    """

    def __init__(self, key: str, display_name: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.display_name = display_name
        self.setStyleSheet(
            "CriterionWeightWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; } "
            "CriterionWeightWidget:hover { border: 1px solid #cbd5e1; background: #f8fafc; }"
        )
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(8, 5, 8, 5)
        vbox.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.rank_badge = QLabel("#1")
        self.rank_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_badge.setFixedSize(24, 18)
        self.rank_badge.setStyleSheet(
            "background: #1e293b; color: #ffffff; font-weight: bold; font-size: 10px; border-radius: 3px;"
        )
        top_row.addWidget(self.rank_badge)

        self.name_lbl = QLabel(display_name)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #1e293b;")
        top_row.addWidget(self.name_lbl, 1)

        self.val_lbl = QLabel("0.0% (0.0000)")
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.val_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #0d9488;")
        top_row.addWidget(self.val_lbl)

        vbox.addLayout(top_row)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(8)
        self.pbar.setStyleSheet(
            "QProgressBar { background: #e2e8f0; border-radius: 4px; border: none; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d9488, stop:1 #2563eb); border-radius: 4px; }"
        )
        vbox.addWidget(self.pbar)

    def set_data(self, weight: float, rank: int):
        pct = weight * 100.0
        self.val_lbl.setText(f"{pct:4.1f}% ({weight:.4f})")
        self.pbar.setValue(int(weight * 1000))
        self.rank_badge.setText(f"#{rank}")
        if rank == 1:
            self.rank_badge.setStyleSheet(
                "background: #0f766e; color: white; font-weight: bold; font-size: 10px; border-radius: 3px;"
            )
            self.val_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #0f766e;")
        elif rank <= 3:
            self.rank_badge.setStyleSheet(
                "background: #0284c7; color: white; font-weight: bold; font-size: 10px; border-radius: 3px;"
            )
            self.val_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #0284c7;")
        else:
            self.rank_badge.setStyleSheet(
                "background: #64748b; color: white; font-weight: bold; font-size: 10px; border-radius: 3px;"
            )
            self.val_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")


class AHPStudioDockWidget(QDockWidget):
    """
    Dockable interactive Analytic Hierarchy Process (AHP) weighting studio for QGIS.
    Dockable anywhere (RightDockWidgetArea by default), movable and floatable.
    """

    def __init__(self, iface=None, parent=None):
        super().__init__("PlanX AHP Studio — Interactive Weight Designer", parent)
        self.iface = iface
        self.setObjectName("PlanX_AHP_Studio_Dock")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        self.criteria_keys: List[str] = []
        self.criteria_names: List[str] = []
        self.matrix: np.ndarray = np.ones((6, 6), dtype=float)
        self.card_widgets: Dict[Tuple[int, int], PairCardWidget] = {}
        self.weight_widgets: List[CriterionWeightWidget] = []
        self.current_scenario_title: str = "Theme A (Hazard Priority)"

        self._updating_matrix = False
        self._init_default_criteria()
        self._setup_ui()
        n = len(self.criteria_names)
        if n == 6 and self.criteria_keys == [k for k, _ in DEFAULT_CRITERIA_LABELS]:
            self._load_matrix(np.array(THEME_A_MATRIX, dtype=float), scenario_name="Theme A (Hazard Priority)")
        else:
            self._load_matrix(np.ones((n, n), dtype=float), scenario_name="Project Layers (Equal)")

    def _init_default_criteria(self):
        project_layers = [lyr for lyr in QgsProject.instance().mapLayers().values()
                          if isinstance(lyr, QgsRasterLayer)]
        score_layers = [lyr for lyr in project_layers
                        if "score_" in lyr.name().lower() or "score" in lyr.name().lower()]

        if len(score_layers) >= 2:
            self.criteria_keys = [lyr.name() for lyr in score_layers[:AHP_MAX_CRITERIA]]
            self.criteria_names = [lyr.name() for lyr in score_layers[:AHP_MAX_CRITERIA]]
        else:
            self.criteria_keys = [k for k, _ in DEFAULT_CRITERIA_LABELS]
            self.criteria_names = [f"{lbl}" for _, lbl in DEFAULT_CRITERIA_LABELS]

        n = len(self.criteria_keys)
        self.matrix = np.ones((n, n), dtype=float)

    def _setup_ui(self):
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Header Banner with Presets & Live CR Badge
        header = QFrame()
        header.setStyleSheet("background: #1e293b; border-radius: 6px; padding: 6px;")
        h_box = QVBoxLayout(header)
        h_box.setContentsMargins(8, 6, 8, 6)
        h_box.setSpacing(6)

        title_row = QHBoxLayout()
        title_lbl = QLabel("🎯 AHP Interactive Studio")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        self.header_cr_badge = QLabel("🟢 CR = 0.0115")
        self.header_cr_badge.setStyleSheet(
            "background: #065f46; color: #a7f3d0; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
        )
        title_row.addWidget(self.header_cr_badge)
        h_box.addLayout(title_row)

        # Scenario Presets
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)

        btn_theme_a = QPushButton("🛡️ Theme A (Hazard)")
        btn_theme_a.setStyleSheet("background: #0f766e; color: white; font-weight: bold; padding: 5px 8px; border-radius: 4px; font-size: 11px;")
        btn_theme_a.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme_a.clicked.connect(self._apply_tema_a)
        preset_row.addWidget(btn_theme_a)

        btn_theme_b = QPushButton("🚗 Theme B (Access)")
        btn_theme_b.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 5px 8px; border-radius: 4px; font-size: 11px;")
        btn_theme_b.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme_b.clicked.connect(self._apply_tema_b)
        preset_row.addWidget(btn_theme_b)

        btn_equal = QPushButton("⚖️ Equal (1/N)")
        btn_equal.setStyleSheet("background: #475569; color: white; font-weight: bold; padding: 5px 8px; border-radius: 4px; font-size: 11px;")
        btn_equal.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_equal.clicked.connect(self._apply_equal)
        preset_row.addWidget(btn_equal)

        h_box.addLayout(preset_row)
        main_layout.addWidget(header)

        # Criteria bar
        crit_bar = QHBoxLayout()
        self.crit_summary_lbl = QLabel(f"Active Criteria: {len(self.criteria_names)}")
        self.crit_summary_lbl.setStyleSheet("font-weight: bold; color: #0f766e; font-size: 11px;")
        crit_bar.addWidget(self.crit_summary_lbl)
        crit_bar.addStretch()

        btn_choose = QPushButton("📁 Choose Layers...")
        btn_choose.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-size: 10px;")
        btn_choose.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_choose.clicked.connect(self._choose_project_layers_dialog)
        crit_bar.addWidget(btn_choose)

        btn_auto_pick = QPushButton("⚡ Auto-detect Score Layers")
        btn_auto_pick.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-size: 10px;")
        btn_auto_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_auto_pick.clicked.connect(self._auto_pick_score_layers)
        crit_bar.addWidget(btn_auto_pick)
        main_layout.addLayout(crit_bar)

        # Main Vertical Splitter: Top = Pairwise / Matrix; Bottom = Weights / Diagnostics / Actions
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # === UPPER PANE: Tabs (Cards vs Matrix) ===
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { font-weight: bold; padding: 5px 10px; font-size: 11px; }")

        # Tab 1: Cards
        self.cards_tab = QWidget()
        cards_vbox = QVBoxLayout(self.cards_tab)
        cards_vbox.setContentsMargins(4, 4, 4, 4)
        cards_vbox.setSpacing(4)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll_content = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_scroll_content)
        self.cards_layout.setSpacing(6)
        self.cards_scroll.setWidget(self.cards_scroll_content)
        cards_vbox.addWidget(self.cards_scroll)

        tabs.addTab(self.cards_tab, "🎛️ Pairwise Cards")

        # Tab 2: Matrix
        self.matrix_tab = QWidget()
        matrix_vbox = QVBoxLayout(self.matrix_tab)
        matrix_vbox.setContentsMargins(4, 4, 4, 4)

        self.matrix_table = QTableWidget()
        self.matrix_table.setStyleSheet("QTableWidget { gridline-color: #cbd5e1; font-size: 11px; }")
        self.matrix_table.cellChanged.connect(self._on_table_cell_changed)
        matrix_vbox.addWidget(self.matrix_table)

        tabs.addTab(self.matrix_tab, "🔢 Reciprocal Matrix Grid")
        splitter.addWidget(tabs)

        # === LOWER PANE: Scrollable Diagnostics, Weights & Actions ===
        bottom_scroll = QScrollArea()
        bottom_scroll.setWidgetResizable(True)
        bottom_content = QWidget()
        bottom_layout = QVBoxLayout(bottom_content)
        bottom_layout.setContentsMargins(4, 4, 4, 4)
        bottom_layout.setSpacing(8)

        # 1. Quality Gate Card
        self.cr_card = QFrame()
        self.cr_card.setStyleSheet("border-radius: 6px; padding: 8px; background: #e8f5e9; border: 1px solid #4caf50;")
        cr_vbox = QVBoxLayout(self.cr_card)
        cr_vbox.setContentsMargins(8, 6, 8, 6)
        cr_vbox.setSpacing(4)

        self.cr_badge_lbl = QLabel("🟢 CONSISTENT (CR = 0.0115 ≤ 0.10)")
        self.cr_badge_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #2e7d32;")
        cr_vbox.addWidget(self.cr_badge_lbl)

        self.cr_desc_lbl = QLabel(
            "Judgments satisfy Saaty's consistency criterion (CR ≤ 0.10). The pairwise matrix is mathematically sound and reliable for WLC suitability analysis."
        )
        self.cr_desc_lbl.setStyleSheet("font-size: 10px; color: #1b5e20;")
        self.cr_desc_lbl.setWordWrap(True)
        cr_vbox.addWidget(self.cr_desc_lbl)

        stats_grid = QGridLayout()
        self.stat_lambda = QLabel("6.071")
        self.stat_ci = QLabel("0.014")
        self.stat_ri = QLabel("1.24")

        for lbl, val_w, col in [
            ("λ max (Eigenvalue):", self.stat_lambda, 0),
            ("CI (Consistency Index):", self.stat_ci, 1),
            ("RI (Random Index):", self.stat_ri, 2),
        ]:
            caption = QLabel(lbl)
            caption.setStyleSheet("font-size: 10px; color: #64748b;")
            val_w.setStyleSheet("font-size: 10px; font-weight: bold; color: #0f172a;")
            stats_grid.addWidget(caption, 0, col * 2)
            stats_grid.addWidget(val_w, 0, col * 2 + 1)
        cr_vbox.addLayout(stats_grid)
        bottom_layout.addWidget(self.cr_card)

        # 2. Live Weights Distribution
        weights_group = QGroupBox("Live Weight Distribution (Weights %)")
        weights_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1e293b; }")
        self.weights_vbox = QVBoxLayout(weights_group)
        self.weights_vbox.setContentsMargins(8, 8, 8, 8)
        self.weights_vbox.setSpacing(5)

        self.weights_container = QWidget()
        self.weights_container_layout = QVBoxLayout(self.weights_container)
        self.weights_container_layout.setContentsMargins(0, 0, 0, 0)
        self.weights_container_layout.setSpacing(5)
        self.weights_vbox.addWidget(self.weights_container)

        # Export Controls Box
        export_box = QGroupBox("📊 Publication Chart & Infographic Export")
        export_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #0f766e; border: 1px solid #99f6e4; border-radius: 6px; margin-top: 6px; padding-top: 10px; background: #f0fdfa; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
        )
        export_vbox = QVBoxLayout(export_box)
        export_vbox.setContentsMargins(6, 6, 6, 6)
        export_vbox.setSpacing(5)

        # Row 1: Chart Type and DPI selectors
        opt_row = QHBoxLayout()
        opt_row.setSpacing(5)

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            "📊 Executive Summary (All-in-One)",
            "📶 Priority Ranking Bar Chart",
            "🕸️ Multi-Criteria Radar Profile",
            "🍩 Proportional Donut Composition",
            "🔥 Pairwise Matrix Heatmap",
            "📈 Pareto & Cumulative 80/20 Curve",
        ])
        self.chart_type_combo.setStyleSheet("font-size: 11px; padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        opt_row.addWidget(self.chart_type_combo, 3)

        self.chart_dpi_combo = QComboBox()
        self.chart_dpi_combo.addItem("300 DPI (Publication)", 300)
        self.chart_dpi_combo.addItem("600 DPI (Ultra Poster)", 600)
        self.chart_dpi_combo.addItem("150 DPI (Web & Screen)", 150)
        self.chart_dpi_combo.setStyleSheet("font-size: 11px; padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        opt_row.addWidget(self.chart_dpi_combo, 2)

        export_vbox.addLayout(opt_row)

        # Row 2: Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)

        btn_export_png = QPushButton("💾 Export Chart (PNG)")
        btn_export_png.setStyleSheet(
            "background: #0f766e; color: white; font-weight: bold; padding: 6px 8px; border-radius: 4px; font-size: 11px;"
        )
        btn_export_png.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_png.setToolTip("Export the selected chart type in high resolution (PNG) for posters and reports.")
        btn_export_png.clicked.connect(self._export_chart_png)
        btn_row.addWidget(btn_export_png, 2)

        btn_copy_chart = QPushButton("📋 Copy to Clipboard")
        btn_copy_chart.setStyleSheet(
            "background: #f1f5f9; color: #1e293b; font-weight: bold; padding: 6px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px;"
        )
        btn_copy_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_chart.setToolTip("Copies the selected high-resolution chart directly to system clipboard.")
        btn_copy_chart.clicked.connect(self._copy_chart_to_clipboard)
        btn_row.addWidget(btn_copy_chart, 2)

        btn_export_bundle = QPushButton("📦 Export All 6 Charts")
        btn_export_bundle.setStyleSheet(
            "background: #f8fafc; color: #0284c7; font-weight: bold; padding: 6px 6px; border: 1px solid #bae6fd; border-radius: 4px; font-size: 11px;"
        )
        btn_export_bundle.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_bundle.setToolTip("Exports all 6 publication charts at once into a target folder.")
        btn_export_bundle.clicked.connect(self._export_all_charts_bundle)
        btn_row.addWidget(btn_export_bundle, 2)

        export_vbox.addLayout(btn_row)
        self.weights_vbox.addWidget(export_box)
        bottom_layout.addWidget(weights_group)

        # 3. Results & Integration
        actions_group = QGroupBox("Results & Synthesis Workflow")
        actions_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1e293b; }")
        actions_vbox = QVBoxLayout(actions_group)
        actions_vbox.setContentsMargins(8, 8, 8, 8)
        actions_vbox.setSpacing(6)

        csv_row = QHBoxLayout()
        csv_lbl = QLabel("WLC CSV:")
        csv_lbl.setStyleSheet("font-weight: bold; font-size: 10px;")
        self.csv_line = QLineEdit()
        self.csv_line.setReadOnly(True)
        self.csv_line.setStyleSheet("background: #f8fafc; font-family: monospace; font-size: 10px;")
        btn_copy_csv = QPushButton("📋 Copy")
        btn_copy_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_csv.clicked.connect(self._copy_csv_weights)
        csv_row.addWidget(csv_lbl)
        csv_row.addWidget(self.csv_line)
        csv_row.addWidget(btn_copy_csv)
        actions_vbox.addLayout(csv_row)

        btn_add_layer = QPushButton("💾 Add AHP Table to QGIS (Vector Layer)")
        btn_add_layer.setStyleSheet("background: #0f766e; color: white; font-weight: bold; padding: 6px; border-radius: 4px; font-size: 11px;")
        btn_add_layer.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_layer.clicked.connect(self._add_ahp_vector_layer)
        actions_vbox.addWidget(btn_add_layer)

        btn_run_wlc = QPushButton("🚀 Launch WLC Suitability Tool (Pass Weights)")
        btn_run_wlc.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 7px; border-radius: 4px; font-size: 12px;")
        btn_run_wlc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_run_wlc.clicked.connect(self._launch_wlc_with_weights)
        actions_vbox.addWidget(btn_run_wlc)

        bottom_layout.addWidget(actions_group)
        bottom_layout.addStretch()

        bottom_scroll.setWidget(bottom_content)
        splitter.addWidget(bottom_scroll)

        splitter.setStretchFactor(0, 52)
        splitter.setStretchFactor(1, 48)
        main_layout.addWidget(splitter)

        self.setWidget(container)

    def _auto_pick_score_layers(self):
        project_layers = [lyr for lyr in QgsProject.instance().mapLayers().values()
                          if isinstance(lyr, QgsRasterLayer)]
        score_layers = [lyr for lyr in project_layers
                        if "score_" in lyr.name().lower() or "score" in lyr.name().lower()]

        if not score_layers:
            QMessageBox.information(
                self,
                "PlanX AHP Studio",
                "No raster layer containing 'score_' in its name was found in the current project. Keeping current criteria.",
            )
            return

        if len(score_layers) > AHP_MAX_CRITERIA:
            score_layers = score_layers[:AHP_MAX_CRITERIA]
            QMessageBox.information(
                self,
                "PlanX AHP Studio",
                f"Found more than {AHP_MAX_CRITERIA} score layers. Selected the first "
                f"{AHP_MAX_CRITERIA} layers for AHP matrix consistency stability.",
            )

        self.criteria_keys = [lyr.name() for lyr in score_layers]
        self.criteria_names = [lyr.name() for lyr in score_layers]
        n = len(self.criteria_names)
        self.crit_summary_lbl.setText(f"Active Criteria: {n} (from project)")
        self._load_matrix(np.ones((n, n), dtype=float), scenario_name=f"Project Layers ({n} criteria)")
        QMessageBox.information(
            self,
            "PlanX AHP Studio",
            f"Successfully loaded {n} score layers as MCDA criteria:\n" + "\n".join(f"• {k}" for k in self.criteria_keys),
        )

    def _choose_project_layers_dialog(self):
        project_layers = [lyr for lyr in QgsProject.instance().mapLayers().values()
                          if isinstance(lyr, QgsRasterLayer)]
        if not project_layers:
            text, ok = QInputDialog.getText(
                self,
                "Custom Criteria Definition",
                "Enter criteria names separated by commas (e.g. Slope, Flood, Fault, Landuse):",
                QLineEdit.EchoMode.Normal,
                ", ".join(self._short_name(n) for n in self.criteria_names),
            )
            if not ok or not text.strip():
                return
            items = [s.strip() for s in text.split(",") if s.strip()]
            if len(items) < 2:
                QMessageBox.warning(self, "Criteria Error", "AHP requires at least 2 criteria for pairwise comparison.")
                return
            self.criteria_keys = items[:AHP_MAX_CRITERIA]
            self.criteria_names = items[:AHP_MAX_CRITERIA]
            n = len(self.criteria_names)
            self.crit_summary_lbl.setText(f"Active Criteria: {n} (custom)")
            self._load_matrix(np.ones((n, n), dtype=float), scenario_name=f"Custom ({n} criteria)")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Project Raster Layers for AHP")
        dialog.resize(360, 420)
        vbox = QVBoxLayout(dialog)

        info = QLabel(f"Select 2 to {AHP_MAX_CRITERIA} raster layers to include as MCDA criteria:")
        info.setWordWrap(True)
        vbox.addWidget(info)

        list_widget = QListWidget()
        for lyr in project_layers:
            item = QListWidgetItem(lyr.name())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            is_checked = lyr.name() in self.criteria_keys or "score" in lyr.name().lower()
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            list_widget.addItem(item)
        vbox.addWidget(list_widget, 1)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        vbox.addLayout(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = []
            for idx in range(list_widget.count()):
                item = list_widget.item(idx)
                if item.checkState() == Qt.CheckState.Checked:
                    selected.append(item.text())
            if len(selected) < 2:
                QMessageBox.warning(self, "Selection Error", "Please select at least 2 raster layers for AHP.")
                return
            if len(selected) > AHP_MAX_CRITERIA:
                selected = selected[:AHP_MAX_CRITERIA]
                QMessageBox.information(
                    self,
                    "Selection Notice",
                    f"Limited to top {AHP_MAX_CRITERIA} layers for AHP consistency stability.",
                )

            self.criteria_keys = selected
            self.criteria_names = selected
            n = len(self.criteria_names)
            self.crit_summary_lbl.setText(f"Active Criteria: {n} (project)")
            self._load_matrix(np.ones((n, n), dtype=float), scenario_name=f"Project Layers ({n} criteria)")

    def _load_matrix(self, new_matrix: np.ndarray, scenario_name: Optional[str] = None):
        if scenario_name:
            self.current_scenario_title = scenario_name
        n = len(self.criteria_names)
        if new_matrix.shape != (n, n):
            self.matrix = np.ones((n, n), dtype=float)
        else:
            self.matrix = new_matrix.copy()

        self._rebuild_cards()
        self._rebuild_matrix_table()
        self._rebuild_weights_widgets()
        self._recalculate_and_refresh()

    def _rebuild_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        n = len(self.criteria_names)
        self.card_widgets.clear()

        for i in range(n):
            for j in range(i + 1, n):
                name_a = self._short_name(self.criteria_names[i])
                name_b = self._short_name(self.criteria_names[j])
                ratio = float(self.matrix[i, j])

                card = PairCardWidget(i, j, name_a, name_b, ratio, self)
                self.card_widgets[(i, j)] = card
                self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _rebuild_weights_widgets(self):
        while self.weights_container_layout.count():
            item = self.weights_container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.weight_widgets.clear()

        for key, name in zip(self.criteria_keys, self.criteria_names):
            short_name = self._short_name(name)
            widget = CriterionWeightWidget(key, short_name, self.weights_container)
            self.weight_widgets.append(widget)
            self.weights_container_layout.addWidget(widget)

    def _short_name(self, name: str) -> str:
        s = name.replace("score_", "").replace(".tif", "").replace("_", " ")
        if len(s) > 28:
            return s[:26] + "..."
        return s

    def _rebuild_matrix_table(self):
        self._updating_matrix = True
        n = len(self.criteria_names)
        self.matrix_table.setRowCount(n)
        self.matrix_table.setColumnCount(n)

        headers = [self._short_name(name) for name in self.criteria_names]
        self.matrix_table.setHorizontalHeaderLabels(headers)
        self.matrix_table.setVerticalHeaderLabels(headers)
        self.matrix_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for i in range(n):
            for j in range(n):
                val = self.matrix[i, j]
                txt = f"{val:.4f}".rstrip("0").rstrip(".") if abs(val - round(val)) > 0.001 else f"{int(round(val))}"
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if i == j:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(QColor("#f1f5f9"))
                    item.setForeground(QColor("#64748b"))
                elif i > j:
                    item.setBackground(QColor("#f0fdf4"))
                else:
                    item.setBackground(QColor("#ffffff"))

                self.matrix_table.setItem(i, j, item)

        self._updating_matrix = False

    def on_card_value_changed(self, i: int, j: int, val: float):
        if self._updating_matrix:
            return
        self.current_scenario_title = "Custom User AHP Scenario"
        self.matrix[i, j] = val
        self.matrix[j, i] = 1.0 / val

        self._updating_matrix = True
        self._update_table_cell(i, j, val)
        self._update_table_cell(j, i, 1.0 / val)
        self._updating_matrix = False

        self._recalculate_and_refresh()

    def _update_table_cell(self, r: int, c: int, val: float):
        txt = f"{val:.4f}".rstrip("0").rstrip(".") if abs(val - round(val)) > 0.001 else f"{int(round(val))}"
        item = self.matrix_table.item(r, c)
        if item:
            item.setText(txt)

    def _on_table_cell_changed(self, r: int, c: int):
        if self._updating_matrix or r == c:
            return
        item = self.matrix_table.item(r, c)
        if not item:
            return
        try:
            val_txt = item.text().strip()
            if "/" in val_txt:
                parts = val_txt.split("/")
                val = float(parts[0]) / float(parts[1])
            else:
                val = float(val_txt)
            if val <= 0:
                raise ValueError()
        except Exception:
            val = self.matrix[r, c]
            self._updating_matrix = True
            self._update_table_cell(r, c, val)
            self._updating_matrix = False
            return

        self.current_scenario_title = "Custom User AHP Scenario"
        self.matrix[r, c] = val
        self.matrix[c, r] = 1.0 / val

        self._updating_matrix = True
        self._update_table_cell(c, r, 1.0 / val)
        self._updating_matrix = False

        pair = (min(r, c), max(r, c))
        if pair in self.card_widgets:
            card = self.card_widgets[pair]
            target_val = self.matrix[pair[0], pair[1]]
            idx = ratio_to_index(target_val)
            card.set_scale_index(idx, emit=False)

        self._recalculate_and_refresh()

    def _recalculate_and_refresh(self):
        res = calculate_ahp(self.matrix)
        weights = res["weights"]
        cr = res["cr"]
        ci = res["ci"]
        lam = res["lambda_max"]
        ri = res["ri"]
        cr_ok = res["cr_ok"]

        # 1. Update Consistency Diagnostics
        self.stat_lambda.setText(f"{lam:.4f}")
        self.stat_ci.setText(f"{ci:.4f}")
        self.stat_ri.setText(f"{ri:.2f}")

        if cr_ok:
            self.header_cr_badge.setText(f"🟢 CR = {cr:.4f}")
            self.header_cr_badge.setStyleSheet("background: #065f46; color: #a7f3d0; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;")
            self.cr_card.setStyleSheet("border-radius: 6px; padding: 8px; background: #ecfdf5; border: 1px solid #10b981;")
            self.cr_badge_lbl.setText(f"🟢 CONSISTENT (CR = {cr:.4f} ≤ 0.10)")
            self.cr_badge_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #065f46;")
            self.cr_desc_lbl.setText(
                "Judgments satisfy Saaty's consistency criterion (CR ≤ 0.10). The pairwise matrix is mathematically sound and reliable for WLC suitability analysis."
            )
            self.cr_desc_lbl.setStyleSheet("font-size: 10px; color: #047857;")
        else:
            self.header_cr_badge.setText(f"🔴 CR = {cr:.4f}")
            self.header_cr_badge.setStyleSheet("background: #991b1b; color: #fecaca; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;")
            self.cr_card.setStyleSheet("border-radius: 6px; padding: 8px; background: #fef2f2; border: 1px solid #ef4444;")
            self.cr_badge_lbl.setText(f"🔴 INCONSISTENT (CR = {cr:.4f} > 0.10)")
            self.cr_badge_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #991b1b;")
            self.cr_desc_lbl.setText(
                f"WARNING: Consistency ratio ({cr*100:.1f}%) exceeds the 10% threshold! Intransitive preferences detected. Please adjust pairwise comparisons to restore consistency."
            )
            self.cr_desc_lbl.setStyleSheet("font-size: 10px; color: #b91c1c;")

        # 2. Update Weights in-place
        sorted_indices = sorted(range(len(weights)), key=lambda k: weights[k], reverse=True)
        ranks = {idx: rank + 1 for rank, idx in enumerate(sorted_indices)}

        for idx, (widget, w_val) in enumerate(zip(self.weight_widgets, weights)):
            widget.set_data(w_val, ranks.get(idx, idx + 1))

        # 3. Update CSV Line
        csv_str = ", ".join(f"{w:.4f}" for w in weights)
        self.csv_line.setText(csv_str)

    def _get_selected_chart_key(self) -> str:
        idx = self.chart_type_combo.currentIndex()
        keys = ["infographic", "bar", "radar", "donut", "heatmap", "pareto"]
        return keys[idx] if 0 <= idx < len(keys) else "infographic"

    def _get_selected_dpi(self) -> int:
        return self.chart_dpi_combo.currentData() or 300

    def _export_chart_png(self):
        chart_key = self._get_selected_chart_key()
        dpi = self._get_selected_dpi()
        safe_title = self.current_scenario_title.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        default_filename = f"AHP_{chart_key.upper()}_{safe_title}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export High-Resolution AHP Chart ({dpi} DPI)",
            default_filename,
            "PNG Image (*.png);;All Files (*.*)",
        )
        if not file_path:
            return

        res = calculate_ahp(self.matrix)
        generate_ahp_infographic(
            criteria_names=[self._short_name(n) for n in self.criteria_names],
            weights=res["weights"],
            cr=res["cr"],
            ci=res["ci"],
            ri=res["ri"],
            lambda_max=res["lambda_max"],
            cr_ok=res["cr_ok"],
            matrix=self.matrix,
            scenario_title=self.current_scenario_title,
            output_path=file_path,
            dpi=dpi,
            chart_type=chart_key,
        )

        QMessageBox.information(
            self,
            "AHP Chart Exported",
            f"🎯 Publication-grade ({dpi} DPI) {self.chart_type_combo.currentText()} exported successfully:\n\n{file_path}\n\n"
            "Ready to be inserted directly into your synthesis poster, report, or presentation.",
        )

    def _copy_chart_to_clipboard(self):
        chart_key = self._get_selected_chart_key()
        dpi = self._get_selected_dpi()
        res = calculate_ahp(self.matrix)
        raw_bytes = generate_ahp_infographic(
            criteria_names=[self._short_name(n) for n in self.criteria_names],
            weights=res["weights"],
            cr=res["cr"],
            ci=res["ci"],
            ri=res["ri"],
            lambda_max=res["lambda_max"],
            cr_ok=res["cr_ok"],
            matrix=self.matrix,
            scenario_title=self.current_scenario_title,
            output_path=None,
            dpi=dpi,
            chart_type=chart_key,
        )

        if not raw_bytes:
            QMessageBox.warning(self, "Export Error", "Could not generate infographic image.")
            return

        qimg = QImage()
        if qimg.loadFromData(raw_bytes):
            QApplication.clipboard().setImage(qimg)
            QMessageBox.information(
                self,
                "Copied to Clipboard",
                f"📋 {dpi} DPI {self.chart_type_combo.currentText()} copied to system clipboard!\n\n"
                "Press Ctrl+V to paste into InDesign, Photoshop, Word, or presentation slides.",
            )
        else:
            QMessageBox.warning(self, "Export Error", "Failed to transfer image to clipboard buffer.")

    def _export_all_charts_bundle(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder for All 6 AHP Charts",
            "",
        )
        if not folder:
            return

        dpi = self._get_selected_dpi()
        safe_title = self.current_scenario_title.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        chart_defs = [
            ("01_Executive_Summary_Infographic", "infographic"),
            ("02_Priority_Ranking_Bar_Chart", "bar"),
            ("03_Multi_Criteria_Radar_Profile", "radar"),
            ("04_Proportional_Donut_Composition", "donut"),
            ("05_Pairwise_Matrix_Heatmap", "heatmap"),
            ("06_Pareto_Cumulative_80_20", "pareto"),
        ]

        res = calculate_ahp(self.matrix)
        exported_files = []
        for prefix, c_key in chart_defs:
            out_file = os.path.join(folder, f"AHP_{prefix}_{safe_title}.png")
            generate_ahp_infographic(
                criteria_names=[self._short_name(n) for n in self.criteria_names],
                weights=res["weights"],
                cr=res["cr"],
                ci=res["ci"],
                ri=res["ri"],
                lambda_max=res["lambda_max"],
                cr_ok=res["cr_ok"],
                matrix=self.matrix,
                scenario_title=self.current_scenario_title,
                output_path=out_file,
                dpi=dpi,
                chart_type=c_key,
            )
            exported_files.append(os.path.basename(out_file))

        msg = (
            f"🎯 Successfully exported all 6 publication charts ({dpi} DPI) to:\n\n"
            f"{folder}\n\n"
            "Exported Graphics:\n" + "\n".join(f"  • {f}" for f in exported_files)
        )
        QMessageBox.information(self, "All Charts Exported", msg)

    def _apply_tema_a(self):
        if len(self.criteria_names) == 6:
            self._load_matrix(np.array(THEME_A_MATRIX, dtype=float), scenario_name="Theme A (Hazard Priority)")
            QMessageBox.information(
                self,
                "Theme A Loaded",
                "🛡️ Theme A (Hazard Priority) loaded successfully!\n"
                "• Active Fault: 36.7%\n• Flood (HAND): 30.0%\n• Slope: 13.4%\n• Agriculture: 7.3%\n• Road: 6.3%\n• Built-up: 6.3%\n"
                "Consistency Ratio: CR = 0.0400 (Consistent)",
            )
        else:
            self._apply_equal()

    def _apply_tema_b(self):
        if len(self.criteria_names) == 6:
            self._load_matrix(np.array(THEME_B_MATRIX, dtype=float), scenario_name="Theme B (Access Priority)")
            QMessageBox.information(
                self,
                "Theme B Loaded",
                "🚗 Theme B (Access Priority) loaded successfully!\n"
                "• Road: 28.5%\n• Built-up: 28.5%\n• Agriculture: 16.8%\n• Slope: 12.0%\n• Flood: 8.7%\n• Fault: 5.5%\n"
                "Consistency Ratio: CR = 0.0199 (Consistent)",
            )
        else:
            self._apply_equal()

    def _apply_equal(self):
        n = len(self.criteria_names)
        self._load_matrix(np.ones((n, n), dtype=float), scenario_name="Equal Weights (1/N)")

    def _copy_csv_weights(self):
        txt = self.csv_line.text().strip()
        QApplication.clipboard().setText(txt)
        QMessageBox.information(self, "Copied to Clipboard", f"WLC weights copied to clipboard:\n{txt}")

    def _add_ahp_vector_layer(self):
        res = calculate_ahp(self.matrix)
        weights = res["weights"]
        cr = res["cr"]
        cr_ok = 1 if res["cr_ok"] else 0

        fields = QgsFields()
        fields.append(QgsField("criterion_id", QMetaType.Type.Int))
        fields.append(QgsField("criterion_name", QMetaType.Type.QString))
        fields.append(QgsField("weight", QMetaType.Type.Double))
        fields.append(QgsField("weight_pct", QMetaType.Type.Double))
        fields.append(QgsField("cr", QMetaType.Type.Double))
        fields.append(QgsField("cr_ok", QMetaType.Type.Int))

        layer_name = f"AHP_Weights_CR_{cr:.4f}"
        mem_layer = QgsVectorLayer("None", layer_name, "memory")
        dp = mem_layer.dataProvider()
        dp.addAttributes(fields)
        mem_layer.updateFields()

        for idx, (name, w) in enumerate(zip(self.criteria_names, weights), start=1):
            feat = QgsFeature(mem_layer.fields())
            feat["criterion_id"] = idx
            feat["criterion_name"] = name
            feat["weight"] = round(float(w), 4)
            feat["weight_pct"] = round(float(w) * 100.0, 2)
            feat["cr"] = round(float(cr), 4)
            feat["cr_ok"] = cr_ok
            dp.addFeature(feat)

        mem_layer.updateExtents()
        QgsProject.instance().addMapLayer(mem_layer)
        QMessageBox.information(
            self,
            "Layer Added",
            f"'{layer_name}' attribute table added to QGIS layer panel!\n"
            f"Criteria, weights, and CR={cr:.4f} recorded.",
        )

    def _launch_wlc_with_weights(self):
        txt = self.csv_line.text().strip()
        project_layers = [lyr for lyr in QgsProject.instance().mapLayers().values()
                          if isinstance(lyr, QgsRasterLayer)]
        matching_layers = []
        for key in self.criteria_keys:
            for lyr in project_layers:
                if lyr.name() == key:
                    matching_layers.append(lyr)
                    break

        params = {"WEIGHTS_CSV": txt}
        if matching_layers:
            params["INPUT_RASTERS"] = matching_layers

        processing.execAlgorithmDialog("planx_suitability_lab:wlc_suitability", params)

    def _open_raw_processing_ahp(self):
        json_mat = json.dumps(self.matrix.tolist())
        processing.execAlgorithmDialog("planx_suitability_lab:ahp_weights", {"MATRIX_JSON": json_mat})


def open_ahp_studio(iface=None, parent=None) -> AHPStudioDockWidget:
    """
    Opens PlanX AHP Studio docked on the right side of QGIS.
    If already opened, brings it to front and focuses it.
    """
    if iface is not None:
        main_win = iface.mainWindow()
        dock = main_win.findChild(QDockWidget, "PlanX_AHP_Studio_Dock")
        if dock is None:
            dock = AHPStudioDockWidget(iface, main_win)
            iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            dash_dock = main_win.findChild(QDockWidget, "PlanX_Suitability_Lab_Dock")
            if dash_dock is not None and hasattr(main_win, "tabifyDockWidget"):
                # Tab grouping is cosmetic: a Qt that refuses the pairing must not
                # stop the studio from opening. Narrow, so a real error still shows.
                with contextlib.suppress(TypeError, RuntimeError):
                    main_win.tabifyDockWidget(dash_dock, dock)
        dock.show()
        dock.raise_()
        dock.activateWindow()
        return dock
    else:
        dock = AHPStudioDockWidget(iface, parent)
        dock.show()
        return dock
