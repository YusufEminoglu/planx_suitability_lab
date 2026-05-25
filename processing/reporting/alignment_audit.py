# -*- coding: utf-8 -*-
from __future__ import annotations

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
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)

from .._mcda_utils import ensure_list


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

    def createInstance(self):
        return AlignmentAuditAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Input rasters to audit (2..20)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.SNAP, "Optional snap raster (reference)", optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Alignment audit table", QgsProcessing.TypeVector))

    @staticmethod
    def _extent_key(gt, xsize, ysize):
        minx = float(gt[0])
        maxy = float(gt[3])
        maxx = minx + float(gt[1]) * xsize
        miny = maxy + float(gt[5]) * ysize
        return (round(minx, 8), round(miny, 8), round(maxx, 8), round(maxy, 8))

    def processAlgorithm(self, parameters, context, feedback):
        rasters = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:20]
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
        fields.append(QgsField("raster", QVariant.String))
        fields.append(QgsField("width", QVariant.Int))
        fields.append(QgsField("height", QVariant.Int))
        fields.append(QgsField("pixel_x", QVariant.Double))
        fields.append(QgsField("pixel_y", QVariant.Double))
        fields.append(QgsField("crs_authid", QVariant.String))
        fields.append(QgsField("aligned_px", QVariant.Int))
        fields.append(QgsField("aligned_extent", QVariant.Int))
        fields.append(QgsField("aligned_shape", QVariant.Int))
        fields.append(QgsField("aligned_all", QVariant.Int))
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
