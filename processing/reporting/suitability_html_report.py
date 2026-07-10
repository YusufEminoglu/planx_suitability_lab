# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)


class SuitabilityHtmlReportAlgorithm(QgsProcessingAlgorithm):
    PROJECT = "PROJECT"
    SUMMARY = "SUMMARY"
    WEIGHT_METHOD = "WEIGHT_METHOD"
    QA_SUMMARY = "QA_SUMMARY"
    OUTPUT = "OUTPUT"

    def name(self):
        return "suitability_html_report"

    def displayName(self):
        return "Reporting: Suitability HTML Report"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Generates an executive HTML report with project metadata, summary, method snapshot, and QA section.</b></p>"
            "<p><b>Inputs:</b> Project name (string), Summary notes (multiline), "
            "Active weight method / scenario label, QA summary (optional multiline).<br>"
            "<b>Output:</b> HTML file with styled cards for project info, executive summary, "
            "method snapshot (WLC/OWA/Monte Carlo/XAI), and QA acceptance block.<br>"
            "<b>Method:</b> Assembles a self-contained HTML document with inline CSS. "
            "Embeds the user-supplied project name, timestamp, weight method, and summary notes. "
            "Includes a static method-snapshot card listing the analysis pipeline capabilities. "
            "Renders the QA summary in a preformatted block, or a default message if not provided.<br>"
            "<b>Typical use:</b> Produce a shareable decision-support document for stakeholders and planning committees.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return SuitabilityHtmlReportAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.PROJECT, "Project name", defaultValue="PlanX Suitability Study"))
        self.addParameter(
            QgsProcessingParameterString(
                self.SUMMARY,
                "Summary notes",
                multiLine=True,
                defaultValue="PlanX Suitability Lab run summary.",
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.WEIGHT_METHOD,
                "Active weight method / scenario",
                defaultValue="AHP / PCA / Entropy",
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.QA_SUMMARY,
                "QA summary (optional)",
                multiLine=True,
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "HTML report", fileFilter="HTML files (*.html)"))

    def processAlgorithm(self, parameters, context, feedback):
        project = self.parameterAsString(parameters, self.PROJECT, context)
        txt = self.parameterAsString(parameters, self.SUMMARY, context)
        weight_method = self.parameterAsString(parameters, self.WEIGHT_METHOD, context)
        qa = self.parameterAsString(parameters, self.QA_SUMMARY, context).strip()
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        qa_block = (
            f"<h2>QA / Numerical Acceptance</h2><pre>{qa}</pre>"
            if qa
            else "<h2>QA / Numerical Acceptance</h2><p>No QA summary was provided in this run.</p>"
        )
        html = f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>PlanX Suitability Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #122b30; background: #f6fbfa; }}
    h1, h2 {{ color: #0e4b59; }}
    .card {{ background: #fff; border: 1px solid #d8e9e5; border-radius: 10px; padding: 14px; margin: 10px 0; }}
    pre {{ background: #f1f7f5; border: 1px solid #d8e9e5; padding: 10px; white-space: pre-wrap; }}
  </style>
</head>
<body>
<h1>PlanX Suitability Lab - Report</h1>
<div class='card'>
  <p><b>Project:</b> {project}</p>
  <p><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  <p><b>Weight scenario:</b> {weight_method}</p>
</div>
<div class='card'>
  <h2>Executive Summary</h2>
  <pre>{txt}</pre>
</div>
<div class='card'>
  <h2>Method Snapshot</h2>
  <ul>
    <li>Policy: hard constraints (mask * weighted score)</li>
    <li>Weight engines: AHP / PCA / Entropy (+ scenario pack)</li>
    <li>Compose: WLC + OWA + scenario delta</li>
    <li>Uncertainty: Monte Carlo (mean/std/p05/p50/p95/stability)</li>
    <li>Explainability: global sensitivity + local contributions + GeoShapley-lite</li>
  </ul>
</div>
<div class='card'>
  {qa_block}
</div>
</body>
</html>
"""
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        return {self.OUTPUT: out}

