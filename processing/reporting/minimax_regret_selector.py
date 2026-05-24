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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
)

from .._mcda_utils import ensure_list


class MinimaxRegretSelectorAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "minimax_regret_selector"

    def displayName(self):
        return "Reporting: Minimax Regret Selector"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return MinimaxRegretSelectorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Scenario suitability rasters (2..12)",
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
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Minimax regret scenario table", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:12]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

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

        count = np.zeros(n_s, dtype=np.float64)
        sum_regret = np.zeros(n_s, dtype=np.float64)
        max_regret = np.zeros(n_s, dtype=np.float64)
        hist = np.zeros((n_s, 101), dtype=np.float64)

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
                    arrs.append(np.clip(raw, 0.0, 100.0))
                    valids.append(v)

                valid_all = np.ones((rows, cols), dtype=bool)
                for v in valids:
                    valid_all &= v

                if m_band is not None:
                    ma = m_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    mv = np.isfinite(ma)
                    if m_nodata is not None:
                        mv &= ma != m_nodata
                    mv &= ma > 0.5
                    valid_all &= mv

                if np.any(valid_all):
                    stack = np.stack([a[valid_all].astype(np.float64) for a in arrs], axis=0)
                    best = np.max(stack, axis=0)
                    n = float(best.size)
                    for i in range(n_s):
                        reg = np.clip(best - stack[i], 0.0, 100.0)
                        count[i] += n
                        sum_regret[i] += float(np.sum(reg))
                        if reg.size:
                            max_regret[i] = max(max_regret[i], float(np.max(reg)))
                        ints = np.clip(np.rint(reg), 0, 100).astype(np.int32)
                        hist[i] += np.bincount(ints, minlength=101).astype(np.float64)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        rows_out = []
        for i, name in enumerate(names):
            n = count[i]
            if n <= 0:
                mean_r = 0.0
                p90_r = 0.0
                max_r = 0.0
            else:
                mean_r = float(sum_regret[i] / n)
                cum = np.cumsum(hist[i])
                p90_r = float(np.searchsorted(cum, 0.90 * n, side="left"))
                max_r = float(max_regret[i])
            minimax_score = float(np.clip(100.0 - max_r, 0.0, 100.0))
            rows_out.append(
                {
                    "scenario": name,
                    "n_cells": int(n),
                    "max_regret": max_r,
                    "mean_regret": mean_r,
                    "p90_regret": p90_r,
                    "minimax_score": minimax_score,
                }
            )

        rows_out.sort(key=lambda r: (r["max_regret"], r["mean_regret"], r["p90_regret"], -r["n_cells"], r["scenario"]))
        for rank, r in enumerate(rows_out, start=1):
            r["rank"] = rank
            r["selected"] = "YES" if rank == 1 else "NO"

        fields = QgsFields()
        fields.append(QgsField("scenario", QVariant.String))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("selected", QVariant.String))
        fields.append(QgsField("n_cells", QVariant.LongLong))
        fields.append(QgsField("max_regret", QVariant.Double))
        fields.append(QgsField("mean_regret", QVariant.Double))
        fields.append(QgsField("p90_regret", QVariant.Double))
        fields.append(QgsField("minimax_score", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        for r in rows_out:
            f = QgsFeature(fields)
            f["scenario"] = r["scenario"]
            f["rank"] = int(r["rank"])
            f["selected"] = r["selected"]
            f["n_cells"] = int(r["n_cells"])
            f["max_regret"] = float(r["max_regret"])
            f["mean_regret"] = float(r["mean_regret"])
            f["p90_regret"] = float(r["p90_regret"])
            f["minimax_score"] = float(r["minimax_score"])
            sink.addFeature(f)

        if rows_out:
            top = rows_out[0]
            feedback.pushInfo(
                "Minimax-regret selected scenario: "
                f"{top['scenario']} (max={top['max_regret']:.2f}, mean={top['mean_regret']:.2f}, p90={top['p90_regret']:.2f})"
            )
        return {self.OUTPUT: dest}

