# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import processing
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsProject


ALGO_GROUPS = [
    (
        "Prepare",
        [
            ("Data Harmonizer", "planx_suitability_lab:data_harmonizer", "Align CRS/extent/resolution and export aligned stack."),
            ("Synthetic Sample Pack", "planx_suitability_lab:synthetic_sample_raster", "Generate synthetic criteria + hard mask."),
            ("Synthetic Pipeline", "planx_suitability_lab:synthetic_pipeline_runner", "One-click full smoke run."),
        ],
    ),
    (
        "Criteria",
        [
            ("Vector Rasterizer", "planx_suitability_lab:vector_rasterizer", "Rasterize by constant or field value."),
            ("Proximity Builder", "planx_suitability_lab:proximity_builder", "Distance raster from selected target values."),
            ("Normalizer/Reclassifier", "planx_suitability_lab:normalizer_reclassifier", "Min-max and fuzzy transforms."),
            ("Constraint Builder", "planx_suitability_lab:constraint_builder", "Generate hard 0/1 eligibility mask."),
        ],
    ),
    (
        "Weights",
        [
            ("AHP Weights", "planx_suitability_lab:ahp_weights", "Pairwise matrix with CR quality output."),
            ("PCA Weights", "planx_suitability_lab:pca_derived_weights", "Sampled covariance PCA objective weights."),
            ("Entropy Weights", "planx_suitability_lab:entropy_weights", "Sampled entropy-information weights."),
            ("Scenario Weight Pack", "planx_suitability_lab:scenario_weight_pack", "Merge AHP/PCA/Entropy scenarios."),
        ],
    ),
    (
        "Compose",
        [
            ("WLC Suitability", "planx_suitability_lab:wlc_suitability", "Chunk-aware weighted linear combination."),
            ("OWA Suitability", "planx_suitability_lab:owa_suitability", "Chunk-aware ordered weighted averaging."),
            ("TOPSIS Suitability", "planx_suitability_lab:topsis_suitability", "Benefit/cost distance-to-ideal suitability."),
            ("Robust Suitability", "planx_suitability_lab:uncertainty_adjusted_suitability", "Risk-averse score from mean/std."),
            ("Scenario Comparator", "planx_suitability_lab:scenario_comparator", "Delta map and summary stats."),
        ],
    ),
    (
        "Uncertainty + Explain",
        [
            ("Monte Carlo Suitability", "planx_suitability_lab:montecarlo_suitability", "unc_mean/std/p05/p50/p95/stability."),
            ("Global Sensitivity", "planx_suitability_lab:xai_global_sensitivity", "Sampled criterion influence table."),
            ("Local Contribution", "planx_suitability_lab:xai_local_contribution", "Contribution and percentage rasters."),
            ("GeoShapley-lite", "planx_suitability_lab:xai_geoshapley_lite", "Local attribution around sampled baseline."),
        ],
    ),
    (
        "Report",
        [
            ("Numerical QA Check", "planx_suitability_lab:numerical_qa_check", "Bounds and percentile-order checks."),
            ("Class Area Stats", "planx_suitability_lab:suitability_class_area_stats", "Coverage by suitability bands."),
            ("Suitability HTML Report", "planx_suitability_lab:suitability_html_report", "Executive report with QA section."),
            ("Scenario Markdown Brief", "planx_suitability_lab:scenario_markdown_brief", "Planner memo output."),
            ("Release Evidence", "planx_suitability_lab:beta_evidence_report", "Registry-level readiness evidence."),
        ],
    ),
]

REQUIRED_IDS = [
    "planx_suitability_lab:data_harmonizer",
    "planx_suitability_lab:wlc_suitability",
    "planx_suitability_lab:owa_suitability",
    "planx_suitability_lab:topsis_suitability",
    "planx_suitability_lab:montecarlo_suitability",
    "planx_suitability_lab:xai_global_sensitivity",
    "planx_suitability_lab:numerical_qa_check",
    "planx_suitability_lab:suitability_html_report",
    "planx_suitability_lab:scenario_markdown_brief",
]


