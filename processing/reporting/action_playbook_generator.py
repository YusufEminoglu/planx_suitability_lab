# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)


class ActionPlaybookGeneratorAlgorithm(QgsProcessingAlgorithm):
    PROJECT = "PROJECT"
    PRIORITY_ZONE = "PRIORITY_ZONE"
    PRIORITY_INDEX = "PRIORITY_INDEX"
    FRONTIER = "FRONTIER"
    SIMILARITY = "SIMILARITY"
    NOTES = "NOTES"
    OUTPUT = "OUTPUT"

    def name(self):
        return "action_playbook_generator"

    def displayName(self):
        return "Reporting: Action Playbook Generator (Markdown)"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ActionPlaybookGeneratorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(self.PROJECT, "Project name", defaultValue="PlanX Suitability Study"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_ZONE, "Priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_INDEX, "Priority index raster (0..100, optional)", optional=True))
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
                self.SIMILARITY,
                "Scenario similarity matrix table (optional)",
                [QgsProcessing.TypeVector],
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
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, "Markdown action playbook", fileFilter="Markdown (*.md)"))

    @staticmethod
    def _zone_name(z):
        mapping = {
            0: "Low Priority",
            1: "Longlist Candidate",
            2: "Detailed Feasibility",
            3: "Immediate Priority",
            4: "Constraint-Revisit Critical",
        }
        return mapping.get(z, f"Zone {z}")

    def _best_lambda_from_frontier(self, src):
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
            # Balanced utility: reward high mean and high high-suitability coverage.
            utility = (0.7 * mean_score) + (0.3 * ge80)
            rows.append((utility, lam, mean_score, ge80))
        if not rows:
            return None
        rows.sort(reverse=True)
        _, lam, mean_score, ge80 = rows[0]
        return {"lambda": lam, "mean_score": mean_score, "area_ge_80_pct": ge80}

    def _similarity_summary(self, src):
        if src is None:
            return None
        names = src.fields().names()
        if "pearson_r" not in names:
            return None
        vals = []
        low_pairs = []
        for f in src.getFeatures():
            r = float(f["pearson_r"])
            vals.append(r)
            if r < 0.70 and "scenario_a" in names and "scenario_b" in names:
                low_pairs.append((str(f["scenario_a"]), str(f["scenario_b"]), r))
        if not vals:
            return None
        out = {
            "mean_r": float(np.mean(vals)),
            "min_r": float(np.min(vals)),
            "max_r": float(np.max(vals)),
            "low_pairs": low_pairs[:3],
        }
        return out

    def processAlgorithm(self, parameters, context, feedback):
        project = self.parameterAsString(parameters, self.PROJECT, context)
        zone_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_ZONE, context)
        idx_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_INDEX, context)
        frontier_src = self.parameterAsSource(parameters, self.FRONTIER, context)
        sim_src = self.parameterAsSource(parameters, self.SIMILARITY, context)
        notes = self.parameterAsString(parameters, self.NOTES, context).strip()
        out = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        ds_z = gdal.Open(zone_rl.source(), gdal.GA_ReadOnly)
        if ds_z is None:
            raise QgsProcessingException("Cannot open priority zone raster.")
        bz = ds_z.GetRasterBand(1)
        az = bz.ReadAsArray().astype(np.int16)
        ndz = bz.GetNoDataValue()
        valid = np.isfinite(az)
        if ndz is not None:
            valid &= az != int(ndz)
        if not np.any(valid):
            raise QgsProcessingException("No valid cells in priority zone raster.")

        counts = {}
        total = int(np.sum(valid))
        for z in range(5):
            counts[z] = int(np.sum(valid & (az == z)))

        zone_mean_index = {}
        if idx_rl is not None:
            ds_i = gdal.Open(idx_rl.source(), gdal.GA_ReadOnly)
            if ds_i is not None and ds_i.RasterXSize == ds_z.RasterXSize and ds_i.RasterYSize == ds_z.RasterYSize:
                bi = ds_i.GetRasterBand(1)
                ai = bi.ReadAsArray().astype(np.float32)
                ndi = bi.GetNoDataValue()
                valid_i = np.isfinite(ai)
                if ndi is not None:
                    valid_i &= ai != ndi
                for z in range(5):
                    m = valid & valid_i & (az == z)
                    zone_mean_index[z] = float(np.mean(ai[m])) if np.any(m) else 0.0

        best_frontier = self._best_lambda_from_frontier(frontier_src)
        sim = self._similarity_summary(sim_src)

        def pct(n):
            return (100.0 * n / total) if total > 0 else 0.0

        md = [
            f"# {project} - Action Playbook",
            "",
            f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Valid analysis cells: {total}",
            "",
            "## 1) Priority Zoning Snapshot",
        ]
        for z in range(5):
            line = f"- Zone {z} ({self._zone_name(z)}): {counts[z]} cells ({pct(counts[z]):.2f}%)"
            if z in zone_mean_index:
                line += f", mean priority index={zone_mean_index[z]:.2f}"
            md.append(line)

        md += [
            "",
            "## 2) Operational Recommendations (EN)",
            "1. Immediate execution: focus first on Zone 3 polygons (high suitability + high confidence).",
            "2. Pipeline development: prepare feasibility packages for Zone 2.",
            "3. Reserve portfolio: keep Zone 1 in longlist and monitor data updates.",
            "4. Policy revision desk: analyze Zone 4 to identify over-restrictive hard constraints.",
            "5. Defer low-value areas: avoid Zone 0 for near-term investment cycles.",
            "",
            "## 3) Uygulama Onerileri (TR)",
            "1. Acil uygulama: once Zone 3 alanlarinda proje uygulamasina gecin.",
            "2. Hazirlik paketi: Zone 2 icin detayli fizibilite ve saha dogrulama planlayin.",
            "3. Aday havuzu: Zone 1'i uzun liste olarak izlemeye alin.",
            "4. Politika revizyonu: Zone 4 uzerinden kisit kurallarini yeniden degerlendirin.",
            "5. Dusek oncelik: Zone 0 alanlari kisa vadeli yatirimdan dislayin.",
        ]

        if best_frontier is not None:
            md += [
                "",
                "## 4) Policy Sensitivity Signal",
                f"- Suggested balanced lambda: **{best_frontier['lambda']:.2f}**",
                f"- Mean robust score at this lambda: {best_frontier['mean_score']:.2f}",
                f"- Area >=80 suitability share: {best_frontier['area_ge_80_pct']:.2f}%",
            ]

        if sim is not None:
            md += [
                "",
                "## 5) Cross-Scenario Reliability",
                f"- Mean Pearson agreement: {sim['mean_r']:.3f}",
                f"- Min / Max Pearson agreement: {sim['min_r']:.3f} / {sim['max_r']:.3f}",
            ]
            if sim["low_pairs"]:
                md.append("- Low-agreement pairs (review assumptions):")
                for a, b, r in sim["low_pairs"]:
                    md.append(f"  - {a} vs {b}: r={r:.3f}")

        md += [
            "",
            "## 6) Planner Notes",
            notes if notes else "_No additional notes provided._",
        ]

        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        return {self.OUTPUT: out}
