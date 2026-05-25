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
)


class ImplementationWavePlannerAlgorithm(QgsProcessingAlgorithm):
    PRIORITY_ZONE = "PRIORITY_ZONE"
    RISK_MATRIX = "RISK_MATRIX"
    OUTPUT = "OUTPUT"

    def name(self):
        return "implementation_wave_planner"

    def displayName(self):
        return "Reporting: Implementation Wave Planner"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ImplementationWavePlannerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_ZONE, "Priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.RISK_MATRIX, "Risk-opportunity matrix raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Implementation wave plan", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        pr_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_ZONE, context)
        rk_rl = self.parameterAsRasterLayer(parameters, self.RISK_MATRIX, context)

        ds_p = gdal.Open(pr_rl.source(), gdal.GA_ReadOnly)
        ds_r = gdal.Open(rk_rl.source(), gdal.GA_ReadOnly)
        if ds_p is None or ds_r is None:
            raise QgsProcessingException("Cannot open priority/risk rasters.")
        if ds_p.RasterXSize != ds_r.RasterXSize or ds_p.RasterYSize != ds_r.RasterYSize:
            raise QgsProcessingException("Priority and risk rasters must share identical dimensions.")

        b_p = ds_p.GetRasterBand(1)
        b_r = ds_r.GetRasterBand(1)
        nd_p = b_p.GetNoDataValue()
        nd_r = b_r.GetNoDataValue()

        p_arr = b_p.ReadAsArray().astype(np.float32)
        r_arr = b_r.ReadAsArray().astype(np.float32)
        valid = np.isfinite(p_arr) & np.isfinite(r_arr)
        if nd_p is not None:
            valid &= p_arr != nd_p
        if nd_r is not None:
            valid &= r_arr != nd_r
        if not np.any(valid):
            raise QgsProcessingException("No overlapping valid cells between priority and risk matrices.")

        p = np.clip(np.rint(p_arr), 0, 4).astype(np.int32)
        r = np.clip(np.rint(r_arr), 0, 4).astype(np.int32)

        wave = np.zeros_like(p, dtype=np.int32)
        # Wave 1: immediate delivery - high priority + invest-now profile.
        wave = np.where((p >= 3) & (r == 1), 1, wave)
        # Wave 2: high priority but requires validation.
        wave = np.where((p >= 3) & (r == 2), 2, wave)
        # Wave 3: medium priority, still strategically meaningful.
        wave = np.where((wave == 0) & (p == 2) & ((r == 1) | (r == 2)), 3, wave)
        # Wave 4: deferred monitoring, contested or low-value zones.
        wave = np.where((wave == 0) & valid, 4, wave)
        wave = np.where(valid, wave, 0)

        gt = ds_p.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        counts = np.zeros(5, dtype=np.float64)
        for w in (1, 2, 3, 4):
            counts[w] = float(np.sum((wave == w) & valid))
        total = float(np.sum(counts[1:5]))

        fields = QgsFields()
        fields.append(QgsField("wave_id", QVariant.Int))
        fields.append(QgsField("wave_label", QVariant.String))
        fields.append(QgsField("strategy", QVariant.String))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("pct", QVariant.Double))
        fields.append(QgsField("area", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        labels = {
            1: ("WAVE_1", "RAPID_DELIVERY"),
            2: ("WAVE_2", "TARGETED_VALIDATION"),
            3: ("WAVE_3", "STRUCTURED_UPLIFT"),
            4: ("WAVE_4", "DEFER_MONITOR"),
        }
        for w in (1, 2, 3, 4):
            c = counts[w]
            feat = QgsFeature(fields)
            feat["wave_id"] = int(w)
            feat["wave_label"] = labels[w][0]
            feat["strategy"] = labels[w][1]
            feat["cells"] = int(c)
            feat["pct"] = float(100.0 * c / total) if total > 0 else 0.0
            feat["area"] = float(c * cell_area)
            sink.addFeature(feat)

        feedback.pushInfo(
            "Implementation wave shares: "
            f"W1={100.0 * counts[1] / max(total, 1.0):.2f}%, "
            f"W2={100.0 * counts[2] / max(total, 1.0):.2f}%, "
            f"W3={100.0 * counts[3] / max(total, 1.0):.2f}%, "
            f"W4={100.0 * counts[4] / max(total, 1.0):.2f}%"
        )
        return {self.OUTPUT: dest}

