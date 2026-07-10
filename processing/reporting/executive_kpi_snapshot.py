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
    QgsCoordinateReferenceSystem,
)


class ExecutiveKpiSnapshotAlgorithm(QgsProcessingAlgorithm):
    SUITABILITY = "SUITABILITY"
    ROBUST = "ROBUST"
    CONSTRAINT = "CONSTRAINT"
    CONSENSUS_ZONE = "CONSENSUS_ZONE"
    ATTENTION_CLASS = "ATTENTION_CLASS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "executive_kpi_snapshot"

    def displayName(self):
        return "Reporting: Executive KPI Snapshot"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Produces a one-row management KPI table from five key rasters for executive dashboards.</b></p>"
            "<p><b>Inputs:</b> Suitability raster (0-100), Robust suitability raster (0-100), "
            "Constraint mask raster (0/1), Consensus zone raster (0-4), Disagreement attention class raster (0-4).<br>"
            "<b>Output:</b> Feature sink with one row: cells_total, area_total, mean_suit, mean_robust, "
            "top80_suit_pct, top80_robust_pct, eligible_pct (constraint-passing), excluded_pct, "
            "consensus_high_pct (zone>=3), consensus_unanim_pct (zone>=4), "
            "high_conflict_pct (attention>=3), critical_conflict_pct (attention>=4), "
            "confidence_gap (mean_suit - mean_robust).<br>"
            "<b>Method:</b> Reads all five rasters, validates dimensional consistency, intersects valid cells. "
            "Computes summary statistics: mean suitability, robust suitability, top-80% area shares, "
            "constraint eligibility, consensus strength, conflict severity, and the confidence gap. "
            "All percentages are relative to the valid overlapping domain.<br>"
            "<b>Typical use:</b> Single-page dashboard summary for senior decision-makers: "
            "how good is the land, how confident are we, and where are the conflicts?</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ExecutiveKpiSnapshotAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUITABILITY, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.ROBUST, "Robust suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSENSUS_ZONE, "Consensus zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.ATTENTION_CLASS, "Disagreement attention class raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Executive KPI table", QgsProcessing.TypeVector))

    @staticmethod
    def _read_arr(rl):
        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException(f"Cannot open raster: {rl.name()}")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)
        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        return arr, valid, ds

    def processAlgorithm(self, parameters, context, feedback):
        suit_rl = self.parameterAsRasterLayer(parameters, self.SUITABILITY, context)
        robust_rl = self.parameterAsRasterLayer(parameters, self.ROBUST, context)
        cons_rl = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)
        cz_rl = self.parameterAsRasterLayer(parameters, self.CONSENSUS_ZONE, context)
        att_rl = self.parameterAsRasterLayer(parameters, self.ATTENTION_CLASS, context)

        suit, v_s, ds = self._read_arr(suit_rl)
        robust, v_r, _ = self._read_arr(robust_rl)
        cons, v_c, _ = self._read_arr(cons_rl)
        cz, v_z, _ = self._read_arr(cz_rl)
        att, v_a, _ = self._read_arr(att_rl)

        shape = suit.shape
        for arr, name in ((robust, "ROBUST"), (cons, "CONSTRAINT"), (cz, "CONSENSUS_ZONE"), (att, "ATTENTION_CLASS")):
            if arr.shape != shape:
                raise QgsProcessingException(f"{name} raster must match SUITABILITY dimensions.")

        valid = v_s & v_r & v_c & v_z & v_a
        if not np.any(valid):
            raise QgsProcessingException("No overlapping valid cells across KPI inputs.")

        suit = np.clip(suit, 0.0, 100.0)
        robust = np.clip(robust, 0.0, 100.0)
        cons_bool = cons > 0.5
        cz_i = np.clip(np.rint(cz), 0, 4).astype(np.int32)
        att_i = np.clip(np.rint(att), 0, 4).astype(np.int32)

        vals_s = suit[valid]
        vals_r = robust[valid]
        vals_cons = cons_bool[valid]
        vals_cz = cz_i[valid]
        vals_att = att_i[valid]
        n = float(vals_s.size)

        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0
        total_area = n * cell_area

        mean_s = float(np.mean(vals_s))
        mean_r = float(np.mean(vals_r))
        top80_s = float(100.0 * np.sum(vals_s >= 80.0) / n)
        top80_r = float(100.0 * np.sum(vals_r >= 80.0) / n)
        eligible_pct = float(100.0 * np.sum(vals_cons) / n)
        excluded_pct = float(100.0 - eligible_pct)
        consensus_high_pct = float(100.0 * np.sum(vals_cz >= 3) / n)
        consensus_unanimous_pct = float(100.0 * np.sum(vals_cz >= 4) / n)
        critical_conflict_pct = float(100.0 * np.sum(vals_att >= 4) / n)
        high_conflict_pct = float(100.0 * np.sum(vals_att >= 3) / n)
        confidence_gap = float(mean_s - mean_r)

        fields = QgsFields()
        fields.append(QgsField("cells_total", QVariant.LongLong))
        fields.append(QgsField("area_total", QVariant.Double))
        fields.append(QgsField("mean_suit", QVariant.Double))
        fields.append(QgsField("mean_robust", QVariant.Double))
        fields.append(QgsField("top80_suit_pct", QVariant.Double))
        fields.append(QgsField("top80_robust_pct", QVariant.Double))
        fields.append(QgsField("eligible_pct", QVariant.Double))
        fields.append(QgsField("excluded_pct", QVariant.Double))
        fields.append(QgsField("consensus_high_pct", QVariant.Double))
        fields.append(QgsField("consensus_unanim_pct", QVariant.Double))
        fields.append(QgsField("high_conflict_pct", QVariant.Double))
        fields.append(QgsField("critical_conflict_pct", QVariant.Double))
        fields.append(QgsField("confidence_gap", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        feat = QgsFeature(fields)
        feat["cells_total"] = int(n)
        feat["area_total"] = float(total_area)
        feat["mean_suit"] = mean_s
        feat["mean_robust"] = mean_r
        feat["top80_suit_pct"] = top80_s
        feat["top80_robust_pct"] = top80_r
        feat["eligible_pct"] = eligible_pct
        feat["excluded_pct"] = excluded_pct
        feat["consensus_high_pct"] = consensus_high_pct
        feat["consensus_unanim_pct"] = consensus_unanimous_pct
        feat["high_conflict_pct"] = high_conflict_pct
        feat["critical_conflict_pct"] = critical_conflict_pct
        feat["confidence_gap"] = confidence_gap
        sink.addFeature(feat)
        return {self.OUTPUT: dest}
