# -*- coding: utf-8 -*-
from __future__ import annotations

from itertools import combinations

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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)

from .._mcda_utils import ensure_list


class ScenarioPortfolioDiversityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_portfolio_diversity"

    def displayName(self):
        return "Reporting: Scenario Portfolio Diversity Audit"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Audits scenario portfolio for redundancy versus diversification using pairwise correlations "
            "and spatial disagreement.</b></p>"
            "<p><b>Inputs:</b> Scenario rasters (3-12), Optional mask raster (0/1), Block size (64-2048).<br>"
            "<b>Output:</b> Feature sink with SUMMARY row (diversity_idx, effective_methods, disagree_std, "
            "health_score, div_class STRONG/MODERATE/REDUNDANT, spread_class) "
            "and SCENARIO rows (uniq_score, mean_abs_corr, role DIVERSIFIER/BALANCER/ANCHOR).<br>"
            "<b>Method:</b> Computes pairwise Pearson correlations between all scenarios. "
            "Diversity index = (1 - mean_abs_corr) * 100. "
            "Effective methods = 1 + (n-1)*(1 - mean_abs_corr), estimating independent information sources. "
            "Spatial disagreement measured as per-cell standard deviation across all scenarios. "
            "Portfolio health = 0.65*diversity + 0.35*(100-disagreement_std).<br>"
            "<b>Typical use:</b> Determine if the scenario set is sufficiently diverse or overly redundant, "
            "guiding whether to add or prune scenarios.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ScenarioPortfolioDiversityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario rasters (3..12)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.MASK, "Optional analysis mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Portfolio diversity audit", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:12]
        if len(layers) < 3:
            raise QgsProcessingException("Provide at least three scenario rasters.")
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)

        names = [l.name() for l in layers]
        n_s = len(layers)
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
                raise QgsProcessingException("All scenario rasters must share identical dimensions.")
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
                raise QgsProcessingException("Mask raster must match scenario raster dimensions.")
            m_band = m_ds.GetRasterBand(1)
            m_nodata = m_band.GetNoDataValue()

        pairs = list(combinations(range(n_s), 2))
        k = len(pairs)
        count = np.zeros(k, dtype=np.float64)
        sx = np.zeros(k, dtype=np.float64)
        sy = np.zeros(k, dtype=np.float64)
        sxx = np.zeros(k, dtype=np.float64)
        syy = np.zeros(k, dtype=np.float64)
        sxy = np.zeros(k, dtype=np.float64)

        spread_sum = 0.0
        spread_count = 0.0

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

                arrs = []
                valids = []
                for i, b in enumerate(bands):
                    raw = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    v = np.isfinite(raw)
                    nd = nodatas[i]
                    if nd is not None:
                        v &= raw != nd
                    a = np.clip(raw, 0.0, 100.0)
                    arrs.append(a)
                    valids.append(v)

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    mv = np.isfinite(ma)
                    if m_nodata is not None:
                        mv &= ma != m_nodata
                    mv &= ma > 0.5
                else:
                    mv = None

                for idx, (i, j) in enumerate(pairs):
                    valid = valids[i] & valids[j]
                    if mv is not None:
                        valid &= mv
                    if not np.any(valid):
                        continue
                    xi = arrs[i][valid].astype(np.float64)
                    yj = arrs[j][valid].astype(np.float64)
                    n = xi.size
                    count[idx] += n
                    sx[idx] += np.sum(xi)
                    sy[idx] += np.sum(yj)
                    sxx[idx] += np.sum(xi * xi)
                    syy[idx] += np.sum(yj * yj)
                    sxy[idx] += np.sum(xi * yj)

                valid_all = np.ones((rows, cols), dtype=bool)
                if mv is not None:
                    valid_all &= mv
                for v in valids:
                    valid_all &= v
                if np.any(valid_all):
                    stack = np.stack([a[valid_all].astype(np.float64) for a in arrs], axis=0)
                    std_cells = np.std(stack, axis=0)
                    spread_sum += float(np.sum(std_cells))
                    spread_count += float(std_cells.size)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        corr = np.eye(n_s, dtype=np.float64)
        for idx, (i, j) in enumerate(pairs):
            n = count[idx]
            if n <= 0:
                r = 0.0
            else:
                num = n * sxy[idx] - sx[idx] * sy[idx]
                denx = n * sxx[idx] - sx[idx] * sx[idx]
                deny = n * syy[idx] - sy[idx] * sy[idx]
                den = np.sqrt(max(denx, 0.0) * max(deny, 0.0))
                r = float(num / den) if den > 1e-12 else 0.0
            corr[i, j] = r
            corr[j, i] = r

        abs_upper = [abs(float(corr[i, j])) for i, j in pairs]
        mean_abs_corr = float(np.mean(abs_upper)) if abs_upper else 1.0
        diversity_idx = float(np.clip((1.0 - mean_abs_corr) * 100.0, 0.0, 100.0))
        effective_methods = float(1.0 + (n_s - 1.0) * (1.0 - mean_abs_corr))
        disagreement_std = float(spread_sum / spread_count) if spread_count > 0 else 0.0
        portfolio_health = float(np.clip((0.65 * diversity_idx) + (0.35 * np.clip(100.0 - disagreement_std, 0.0, 100.0)), 0.0, 100.0))

        if diversity_idx >= 45.0:
            diversity_class = "STRONG"
        elif diversity_idx >= 25.0:
            diversity_class = "MODERATE"
        else:
            diversity_class = "REDUNDANT"
        if disagreement_std >= 20.0:
            spread_class = "HIGH_DIVERGENCE"
        elif disagreement_std >= 10.0:
            spread_class = "BALANCED_DIVERGENCE"
        else:
            spread_class = "LOW_DIVERGENCE"

        uniq_rows = []
        for i, name in enumerate(names):
            others = [abs(float(corr[i, j])) for j in range(n_s) if j != i]
            mean_abs_i = float(np.mean(others)) if others else 1.0
            uniq = float(np.clip((1.0 - mean_abs_i) * 100.0, 0.0, 100.0))
            if uniq >= 40.0:
                role = "DIVERSIFIER"
            elif uniq >= 20.0:
                role = "BALANCER"
            else:
                role = "ANCHOR"
            uniq_rows.append((name, mean_abs_i, uniq, role))
        uniq_rows.sort(key=lambda x: (-x[2], x[1], x[0]))

        fields = QgsFields()
        fields.append(QgsField("row_type", QVariant.String))
        fields.append(QgsField("scenario", QVariant.String))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("uniq_score", QVariant.Double))
        fields.append(QgsField("mean_abs_corr", QVariant.Double))
        fields.append(QgsField("role", QVariant.String))
        fields.append(QgsField("diversity_idx", QVariant.Double))
        fields.append(QgsField("eff_methods", QVariant.Double))
        fields.append(QgsField("disagree_std", QVariant.Double))
        fields.append(QgsField("health_score", QVariant.Double))
        fields.append(QgsField("div_class", QVariant.String))
        fields.append(QgsField("spread_class", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        summary = QgsFeature(fields)
        summary["row_type"] = "SUMMARY"
        summary["scenario"] = "__PORTFOLIO__"
        summary["rank"] = 0
        summary["uniq_score"] = 0.0
        summary["mean_abs_corr"] = mean_abs_corr
        summary["role"] = "PORTFOLIO"
        summary["diversity_idx"] = diversity_idx
        summary["eff_methods"] = effective_methods
        summary["disagree_std"] = disagreement_std
        summary["health_score"] = portfolio_health
        summary["div_class"] = diversity_class
        summary["spread_class"] = spread_class
        sink.addFeature(summary)

        for rank, (name, mean_abs_i, uniq, role) in enumerate(uniq_rows, start=1):
            f = QgsFeature(fields)
            f["row_type"] = "SCENARIO"
            f["scenario"] = name
            f["rank"] = int(rank)
            f["uniq_score"] = float(uniq)
            f["mean_abs_corr"] = float(mean_abs_i)
            f["role"] = role
            f["diversity_idx"] = diversity_idx
            f["eff_methods"] = effective_methods
            f["disagree_std"] = disagreement_std
            f["health_score"] = portfolio_health
            f["div_class"] = diversity_class
            f["spread_class"] = spread_class
            sink.addFeature(f)

        feedback.pushInfo(
            "Portfolio diversity: "
            f"index={diversity_idx:.2f}, effective_methods={effective_methods:.2f}, disagreement_std={disagreement_std:.2f}, health={portfolio_health:.2f}"
        )
        return {self.OUTPUT: dest}
