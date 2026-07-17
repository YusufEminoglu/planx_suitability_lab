# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_weights_csv, raster_calc


class LocalContributionAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    OUTPUT_DIR = "OUTPUT_DIR"

    def name(self):
        return "xai_local_contribution"

    def displayName(self):
        return "XAI: Local Contribution Decomposition"

    def group(self):
        return "Explainability"

    def groupId(self):
        return "xai"

    def shortHelpString(self):
        return (
            "<p><b>Decomposes final suitability into per-criterion absolute contribution "
            "and percentage share rasters.</b></p>"
            "<p><b>Inputs:</b> Up to 6 criterion rasters (normalized, aligned, same dimensions); "
            "optional weights CSV (comma-separated, one per criterion; equal weights if blank).<br>"
            "<b>Output:</b> Folder containing N absolute contribution rasters (xai_local_contribution_{i}.tif), "
            "N percentage rasters (xai_local_contribution_pct_{i}.tif, range 0-100), "
            "and one denominator raster (xai_local_contribution_total_abs.tif). "
            "All rasters are Float32, full extent, pixel-wise computation.<br>"
            "<b>Method:</b> For each criterion, the absolute weighted contribution is |value * weight|. "
            "The per-cell denominator is the sum of all absolute contributions (clamped to >=1e-6 to avoid division by zero). "
            "Each criterion's percentage share = (abs_contribution / denominator) * 100, "
            "showing what fraction of the total weighted score originates from each input at every cell.<br>"
            "<b>Typical use:</b> Inspect which criteria dominate suitability at any location. "
            "A single criterion contributing over 50% may warrant closer data-quality scrutiny at that site.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return LocalContributionAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, "Weights CSV", defaultValue=""))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_DIR, "Output folder for xai_local_contribution_*"))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        if not layers:
            raise Exception("No criterion rasters were provided.")
        out_dir = self.parameterAsString(parameters, self.OUTPUT_DIR, context)
        weights = parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), len(layers))

        letters = ["A", "B", "C", "D", "E", "F"]
        abs_terms = []
        for i, lyr in enumerate(layers):
            out_abs = os.path.join(out_dir, f"xai_local_contribution_{i+1}.tif")
            raster_calc([lyr.source()], f"{letters[0]}*{weights[i]:.12f}", out_abs)
            abs_terms.append(out_abs)

        # Sum of absolute weighted contributions for local share denominator.
        denom = os.path.join(out_dir, "xai_local_contribution_total_abs.tif")
        d_letters = letters[: len(abs_terms)]
        d_formula = "maximum(0.000001,(" + "+".join([f"abs({letter})" for letter in d_letters]) + "))"
        raster_calc(abs_terms, d_formula, denom)

        for i, abs_path in enumerate(abs_terms):
            out_pct = os.path.join(out_dir, f"xai_local_contribution_pct_{i+1}.tif")
            raster_calc([abs_path, denom], "(A/B)*100.0", out_pct)

        return {self.OUTPUT_DIR: out_dir}

