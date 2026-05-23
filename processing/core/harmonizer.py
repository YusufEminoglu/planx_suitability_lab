# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re

import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from .._mcda_utils import ensure_list


class DataHarmonizerAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    SNAP_RASTER = "SNAP_RASTER"
    TARGET_EXTENT = "TARGET_EXTENT"
    TARGET_RES = "TARGET_RES"
    RESAMPLING = "RESAMPLING"
    NODATA = "NODATA"
    OUTPUT_RASTER = "OUTPUT_RASTER"
    OUTPUT_DIR = "OUTPUT_DIR"
    OUTPUT_MANIFEST = "OUTPUT_MANIFEST"

    RESAMPLING_OPTIONS = ["Nearest", "Bilinear", "Cubic"]

    def name(self):
        return "data_harmonizer"

    def displayName(self):
        return "Core: Data Harmonizer"

    def group(self):
        return "Core"

    def groupId(self):
        return "core"

    def createInstance(self):
        return DataHarmonizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, "Input rasters", QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterRasterLayer(self.SNAP_RASTER, "Snap raster (optional)", optional=True))
        self.addParameter(QgsProcessingParameterExtent(self.TARGET_EXTENT, "Target extent (optional)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TARGET_RES,
                "Target resolution (set <=0 to inherit from snap/first raster)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(QgsProcessingParameterEnum(self.RESAMPLING, "Resampling", options=self.RESAMPLING_OPTIONS, defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NODATA,
                "Output nodata",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=-9999.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_RASTER, "Preview aligned raster"))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_DIR, "Aligned raster folder"))
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_MANIFEST,
                "Alignment manifest (txt)",
                fileFilter="Text files (*.txt)",
            )
        )

    def _safe_name(self, text):
        return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_") or "raster"

    def processAlgorithm(self, parameters, context, feedback):
        rasters = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        if not rasters:
            raise QgsProcessingException("No input rasters provided.")

        snap = self.parameterAsRasterLayer(parameters, self.SNAP_RASTER, context)
        target_extent = self.parameterAsExtent(parameters, self.TARGET_EXTENT, context)
        res = float(self.parameterAsDouble(parameters, self.TARGET_RES, context))
        resampling = int(self.parameterAsEnum(parameters, self.RESAMPLING, context))
        nodata = float(self.parameterAsDouble(parameters, self.NODATA, context))
        out_preview = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        out_dir = self.parameterAsString(parameters, self.OUTPUT_DIR, context)
        manifest = self.parameterAsFileOutput(parameters, self.OUTPUT_MANIFEST, context)
        os.makedirs(out_dir, exist_ok=True)

        target_crs = snap.crs() if snap is not None else rasters[0].crs()
        if target_extent.isEmpty():
            if snap is not None:
                target_extent = snap.extent()
            else:
                raise QgsProcessingException("Provide TARGET_EXTENT or SNAP_RASTER.")
        if res <= 0:
            if snap is not None:
                res = float(snap.rasterUnitsPerPixelX())
            else:
                res = float(rasters[0].rasterUnitsPerPixelX())
        if res <= 0:
            raise QgsProcessingException("Target resolution must be greater than 0.")

        aligned = []
        for i, rl in enumerate(rasters, start=1):
            if feedback.isCanceled():
                break
            fname = f"aligned_{i:02d}_{self._safe_name(rl.name())}.tif"
            out_i = os.path.join(out_dir, fname)
            processing.run(
                "gdal:warpreproject",
                {
                    "INPUT": rl.source(),
                    "SOURCE_CRS": None,
                    "TARGET_CRS": target_crs,
                    "RESAMPLING": resampling,
                    "NODATA": nodata,
                    "TARGET_RESOLUTION": res,
                    "OPTIONS": "",
                    "DATA_TYPE": 5,
                    "TARGET_EXTENT": target_extent,
                    "TARGET_EXTENT_CRS": target_crs,
                    "MULTITHREADING": True,
                    "EXTRA": "",
                    "OUTPUT": out_i,
                },
                context=context,
                feedback=feedback,
            )
            aligned.append(out_i)
            feedback.setProgress(int((i / max(1, len(rasters))) * 100))

        if not aligned:
            raise QgsProcessingException("No aligned raster was produced.")
        processing.run(
            "gdal:translate",
            {
                "INPUT": aligned[0],
                "TARGET_CRS": None,
                "NODATA": nodata,
                "COPY_SUBDATASETS": False,
                "OPTIONS": "",
                "EXTRA": "",
                "DATA_TYPE": 5,
                "OUTPUT": out_preview,
            },
            context=context,
            feedback=feedback,
        )

        lines = [
            "PlanX Suitability Lab - Harmonizer Manifest",
            f"Input count: {len(rasters)}",
            f"Target CRS: {target_crs.authid()}",
            f"Target resolution: {res}",
            f"Target extent: {target_extent.toString()}",
            f"Resampling: {self.RESAMPLING_OPTIONS[resampling]}",
            f"Nodata: {nodata}",
            "",
            "Aligned outputs:",
        ]
        for i, path in enumerate(aligned, start=1):
            lines.append(f"{i}. {path}")
        with open(manifest, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return {
            self.OUTPUT_RASTER: out_preview,
            self.OUTPUT_DIR: out_dir,
            self.OUTPUT_MANIFEST: manifest,
        }

