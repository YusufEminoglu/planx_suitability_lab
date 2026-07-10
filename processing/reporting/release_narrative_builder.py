# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import numpy as np
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)


class ReleaseNarrativeBuilderAlgorithm(QgsProcessingAlgorithm):
    PROJECT = "PROJECT"
    VERSION = "VERSION"
    HIGHLIGHTS = "HIGHLIGHTS"
    FRONTIER = "FRONTIER"
    BUDGET = "BUDGET"
    SIMILARITY = "SIMILARITY"
    OUTPUT = "OUTPUT"

    def name(self):
        return "release_narrative_builder"

    def displayName(self):
        return "Reporting: Release Narrative Builder (Markdown)"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Builds an English narrative paragraph describing a release version from diagnostic tables.</b></p>"
            "<p><b>Inputs:</b> Project name, Release version label, Optional manual highlights (multiline), "
            "Optional policy sensitivity frontier table, Optional budget phasing table, "
            "Optional scenario similarity matrix table.<br>"
            "<b>Output:</b> Markdown file with release title, timestamp, one-paragraph English description, "
            "and optional manual highlights section.<br>"
            "<b>Method:</b> Constructs a base sentence about the suite upgrade. "
            "If similarity data provided, appends cross-scenario reliability stats (mean/min/max Pearson r). "
            "If frontier data provided, appends policy signal (best lambda from 0.7*mean + 0.3*area>=80 utility). "
            "If budget data provided, appends impact-capture figures at ~30%, ~50%, and ~80% budget. "
            "All clauses are joined into a single flowing paragraph in English.<br>"
            "<b>Typical use:</b> Automatically generate a release announcement paragraph "
            "for stakeholder communication.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ReleaseNarrativeBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.PROJECT, "Project name", defaultValue="PlanX Suitability Lab"))
        self.addParameter(QgsProcessingParameterString(self.VERSION, "Release version label", defaultValue="1.x.x"))
        self.addParameter(
            QgsProcessingParameterString(
                self.HIGHLIGHTS,
                "Manual highlights (optional)",
                multiLine=True,
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.FRONTIER,
                "Policy sensitivity frontier table (optional)",
                [QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BUDGET,
                "Budget phasing table (optional)",
                [QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SIMILARITY,
                "Scenario similarity matrix table (optional)",
                [QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "Release narrative markdown", fileFilter="Markdown (*.md)"))

    @staticmethod
    def _frontier_pick(src):
        if src is None:
            return None
        names = src.fields().names()
        if "lambda" not in names or "mean_score" not in names:
            return None
        rows = []
        for f in src.getFeatures():
            lam = float(f["lambda"])
            mean_score = float(f["mean_score"])
            ge80 = float(f["area_ge_80_pct"]) if "area_ge_80_pct" in names else 0.0
            utility = (0.7 * mean_score) + (0.3 * ge80)
            rows.append((utility, lam, mean_score, ge80))
        if not rows:
            return None
        rows.sort(reverse=True)
        _, lam, mean_score, ge80 = rows[0]
        return {"lambda": lam, "mean_score": mean_score, "area_ge_80_pct": ge80}

    @staticmethod
    def _budget_pick(src):
        if src is None:
            return None
        names = src.fields().names()
        need = {"budget_pct", "impact_capture_pct"}
        if not need.issubset(set(names)):
            return None
        rows = []
        for f in src.getFeatures():
            b = int(f["budget_pct"])
            cap = float(f["impact_capture_pct"])
            rows.append((b, cap))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])

        def nearest(target):
            return min(rows, key=lambda x: abs(x[0] - target))

        b30 = nearest(30)
        b50 = nearest(50)
        b80 = nearest(80)
        return {"b30": b30, "b50": b50, "b80": b80}

    @staticmethod
    def _similarity_pick(src):
        if src is None:
            return None
        names = src.fields().names()
        if "pearson_r" not in names:
            return None
        vals = [float(f["pearson_r"]) for f in src.getFeatures()]
        if not vals:
            return None
        return {"mean_r": float(np.mean(vals)), "min_r": float(np.min(vals)), "max_r": float(np.max(vals))}

    def processAlgorithm(self, parameters, context, feedback):
        project = self.parameterAsString(parameters, self.PROJECT, context)
        version = self.parameterAsString(parameters, self.VERSION, context)
        highlights = self.parameterAsString(parameters, self.HIGHLIGHTS, context).strip()
        frontier = self.parameterAsSource(parameters, self.FRONTIER, context)
        budget = self.parameterAsSource(parameters, self.BUDGET, context)
        similarity = self.parameterAsSource(parameters, self.SIMILARITY, context)
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        fpick = self._frontier_pick(frontier)
        bpick = self._budget_pick(budget)
        spick = self._similarity_pick(similarity)

        lines = [
            f"# {project} {version} - Release Narrative",
            "",
            f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## One-Paragraph Release Description (EN)",
        ]

        en_parts = [
            f"{project} {version} upgrades the suite into a governance-ready raster MCDA decision studio by combining objective+subjective weighting diagnostics, multi-scenario synthesis, uncertainty-aware policy sensitivity, and direct implementation planning outputs."
        ]
        if spick is not None:
            en_parts.append(
                f"Cross-scenario reliability is strong with mean Pearson agreement {spick['mean_r']:.3f} (range {spick['min_r']:.3f}-{spick['max_r']:.3f})."
            )
        if fpick is not None:
            en_parts.append(
                f"The policy frontier indicates a balanced risk-aversion setting around lambda={fpick['lambda']:.2f}, with mean robust score {fpick['mean_score']:.2f} and {fpick['area_ge_80_pct']:.2f}% area above 80."
            )
        if bpick is not None:
            en_parts.append(
                f"Budget phasing shows impact capture of {bpick['b30'][1]:.2f}% at ~{bpick['b30'][0]}% budget, {bpick['b50'][1]:.2f}% at ~{bpick['b50'][0]}%, and {bpick['b80'][1]:.2f}% at ~{bpick['b80'][0]}%."
            )
        lines.append(" ".join(en_parts))

        if highlights:
            lines += [
                "",
                "## Manual Highlights",
                highlights,
            ]

        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return {self.OUTPUT: out}
