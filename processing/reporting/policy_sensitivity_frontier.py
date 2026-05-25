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
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsCoordinateReferenceSystem,
)


class PolicySensitivityFrontierAlgorithm(QgsProcessingAlgorithm):
    MEAN = "MEAN"
    STD = "STD"
    LAMBDAS = "LAMBDAS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "policy_sensitivity_frontier"

    def displayName(self):
        return "Reporting: Policy Sensitivity Frontier"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return PolicySensitivityFrontierAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.MEAN, "Uncertainty mean raster (unc_mean)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.STD, "Uncertainty std raster (unc_std)"))
        self.addParameter(
            QgsProcessingParameterString(
                self.LAMBDAS,
                "Risk-aversion lambda list (CSV, e.g. 0,0.5,1,1.5,2)",
                defaultValue="0,0.5,1,1.5,2",
                optional=False,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Policy sensitivity frontier table", QgsProcessing.TypeVector))

    @staticmethod
    def _parse_lambdas(text: str):
        vals = []
        for raw in (text or "").split(","):
            token = raw.strip()
            if not token:
                continue
            vals.append(float(token))
        vals = sorted(set(vals))
        if not vals:
            vals = [0.0, 1.0, 2.0]
        return vals

    def processAlgorithm(self, parameters, context, feedback):
        mean_rl = self.parameterAsRasterLayer(parameters, self.MEAN, context)
        std_rl = self.parameterAsRasterLayer(parameters, self.STD, context)
        lambdas = self._parse_lambdas(self.parameterAsString(parameters, self.LAMBDAS, context))

        ds_m = gdal.Open(mean_rl.source(), gdal.GA_ReadOnly)
        ds_s = gdal.Open(std_rl.source(), gdal.GA_ReadOnly)
        if ds_m is None or ds_s is None:
            raise QgsProcessingException("Cannot open uncertainty mean/std rasters.")
        if ds_m.RasterXSize != ds_s.RasterXSize or ds_m.RasterYSize != ds_s.RasterYSize:
            raise QgsProcessingException("Mean and std rasters must have same dimensions.")

        bm = ds_m.GetRasterBand(1)
        bs = ds_s.GetRasterBand(1)
        mean = bm.ReadAsArray().astype(np.float32)
        std = bs.ReadAsArray().astype(np.float32)
        ndm = bm.GetNoDataValue()
        nds = bs.GetNoDataValue()
        valid = np.isfinite(mean) & np.isfinite(std)
        if ndm is not None:
            valid &= mean != ndm
        if nds is not None:
            valid &= std != nds
        if not np.any(valid):
            raise QgsProcessingException("No valid overlapping cells in mean/std rasters.")

        fields = QgsFields()
        fields.append(QgsField("lambda", QVariant.Double))
        fields.append(QgsField("mean_score", QVariant.Double))
        fields.append(QgsField("median_score", QVariant.Double))
        fields.append(QgsField("p90_score", QVariant.Double))
        fields.append(QgsField("area_ge_80_pct", QVariant.Double))
        fields.append(QgsField("area_ge_60_pct", QVariant.Double))
        fields.append(QgsField("delta_vs_prev", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        prev_mean = None
        for lam in lambdas:
            robust = np.clip(mean - float(lam) * std, 0.0, 100.0)
            vals = robust[valid]
            m = float(np.mean(vals))
            med = float(np.median(vals))
            p90 = float(np.percentile(vals, 90))
            ge80 = float((np.sum(vals >= 80.0) / vals.size) * 100.0)
            ge60 = float((np.sum(vals >= 60.0) / vals.size) * 100.0)
            delta = 0.0 if prev_mean is None else float(m - prev_mean)
            prev_mean = m

            f = QgsFeature(fields)
            f["lambda"] = float(lam)
            f["mean_score"] = m
            f["median_score"] = med
            f["p90_score"] = p90
            f["area_ge_80_pct"] = ge80
            f["area_ge_60_pct"] = ge60
            f["delta_vs_prev"] = delta
            sink.addFeature(f)

        return {self.OUTPUT: dest}
