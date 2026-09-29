# -*- coding: utf-8 -*-
from __future__ import annotations

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
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)

from .._mcda_utils import ensure_list, limit_layers


class AlignmentAuditAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    SNAP = "SNAP"
    OUTPUT = "OUTPUT"

    def name(self):
        return "alignment_audit"

    def displayName(self):
        return "Reporting: Raster Alignment Audit"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Checks pixel size, extent, and shape consistency across a set of input rasters.</b></p>"
            "<p><b>Inputs:</b> Input rasters to audit (2-20), Optional snap raster (reference for alignment).<br>"
            "<b>Output:</b> Feature sink with one row per raster: width, height, pixel_x, pixel_y, crs_authid, "
            "aligned_px (0/1), aligned_extent (0/1), aligned_shape (0/1), aligned_all (0/1). "
            "Summary row with reference raster info and overall alignment status.<br>"
            "<b>Method:</b> Uses the first raster (or optional snap raster) as reference. "
            "For each subsequent raster, compares pixel size (tolerance 1e-9), extent key (rounded to 8 decimals), "
            "and shape (width/height). Reports alignment per dimension and an overall flag. "
            "First raster always serves as reference unless snap is provided.<br>"
            "<b>Typical use:</b> Pre-flight check before any multi-raster analysis to prevent misalignment errors.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return AlignmentAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Input rasters to audit (2..20)",
                QgsProcessing.SourceType.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.SNAP, "Optional snap raster (reference)", optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Alignment audit table", QgsProcessing.SourceType.TypeVector))

    @staticmethod
    def _extent_key(gt, xsize, ysize):
        minx = float(gt[0])
        maxy = float(gt[3])
        maxx = minx + float(gt[1]) * xsize
        miny = maxy + float(gt[5]) * ysize
        return (round(minx, 8), round(miny, 8), round(maxx, 8), round(maxy, 8))

    def processAlgorithm(self, parameters, context, feedback):
        rasters = limit_layers(ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)), 20, "scenario rasters")
        if len(rasters) < 2:
            raise QgsProcessingException("Provide at least two rasters.")

        snap = self.parameterAsRasterLayer(parameters, self.SNAP, context)
        ref_gt = None
        ref_x = None
        ref_y = None
        ref_ext = None
        ref_w = None
        ref_h = None
        ref_name = "first_input"

        if snap is not None:
            ds_ref = gdal.Open(snap.source(), gdal.GA_ReadOnly)
            if ds_ref is None:
                raise QgsProcessingException("Cannot open snap raster.")
            ref_gt = ds_ref.GetGeoTransform()
            ref_w = ds_ref.RasterXSize
            ref_h = ds_ref.RasterYSize
            ref_x = float(ref_gt[1])
            ref_y = abs(float(ref_gt[5]))
            ref_ext = self._extent_key(ref_gt, ref_w, ref_h)
            ref_name = snap.name()

        fields = QgsFields()
        fields.append(QgsField("raster", QMetaType.Type.QString))
        fields.append(QgsField("width", QMetaType.Type.Int))
        fields.append(QgsField("height", QMetaType.Type.Int))
        fields.append(QgsField("pixel_x", QMetaType.Type.Double))
        fields.append(QgsField("pixel_y", QMetaType.Type.Double))
        fields.append(QgsField("crs_authid", QMetaType.Type.QString))
        fields.append(QgsField("aligned_px", QMetaType.Type.Int))
        fields.append(QgsField("aligned_extent", QMetaType.Type.Int))
        fields.append(QgsField("aligned_shape", QMetaType.Type.Int))
        fields.append(QgsField("aligned_all", QMetaType.Type.Int))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        aligned_all_count = 0
        total = len(rasters)
        for i, rl in enumerate(rasters):
            ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {rl.name()}")
            gt = ds.GetGeoTransform()
            w = ds.RasterXSize
            h = ds.RasterYSize
            px = float(gt[1])
            py = abs(float(gt[5]))
            ext = self._extent_key(gt, w, h)

            if ref_gt is None:
                ref_gt = gt
                ref_w = w
                ref_h = h
                ref_x = px
                ref_y = py
                ref_ext = ext
                ref_name = rl.name()

            aligned_px = int(abs(px - ref_x) <= 1e-9 and abs(py - ref_y) <= 1e-9)
            aligned_extent = int(ext == ref_ext)
            aligned_shape = int(w == ref_w and h == ref_h)
            aligned_all = int(aligned_px and aligned_extent and aligned_shape)
            aligned_all_count += aligned_all

            feat = QgsFeature(fields)
            feat["raster"] = rl.name()
            feat["width"] = int(w)
            feat["height"] = int(h)
            feat["pixel_x"] = px
            feat["pixel_y"] = py
            feat["crs_authid"] = rl.crs().authid() if rl.crs().isValid() else ""
            feat["aligned_px"] = aligned_px
            feat["aligned_extent"] = aligned_extent
            feat["aligned_shape"] = aligned_shape
            feat["aligned_all"] = aligned_all
            sink.addFeature(feat)
            feedback.setProgress(int(((i + 1) / max(1, total)) * 100))

        summary = QgsFeature(fields)
        summary["raster"] = f"__SUMMARY__ ref={ref_name}"
        summary["width"] = int(ref_w or 0)
        summary["height"] = int(ref_h or 0)
        summary["pixel_x"] = float(ref_x or 0.0)
        summary["pixel_y"] = float(ref_y or 0.0)
        summary["crs_authid"] = ""
        summary["aligned_px"] = int(aligned_all_count == total)
        summary["aligned_extent"] = int(aligned_all_count == total)
        summary["aligned_shape"] = int(aligned_all_count == total)
        summary["aligned_all"] = int(aligned_all_count == total)
        sink.addFeature(summary)
        return {self.OUTPUT: dest}
