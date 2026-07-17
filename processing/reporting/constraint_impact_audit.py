# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)

from .._mcda_utils import ensure_list


class ConstraintImpactAuditAlgorithm(QgsProcessingAlgorithm):
    SUITABILITY = "SUITABILITY"
    CONSTRAINTS = "CONSTRAINTS"
    HIGH_THRESHOLD = "HIGH_THRESHOLD"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "constraint_impact_audit"

    def displayName(self):
        return "Reporting: Constraint Impact Audit"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Measures how much each hard constraint mask reduces available suitability and high-suitability area.</b></p>"
            "<p><b>Inputs:</b> Suitability raster (0-100), Constraint mask rasters (0/1, 0=excluded), "
            "High suitability threshold (0-100, default 70), Block size (64-2048).<br>"
            "<b>Output:</b> Feature sink with per-constraint rows: excluded_cells, excluded_pct, excluded_area, "
            "excluded_high_cells, excluded_high_pct, priority_risk (CRITICAL>=25%, HIGH>=12%, MEDIUM>=5%, LOW). "
            "Union row __ALL_CONSTRAINTS_UNION__ with combined impact.<br>"
            "<b>Method:</b> For each constraint mask, counts cells where mask <= 0.5 and suitability is valid. "
            "Also counts high-suitability cells (>= threshold) excluded by each constraint. "
            "Computes excluded percentage relative to total valid and total high cells. "
            "The union row reports the combined exclusion of all constraints.<br>"
            "<b>Typical use:</b> Evaluate whether hard constraints (protected areas, hazard zones) "
            "excessively restrict development options, especially in high-suitability zones.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ConstraintImpactAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUITABILITY, "Suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.CONSTRAINTS,
                "Constraint mask rasters (0/1, 0=excluded)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH_THRESHOLD,
                "High suitability threshold",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Constraint impact table", QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        suit_rl = self.parameterAsRasterLayer(parameters, self.SUITABILITY, context)
        constraints = ensure_list(self.parameterAsLayerList(parameters, self.CONSTRAINTS, context))[:12]
        if not constraints:
            raise QgsProcessingException("Provide at least one constraint raster.")
        high_thr = float(self.parameterAsDouble(parameters, self.HIGH_THRESHOLD, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        ds_s = gdal.Open(suit_rl.source(), gdal.GA_ReadOnly)
        if ds_s is None:
            raise QgsProcessingException("Cannot open suitability raster.")
        b_s = ds_s.GetRasterBand(1)
        nd_s = b_s.GetNoDataValue()
        xsize = ds_s.RasterXSize
        ysize = ds_s.RasterYSize
        gt = ds_s.GetGeoTransform()
        pixel_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        c_bands = []
        c_nodata = []
        c_names = []
        for c in constraints:
            ds = gdal.Open(c.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open constraint raster: {c.name()}")
            if ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All constraints must match suitability raster dimensions.")
            b = ds.GetRasterBand(1)
            c_bands.append(b)
            c_nodata.append(b.GetNoDataValue())
            c_names.append(c.name())

        n = len(c_bands)
        excluded = np.zeros(n, dtype=np.float64)
        excluded_high = np.zeros(n, dtype=np.float64)
        valid_total = 0.0
        high_total = 0.0
        excluded_any = 0.0
        excluded_any_high = 0.0

        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)
        done = 0

        for yoff in range(0, ysize, block):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    break
                cols = min(block, xsize - xoff)

                suit = b_s.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                valid = np.isfinite(suit)
                if nd_s is not None:
                    valid &= suit != nd_s
                suit = np.clip(suit, 0.0, 100.0)
                high = valid & (suit >= high_thr)

                ex_any = np.zeros_like(valid, dtype=bool)
                for i, cb in enumerate(c_bands):
                    ca = cb.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(ca)
                    nd = c_nodata[i]
                    if nd is not None:
                        c_valid &= ca != nd
                    c_ex = valid & c_valid & (ca <= 0.5)
                    excluded[i] += float(np.sum(c_ex))
                    excluded_high[i] += float(np.sum(c_ex & high))
                    ex_any |= c_ex

                valid_total += float(np.sum(valid))
                high_total += float(np.sum(high))
                excluded_any += float(np.sum(ex_any))
                excluded_any_high += float(np.sum(ex_any & high))

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        fields = QgsFields()
        fields.append(QgsField("constraint", QMetaType.Type.QString))
        fields.append(QgsField("excluded_cells", QMetaType.Type.LongLong))
        fields.append(QgsField("excluded_pct", QMetaType.Type.Double))
        fields.append(QgsField("excluded_area", QMetaType.Type.Double))
        fields.append(QgsField("excluded_high_cells", QMetaType.Type.LongLong))
        fields.append(QgsField("excluded_high_pct", QMetaType.Type.Double))
        fields.append(QgsField("priority_risk", QMetaType.Type.QString))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        def _risk_tag(ex_pct: float, high_pct: float) -> str:
            if ex_pct >= 25.0 or high_pct >= 25.0:
                return "CRITICAL"
            if ex_pct >= 12.0 or high_pct >= 12.0:
                return "HIGH"
            if ex_pct >= 5.0 or high_pct >= 5.0:
                return "MEDIUM"
            return "LOW"

        for i, name in enumerate(c_names):
            ex = excluded[i]
            exh = excluded_high[i]
            ex_pct = (100.0 * ex / valid_total) if valid_total > 0 else 0.0
            ex_high_pct = (100.0 * exh / high_total) if high_total > 0 else 0.0

            f = QgsFeature(fields)
            f["constraint"] = name
            f["excluded_cells"] = int(ex)
            f["excluded_pct"] = float(ex_pct)
            f["excluded_area"] = float(ex * pixel_area)
            f["excluded_high_cells"] = int(exh)
            f["excluded_high_pct"] = float(ex_high_pct)
            f["priority_risk"] = _risk_tag(ex_pct, ex_high_pct)
            sink.addFeature(f)

        total_feature = QgsFeature(fields)
        total_ex_pct = (100.0 * excluded_any / valid_total) if valid_total > 0 else 0.0
        total_ex_high_pct = (100.0 * excluded_any_high / high_total) if high_total > 0 else 0.0
        total_feature["constraint"] = "__ALL_CONSTRAINTS_UNION__"
        total_feature["excluded_cells"] = int(excluded_any)
        total_feature["excluded_pct"] = float(total_ex_pct)
        total_feature["excluded_area"] = float(excluded_any * pixel_area)
        total_feature["excluded_high_cells"] = int(excluded_any_high)
        total_feature["excluded_high_pct"] = float(total_ex_high_pct)
        total_feature["priority_risk"] = _risk_tag(total_ex_pct, total_ex_high_pct)
        sink.addFeature(total_feature)

        return {self.OUTPUT: dest}
