# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import deque

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
)


class SpatialFragmentationAuditAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    THRESHOLD = "THRESHOLD"
    CONNECTIVITY = "CONNECTIVITY"
    OUTPUT = "OUTPUT"

    def name(self):
        return "spatial_fragmentation_audit"

    def displayName(self):
        return "Reporting: Spatial Fragmentation Audit"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return SpatialFragmentationAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                "High-priority threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=70.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONNECTIVITY,
                "Connectivity (4 or 8)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=8,
                minValue=4,
                maxValue=8,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Spatial fragmentation metrics", QgsProcessing.TypeVector))

    def _neighbors(self, r, c, rows, cols, conn):
        if conn == 4:
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        else:
            offsets = [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1), (0, 1),
                (1, -1), (1, 0), (1, 1),
            ]
        for dr, dc in offsets:
            rr = r + dr
            cc = c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                yield rr, cc

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        thr = float(self.parameterAsDouble(parameters, self.THRESHOLD, context))
        conn = int(self.parameterAsInt(parameters, self.CONNECTIVITY, context))
        conn = 4 if conn == 4 else 8

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open input raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)

        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        arr = np.clip(arr, 0.0, 100.0)
        high = valid & (arr >= thr)

        total_valid = int(np.sum(valid))
        total_high = int(np.sum(high))
        if total_valid <= 0:
            raise QgsProcessingException("No valid cells found in input raster.")

        rows, cols = high.shape
        visited = np.zeros_like(high, dtype=bool)
        patches = []
        q = deque()

        for r in range(rows):
            if feedback.isCanceled():
                break
            for c in range(cols):
                if not high[r, c] or visited[r, c]:
                    continue
                visited[r, c] = True
                q.clear()
                q.append((r, c))
                size = 0
                while q:
                    rr, cc = q.popleft()
                    size += 1
                    for nr, nc in self._neighbors(rr, cc, rows, cols, conn):
                        if high[nr, nc] and (not visited[nr, nc]):
                            visited[nr, nc] = True
                            q.append((nr, nc))
                patches.append(size)
            if rows > 1:
                feedback.setProgress(int((r / (rows - 1)) * 100))

        n_patches = len(patches)
        largest_patch = max(patches) if patches else 0
        mean_patch = float(np.mean(patches)) if patches else 0.0
        median_patch = float(np.median(patches)) if patches else 0.0
        share_high = 100.0 * (total_high / total_valid)
        largest_share_high = 100.0 * (largest_patch / total_high) if total_high > 0 else 0.0

        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0
        high_area = total_high * cell_area
        mean_patch_area = mean_patch * cell_area

        if total_high == 0:
            frag_class = "NO_HIGH_PRIORITY_AREA"
        elif n_patches <= 3 and largest_share_high >= 50.0:
            frag_class = "COMPACT"
        elif n_patches <= 10 and largest_share_high >= 30.0:
            frag_class = "MODERATE"
        else:
            frag_class = "FRAGMENTED"

        fields = QgsFields()
        fields.append(QgsField("threshold", QVariant.Double))
        fields.append(QgsField("connectivity", QVariant.Int))
        fields.append(QgsField("valid_cells", QVariant.LongLong))
        fields.append(QgsField("high_cells", QVariant.LongLong))
        fields.append(QgsField("high_share_pct", QVariant.Double))
        fields.append(QgsField("patch_count", QVariant.Int))
        fields.append(QgsField("largest_patch", QVariant.LongLong))
        fields.append(QgsField("largest_share_pct", QVariant.Double))
        fields.append(QgsField("mean_patch", QVariant.Double))
        fields.append(QgsField("median_patch", QVariant.Double))
        fields.append(QgsField("high_area", QVariant.Double))
        fields.append(QgsField("mean_patch_area", QVariant.Double))
        fields.append(QgsField("fragmentation", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        feat = QgsFeature(fields)
        feat["threshold"] = float(thr)
        feat["connectivity"] = int(conn)
        feat["valid_cells"] = int(total_valid)
        feat["high_cells"] = int(total_high)
        feat["high_share_pct"] = float(share_high)
        feat["patch_count"] = int(n_patches)
        feat["largest_patch"] = int(largest_patch)
        feat["largest_share_pct"] = float(largest_share_high)
        feat["mean_patch"] = float(mean_patch)
        feat["median_patch"] = float(median_patch)
        feat["high_area"] = float(high_area)
        feat["mean_patch_area"] = float(mean_patch_area)
        feat["fragmentation"] = frag_class
        sink.addFeature(feat)
        return {self.OUTPUT: dest}
