# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsCoordinateReferenceSystem,
)

from .._mcda_utils import ensure_list, parse_weights_csv


class GlobalSensitivityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    SAMPLE = "SAMPLE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "xai_global_sensitivity"

    def displayName(self):
        return "XAI: Global Sensitivity"

    def group(self):
        return "Explainability"

    def groupId(self):
        return "xai"

    def shortHelpString(self):
        return (
            "<p><b>Ranks criterion influence on suitability via sampled spatial-variance analysis "
            "across the study area.</b></p>"
            "<p><b>Inputs:</b> Multiple criterion rasters (normalized, aligned); "
            "optional weights CSV (comma-separated, one per criterion; equal weights if blank); "
            "sampling stride in cells (>=1, default 8).<br>"
            "<b>Output:</b> Attribute table (no geometry) with fields: criterion name, weight, "
            "sampled mean, sampled std, weighted_std (std * weight), "
            "importance (0-1, normalized across all criteria).<br>"
            "<b>Method:</b> Each criterion raster is sampled at a regular stride; "
            "the standard deviation of sampled values reflects spatial variation. "
            "Multiplying by the user-assigned weight yields a weighted sensitivity proxy. "
            "Importance scores are normalized so they sum to 1, "
            "ranking criteria by their contribution to overall suitability variation. "
            "Higher importance means the criterion drives differentiation across the study area.<br>"
            "<b>Typical use:</b> Quickly identify which criteria dominate the suitability pattern. "
            "Low-importance criteria may be candidates for removal to simplify the model.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return GlobalSensitivityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, "Criterion rasters", QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, "Weights CSV (optional)", defaultValue="", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SAMPLE,
                "Sampling stride (cells)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=8,
                minValue=1,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "xai_global_table", QgsProcessing.TypeVector))

    def _sample_stats(self, raster_path, stride):
        ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
        arr = ds.GetRasterBand(1).ReadAsArray()
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        sampled = arr[::stride, ::stride].astype(np.float32)
        mask = np.isfinite(sampled)
        if nodata is not None:
            mask &= sampled != nodata
        vals = sampled[mask]
        if vals.size == 0:
            return 0.0, 0.0
        return float(np.mean(vals)), float(np.std(vals))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        if not layers:
            raise Exception("No criterion rasters provided for global sensitivity.")
        stride = int(self.parameterAsInt(parameters, self.SAMPLE, context))
        weights = parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), len(layers))

        stats = []
        for i, lyr in enumerate(layers):
            mean_v, std_v = self._sample_stats(lyr.source(), stride)
            weighted_std = std_v * weights[i]
            stats.append((lyr.name(), weights[i], mean_v, std_v, weighted_std))

        total = sum(abs(r[4]) for r in stats) or 1.0
        fields = QgsFields()
        fields.append(QgsField("criterion", QVariant.String))
        fields.append(QgsField("weight", QVariant.Double))
        fields.append(QgsField("mean", QVariant.Double))
        fields.append(QgsField("std", QVariant.Double))
        fields.append(QgsField("weighted_std", QVariant.Double))
        fields.append(QgsField("importance", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        for row in stats:
            f = QgsFeature(fields)
            f["criterion"] = row[0]
            f["weight"] = row[1]
            f["mean"] = row[2]
            f["std"] = row[3]
            f["weighted_std"] = row[4]
            f["importance"] = abs(row[4]) / total
            sink.addFeature(f)
        return {self.OUTPUT: dest}
