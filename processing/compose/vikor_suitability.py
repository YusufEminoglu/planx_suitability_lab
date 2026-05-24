# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)

from .._mcda_utils import ensure_list, parse_impacts_csv, parse_weights_csv, smart_output_path


class VIKORSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    IMPACTS_CSV = "IMPACTS_CSV"
    V = "V"
    CONSTRAINT = "CONSTRAINT"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "vikor_suitability"

    def displayName(self):
        return "Compose: VIKOR Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return VIKORSuitabilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6, normalized to 0-100)",
                QgsProcessing.TypeRaster,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.WEIGHTS_CSV, "Criteria weights CSV (optional)", defaultValue="", optional=True))
        self.addParameter(
            QgsProcessingParameterString(
                self.IMPACTS_CSV,
                "Impacts CSV per criterion (B/C or +/-1, optional; default all benefit)",
                defaultValue="",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.V,
                "Compromise weight v (0..1, higher favors group utility S)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0.0,
                maxValue=1.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
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
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_vikor"))

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
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))[:6]
        if not layers:
            raise QgsProcessingException("No criterion rasters provided for VIKOR.")
        n = len(layers)
        weights = np.array(parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), n), dtype=np.float64)
        impacts = np.array(parse_impacts_csv(self.parameterAsString(parameters, self.IMPACTS_CSV, context), n), dtype=np.int8)
        v = float(self.parameterAsDouble(parameters, self.V, context))
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, layers[0], "vikor_suitability")
        constraint = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)

        datasets = []
        bands = []
        nodatas = []
        xsize = None
        ysize = None
        template_ds = None
        for lyr in layers:
            ds = gdal.Open(lyr.source(), gdal.GA_ReadOnly)
            if ds is None:
                raise QgsProcessingException(f"Cannot open raster: {lyr.name()}")
            b = ds.GetRasterBand(1)
            if xsize is None:
                xsize = ds.RasterXSize
                ysize = ds.RasterYSize
                template_ds = ds
            elif ds.RasterXSize != xsize or ds.RasterYSize != ysize:
                raise QgsProcessingException("All criterion rasters must share identical dimensions.")
            datasets.append(ds)
            bands.append(b)
            nodatas.append(b.GetNoDataValue())

        c_band = None
        c_nodata = None
        if constraint is not None:
            cds = gdal.Open(constraint.source(), gdal.GA_ReadOnly)
            if cds is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if cds.RasterXSize != xsize or cds.RasterYSize != ysize:
                raise QgsProcessingException("Constraint raster must match criterion grid dimensions.")
            c_band = cds.GetRasterBand(1)
            c_nodata = c_band.GetNoDataValue()

        blocks_x = (xsize + block - 1) // block
        blocks_y = (ysize + block - 1) // block
        total_blocks = max(1, blocks_x * blocks_y)

        # Pass 1: per-criterion best/worst values under valid (+constraint) cells.
        best = np.full(n, -np.inf, dtype=np.float64)
        worst = np.full(n, np.inf, dtype=np.float64)
        done = 0
        for yoff in range(0, ysize, block):
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                cols = min(block, xsize - xoff)
                arrs = []
                base_valid = np.ones((rows, cols), dtype=bool)
                for j, b in enumerate(bands):
                    a = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    arrs.append(np.clip(a, 0.0, 100.0))
                    m = np.isfinite(a)
                    nd = nodatas[j]
                    if nd is not None:
                        m &= a != nd
                    base_valid &= m

                if c_band is not None:
                    c_arr = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(c_arr)
                    if c_nodata is not None:
                        c_valid &= c_arr != c_nodata
                    valid = base_valid & c_valid & (c_arr > 0.5)
                else:
                    valid = base_valid

                if np.any(valid):
                    for j in range(n):
                        vals = arrs[j][valid].astype(np.float64)
                        vmax = float(np.max(vals))
                        vmin = float(np.min(vals))
                        if impacts[j] > 0:
                            best[j] = max(best[j], vmax)
                            worst[j] = min(worst[j], vmin)
                        else:
                            best[j] = min(best[j], vmin)
                            worst[j] = max(worst[j], vmax)
                done += 1
                feedback.setProgress(int((done / (3 * total_blocks)) * 100))

        for j in range(n):
            if not np.isfinite(best[j]):
                best[j] = 50.0
            if not np.isfinite(worst[j]):
                worst[j] = 50.0

        den = np.maximum(np.abs(best - worst), 1e-9)

        # Pass 2: global S* S- R* R-.
        s_star = np.inf
        s_minus = -np.inf
        r_star = np.inf
        r_minus = -np.inf
        done = 0
        for yoff in range(0, ysize, block):
            rows = min(block, ysize - yoff)
            for xoff in range(0, xsize, block):
                cols = min(block, xsize - xoff)
                arrs = []
                base_valid = np.ones((rows, cols), dtype=bool)
                for j, b in enumerate(bands):
                    a = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    arrs.append(np.clip(a, 0.0, 100.0))
                    m = np.isfinite(a)
                    nd = nodatas[j]
                    if nd is not None:
                        m &= a != nd
                    base_valid &= m

                if c_band is not None:
                    c_arr = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(c_arr)
                    if c_nodata is not None:
                        c_valid &= c_arr != c_nodata
                    valid = base_valid & c_valid & (c_arr > 0.5)
                else:
                    valid = base_valid

                if np.any(valid):
                    s_stack = np.zeros((n, rows, cols), dtype=np.float64)
                    for j in range(n):
                        if impacts[j] > 0:
                            diff = (best[j] - arrs[j].astype(np.float64)) / den[j]
                        else:
                            diff = (arrs[j].astype(np.float64) - best[j]) / den[j]
                        s_stack[j] = np.clip(diff, 0.0, 1.0) * weights[j]

                    s_map = np.sum(s_stack, axis=0)
                    r_map = np.max(s_stack, axis=0)
                    s_vals = s_map[valid]
                    r_vals = r_map[valid]
                    if s_vals.size > 0:
                        s_star = min(s_star, float(np.min(s_vals)))
                        s_minus = max(s_minus, float(np.max(s_vals)))
                        r_star = min(r_star, float(np.min(r_vals)))
                        r_minus = max(r_minus, float(np.max(r_vals)))

                done += 1
                feedback.setProgress(int((total_blocks + done) / (3 * total_blocks) * 100))

        if not np.isfinite(s_star):
            s_star = 0.0
        if not np.isfinite(s_minus):
            s_minus = 1.0
        if not np.isfinite(r_star):
            r_star = 0.0
        if not np.isfinite(r_minus):
            r_minus = 1.0

        ds = max(s_minus - s_star, 1e-9)
        dr = max(r_minus - r_star, 1e-9)

        out_nodata = nodatas[0] if nodatas[0] is not None else -9999.0
        out_ds, out_band = self._create_output(template_ds, out, out_nodata)

        # Pass 3: compute Q and convert to suitability (100 - Q*100).
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
                base_valid = np.ones((rows, cols), dtype=bool)
                for j, b in enumerate(bands):
                    a = b.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    arrs.append(np.clip(a, 0.0, 100.0))
                    m = np.isfinite(a)
                    nd = nodatas[j]
                    if nd is not None:
                        m &= a != nd
                    base_valid &= m

                missing_mask = ~base_valid
                if c_band is not None:
                    c_arr = c_band.ReadAsArray(xoff, yoff, cols, rows).astype(np.float32)
                    c_valid = np.isfinite(c_arr)
                    if c_nodata is not None:
                        c_valid &= c_arr != c_nodata
                    pass_mask = c_valid & (c_arr > 0.5)
                    valid = base_valid & pass_mask
                    fail_mask = base_valid & c_valid & (~pass_mask)
                    missing_mask |= ~c_valid
                else:
                    valid = base_valid
                    fail_mask = np.zeros((rows, cols), dtype=bool)

                s_stack = np.zeros((n, rows, cols), dtype=np.float64)
                for j in range(n):
                    if impacts[j] > 0:
                        diff = (best[j] - arrs[j].astype(np.float64)) / den[j]
                    else:
                        diff = (arrs[j].astype(np.float64) - best[j]) / den[j]
                    s_stack[j] = np.clip(diff, 0.0, 1.0) * weights[j]
                s_map = np.sum(s_stack, axis=0)
                r_map = np.max(s_stack, axis=0)
                q_map = v * ((s_map - s_star) / ds) + (1.0 - v) * ((r_map - r_star) / dr)
                score = (100.0 * (1.0 - q_map)).astype(np.float32)
                score = np.clip(score, 0.0, 100.0)

                out_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_arr[valid] = score[valid]
                out_arr[fail_mask] = 0.0
                out_band.WriteArray(out_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((2 * total_blocks + done) / (3 * total_blocks) * 100))

        out_ds = None
        for ds in datasets:
            ds = None
        feedback.pushInfo(f"VIKOR completed with v={v:.2f}. Output range constrained to [0,100].")
        return {self.OUTPUT: out}
