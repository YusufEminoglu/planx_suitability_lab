# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from qgis.core import (
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)


class BetaEvidenceReportAlgorithm(QgsProcessingAlgorithm):
    SUMMARY = "SUMMARY"
    OUTPUT = "OUTPUT"

    def name(self):
        return "beta_evidence_report"

    def displayName(self):
        return "Reporting: Beta Evidence Report (HTML)"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return BetaEvidenceReportAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.SUMMARY,
                "Execution summary notes",
                multiLine=True,
                defaultValue="Beta evidence summary for suitability workflow.",
            )
        )
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "HTML evidence report", fileFilter="HTML files (*.html)"))

    def processAlgorithm(self, parameters, context, feedback):
        txt = self.parameterAsString(parameters, self.SUMMARY, context)
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        reg = QgsApplication.processingRegistry()
        required = [
            "planx_suitability_lab:data_harmonizer",
            "planx_suitability_lab:proximity_builder",
            "planx_suitability_lab:ahp_weights",
            "planx_suitability_lab:wlc_suitability",
            "planx_suitability_lab:montecarlo_suitability",
            "planx_suitability_lab:xai_global_sensitivity",
            "planx_suitability_lab:suitability_html_report",
            "planx_suitability_lab:numerical_qa_check",
        ]
        rows = []
        ok = 0
        for aid in required:
            exists = reg.algorithmById(aid) is not None
            if exists:
                ok += 1
            rows.append(f"<tr><td>{aid}</td><td>{'PASS' if exists else 'FAIL'}</td></tr>")
        status = "READY" if ok == len(required) else "NOT READY"
        html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>PlanX Beta Evidence</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:22px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #dbe7e4;padding:8px}}th{{background:#edf6f4}}</style>
</head><body>
<h1>PlanX Suitability Lab - Beta Evidence Report</h1>
<p><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><b>Status:</b> {status} ({ok}/{len(required)} required algorithms registered)</p>
<h2>Registry checks</h2>
<table><thead><tr><th>Algorithm</th><th>Check</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Summary</h2><pre>{txt}</pre>
</body></html>"""
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        return {self.OUTPUT: out}

