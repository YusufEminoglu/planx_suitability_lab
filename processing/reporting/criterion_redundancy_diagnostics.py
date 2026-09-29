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

from .._mcda_utils import ensure_list, limit_layers


class CriterionRedundancyDiagnosticsAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    MAX_SAMPLES = "MAX_SAMPLES"
    BLOCK = "BLOCK"
    OUTPUT_PAIRS = "OUTPUT_PAIRS"
    OUTPUT_CRITERIA = "OUTPUT_CRITERIA"

    def name(self):
        return "criterion_redundancy_diagnostics"

    def displayName(self):
        return "Reporting: Criterion Redundancy Diagnostics"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Diagnoses criterion redundancy via pairwise correlation and Variance Inflation Factor (VIF).</b></p>"
            "<p><b>Inputs:</b> Criterion rasters (2-10), Optional mask raster (0/1), "
            "Maximum sampled cells (2000-3000000, default 250000), Block size (64-2048).<br>"
            "<b>Output:</b> Two feature sinks - Pairwise redundancy matrix (criterion_a, criterion_b, corr, abs_corr, "
            "redundancy label VERY_HIGH/HIGH/MEDIUM/LOW, samples) and Per-criterion diagnostics "
            "(mean_abs_corr, max_abs_corr, vif, redundancy_flag REVIEW/WATCH/OK).<br>"
            "<b>Method:</b> Samples up to max_samples valid cells across all criteria using block aggregation "
            "with a fixed random seed (42). Computes full correlation matrix and VIF via pseudo-inverse of the correlation matrix. "
            "Flags criteria: REVIEW if max_abs_corr>=0.9 or VIF>=10, WATCH if >=0.75 or >=5, OK otherwise.<br>"
            "<b>Typical use:</b> Identify redundant criteria before weighting to avoid double-counting information in MCDA.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return CriterionRedundancyDiagnosticsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (2..10)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.MASK, "Optional analysis mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_SAMPLES,
                "Maximum sampled valid cells",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=250000,
                minValue=2000,
                maxValue=3000000,
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
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_PAIRS, "Pairwise redundancy matrix", QgsProcessing.SourceType.TypeVector))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_CRITERIA, "Per-criterion diagnostics", QgsProcessing.SourceType.TypeVector))

    @staticmethod
    def _redundancy_label(abs_corr: float) -> str:
        if abs_corr >= 0.9:
            return "VERY_HIGH"
        if abs_corr >= 0.75:
            return "HIGH"
        if abs_corr >= 0.55:
            return "MEDIUM"
        return "LOW"

    def processAlgorithm(self, parameters, context, feedback):
        layers = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 10, "criterion rasters")
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two criterion rasters.")

        max_samples = int(self.parameterAsInt(parameters, self.MAX_SAMPLES, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)

        names = [lyr.name() for lyr in layers]
        datasets = []
        bands = []
        nodatas = []
        xsize = None
        ysize = None

        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            b = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All criterion rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(b)
            nodatas.append(b.GetNoDataValue())

        m_band = None
        m_nodata = None
        if mask is not None:
            m_ds = gdal.Open(mask.source(), gdal.GA_ReadOnly)
            if m_ds is None:
                raise QgsProcessingException("Cannot open mask raster.")
            if m_ds.RasterXSize != xsize or m_ds.RasterYSize != ysize:
                raise QgsProcessingException("Mask raster must match criterion raster dimensions.")
            m_band = m_ds.GetRasterBand(1)
            m_nodata = m_band.GetNoDataValue()

        samples = []
        k = len(layers)
        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)
        done = 0
        rng = np.random.default_rng(42)

        for yoff in range(0, ysize, block):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    break
                cols = min(block, xsize - xoff)

                arrs = []
                valid = None
                for i, b in enumerate(bands):
                    a = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    ok = np.isfinite(a)
                    nd = nodatas[i]
                    if nd is not None:
                        ok &= a != nd
                    arrs.append(a)
                    valid = ok if valid is None else (valid & ok)

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    m_ok = np.isfinite(ma)
                    if m_nodata is not None:
                        m_ok &= ma != m_nodata
                    m_ok &= ma > 0.5
                    valid &= m_ok

                if np.any(valid):
                    block_stack = np.column_stack([np.clip(arr[valid], 0.0, 100.0) for arr in arrs]).astype(np.float64)
                    if block_stack.shape[0] > 0:
                        samples.append(block_stack)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        if not samples:
            raise QgsProcessingException("No overlapping valid cells across criteria.")

        sample_mat = np.vstack(samples)
        if sample_mat.shape[0] > max_samples:
            sel = rng.choice(sample_mat.shape[0], size=max_samples, replace=False)
            sample_mat = sample_mat[sel, :]

        corr = np.corrcoef(sample_mat, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0)
        corr = np.clip(corr, -1.0, 1.0)

        reg = corr.copy()
        reg += np.eye(k) * 1e-6
        try:
            inv_corr = np.linalg.pinv(reg)
            vifs = np.diag(inv_corr)
        except Exception:
            vifs = np.full(k, np.nan, dtype=np.float64)

        pair_fields = QgsFields()
        pair_fields.append(QgsField("criterion_a", QMetaType.Type.QString))
        pair_fields.append(QgsField("criterion_b", QMetaType.Type.QString))
        pair_fields.append(QgsField("corr", QMetaType.Type.Double))
        pair_fields.append(QgsField("abs_corr", QMetaType.Type.Double))
        pair_fields.append(QgsField("redundancy", QMetaType.Type.QString))
        pair_fields.append(QgsField("samples", QMetaType.Type.LongLong))
        pair_sink, pair_dest = self.parameterAsSink(parameters, self.OUTPUT_PAIRS, context, pair_fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        for i in range(k):
            for j in range(i + 1, k):
                c = float(corr[i, j])
                ac = abs(c)
                f = QgsFeature(pair_fields)
                f["criterion_a"] = names[i]
                f["criterion_b"] = names[j]
                f["corr"] = c
                f["abs_corr"] = ac
                f["redundancy"] = self._redundancy_label(ac)
                f["samples"] = int(sample_mat.shape[0])
                pair_sink.addFeature(f)

        crit_fields = QgsFields()
        crit_fields.append(QgsField("criterion", QMetaType.Type.QString))
        crit_fields.append(QgsField("mean_abs_corr", QMetaType.Type.Double))
        crit_fields.append(QgsField("max_abs_corr", QMetaType.Type.Double))
        crit_fields.append(QgsField("vif", QMetaType.Type.Double))
        crit_fields.append(QgsField("redundancy_flag", QMetaType.Type.QString))
        crit_sink, crit_dest = self.parameterAsSink(parameters, self.OUTPUT_CRITERIA, context, crit_fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        abs_corr = np.abs(corr)
        for i in range(k):
            others = [abs_corr[i, j] for j in range(k) if j != i]
            mean_abs = float(np.mean(others)) if others else 0.0
            max_abs = float(np.max(others)) if others else 0.0
            vif = float(vifs[i]) if np.isfinite(vifs[i]) else 0.0
            if max_abs >= 0.9 or vif >= 10:
                flag = "REVIEW"
            elif max_abs >= 0.75 or vif >= 5:
                flag = "WATCH"
            else:
                flag = "OK"

            feat = QgsFeature(crit_fields)
            feat["criterion"] = names[i]
            feat["mean_abs_corr"] = mean_abs
            feat["max_abs_corr"] = max_abs
            feat["vif"] = vif
            feat["redundancy_flag"] = flag
            crit_sink.addFeature(feat)

        feedback.pushInfo(f"Sampled cells used: {sample_mat.shape[0]}")
        return {self.OUTPUT_PAIRS: pair_dest, self.OUTPUT_CRITERIA: crit_dest}
