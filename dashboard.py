# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsProject
from qgis.PyQt.QtCore import QUrl
import os


STEPS = [
    ('Prepare', 'planx_suitability_lab:data_harmonizer'),
    ('Criteria', 'planx_suitability_lab:proximity_builder'),
    ('Weights', 'planx_suitability_lab:ahp_weights'),
    ('Compose', 'planx_suitability_lab:wlc_suitability'),
    ('Uncertainty', 'planx_suitability_lab:montecarlo_suitability'),
    ('Explain', 'planx_suitability_lab:xai_global_sensitivity'),
    ('Report', 'planx_suitability_lab:suitability_html_report'),
]


class SuitabilityDashboard(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle('PlanX Suitability Lab - Dashboard / Kontrol Paneli')
        self.resize(1100, 720)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        shell = QHBoxLayout(self)
        self.nav = QListWidget()
        for lab in ('Overview / Genel', 'Flow / Akis', 'Beta Readiness'):
            QListWidgetItem(lab, self.nav)
        self.nav.setFixedWidth(160)
        self.nav.setCurrentRow(0)
        shell.addWidget(self.nav)

        self.pages = []
        body = QVBoxLayout()
        title = QLabel('PlanX Suitability Lab')
        title.setStyleSheet('font-size:22px;font-weight:700;color:#12343b;')
        body.addWidget(title)

        self.overview = QTextBrowser()
        self.flow = QTextBrowser()
        self.beta = QTextBrowser()
        self.pages = [self.overview, self.flow, self.beta]
        for i, pg in enumerate(self.pages):
            pg.setVisible(i == 0)
            body.addWidget(pg, 1)

        row = QHBoxLayout()
        open_btn = QPushButton('Open Selected Step')
        open_btn.clicked.connect(self._open_selected_step)
        row.addWidget(open_btn)
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self._refresh)
        row.addWidget(refresh)
        copy_diag = QPushButton('Copy Diagnostics')
        copy_diag.clicked.connect(self._copy_diagnostics)
        row.addWidget(copy_diag)
        copy_issue = QPushButton('Copy Issue Template')
        copy_issue.clicked.connect(self._copy_issue)
        row.addWidget(copy_issue)
        copy_hub = QPushButton('Copy Hub Changelog Draft')
        copy_hub.clicked.connect(self._copy_hub)
        row.addWidget(copy_hub)
        guide = QPushButton('Open Command Guide (EN/TR)')
        guide.clicked.connect(self._open_command_guide)
        row.addWidget(guide)
        sample = QPushButton('Run Synthetic Pack')
        sample.clicked.connect(self._run_synthetic_pack)
        row.addWidget(sample)
        pipe = QPushButton('Run Synthetic Pipeline')
        pipe.clicked.connect(self._run_synthetic_pipeline)
        row.addWidget(pipe)
        beta_report = QPushButton('Generate Beta Evidence')
        beta_report.clicked.connect(self._run_beta_evidence)
        row.addWidget(beta_report)
        body.addLayout(row)

        shell.addLayout(body, 1)
        self.nav.currentRowChanged.connect(self._switch)

    def _switch(self, idx):
        for i, pg in enumerate(self.pages):
            pg.setVisible(i == idx)

    def _refresh(self):
        layers = list(QgsProject.instance().mapLayers().values())
        vectors = [l for l in layers if hasattr(l, 'featureCount')]
        rasters = [l for l in layers if not hasattr(l, 'featureCount')]
        reg = QgsApplication.processingRegistry()
        miss = [aid for _, aid in STEPS if reg.algorithmById(aid) is None]
        status = 'READY' if (len(layers) > 0 and not miss) else 'NOT READY'

        self.overview.setHtml(
            '<h2>Overview / Genel Bakis</h2>'
            '<p><b>EN:</b> Raster MCDA workflow with hard constraints, uncertainty, and explainability.</p>'
            '<p><b>TR:</b> Sert kisitlar, belirsizlik ve aciklanabilirlik ile raster MCDA is akisi.</p>'
            '<ul>' + ''.join(f'<li><b>{k}</b> -> {v}</li>' for k, v in STEPS) + '</ul>'
            '<p><b>Shortcuts:</b> Ctrl+R Refresh, Ctrl+D Copy Diagnostics, Ctrl+I Copy Issue, Ctrl+H Open Guide</p>'
        )
        self.flow.setHtml(
            '<h2>Flow / Akis</h2>'
            '<ol>'
            '<li><b>Prepare</b>: harmonize rasters and extent/resolution | rasterlari hizala</li>'
            '<li><b>Criteria</b>: build criteria/proximity/masks | kriter/proximity/maske uret</li>'
            '<li><b>Weights</b>: AHP, PCA, Entropy</li>'
            '<li><b>Compose</b>: WLC/OWA</li>'
            '<li><b>Uncertainty</b>: Monte Carlo outputs</li>'
            '<li><b>Explain</b>: global/local contributions</li>'
            '<li><b>Report</b>: HTML summary</li>'
            '</ol>'
        )
        self.beta.setHtml(
            f'<h2>Beta Readiness: {status}</h2>'
            f'<p>Layers: {len(layers)} ({len(vectors)} vector, {len(rasters)} raster)</p>'
            f'<p>Registered steps: {len(STEPS)-len(miss)}/{len(STEPS)}</p>'
            f"<p>Missing: {', '.join(miss) if miss else 'None'}</p>"
        )

    def _open_selected_step(self):
        idx = self.nav.currentRow()
        if idx == 1:
            # open first flow step quickly
            processing.execAlgorithmDialog(STEPS[0][1])
        elif idx == 2:
            processing.execAlgorithmDialog(STEPS[3][1])
        else:
            processing.execAlgorithmDialog(STEPS[0][1])

    def _copy_diagnostics(self):
        layers = list(QgsProject.instance().mapLayers().values())
        reg = QgsApplication.processingRegistry()
        miss = [aid for _, aid in STEPS if reg.algorithmById(aid) is None]
        txt = (
            'PlanX Suitability Lab Diagnostics\n'
            '================================\n'
            f'Loaded layers: {len(layers)}\n'
            f'Step registry coverage: {len(STEPS)-len(miss)}/{len(STEPS)}\n'
            f"Missing step algorithms: {', '.join(miss) if miss else 'None'}\n"
        )
        QApplication.clipboard().setText(txt)

    def _copy_issue(self):
        txt = (
            'PlanX Suitability Lab Issue Template\n'
            '====================================\n\n'
            'Summary:\n-\n\nExpected:\n-\n\nActual:\n-\n\nReproduction:\n1.\n2.\n3.\n'
        )
        QApplication.clipboard().setText(txt)

    def _copy_hub(self):
        txt = (
            'PlanX Suitability Lab 0.3.0 beta - hardened raster MCDA workflow release.\n'
            '- Added advanced normalizer/reclassifier modes (min-max, fuzzy linear/sigmoid/gaussian).\n'
            '- Rebuilt OWA as true multi-raster composition using criteria and order weights.\n'
            '- Expanded harmonizer to batch outputs and synthetic runner to full WLC/OWA/QA/report chain.'
        )
        QApplication.clipboard().setText(txt)

    def _open_command_guide(self):
        guide_path = os.path.join(os.path.dirname(__file__), 'docs', 'COMMAND_GUIDE.html')
        if os.path.exists(guide_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(guide_path))

    def _run_synthetic_pack(self):
        processing.execAlgorithmDialog('planx_suitability_lab:synthetic_sample_raster')

    def _run_synthetic_pipeline(self):
        processing.execAlgorithmDialog('planx_suitability_lab:synthetic_pipeline_runner')

    def _run_beta_evidence(self):
        processing.execAlgorithmDialog('planx_suitability_lab:beta_evidence_report')

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_R:
            self._refresh()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_D:
            self._copy_diagnostics()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_I:
            self._copy_issue()
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_H:
            self._open_command_guide()
            return
        super().keyPressEvent(event)
