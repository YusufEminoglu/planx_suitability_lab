# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal, osr
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterExtent, QgsProcessingParameterNumber, QgsProcessingParameterFolderDestination


class SyntheticSampleRasterAlgorithm(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    PIXEL = "PIXEL"
    OUTPUT_DIR = "OUTPUT_DIR"

    def name(self):
        return "synthetic_sample_raster"

    def displayName(self):
        return "Core: Synthetic Sample Raster Pack"

    def group(self):
        return "Core"

    def groupId(self):
        return "core"

    def createInstance(self):
        return SyntheticSampleRasterAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(self.EXTENT, "Study extent"))
        self.addParameter(
            QgsProcessingParameterNumber(self.PIXEL, "Pixel size", type=QgsProcessingParameterNumber.Double, defaultValue=30.0, minValue=1.0)
        )
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_DIR, "Output folder"))

    def _write(self, path, arr, gt, wkt):
        drv = gdal.GetDriverByName("GTiff")
        ds = drv.Create(path, arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32)
        ds.SetGeoTransform(gt)
        ds.SetProjection(wkt)
        band = ds.GetRasterBand(1)
        band.WriteArray(arr.astype(np.float32))
        band.SetNoDataValue(-9999.0)
        band.FlushCache()
        ds = None

    def processAlgorithm(self, parameters, context, feedback):
        ex = self.parameterAsExtent(parameters, self.EXTENT, context)
        pix = float(self.parameterAsDouble(parameters, self.PIXEL, context))
        out_dir = self.parameterAsString(parameters, self.OUTPUT_DIR, context)

        width = max(10, int((ex.xMaximum() - ex.xMinimum()) / pix))
        height = max(10, int((ex.yMaximum() - ex.yMinimum()) / pix))
        x = np.linspace(0, 1, width, dtype=np.float32)
        y = np.linspace(0, 1, height, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        rng = np.random.default_rng(7)

        c1 = np.clip(100 * (1.0 - xx) + 8 * rng.normal(size=xx.shape), 0, 100)
        c2 = np.clip(100 * yy + 8 * rng.normal(size=xx.shape), 0, 100)
        c3 = np.clip(100 * (1.0 - np.abs(xx - yy)) + 10 * rng.normal(size=xx.shape), 0, 100)
        c4 = np.clip(100 * (1.0 - np.sqrt((xx - 0.65) ** 2 + (yy - 0.35) ** 2)), 0, 100)
        constraint = ((xx > 0.15) & (yy > 0.10)).astype(np.float32)

        gt = (ex.xMinimum(), pix, 0.0, ex.yMaximum(), 0.0, -pix)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(3857)
        wkt = srs.ExportToWkt()

        p1 = out_dir + "/criterion_1.tif"
        p2 = out_dir + "/criterion_2.tif"
        p3 = out_dir + "/criterion_3.tif"
        p4 = out_dir + "/criterion_4.tif"
        pm = out_dir + "/constraint_mask.tif"
        self._write(p1, c1, gt, wkt)
        self._write(p2, c2, gt, wkt)
        self._write(p3, c3, gt, wkt)
        self._write(p4, c4, gt, wkt)
        self._write(pm, constraint, gt, wkt)

        return {
            "CRITERION_1": p1,
            "CRITERION_2": p2,
            "CRITERION_3": p3,
            "CRITERION_4": p4,
            "CONSTRAINT_MASK": pm,
            self.OUTPUT_DIR: out_dir,
        }

