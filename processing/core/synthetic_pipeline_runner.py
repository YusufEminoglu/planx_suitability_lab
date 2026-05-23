# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import processing
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterExtent, QgsProcessingParameterFolderDestination, QgsProcessingParameterNumber


class SyntheticPipelineRunnerAlgorithm(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    PIXEL = "PIXEL"
    OUTDIR = "OUTDIR"

    def name(self):
        return "synthetic_pipeline_runner"

    def displayName(self):
        return "Core: Synthetic End-to-End Pipeline Runner"

    def group(self):
        return "Core"

    def groupId(self):
        return "core"

    def createInstance(self):
        return SyntheticPipelineRunnerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(self.EXTENT, "Study extent"))
        self.addParameter(
            QgsProcessingParameterNumber(self.PIXEL, "Pixel size", type=QgsProcessingParameterNumber.Double, defaultValue=30.0, minValue=1.0)
        )
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTDIR, "Output folder"))

    def processAlgorithm(self, parameters, context, feedback):
        ex = self.parameterAsExtent(parameters, self.EXTENT, context)
        pix = float(self.parameterAsDouble(parameters, self.PIXEL, context))
        outdir = self.parameterAsString(parameters, self.OUTDIR, context)
        os.makedirs(outdir, exist_ok=True)

        syn = processing.run(
            "planx_suitability_lab:synthetic_sample_raster",
            {"EXTENT": ex, "PIXEL": pix, "OUTPUT_DIR": outdir},
            context=context,
            feedback=feedback,
        )
        wlc_out = os.path.join(outdir, "suitability_wlc.tif")
        owa_out = os.path.join(outdir, "suitability_owa.tif")
        topsis_out = os.path.join(outdir, "suitability_topsis.tif")
        delta_out = os.path.join(outdir, "suitability_delta_owa_minus_wlc.tif")
        delta_topsis = os.path.join(outdir, "suitability_delta_topsis_minus_wlc.tif")
        mc_mean = os.path.join(outdir, "unc_mean.tif")
        mc_std = os.path.join(outdir, "unc_std.tif")
        mc_p05 = os.path.join(outdir, "unc_p05.tif")
        mc_p50 = os.path.join(outdir, "unc_p50.tif")
        mc_p95 = os.path.join(outdir, "unc_p95.tif")
        mc_stb = os.path.join(outdir, "stability_index.tif")
        robust_out = os.path.join(outdir, "suitability_robust.tif")
        rep = os.path.join(outdir, "suitability_report.html")
        brief = os.path.join(outdir, "scenario_brief.md")
        q = os.path.join(outdir, "beta_evidence.html")

        processing.run(
            "planx_suitability_lab:wlc_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "WEIGHTS_CSV": "0.25,0.25,0.25,0.25",
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "OUTPUT": wlc_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:owa_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "CRITERIA_WEIGHTS": "0.25,0.25,0.25,0.25",
                "ORDER_WEIGHTS": "0.4,0.3,0.2,0.1",
                "SORT_MODE": 0,
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "OUTPUT": owa_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:topsis_suitability",
            {
                "INPUT_RASTERS": [syn["CRITERION_1"], syn["CRITERION_2"], syn["CRITERION_3"], syn["CRITERION_4"]],
                "WEIGHTS_CSV": "0.25,0.25,0.25,0.25",
                "IMPACTS_CSV": "B,B,B,C",
                "CONSTRAINT": syn["CONSTRAINT_MASK"],
                "BLOCK": 256,
                "OUTPUT": topsis_out,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_comparator",
            {"A": wlc_out, "B": owa_out, "OUTPUT": delta_out},
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_comparator",
            {"A": wlc_out, "B": topsis_out, "OUTPUT": delta_topsis},
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:montecarlo_suitability",
            {
                "INPUT": wlc_out,
                "ITER": 120,
                "SIGMA": 0.08,
                "BLOCK": 256,
                "OUT_MEAN": mc_mean,
                "OUT_STD": mc_std,
                "OUT_P05": mc_p05,
                "OUT_P50": mc_p50,
                "OUT_P95": mc_p95,
                "OUT_STAB": mc_stb,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:uncertainty_adjusted_suitability",
            {
                "MEAN": mc_mean,
                "STD": mc_std,
                "RISK": 1.0,
                "OUTPUT": robust_out,
            },
            context=context,
            feedback=feedback,
        )
        qa = processing.run(
            "planx_suitability_lab:numerical_qa_check",
            {
                "SUIT": wlc_out,
                "P05": mc_p05,
                "P50": mc_p50,
                "P95": mc_p95,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:suitability_html_report",
            {
                "PROJECT": "PlanX Synthetic Smoke Study",
                "SUMMARY": "Synthetic run completed with WLC, OWA, TOPSIS, scenario deltas and Monte Carlo uncertainty outputs.",
                "WEIGHT_METHOD": "Equal criteria; OWA descending order weights; TOPSIS impacts=B,B,B,C",
                "QA_SUMMARY": qa["OUTPUT"],
                "OUTPUT": rep,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:scenario_markdown_brief",
            {
                "PROJECT": "PlanX Synthetic Smoke Study",
                "BASELINE": "WLC baseline",
                "SCENARIO": "OWA/TOPSIS and robust overlay",
                "QA": qa["OUTPUT"],
                "NOTES": "Synthetic smoke run for environment verification.",
                "OUTPUT": brief,
            },
            context=context,
            feedback=feedback,
        )
        processing.run(
            "planx_suitability_lab:beta_evidence_report",
            {
                "SUMMARY": "Synthetic pipeline executed: synthetic -> WLC/OWA/TOPSIS -> deltas -> Monte Carlo -> QA -> reports.\n\n"
                + qa["OUTPUT"],
                "OUTPUT": q,
            },
            context=context,
            feedback=feedback,
        )
        return {
            "SYNTHETIC_DIR": syn["OUTPUT_DIR"],
            "WLC": wlc_out,
            "OWA": owa_out,
            "TOPSIS": topsis_out,
            "DELTA": delta_out,
            "DELTA_TOPSIS": delta_topsis,
            "UNC_MEAN": mc_mean,
            "UNC_STD": mc_std,
            "UNC_P05": mc_p05,
            "UNC_P50": mc_p50,
            "UNC_P95": mc_p95,
            "STABILITY": mc_stb,
            "ROBUST": robust_out,
            "SUITABILITY_REPORT": rep,
            "SCENARIO_BRIEF": brief,
            "QA_SUMMARY": qa["OUTPUT"],
            "EVIDENCE_HTML": q,
            self.OUTDIR: outdir,
        }
