# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterString, QgsProcessingParameterFileDestination


class SuitabilityHtmlReportAlgorithm(QgsProcessingAlgorithm):
    SUMMARY = 'SUMMARY'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'suitability_html_report'

    def displayName(self):
        return 'Reporting: Suitability HTML Report'

    def group(self):
        return 'Reporting'

    def groupId(self):
        return 'reporting'

    def createInstance(self):
        return SuitabilityHtmlReportAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.SUMMARY, 'Summary notes', multiLine=True, defaultValue='PlanX Suitability Lab run summary.'))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, 'HTML report', fileFilter='HTML files (*.html)'))

    def processAlgorithm(self, parameters, context, feedback):
        txt = self.parameterAsString(parameters, self.SUMMARY, context)
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        html = f"""
<!doctype html><html><head><meta charset='utf-8'><title>PlanX Suitability Report</title></head>
<body>
<h1>PlanX Suitability Lab - HTML Report</h1>
<p><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p>{txt}</p>
<ul>
<li>Policy: hard constraints (mask * weighted score)</li>
<li>Weight methods: AHP / PCA / Entropy</li>
<li>Uncertainty: Monte Carlo summary outputs</li>
<li>XAI: global sensitivity + local contributions + GeoShapley-lite</li>
</ul>
</body></html>
"""
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        return {self.OUTPUT: out}
