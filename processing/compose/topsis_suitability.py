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


class TOPSISSuitabilityAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = "INPUT_RASTERS"
    WEIGHTS_CSV = "WEIGHTS_CSV"
    IMPACTS_CSV = "IMPACTS_CSV"
    CONSTRAINT = "CONSTRAINT"
    BLOCK = "BLOCK"
    OUTPUT = "OUTPUT"

    def name(self):
        return "topsis_suitability"

    def displayName(self):
        return "Compose: TOPSIS Suitability"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return TOPSISSuitabilityAlgorithm()

    def shortHelpString(self):
        return (
            "<p><b>Multi-criteria suitability via Technique for Order Preference "
            "by Similarity to Ideal Solution (TOPSIS).</b></p>\n"
            "<p><b>Inputs:</b> Up to 6 criterion rasters (normalized 0–100); "
            "optional criteria weights CSV; optional impacts CSV "
            "(B/C or +/-1, default all benefit); optional constraint mask (0/1); "
            "block size 64–2048.<br>\n"
            "<b>Output:</b> Closeness coefficient raster (Float32, 0–100); "
            "1.0 = ideal, 0.0 = anti-ideal; constraint-failing cells set to 0.<br>\n"
            "<b>Method:</b> Three-pass: (1) vector normalisation denominators "
            "across all valid cells; (2) identify ideal-positive and "
            "ideal-negative points in weighted normalised space per criterion "
            "(benefit: max=ideal; cost: min=ideal); "
            "(3) per-cell Euclidean distances d+ and d-, "
            "closeness = d-/(d+ + d-) scaled to 0–100.<br>\n"
            "<b>Typical use:</b> Ranking alternatives when both benefit and cost "
            "criteria matter and the best compromise close to the ideal is sought.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                "Criterion rasters (max 6, normalized to 0-100)",
                QgsProcessing.SourceType.TypeRaster,
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
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Constraint mask raster (0/1)", optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BLOCK,
                "Block size (pixels)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=256,
                minValue=64,
                maxValue=2048,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "suitability_topsis"))

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
            raise QgsProcessingException("No criterion rasters provided for TOPSIS.")
        n = len(layers)
        weights = np.array(parse_weights_csv(self.parameterAsString(parameters, self.WEIGHTS_CSV, context), n), dtype=np.float64)
        impacts = np.array(parse_impacts_csv(self.parameterAsString(parameters, self.IMPACTS_CSV, context), n), dtype=np.int8)
        block = int(self.parameterAsInt(parameters, self.BLOCK, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, layers[0], "topsis_suitability")
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

        # Pass 1: criterion normalization denominators (vector norm).
        sumsq = np.zeros(n, dtype=np.float64)
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
                    pass_mask = (c_arr > 0.5) & c_valid
                    valid = base_valid & pass_mask
                else:
                    valid = base_valid
                if np.any(valid):
                    for j in range(n):
                        vals = arrs[j][valid].astype(np.float64)
                        sumsq[j] += np.sum(vals * vals)
                done += 1
                feedback.setProgress(int((done / (3 * total_blocks)) * 100))

        den = np.sqrt(np.maximum(sumsq, 1e-12))

        # Pass 2: ideal positive/negative points in weighted normalized space.
        pos = np.where(impacts > 0, -np.inf, np.inf).astype(np.float64)
        neg = np.where(impacts > 0, np.inf, -np.inf).astype(np.float64)
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
                    pass_mask = (c_arr > 0.5) & c_valid
                    valid = base_valid & pass_mask
                else:
                    valid = base_valid
                if np.any(valid):
                    for j in range(n):
                        v = (arrs[j].astype(np.float64) / den[j]) * weights[j]
                        vals = v[valid]
                        vmax = float(np.max(vals))
                        vmin = float(np.min(vals))
                        if impacts[j] > 0:
                            pos[j] = max(pos[j], vmax)
                            neg[j] = min(neg[j], vmin)
                        else:
                            pos[j] = min(pos[j], vmin)
                            neg[j] = max(neg[j], vmax)
                done += 1
                feedback.setProgress(int((total_blocks + done) / (3 * total_blocks) * 100))

        # Fix any uninitialized ideals.
        for j in range(n):
            if not np.isfinite(pos[j]):
                pos[j] = 0.0
            if not np.isfinite(neg[j]):
                neg[j] = 0.0

        out_nodata = nodatas[0] if nodatas[0] is not None else -9999.0
        out_ds, out_band = self._create_output(template_ds, out, out_nodata)

        # Pass 3: closeness coefficient.
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
                    pass_mask = (c_arr > 0.5) & c_valid
                    missing_mask |= ~c_valid
                    valid = base_valid & pass_mask
                    fail_mask = base_valid & c_valid & (~pass_mask)
                else:
                    valid = base_valid
                    fail_mask = np.zeros((rows, cols), dtype=bool)

                # Compute weighted normalized matrix for block.
                v_stack = np.zeros((n, rows, cols), dtype=np.float64)
                for j in range(n):
                    v_stack[j] = (arrs[j].astype(np.float64) / den[j]) * weights[j]

                d_plus = np.sqrt(np.sum((v_stack - pos[:, None, None]) ** 2, axis=0))
                d_minus = np.sqrt(np.sum((v_stack - neg[:, None, None]) ** 2, axis=0))
                closeness = (d_minus / (d_plus + d_minus + 1e-12)) * 100.0
                closeness = np.clip(closeness, 0.0, 100.0).astype(np.float32)

                out_arr = np.full((rows, cols), out_nodata, dtype=np.float32)
                out_arr[valid] = closeness[valid]
                out_arr[fail_mask] = 0.0  # hard-constraint policy
                out_band.WriteArray(out_arr, xoff, yoff)

                done += 1
                feedback.setProgress(int((2 * total_blocks + done) / (3 * total_blocks) * 100))

        out_ds = None
        for ds in datasets:
            ds = None
        return {self.OUTPUT: out}
