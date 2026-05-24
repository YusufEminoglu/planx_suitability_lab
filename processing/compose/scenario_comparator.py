# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)
from .._mcda_utils import smart_output_path


class ScenarioComparatorAlgorithm(QgsProcessingAlgorithm):
    A = "A"
    B = "B"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"
    STATS = "STATS"

    def name(self):
        return "scenario_comparator"

    def displayName(self):
        return "Compose: Scenario Comparator (delta)"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return ScenarioComparatorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.A, "Baseline suitability"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.B, "Scenario suitability"))
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Delta raster (B-A)"))
        self.addOutput(QgsProcessingOutputString(self.STATS, "Delta stats summary"))

    def _create_output(self, template_ds, out_path, nodata):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            out_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=["COMPRESS=LZW", "TILED=YES"],
        )
        out_ds.SetGeoTransform(template_ds.GetGeoTransform())
        out_ds.SetProjection(template_ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(float(nodata))
        return out_ds, out_band

    def processAlgorithm(self, parameters, context, feedback):
        a = self.parameterAsRasterLayer(parameters, self.A, context)
        b = self.parameterAsRasterLayer(parameters, self.B, context)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, a, "scenario_comparator_delta")

        dsa = gdal.Open(a.source(), gdal.GA_ReadOnly)
        dsb = gdal.Open(b.source(), gdal.GA_ReadOnly)
        if dsa is None or dsb is None:
            raise QgsProcessingException("Cannot open baseline/scenario raster.")
        if dsa.RasterXSize != dsb.RasterXSize or dsa.RasterYSize != dsb.RasterYSize:
            raise QgsProcessingException("Baseline and scenario rasters must share the same dimensions.")

        ba = dsa.GetRasterBand(1)
        bb = dsb.GetRasterBand(1)
        nda = ba.GetNoDataValue()
        ndb = bb.GetNoDataValue()
        out_nodata = nda if nda is not None else (ndb if ndb is not None else -9999.0)

        out_ds, out_band = self._create_output(dsa, out, out_nodata)
        xsize = dsa.RasterXSize
        ysize = dsa.RasterYSize

        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)
        done = 0

        sum_delta = 0.0
        count = 0
        min_delta = None
        max_delta = None

        for yoff in range(0, ysize, block):
            if feedback.isCanceled():
                break
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                if feedback.isCanceled():
                    break
                cols = min(block, xsize - xoff)
                aa = ba.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                bbv = bb.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                valid = np.isfinite(aa) & np.isfinite(bbv)
                if nda is not None:
                    valid &= aa != nda
                if ndb is not None:
                    valid &= bbv != ndb

                delta = (bbv - aa).astype(np.float32)
                if np.any(valid):
                    vals = delta[valid]
                    sum_delta += float(np.sum(vals))
                    count += int(vals.size)
                    vmin = float(np.min(vals))
                    vmax = float(np.max(vals))
                    min_delta = vmin if min_delta is None else min(min_delta, vmin)
                    max_delta = vmax if max_delta is None else max(max_delta, vmax)

                delta = np.where(valid, delta, out_nodata).astype(np.float32)
                out_band.WriteArray(delta, xoff, yoff)

                done += 1
                feedback.setProgress(int((done / total_blocks) * 100))

        out_ds = None
        dsa = None
        dsb = None
        mean_delta = (sum_delta / count) if count > 0 else 0.0
        msg = (
            "Scenario delta stats\n"
            f"- valid_cells: {count}\n"
            f"- delta_min: {0.0 if min_delta is None else min_delta:.4f}\n"
            f"- delta_max: {0.0 if max_delta is None else max_delta:.4f}\n"
            f"- delta_mean: {mean_delta:.4f}\n"
        )
        feedback.pushInfo(msg)
        return {self.OUTPUT: out, self.STATS: msg}
