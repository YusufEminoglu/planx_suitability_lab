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
        mc_mean = os.path.join(outdir, "unc_mean.tif")
        mc_std = os.path.join(outdir, "unc_std.tif")
        mc_p05 = os.path.join(outdir, "unc_p05.tif")
        mc_p50 = os.path.join(outdir, "unc_p50.tif")
        mc_p95 = os.path.join(outdir, "unc_p95.tif")
        mc_stb = os.path.join(outdir, "stability_index.tif")
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
            "planx_suitability_lab:montecarlo_suitability",
            {
                "INPUT": wlc_out,
                "ITER": 120,
                "SIGMA": 0.08,
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
            "planx_suitability_lab:beta_evidence_report",
            {
                "SUMMARY": "Synthetic pipeline executed: synthetic -> WLC -> Monte Carlo.",
                "OUTPUT": q,
            },
            context=context,
            feedback=feedback,
        )
        return {
            "SYNTHETIC_DIR": syn["OUTPUT_DIR"],
            "WLC": wlc_out,
            "UNC_MEAN": mc_mean,
            "UNC_STD": mc_std,
            "UNC_P05": mc_p05,
            "UNC_P50": mc_p50,
            "UNC_P95": mc_p95,
            "STABILITY": mc_stb,
            "EVIDENCE_HTML": q,
            self.OUTDIR: outdir,
        }

