# -*- coding: utf-8 -*-
from __future__ import annotations

from math import ceil

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
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsCoordinateReferenceSystem,
)


class InterventionBudgetPhasingAlgorithm(QgsProcessingAlgorithm):
    PRIORITY_ZONE = "PRIORITY_ZONE"
    PRIORITY_INDEX = "PRIORITY_INDEX"
    COST = "COST"
    COST_BY_ZONE = "COST_BY_ZONE"
    STEP = "STEP"
    OUTPUT = "OUTPUT"

    def name(self):
        return "intervention_budget_phasing"

    def displayName(self):
        return "Reporting: Intervention Budget Phasing"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Computes a budget-step impact-capture curve by ranking cells by intervention urgency.</b></p>"
            "<p><b>Inputs:</b> Priority zone raster (0-4), Optional priority index raster, "
            "Optional per-cell cost raster, Fallback unit cost by zone CSV (5 values for zones 0-4), "
            "Budget step percent (5-50, default 10).<br>"
            "<b>Output:</b> Feature sink with one row per budget checkpoint: budget_pct, phase_label "
            "(Quick Wins <=30%, Core Delivery <=60%, Scale-out <=90%, Full Coverage), "
            "cells_selected, cells_pct, cost_cum, impact_cum, impact_capture_pct, avg_index_selected.<br>"
            "<b>Method:</b> Ranks cells by (zone*1000 + priority_index) descending, then sorts. "
            "Computes cumulative cost and cumulative impact (priority index) along this ranked order. "
            "At each budget checkpoint, reports how many cells are captured, cumulative impact, "
            "and what percentage of total possible impact has been achieved. "
            "Missing cost cells fall back to zone-specific unit costs.<br>"
            "<b>Typical use:</b> Build a business case: show decision-makers how much impact each budget increment buys.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return InterventionBudgetPhasingAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_ZONE, "Priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_INDEX, "Priority index raster (optional)", optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(self.COST, "Per-cell intervention cost raster (optional)", optional=True))
        self.addParameter(
            QgsProcessingParameterString(
                self.COST_BY_ZONE,
                "Fallback unit cost by zone CSV for zones 0..4 (e.g. 0.6,0.9,1.2,1.5,1.8)",
                defaultValue="0.6,0.9,1.2,1.5,1.8",
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STEP,
                "Budget step percent",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=10,
                minValue=5,
                maxValue=50,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Budget phasing table", QgsProcessing.TypeVector))

    @staticmethod
    def _parse_zone_costs(text: str):
        vals = [float(v.strip()) for v in (text or "").split(",") if v.strip()]
        if len(vals) != 5:
            raise QgsProcessingException("COST_BY_ZONE must contain exactly 5 numeric values for zones 0..4.")
        if any(v <= 0 for v in vals):
            raise QgsProcessingException("COST_BY_ZONE values must be positive.")
        return np.array(vals, dtype=np.float64)

    @staticmethod
    def _phase_label(p):
        if p <= 30:
            return "Quick Wins"
        if p <= 60:
            return "Core Delivery"
        if p <= 90:
            return "Scale-out"
        return "Full Coverage"

    def processAlgorithm(self, parameters, context, feedback):
        z_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_ZONE, context)
        idx_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_INDEX, context)
        c_rl = self.parameterAsRasterLayer(parameters, self.COST, context)
        fallback_cost = self._parse_zone_costs(self.parameterAsString(parameters, self.COST_BY_ZONE, context))
        step = int(self.parameterAsInt(parameters, self.STEP, context))

        ds_z = gdal.Open(z_rl.source(), gdal.GA_ReadOnly)
        if ds_z is None:
            raise QgsProcessingException("Cannot open priority zone raster.")
        bz = ds_z.GetRasterBand(1)
        z = bz.ReadAsArray().astype(np.int16)
        ndz = bz.GetNoDataValue()
        valid = np.isfinite(z)
        if ndz is not None:
            valid &= z != int(ndz)

        if idx_rl is not None:
            ds_i = gdal.Open(idx_rl.source(), gdal.GA_ReadOnly)
            if ds_i is None:
                raise QgsProcessingException("Cannot open priority index raster.")
            if ds_i.RasterXSize != ds_z.RasterXSize or ds_i.RasterYSize != ds_z.RasterYSize:
                raise QgsProcessingException("Priority index raster must match priority zone dimensions.")
            bi = ds_i.GetRasterBand(1)
            idx = bi.ReadAsArray().astype(np.float32)
            ndi = bi.GetNoDataValue()
            valid_i = np.isfinite(idx)
            if ndi is not None:
                valid_i &= idx != ndi
            valid &= valid_i
        else:
            idx = np.clip((z.astype(np.float32) / 4.0) * 100.0, 0.0, 100.0)

        if c_rl is not None:
            ds_c = gdal.Open(c_rl.source(), gdal.GA_ReadOnly)
            if ds_c is None:
                raise QgsProcessingException("Cannot open cost raster.")
            if ds_c.RasterXSize != ds_z.RasterXSize or ds_c.RasterYSize != ds_z.RasterYSize:
                raise QgsProcessingException("Cost raster must match priority zone dimensions.")
            bc = ds_c.GetRasterBand(1)
            c = bc.ReadAsArray().astype(np.float32)
            ndc = bc.GetNoDataValue()
            valid_c = np.isfinite(c)
            if ndc is not None:
                valid_c &= c != ndc
            valid &= valid_c
            c = np.where(c > 0, c, np.nan)
        else:
            c = np.full(z.shape, np.nan, dtype=np.float32)

        if not np.any(valid):
            raise QgsProcessingException("No valid cells available for budget phasing.")

        zf = z[valid].astype(np.int16)
        idxf = np.clip(idx[valid].astype(np.float64), 0.0, 100.0)
        cf = c[valid].astype(np.float64)
        missing_cost = ~np.isfinite(cf) | (cf <= 0)
        cf[missing_cost] = fallback_cost[np.clip(zf[missing_cost], 0, 4)]

        # Rank by intervention urgency: high zones first, then high index.
        rank = (zf.astype(np.float64) * 1000.0) + idxf
        order = np.argsort(-rank)
        cf = cf[order]
        idxf = idxf[order]

        cum_cost = np.cumsum(cf)
        cum_impact = np.cumsum(idxf)
        total_cost = float(cum_cost[-1])
        total_impact = float(cum_impact[-1])
        n_cells = int(cf.size)

        fields = QgsFields()
        fields.append(QgsField("budget_pct", QVariant.Int))
        fields.append(QgsField("phase_label", QVariant.String))
        fields.append(QgsField("cells_selected", QVariant.LongLong))
        fields.append(QgsField("cells_pct", QVariant.Double))
        fields.append(QgsField("cost_cum", QVariant.Double))
        fields.append(QgsField("impact_cum", QVariant.Double))
        fields.append(QgsField("impact_capture_pct", QVariant.Double))
        fields.append(QgsField("avg_index_selected", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        checkpoints = list(range(step, 101, step))
        if checkpoints[-1] != 100:
            checkpoints.append(100)

        for p in checkpoints:
            budget = (p / 100.0) * total_cost
            k = int(np.searchsorted(cum_cost, budget, side="left")) + 1
            k = min(max(k, 1), n_cells)
            cost_k = float(cum_cost[k - 1])
            impact_k = float(cum_impact[k - 1])
            cap = (impact_k / total_impact * 100.0) if total_impact > 1e-12 else 0.0
            avg_idx = float(np.mean(idxf[:k])) if k > 0 else 0.0

            f = QgsFeature(fields)
            f["budget_pct"] = int(p)
            f["phase_label"] = self._phase_label(p)
            f["cells_selected"] = int(k)
            f["cells_pct"] = float(k / n_cells * 100.0)
            f["cost_cum"] = cost_k
            f["impact_cum"] = impact_k
            f["impact_capture_pct"] = cap
            f["avg_index_selected"] = avg_idx
            sink.addFeature(f)

        return {self.OUTPUT: dest}
