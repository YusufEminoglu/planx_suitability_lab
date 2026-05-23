# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
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
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, 1, None)
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

