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
)

from .._mcda_utils import ensure_list


class ScenarioSimilarityMatrixAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    MASK = "MASK"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_similarity_matrix"

    def displayName(self):
        return "Reporting: Scenario Similarity Matrix"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return ScenarioSimilarityMatrixAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Suitability scenario rasters (2..8)",
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
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario similarity matrix", QgsProcessing.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:8]
        if len(layers) < 2:
            raise QgsProcessingException("Provide at least two scenario rasters.")
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
                raise QgsProcessingException("Mask raster must match scenario raster grid dimensions.")
            m_band = m_ds.GetRasterBand(1)
            m_nodata = m_band.GetNoDataValue()

        pairs = list(combinations(range(len(layers)), 2))
        k = len(pairs)
        count = np.zeros(k, dtype=np.float64)
        sx = np.zeros(k, dtype=np.float64)
        sy = np.zeros(k, dtype=np.float64)
        sxx = np.zeros(k, dtype=np.float64)
        syy = np.zeros(k, dtype=np.float64)
        sxy = np.zeros(k, dtype=np.float64)
        sad = np.zeros(k, dtype=np.float64)
        ssd = np.zeros(k, dtype=np.float64)

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
                for j, b in enumerate(bands):
                    raw = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    v = np.isfinite(raw)
                    nd = nodatas[j]
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
                    d = xi - yj
                    n = xi.size
                    count[idx] += n
                    sx[idx] += np.sum(xi)
                    sy[idx] += np.sum(yj)
                    sxx[idx] += np.sum(xi * xi)
                    syy[idx] += np.sum(yj * yj)
                    sxy[idx] += np.sum(xi * yj)
                    sad[idx] += np.sum(np.abs(d))
                    ssd[idx] += np.sum(d * d)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        fields = QgsFields()
        fields.append(QgsField("scenario_a", QVariant.String))
        fields.append(QgsField("scenario_b", QVariant.String))
        fields.append(QgsField("n_cells", QVariant.LongLong))
        fields.append(QgsField("pearson_r", QVariant.Double))
        fields.append(QgsField("mae", QVariant.Double))
        fields.append(QgsField("rmse", QVariant.Double))
        fields.append(QgsField("agreement", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        for idx, (i, j) in enumerate(pairs):
            n = count[idx]
            if n <= 0:
                r = 0.0
                mae = 0.0
                rmse = 0.0
            else:
                num = n * sxy[idx] - sx[idx] * sy[idx]
                denx = n * sxx[idx] - sx[idx] * sx[idx]
                deny = n * syy[idx] - sy[idx] * sy[idx]
                den = np.sqrt(max(denx, 0.0) * max(deny, 0.0))
                r = float(num / den) if den > 1e-12 else 0.0
                mae = float(sad[idx] / n)
                rmse = float(np.sqrt(ssd[idx] / n))
            if r >= 0.95:
                ag = "VERY_HIGH"
            elif r >= 0.85:
                ag = "HIGH"
            elif r >= 0.70:
                ag = "MEDIUM"
            else:
                ag = "LOW"

            feat = QgsFeature(fields)
            feat["scenario_a"] = names[i]
            feat["scenario_b"] = names[j]
            feat["n_cells"] = int(n)
            feat["pearson_r"] = r
            feat["mae"] = mae
            feat["rmse"] = rmse
            feat["agreement"] = ag
            sink.addFeature(feat)

        return {self.OUTPUT: dest}
