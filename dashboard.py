# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime

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
    QLineEdit,
    QPushButton,
    QScrollArea,
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
    "planx_suitability_lab:uncertainty_adjusted_suitability",
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
        self.recent_runs = []
        self.card_widgets = []
        self.setWindowTitle("PlanX Suitability Lab - Studio Console")
        self.resize(1320, 860)
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
            QTabBar::tab:selected { background: #ffffff; font-weight: 700; }
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
            QComboBox, QLineEdit {
                background: #ffffff;
                border: 1px solid #c9d9de;
                border-radius: 7px;
                padding: 6px;
                color: #17323a;
            }
            QFrame[classCard="true"] {
                background: #fbfefe;
                border: 1px solid #d5e5e8;
                border-radius: 12px;
            }
            QLabel[classTitle="true"] { color: #173741; font-weight: 700; font-size: 13px; }
            QLabel[classMeta="true"] { color: #4a6871; font-size: 11px; }
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
        top = QHBoxLayout()
        self.workflow_combo = QComboBox()
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                self.workflow_combo.addItem(f"{group} - {title_txt}", (aid, desc))
        top.addWidget(self.workflow_combo, 1)
        run_sel = QPushButton("Run Selected")
        run_sel.clicked.connect(self._run_selected)
        top.addWidget(run_sel)
        wf.addLayout(top)
        self.workflow_desc = QTextBrowser()
        self.workflow_desc.setMaximumHeight(95)
        wf.addWidget(self.workflow_desc)
        self.workflow_map = QTextBrowser()
        wf.addWidget(self.workflow_map, 1)
        self.workflow_combo.currentIndexChanged.connect(self._update_selected_desc)
        self.tabs.addTab(workflow_tab, "Workflow")

        modules_tab = QWidget()
        ml = QVBoxLayout(modules_tab)
        ml.setContentsMargins(10, 10, 10, 10)
        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter modules (name, group, id)...")
        self.search.textChanged.connect(self._filter_cards)
        filter_row.addWidget(self.search, 1)
        self.group_filter = QComboBox()
        self.group_filter.addItem("All Groups", "")
        for g, _ in ALGO_GROUPS:
            self.group_filter.addItem(g, g)
        self.group_filter.currentIndexChanged.connect(self._filter_cards)
        filter_row.addWidget(self.group_filter)
        ml.addLayout(filter_row)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        cards_host = QWidget()
        self.cards_grid = QGridLayout(cards_host)
        self.cards_grid.setContentsMargins(4, 4, 4, 4)
        self.cards_grid.setHorizontalSpacing(10)
        self.cards_grid.setVerticalSpacing(10)
        self.cards_scroll.setWidget(cards_host)
        ml.addWidget(self.cards_scroll, 1)
        self.tabs.addTab(modules_tab, "Modules")

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

        runlog_tab = QWidget()
        rl = QVBoxLayout(runlog_tab)
        rl.setContentsMargins(10, 10, 10, 10)
        self.runlog = QTextBrowser()
        rl.addWidget(self.runlog, 1)
        clear_log = QPushButton("Clear Run Log")
        clear_log.setObjectName("ghost")
        clear_log.clicked.connect(self._clear_runlog)
        rl.addWidget(clear_log, 0, Qt.AlignRight)
        self.tabs.addTab(runlog_tab, "Recent Runs")

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

        self._build_cards()

    def _build_cards(self):
        for w in self.card_widgets:
            w.setParent(None)
        self.card_widgets = []
        idx = 0
        for group, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                card = QFrame()
                card.setProperty("classCard", "true")
                v = QVBoxLayout(card)
                v.setContentsMargins(10, 10, 10, 10)
                t = QLabel(title_txt)
                t.setProperty("classTitle", "true")
                m = QLabel(f"{group} | {aid}")
                m.setProperty("classMeta", "true")
                d = QLabel(desc)
                d.setWordWrap(True)
                d.setStyleSheet("color:#294e58; font-size:12px;")
                run = QPushButton("Run")
                run.clicked.connect(lambda _, x=aid, n=title_txt: self._run_algorithm(x, n))
                v.addWidget(t)
                v.addWidget(m)
                v.addWidget(d, 1)
                v.addWidget(run, 0, Qt.AlignRight)
                card.meta = (group.lower(), title_txt.lower(), aid.lower(), desc.lower())
                r = idx // 3
                c = idx % 3
                self.cards_grid.addWidget(card, r, c)
                self.card_widgets.append(card)
                idx += 1

    def _filter_cards(self):
        q = (self.search.text() or "").strip().lower()
        group = self.group_filter.currentData() or ""
        g = group.lower().strip()
        for card in self.card_widgets:
            mg, mt, ma, md = card.meta
            ok_q = (q in mg) or (q in mt) or (q in ma) or (q in md) if q else True
            ok_g = (mg == g) if g else True
            card.setVisible(ok_q and ok_g)

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

    def _track_run(self, algo_id, label):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.recent_runs.insert(0, f"[{ts}] {label} ({algo_id})")
        self.recent_runs = self.recent_runs[:30]
        self._refresh_runlog()

    def _refresh_runlog(self):
        if not self.recent_runs:
            self.runlog.setHtml("<h3>Recent Runs</h3><p>No runs yet.</p>")
            return
        html = "<h3>Recent Runs</h3><ul>" + "".join(f"<li>{line}</li>" for line in self.recent_runs) + "</ul>"
        self.runlog.setHtml(html)

    def _clear_runlog(self):
        self.recent_runs = []
        self._refresh_runlog()

    def _run_algorithm(self, algo_id, label):
        processing.execAlgorithmDialog(algo_id)
        self._track_run(algo_id, label)

    def _run_selected(self):
        data = self.workflow_combo.currentData()
        if not data:
            return
        aid, _ = data
        label = self.workflow_combo.currentText()
        self._run_algorithm(aid, label)

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
        self._refresh_runlog()

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
            "PlanX Suitability Lab 1.2.1 - production MCDA release.\n"
            "- Added TOPSIS, robust suitability, and class-area stats for decision-grade analysis.\n"
            "- Strengthened chunk-aware raster engines and geometry-free analytics tables.\n"
            "- Introduced redesigned studio dashboard and unique custom icon."
        )
        QApplication.clipboard().setText(txt)

    def _open_command_guide(self):
        guide_path = os.path.join(os.path.dirname(__file__), "docs", "COMMAND_GUIDE.html")
        if os.path.exists(guide_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))

    def _run_synthetic_pipeline(self):
        self._run_algorithm("planx_suitability_lab:synthetic_pipeline_runner", "Synthetic Pipeline")

    def _run_release_evidence(self):
        self._run_algorithm("planx_suitability_lab:beta_evidence_report", "Release Evidence")

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

