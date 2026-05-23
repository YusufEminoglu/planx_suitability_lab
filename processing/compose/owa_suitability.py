# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_weights_csv


class OWASuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    CRITERIA_WEIGHTS = "CRITERIA_WEIGHTS"
    ORDER_WEIGHTS = "ORDER_WEIGHTS"
    SORT_MODE = "SORT_MODE"
    CONSTRAINT = "CONSTRAINT"
    OUTPUT = "OUTPUT"

    SORT_OPTIONS = ["Descending (high score first)", "Ascending (low score first)"]

    def name(self):
        return "owa_suitability"

    def displayName(self):
        return "Compose: OWA Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return OWASuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6, normalized to 0-100)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.CRITERIA_WEIGHTS,
                "Criteria weights CSV (optional)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.ORDER_WEIGHTS,
                "Order weights CSV (optional)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterEnum(self.SORT_MODE, "Ordering mode", options=self.SORT_OPTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_owa"))

    def _write_like(self, template_ds, output_path, array, nodata):
        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(
            output_path,
            template_ds.RasterXSize,
            template_ds.RasterYSize,
            1,
            gdal.GDT_Float32,
            options=["COMPRESS=LZW", "TILED=YES"],
        )
        out_ds.SetGeoTransform(template_ds.GetGeoTransform())
        out_ds.SetProjection(template_ds.GetProjection())
        band = out_ds.GetRasterBand(1)
        band.WriteArray(array.astype(np.float32))
        if nodata is not None:
            band.SetNoDataValue(float(nodata))
        band.FlushCache()
        out_ds = None

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        if not layers:
            raise QgsProcessingException("No criterion rasters provided for OWA.")
        n = len(layers)
        criteria_w = parse_weights_csv(self.parameterAsString(parameters, self.CRITERIA_WEIGHTS, context), n)
        order_w = parse_weights_csv(self.parameterAsString(parameters, self.ORDER_WEIGHTS, context), n)
        sort_mode = int(self.parameterAsEnum(parameters, self.SORT_MODE, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)

        arrays = []
        nodata = None
        template_ds = None
        valid = None
        shape = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            nd = ds.GetRasterBand(1).GetNoDataValue()
            if template_ds is None:
                template_ds = ds
                nodata = nd
                shape = arr.shape
                valid = np.isfinite(arr)
                if nd is not None:
                    valid &= arr != nd
            else:
                if arr.shape != shape:
                    raise QgsProcessingException("All input rasters must share the same extent/resolution grid.")
                m = np.isfinite(arr)
                if nd is not None:
                    m &= arr != nd
                valid &= m
            arrays.append(np.clip(arr, 0.0, 100.0))

        stack = np.stack(arrays, axis=0)  # (n,h,w)
        if sort_mode == 0:
            order_idx = np.argsort(stack, axis=0)[::-1, :, :]
        else:
            order_idx = np.argsort(stack, axis=0)
        sorted_vals = np.take_along_axis(stack, order_idx, axis=0)

        cw = np.array(criteria_w, dtype=np.float32)[:, None, None]
        cw_grid = np.broadcast_to(cw, stack.shape)
        sorted_cw = np.take_along_axis(cw_grid, order_idx, axis=0)
        ow = np.array(order_w, dtype=np.float32)[:, None, None]

        alpha = sorted_cw * ow
        denom = np.sum(alpha, axis=0)
        num = np.sum(alpha * sorted_vals, axis=0)
        result = np.where(denom > 1e-12, num / denom, 0.0).astype(np.float32)
        result = np.clip(result, 0.0, 100.0)

        if constraint is not None:
            cds = gdal.Open(constraint.source(), gdal.GA_ReadOnly)
            carr = cds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            cnd = cds.GetRasterBand(1).GetNoDataValue()
            cmask = np.isfinite(carr)
            if cnd is not None:
                cmask &= carr != cnd
            pass_mask = (carr > 0.5) & cmask
            result = np.where(pass_mask, result, 0.0)
            valid &= cmask

        out_nodata = nodata if nodata is not None else -9999.0
        result = np.where(valid, result, out_nodata)
        self._write_like(template_ds, out, result, out_nodata)
        return {self.OUTPUT: out}

