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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
)

from .._mcda_utils import ensure_list


class MethodBenchmarkLeaderboardAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    HIGH_THRESHOLD = "HIGH_THRESHOLD"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "method_benchmark_leaderboard"

    def displayName(self):
        return "Reporting: Method Benchmark Leaderboard"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return MethodBenchmarkLeaderboardAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario rasters to benchmark (2..12)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.MASK, "Optional analysis mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HIGH_THRESHOLD,
                "High suitability threshold (0-100)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
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
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Method benchmark leaderboard", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:12]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        high_thr = float(self.parameterAsDouble(parameters, self.HIGH_THRESHOLD, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)

        names = [l.name() for l in layers]
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

        n_s = len(layers)
        count = np.zeros(n_s, dtype=np.float64)
        summ = np.zeros(n_s, dtype=np.float64)
        sumsq = np.zeros(n_s, dtype=np.float64)
        hist = np.zeros((n_s, 101), dtype=np.float64)

        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)
        done = 0

        hi_idx = int(np.clip(ceil(high_thr), 0, 100))

        for yoff in range(0, ysize, block):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    break
                cols = min(block, xsize - xoff)

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    mv = np.isfinite(ma)
                    if m_nodata is not None:
                        mv &= ma != m_nodata
                    mv &= ma > 0.5
                else:
                    mv = None

                for i, b in enumerate(bands):
                    raw = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    valid = np.isfinite(raw)
                    nd = nodatas[i]
                    if nd is not None:
                        valid &= raw != nd
                    if mv is not None:
                        valid &= mv
                    if not np.any(valid):
                        continue

                    a = np.clip(raw, 0.0, 100.0)
                    vals = a[valid].astype(np.float64)
                    n = float(vals.size)
                    count[i] += n
                    summ[i] += float(np.sum(vals))
                    sumsq[i] += float(np.sum(vals * vals))
                    ints = np.clip(np.rint(vals), 0, 100).astype(np.int32)
                    hist[i] += np.bincount(ints, minlength=101).astype(np.float64)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        rows_out = []
        for i, name in enumerate(names):
            n = count[i]
            if n <= 0:
                mean = 0.0
                std = 0.0
                p90 = 0.0
                high_pct = 0.0
            else:
                mean = float(summ[i] / n)
                var = max(0.0, float((sumsq[i] / n) - (mean * mean)))
                std = float(np.sqrt(var))
                cum = np.cumsum(hist[i])
                tgt = 0.90 * n
                p90 = float(np.searchsorted(cum, tgt, side="left"))
                high_pct = float(100.0 * np.sum(hist[i, hi_idx:]) / n)
            stability = float(np.clip(100.0 - std, 0.0, 100.0))
            score = float(np.clip((0.35 * mean) + (0.30 * high_pct) + (0.20 * p90) + (0.15 * stability), 0.0, 100.0))
            if score >= 80.0:
                grade = "A"
            elif score >= 70.0:
                grade = "B"
            elif score >= 60.0:
                grade = "C"
            else:
                grade = "D"
            rows_out.append(
                {
                    "scenario": name,
                    "n_cells": int(n),
                    "mean_score": mean,
                    "std_score": std,
                    "p90_score": p90,
                    "high_pct": high_pct,
                    "stability_score": stability,
                    "composite_score": score,
                    "grade": grade,
                }
            )

        rows_out.sort(key=lambda r: (-r["composite_score"], r["std_score"], -r["mean_score"]))
        for rank, r in enumerate(rows_out, start=1):
            r["rank"] = rank

        fields = QgsFields()
        fields.append(QgsField("scenario", QVariant.String))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("n_cells", QVariant.LongLong))
        fields.append(QgsField("mean_score", QVariant.Double))
        fields.append(QgsField("std_score", QVariant.Double))
        fields.append(QgsField("p90_score", QVariant.Double))
        fields.append(QgsField("high_pct", QVariant.Double))
        fields.append(QgsField("stability", QVariant.Double))
        fields.append(QgsField("composite", QVariant.Double))
        fields.append(QgsField("grade", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        for r in rows_out:
            f = QgsFeature(fields)
            f["scenario"] = r["scenario"]
            f["rank"] = int(r["rank"])
            f["n_cells"] = int(r["n_cells"])
            f["mean_score"] = float(r["mean_score"])
            f["std_score"] = float(r["std_score"])
            f["p90_score"] = float(r["p90_score"])
            f["high_pct"] = float(r["high_pct"])
            f["stability"] = float(r["stability_score"])
            f["composite"] = float(r["composite_score"])
            f["grade"] = r["grade"]
            sink.addFeature(f)

        if rows_out:
            top = rows_out[0]
            feedback.pushInfo(
                "Benchmark leader: "
                f"{top['scenario']} (score={top['composite_score']:.2f}, mean={top['mean_score']:.2f}, high%={top['high_pct']:.2f})"
            )
        return {self.OUTPUT: dest}
