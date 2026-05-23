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
    QgsProcessingOutputString,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)


class SuitabilityClassAreaStatsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BREAKS = "BREAKS"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"
    SUMMARY = "SUMMARY"

    def name(self):
        return "suitability_class_area_stats"

    def displayName(self):
        return "Reporting: Suitability Class Area Stats"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return SuitabilityClassAreaStatsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Suitability raster (0-100)"))
        self.addParameter(QgsProcessingParameterString(self.BREAKS, "Class breaks CSV (internal bounds)", defaultValue="20,40,60,80"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=512,
                minValue=64,
                maxValue=4096,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Class area stats table", QgsProcessing.TypeVector))
        self.addOutput(QgsProcessingOutputString(self.SUMMARY, "Stats summary"))

    def _parse_breaks(self, text):
        vals = [float(v.strip()) for v in text.split(",") if v.strip()]
        vals = sorted(set(vals))
        vals = [v for v in vals if 0.0 < v < 100.0]
        return [0.0] + vals + [100.0]

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        breaks = self._parse_breaks(self.parameterAsString(parameters, self.BREAKS, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open suitability raster for class statistics.")
        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        xsize = ds.RasterXSize
        ysize = ds.RasterYSize
        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 0.0

        classes = len(breaks) - 1
        counts = np.zeros(classes, dtype=np.int64)
        total_valid = 0

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
                arr = band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                valid = np.isfinite(arr)
                if nodata is not None:
                    valid &= arr != nodata
                if np.any(valid):
                    vals = np.clip(arr[valid], 0.0, 100.0)
                    idx = np.digitize(vals, breaks[1:-1], right=True)
                    binc = np.bincount(idx, minlength=classes)
                    counts[: len(binc)] += binc
                    total_valid += int(vals.size)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        fields = QgsFields()
        fields.append(QgsField("class_id", QVariant.Int))
        fields.append(QgsField("class_label", QVariant.String))
        fields.append(QgsField("min_score", QVariant.Double))
        fields.append(QgsField("max_score", QVariant.Double))
        fields.append(QgsField("cell_count", QVariant.LongLong))
        fields.append(QgsField("pct_valid", QVariant.Double))
        fields.append(QgsField("area_units2", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

        top_id = 1
        top_count = -1
        for i in range(classes):
            cmin = breaks[i]
            cmax = breaks[i + 1]
            cnt = int(counts[i])
            pct = (100.0 * cnt / total_valid) if total_valid > 0 else 0.0
            area = float(cnt * cell_area)
            if cnt > top_count:
                top_count = cnt
                top_id = i + 1
            f = QgsFeature(fields)
            f["class_id"] = i + 1
            f["class_label"] = f"{cmin:.1f}-{cmax:.1f}"
            f["min_score"] = float(cmin)
            f["max_score"] = float(cmax)
            f["cell_count"] = cnt
            f["pct_valid"] = float(pct)
            f["area_units2"] = area
            sink.addFeature(f)

        summary = (
            "Suitability class stats\n"
            f"- classes: {classes}\n"
            f"- valid_cells: {total_valid}\n"
            f"- top_class_id: {top_id}\n"
            f"- cell_area_units2: {cell_area:.6f}\n"
        )
        feedback.pushInfo(summary)
        return {self.OUTPUT: dest, self.SUMMARY: summary}

