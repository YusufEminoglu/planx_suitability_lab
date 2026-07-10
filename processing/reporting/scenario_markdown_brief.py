# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)


class ScenarioMarkdownBriefAlgorithm(QgsProcessingAlgorithm):
    PROJECT = "PROJECT"
    BASELINE = "BASELINE"
    SCENARIO = "SCENARIO"
    QA = "QA"
    NOTES = "NOTES"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_markdown_brief"

    def displayName(self):
        return "Reporting: Scenario Markdown Brief"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Produces a planning-memo markdown brief for a single scenario versus baseline.</b></p>"
            "<p><b>Inputs:</b> Project name, Baseline label, Scenario label, "
            "QA summary (optional multiline), Planner notes (optional multiline).<br>"
            "<b>Output:</b> Markdown file with interpretation checklist, QA summary, planner notes, "
            "and a recommendation template (priority zones, high-uncertainty zones, data improvements).<br>"
            "<b>Method:</b> Assembles a structured markdown document with timestamp, scenario labels, "
            "and a pre-written interpretation checklist covering suitability mean, robust suitability, "
            "uncertainty spread, local contributions, and hard-constraint behavior. "
            "Appends user-supplied QA text and planner notes. "
            "Includes a numbered recommendation template for manual completion.<br>"
            "<b>Typical use:</b> Create a standardized planning memo to accompany each scenario result set.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ScenarioMarkdownBriefAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.PROJECT, "Project name", defaultValue="PlanX Suitability Study"))
        self.addParameter(QgsProcessingParameterString(self.BASELINE, "Baseline label", defaultValue="WLC baseline"))
        self.addParameter(QgsProcessingParameterString(self.SCENARIO, "Scenario label", defaultValue="Alternative scenario"))
        self.addParameter(
            QgsProcessingParameterString(
                self.QA,
                "QA summary (optional)",
                multiLine=True,
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.NOTES,
                "Planner notes (optional)",
                multiLine=True,
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "Markdown brief", fileFilter="Markdown (*.md)"))

    def processAlgorithm(self, parameters, context, feedback):
        project = self.parameterAsString(parameters, self.PROJECT, context)
        baseline = self.parameterAsString(parameters, self.BASELINE, context)
        scenario = self.parameterAsString(parameters, self.SCENARIO, context)
        qa = self.parameterAsString(parameters, self.QA, context).strip()
        notes = self.parameterAsString(parameters, self.NOTES, context).strip()
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        md = [
            f"# {project} - Scenario Brief",
            "",
            f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Baseline: {baseline}",
            f"- Scenario: {scenario}",
            "",
            "## Interpretation Checklist",
            "- Review suitability mean and robust suitability together.",
            "- Validate uncertainty spread before selecting priority areas.",
            "- Check local contribution and GeoShapley-lite outputs for explainability.",
            "- Confirm hard-constraint behavior in protected/restricted zones.",
            "",
            "## QA Summary",
            qa if qa else "_No QA summary provided._",
            "",
            "## Planner Notes",
            notes if notes else "_No planner notes provided._",
            "",
            "## Recommendation Template",
            "1. Priority intervention zones:",
            "2. High-uncertainty zones to investigate:",
            "3. Data improvements before final decision:",
        ]
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        return {self.OUTPUT: out}

