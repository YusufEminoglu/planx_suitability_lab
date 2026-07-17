# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import os
import tempfile
from collections import deque

import numpy as np
import processing
from osgeo import gdal
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsVectorLayer,
)


def label_components(mask: np.ndarray, connectivity: int = 8):
    """
    Label contiguous True regions of a boolean mask.
    Returns (labels int32 array with 0 = background, component count).
    Pure numpy/stdlib so it is testable without QGIS.
    """
    if connectivity == 4:
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    else:
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1), (0, 1),
            (1, -1), (1, 0), (1, 1),
        ]
    rows, cols = mask.shape
    labels = np.zeros(mask.shape, dtype=np.int32)
    current = 0
    q = deque()
    for r in range(rows):
        for c in range(cols):
            if not mask[r, c] or labels[r, c] != 0:
                continue
            current += 1
            labels[r, c] = current
            q.clear()
            q.append((r, c))
            while q:
                rr, cc = q.popleft()
                for dr, dc in offsets:
                    nr = rr + dr
                    nc = cc + dc
                    if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and labels[nr, nc] == 0:
                        labels[nr, nc] = current
                        q.append((nr, nc))
    return labels, current


def rank_sites(
    labels: np.ndarray,
    count: int,
    values: np.ndarray,
    cell_area_m2: float,
    min_area_ha: float,
    top_n: int,
):
    """
    Build ranked site records from labeled components.
    Ranking: mean suitability desc, then area desc, then label asc (deterministic).
    Returns list of dicts with label, cells, area_ha, mean, max — rank = list index + 1.
    """
    sites = []
    for label in range(1, count + 1):
        sel = labels == label
        cells = int(np.sum(sel))
        if cells <= 0:
            continue
        area_ha = cells * cell_area_m2 / 10000.0
        if min_area_ha > 0 and area_ha < min_area_ha:
            continue
        vals = values[sel]
        sites.append(
            {
                "label": int(label),
                "cells": cells,
                "area_ha": float(area_ha),
                "mean": float(np.mean(vals)),
                "max": float(np.max(vals)),
            }
        )
    sites.sort(key=lambda s: (-s["mean"], -s["area_ha"], s["label"]))
    if top_n > 0:
        sites = sites[:top_n]
    return sites