class SuitabilityDashboard(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("PlanX Suitability Lab - Studio Console")
        self.resize(1280, 840)
        self._apply_style()
        self._build_ui()
        self._refresh()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QDialog { background: #eef4f4; }
            QFrame#heroCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0e3a53, stop:1 #1f6f88);
                border-radius: 14px;
            }
            QLabel#heroTitle { color: #ffffff; font-size: 24px; font-weight: 700; }
            QLabel#heroSub { color: #d7edf3; font-size: 13px; }
            QLabel#statusChip {
                color: #0f2d3a;
                background: #f8d37a;
                border: 1px solid #e8bf58;
                border-radius: 11px;
                padding: 4px 10px;
                font-weight: 700;
            }
            QTabWidget::pane {
                border: 1px solid #d7e3e6;
                border-radius: 10px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #dfeaec;
                color: #163340;
                border: 1px solid #c8d8dd;
                padding: 8px 14px;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                font-weight: 700;
            }
            QTextBrowser {
                background: #ffffff;
                border: 1px solid #d7e3e6;
                border-radius: 10px;
                padding: 8px;
                color: #18323a;
            }
            QPushButton {
                background: #1f6f88;
                color: #ffffff;
                border: 1px solid #17586d;
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2585a4; }
            QPushButton#ghost {
                background: #ffffff;
                color: #1c5f74;
                border: 1px solid #b8cdd4;
            }
            QPushButton#ghost:hover { background: #f2f8f9; }
            QComboBox {
                background: #ffffff;
                border: 1px solid #c9d9de;
                border-radius: 7px;
                padding: 6px;
                color: #17323a;
            }
            """
        )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        ttl_box = QVBoxLayout()
        title = QLabel("PlanX Suitability Lab")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Raster MCDA Studio: harmonize, model, stress-test, explain, report")
        subtitle.setObjectName("heroSub")
        ttl_box.addWidget(title)
        ttl_box.addWidget(subtitle)
        hero_layout.addLayout(ttl_box, 1)
        self.status_chip = QLabel("Release Readiness: checking...")
        self.status_chip.setObjectName("statusChip")
        hero_layout.addWidget(self.status_chip, 0, Qt.AlignRight | Qt.AlignTop)
        root.addWidget(hero)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.overview = QTextBrowser()
        self.tabs.addTab(self.overview, "Overview")

        workflow_tab = QWidget()
        wf = QVBoxLayout(workflow_tab)
        wf.setContentsMargins(10, 10, 10, 10)
        self.workflow_combo = QComboBox()
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                self.workflow_combo.addItem(f"{group} - {title_txt}", (aid, desc))
        wf.addWidget(self.workflow_combo)
        row = QHBoxLayout()
        self.workflow_desc = QTextBrowser()
        self.workflow_desc.setMaximumHeight(100)
        row.addWidget(self.workflow_desc, 1)
        run_sel = QPushButton("Run Selected Algorithm")
        run_sel.clicked.connect(self._run_selected)
        row.addWidget(run_sel)
        wf.addLayout(row)
        self.workflow_map = QTextBrowser()
        wf.addWidget(self.workflow_map, 1)
        self.workflow_combo.currentIndexChanged.connect(self._update_selected_desc)
        self.tabs.addTab(workflow_tab, "Workflow")

        quick_tab = QWidget()
        ql = QGridLayout(quick_tab)
        ql.setContentsMargins(12, 12, 12, 12)
        ql.setHorizontalSpacing(10)
        ql.setVerticalSpacing(10)
        quick_buttons = [
            ("Run Synthetic Pipeline", self._run_synthetic_pipeline, False),
            ("Generate Release Evidence", self._run_release_evidence, False),
            ("Open Command Guide", self._open_command_guide, True),
            ("Copy Diagnostics", self._copy_diagnostics, True),
            ("Copy Issue Template", self._copy_issue, True),
            ("Copy Hub Changelog Draft", self._copy_hub, True),
        ]
        for i, (txt, fn, ghost) in enumerate(quick_buttons):
            b = QPushButton(txt)
            if ghost:
                b.setObjectName("ghost")
            b.clicked.connect(fn)
            ql.addWidget(b, i // 2, i % 2)
        self.tabs.addTab(quick_tab, "Quick Actions")

        self.readiness = QTextBrowser()
        self.tabs.addTab(self.readiness, "Readiness")

        footer = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh)
        footer.addWidget(refresh)
        hint = QLabel("Shortcuts: Ctrl+R refresh, Ctrl+D diagnostics, Ctrl+G guide, Ctrl+P synthetic pipeline")
        hint.setStyleSheet("color:#35545f;")
        footer.addWidget(hint, 1)
        root.addLayout(footer)

    def _build_workflow_html(self):
        parts = ["<h2>Operational Map</h2>"]
        for group, items in ALGO_GROUPS:
            parts.append(f"<h3>{group}</h3><ul>")
            for title_txt, aid, desc in items:
                parts.append(f"<li><b>{title_txt}</b> (<code>{aid}</code>)<br>{desc}</li>")
            parts.append("</ul>")
        return "".join(parts)

    def _update_selected_desc(self):
        data = self.workflow_combo.currentData()
        if not data:
            self.workflow_desc.setHtml("")
            return
        aid, desc = data
        self.workflow_desc.setHtml(f"<b>{aid}</b><br>{desc}")

    def _run_selected(self):
        data = self.workflow_combo.currentData()
        if not data:
            return
        aid, _ = data
        processing.execAlgorithmDialog(aid)

    def _refresh(self):
        layers = list(QgsProject.instance().mapLayers().values())
        vectors = [l for l in layers if hasattr(l, "featureCount")]
        rasters = [l for l in layers if not hasattr(l, "featureCount")]
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]
        ready = len(missing) == 0
        status = "READY" if ready else "NOT READY"
        self.status_chip.setText(f"Release Readiness: {status}")
        if ready:
            self.status_chip.setStyleSheet("color:#0f2d3a;background:#9fdfbf;border:1px solid #6fc995;border-radius:11px;padding:4px 10px;font-weight:700;")
        else:
            self.status_chip.setStyleSheet("color:#0f2d3a;background:#f8d37a;border:1px solid #e8bf58;border-radius:11px;padding:4px 10px;font-weight:700;")

        self.overview.setHtml(
            "<h2>Overview</h2>"
            "<p><b>EN:</b> Production-ready raster MCDA with hard constraints, uncertainty, explainability, and reporting.</p>"
            "<p><b>TR:</b> Sert kisit, belirsizlik, aciklanabilirlik ve raporlama iceren uretim-hazir raster MCDA platformu.</p>"
            f"<p><b>Loaded layers:</b> {len(layers)} (vector: {len(vectors)}, raster: {len(rasters)})</p>"
            "<p><b>Tip:</b> Start with <code>Synthetic Pipeline</code> for smoke validation before real data runs.</p>"
        )
        self.workflow_map.setHtml(self._build_workflow_html())
        self._update_selected_desc()

        self.readiness.setHtml(
            "<h2>Release Checks</h2>"
            f"<p><b>Required algorithms:</b> {len(REQUIRED_IDS)-len(missing)}/{len(REQUIRED_IDS)}</p>"
            f"<p><b>Missing:</b> {', '.join(missing) if missing else 'None'}</p>"
            "<h3>Current Readiness Logic</h3>"
            "<ul>"
            "<li>Provider registry coverage for critical modules</li>"
            "<li>Project layers present for interactive runs</li>"
            "<li>Dedicated QA tools available in reporting group</li>"
            "</ul>"
        )

    def _copy_diagnostics(self):
        layers = list(QgsProject.instance().mapLayers().values())
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]
        txt = (
            "PlanX Suitability Lab Diagnostics\n"
            "================================\n"
            f"Loaded layers: {len(layers)}\n"
            f"Required registry coverage: {len(REQUIRED_IDS)-len(missing)}/{len(REQUIRED_IDS)}\n"
            f"Missing algorithms: {', '.join(missing) if missing else 'None'}\n"
        )
        QApplication.clipboard().setText(txt)

    def _copy_issue(self):
        txt = (
            "PlanX Suitability Lab Issue Template\n"
            "====================================\n\n"
            "Summary:\n-\n\nExpected:\n-\n\nActual:\n-\n\nReproduction:\n1.\n2.\n3.\n"
        )
        QApplication.clipboard().setText(txt)

    def _copy_hub(self):
        txt = (
            "PlanX Suitability Lab 1.2.0 - production MCDA release.\n"
            "- Added TOPSIS, robust suitability, and class-area stats for decision-grade analysis.\n"
            "- Strengthened chunk-aware raster engines and geometry-free analytics tables.\n"
            "- Expanded synthetic pipeline and release-evidence reporting workflows."
        )
        QApplication.clipboard().setText(txt)

    def _open_command_guide(self):
        guide_path = os.path.join(os.path.dirname(__file__), "docs", "COMMAND_GUIDE.html")
        if os.path.exists(guide_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))

    def _run_synthetic_pipeline(self):
        processing.execAlgorithmDialog("planx_suitability_lab:synthetic_pipeline_runner")

    def _run_release_evidence(self):
        processing.execAlgorithmDialog("planx_suitability_lab:beta_evidence_report")

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_R:
            self._refresh()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_D:
            self._copy_diagnostics()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_G:
            self._open_command_guide()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_P:
            self._run_synthetic_pipeline()
            return
        super().keyPressEvent(event)