class CandidateSiteExtractorAlgorithm(QgsProcessingAlgorithm):
    SUIT = "SUIT"
    THRESHOLD = "THRESHOLD"
    MIN_AREA_HA = "MIN_AREA_HA"
    TOP_N = "TOP_N"
    CONNECTIVITY = "CONNECTIVITY"
    OUTPUT = "OUTPUT"

    def name(self):
        return "candidate_site_extractor"

    def displayName(self):
        return "Compose: Candidate Site Extractor"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def shortHelpString(self):
        return (
            "<p><b>Extracts contiguous high-suitability patches as ranked "
            "candidate site polygons.</b></p>\n"
            "<p><b>Inputs:</b> Suitability raster (0–100); "
            "site threshold (cells ≥ value, default 75); "
            "minimum site area in hectares (0=no filter); "
            "maximum number of top-ranked sites (0=all, up to 1000); "
            "connectivity 4 or 8 (default 8).<br>\n"
            "<b>Output:</b> Vector polygon layer with fields: site_id, rank, "
            "cells, area_ha, mean_suit, max_suit, compactness (0–1). "
            "Use a projected CRS for meaningful hectare values.<br>\n"
            "<b>Method:</b> Thresholds suitability, labels contiguous "
            "components via BFS (4- or 8-connectivity), filters by minimum "
            "area, ranks by mean suitability (area as tie-break), "
            "takes top-N, polygonises via GDAL, and computes "
            "compactness = 4π·area/perimeter².<br>\n"
            "<b>Typical use:</b> Identifying the best contiguous land parcels "
            "for development, conservation, or infrastructure siting.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return CandidateSiteExtractorAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.SUIT, "Suitability raster (0-100)"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                "Site threshold (cells >= value)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=75.0,
                minValue=0.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_AREA_HA,
                "Minimum site area (ha, 0 = no filter)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=1.0,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TOP_N,
                "Maximum number of sites (0 = all)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=20,
                minValue=0,
                maxValue=1000,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONNECTIVITY,
                "Connectivity (4 or 8)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=8,
                minValue=4,
                maxValue=8,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "Candidate sites", QgsProcessing.SourceType.TypeVectorPolygon)
        )

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.SUIT, context)
        thr = float(self.parameterAsDouble(parameters, self.THRESHOLD, context))
        min_area_ha = float(self.parameterAsDouble(parameters, self.MIN_AREA_HA, context))
        top_n = int(self.parameterAsInt(parameters, self.TOP_N, context))
        conn = int(self.parameterAsInt(parameters, self.CONNECTIVITY, context))
        conn = 4 if conn == 4 else 8

        ds = gdal.Open(rl.source(), gdal.GA_ReadOnly)
        if ds is None:
            raise QgsProcessingException("Cannot open suitability raster.")
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        arr = b.ReadAsArray().astype(np.float32)

        valid = np.isfinite(arr)
        if nd is not None:
            valid &= arr != nd
        arr = np.clip(arr, 0.0, 100.0)
        high = valid & (arr >= thr)

        gt = ds.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        feedback.pushInfo(f"High-suitability cells: {int(np.sum(high))} of {int(np.sum(valid))} valid.")
        feedback.setProgress(10)

        labels, count = label_components(high, conn)
        feedback.pushInfo(f"Contiguous patches found: {count}.")
        feedback.setProgress(45)

        sites = rank_sites(labels, count, arr, cell_area, min_area_ha, top_n)
        feedback.pushInfo(f"Sites kept after area filter and ranking: {len(sites)}.")
        feedback.setProgress(60)

        fields = QgsFields()
        fields.append(QgsField("site_id", QVariant.Int))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("area_ha", QVariant.Double))
        fields.append(QgsField("mean_suit", QVariant.Double))
        fields.append(QgsField("max_suit", QVariant.Double))
        fields.append(QgsField("compactness", QVariant.Double))
        sink, dest = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields, Qgis.WkbType.MultiPolygon, rl.crs()
        )
        if sink is None:
            raise QgsProcessingException("Cannot create output sink.")

        if not sites:
            feedback.pushInfo("No candidate sites match the threshold/area criteria.")
            return {self.OUTPUT: dest}

        # Raster of rank values (0 = background) for vectorization.
        lut = np.zeros(count + 1, dtype=np.int32)
        for rank, site in enumerate(sites, start=1):
            lut[site["label"]] = rank
        rank_arr = lut[labels]

        fd, rank_tif = tempfile.mkstemp(prefix="planx_sites_", suffix=".tif")
        os.close(fd)
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(rank_tif, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Int32, options=["COMPRESS=LZW"])
        out_ds.SetGeoTransform(ds.GetGeoTransform())
        out_ds.SetProjection(ds.GetProjection())
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(0.0)
        out_band.WriteArray(rank_arr)
        out_band.FlushCache()
        out_ds = None
        ds = None
        feedback.setProgress(70)

        fd, poly_path = tempfile.mkstemp(prefix="planx_sites_", suffix=".gpkg")
        os.close(fd)
        os.unlink(poly_path)
        processing.run(
            "gdal:polygonize",
            {
                "INPUT": rank_tif,
                "BAND": 1,
                "FIELD": "rank",
                "EIGHT_CONNECTEDNESS": conn == 8,
                "EXTRA": "",
                "OUTPUT": poly_path,
            },
        )
        vl = QgsVectorLayer(poly_path, "candidate_sites", "ogr")
        if not vl.isValid():
            raise QgsProcessingException("Polygonize step failed to produce a valid layer.")
        feedback.setProgress(85)

        geoms_by_rank: dict[int, list] = {}
        for f in vl.getFeatures():
            rank = int(f["rank"])
            if rank <= 0:
                continue
            geoms_by_rank.setdefault(rank, []).append(QgsGeometry(f.geometry()))

        for rank, site in enumerate(sites, start=1):
            parts = geoms_by_rank.get(rank, [])
            if not parts:
                continue
            geom = parts[0] if len(parts) == 1 else QgsGeometry.collectGeometry(parts)
            geom.convertToMultiType()
            area = float(geom.area())
            perim = float(geom.length())
            compactness = (4.0 * math.pi * area / (perim * perim)) if perim > 0 else 0.0
            feat = QgsFeature(fields)
            feat.setGeometry(geom)
            feat["site_id"] = int(rank)
            feat["rank"] = int(rank)
            feat["cells"] = int(site["cells"])
            feat["area_ha"] = float(site["area_ha"])
            feat["mean_suit"] = float(site["mean"])
            feat["max_suit"] = float(site["max"])
            feat["compactness"] = float(min(1.0, max(0.0, compactness)))
            sink.addFeature(feat)

        vl = None
        for tmp in (rank_tif,):
            try:
                os.unlink(tmp)
            except OSError:
                pass

        feedback.setProgress(100)
        return {self.OUTPUT: dest}
