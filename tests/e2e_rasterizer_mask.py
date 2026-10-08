#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vector Rasterizer: reference raster + background value -> constraint mask.

Run with OSGeo4W:
  C:/OSGeo4W/bin/python-qgis-ltr.bat tests/e2e_rasterizer_mask.py   (QGIS 3.44)
  C:/OSGeo4W/bin/python-qgis.bat tests/e2e_rasterizer_mask.py       (QGIS 4.x)

What it proves:
  * defaults reproduce the historical output (vector extent, background 0 = NoData)
  * reference raster + burn 0 + background 1 + NoData off gives a 0/1 mask that
    has the SAME shape and geotransform as the analysis grid
  * a vector in another CRS is reprojected to the reference CRS
  * WLC with that mask zeroes the polygon and leaves every other cell untouched
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication  # noqa: E402

qgs = QgsApplication([], False)
qgs.initQgis()

import qgis  # noqa: E402

sys.path.insert(0, str(Path(qgis.__file__).resolve().parents[1] / "plugins"))
sys.path.append(str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import processing  # noqa: E402
from osgeo import gdal, ogr, osr  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

from planx_suitability_lab.provider import PlanXSuitabilityLabProvider  # noqa: E402

provider = PlanXSuitabilityLabProvider()   # keep a reference: the registry does not own it
QgsApplication.processingRegistry().addProvider(provider)

failures = []


def check(cond, label):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


tmp = tempfile.mkdtemp(prefix="rast_mask_")
P = lambda name: os.path.join(tmp, name)  # noqa: E731
N, X0, Y0, RES = 60, 500000.0, 4200000.0, 30.0
srs = osr.SpatialReference()
srs.ImportFromEPSG(5253)
srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def write_grid(name, arr):
    ds = gdal.GetDriverByName("GTiff").Create(P(name), N, N, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((X0, RES, 0, Y0, 0, -RES))
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.WriteArray(arr.astype("float32"))
    ds.FlushCache()
    return P(name)


def read(path):
    ds = gdal.Open(path)
    band = ds.GetRasterBand(1)
    return band.ReadAsArray().astype("float64"), band.GetNoDataValue(), ds.GetGeoTransform(), (ds.RasterXSize, ds.RasterYSize)


def write_polygon(name, target_srs, value=7.0):
    """Square covering grid cells rows 20..39, cols 20..39, in `target_srs`."""
    xa, xb = X0 + 20 * RES, X0 + 40 * RES
    ya, yb = Y0 - 40 * RES, Y0 - 20 * RES
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [(xa, ya), (xb, ya), (xb, yb), (xa, yb), (xa, ya)]:
        ring.AddPoint_2D(x, y)
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    poly.AssignSpatialReference(srs)
    if target_srs.GetAuthorityCode(None) != srs.GetAuthorityCode(None):
        poly.Transform(osr.CoordinateTransformation(srs, target_srs))
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(P(name))
    lyr = ds.CreateLayer("zone", target_srs, ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("val", ogr.OFTReal))
    feat = ogr.Feature(lyr.GetLayerDefn())
    feat.SetGeometry(poly)
    feat.SetField("val", value)
    lyr.CreateFeature(feat)
    ds = None
    return P(name)


yy, xx = np.mgrid[0:N, 0:N]
crit = [write_grid("a.tif", xx * 100.0 / (N - 1)), write_grid("b.tif", yy * 100.0 / (N - 1)), write_grid("c.tif", 100 - xx * 100.0 / (N - 1))]
inside = np.zeros((N, N), bool)
inside[20:40, 20:40] = True

zone = write_polygon("zone.gpkg", srs)
rast = "planx_suitability_lab:vector_rasterizer"

print("=== 1) Defaults reproduce the historical output ===")
out = processing.run(rast, {"INPUT": zone, "FIELD": None, "BURN": 1.0, "PIXEL": RES, "OUTPUT": P("legacy.tif")})["OUTPUT"]
a, nd, gt, size = read(out)
check(size == (20, 20), f"covers only the vector extent ({size})")
check(nd == 0.0, f"background 0 is NoData ({nd})")
check(set(np.unique(a)) == {1.0}, f"burned cells = 1 ({np.unique(a)})")

print("=== 2) Reference raster + burn 0 + background 1 + NoData off = exclusion mask ===")
out = processing.run(rast, {"INPUT": zone, "FIELD": None, "BURN": 0.0, "PIXEL": RES, "REFERENCE": crit[0],
                            "BACKGROUND": 1.0, "BG_NODATA": False, "OUTPUT": P("mask.tif")})["OUTPUT"]
m, nd, gt, size = read(out)
check(size == (N, N), f"same shape as the grid ({size})")
check(all(abs(x - y) < 1e-9 for x, y in zip(gt, (X0, RES, 0, Y0, 0, -RES))), f"same geotransform ({gt})")
check(set(np.unique(m)) == {0.0, 1.0}, f"only 0 and 1 ({np.unique(m)})")
check(bool((m[inside] == 0).all()), "polygon interior is 0 (excluded)")
check(bool((m[~inside] == 1).all()), "everything else is 1 (allowed)")
check(nd == -9999.0 and not (m == nd).any(), "no cell is NoData")

print("=== 3) A vector in another CRS is reprojected ===")
wgs = osr.SpatialReference()
wgs.ImportFromEPSG(4326)
wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
zone84 = write_polygon("zone84.gpkg", wgs)
out = processing.run(rast, {"INPUT": zone84, "FIELD": None, "BURN": 0.0, "PIXEL": RES, "REFERENCE": crit[0],
                            "BACKGROUND": 1.0, "BG_NODATA": False, "OUTPUT": P("mask84.tif")})["OUTPUT"]
m84, _, _, size84 = read(out)
check(size84 == (N, N), f"EPSG:4326 input still lands on the grid ({size84})")
check(abs(int((m84 == 0).sum()) - int((m == 0).sum())) <= 40, f"excluded cells {(m84 == 0).sum()} ~ {(m == 0).sum()}")

print("=== 4) Value field on the reference grid ===")
out = processing.run(rast, {"INPUT": zone, "FIELD": "val", "BURN": 1.0, "PIXEL": RES, "REFERENCE": crit[0],
                            "BACKGROUND": 0.0, "BG_NODATA": True, "OUTPUT": P("field.tif")})["OUTPUT"]
f, nd, _, size = read(out)
check(size == (N, N) and nd == 0.0, f"grid-shaped, background NoData 0 ({size}, {nd})")
check(bool((f[inside] == 7.0).all()), "attribute value burned")

print("=== 5) WLC with the mask ===")
suit = processing.run("planx_suitability_lab:wlc_suitability", {"INPUT_RASTERS": crit, "WEIGHTS_CSV": "0.4,0.3,0.3",
                      "CONSTRAINT": P("mask.tif"), "BLOCK": 256, "OUTPUT": P("suit.tif")})["OUTPUT"]
s, _, _, _ = read(suit)
exp = 0.4 * (xx * 100.0 / (N - 1)) + 0.3 * (yy * 100.0 / (N - 1)) + 0.3 * (100 - xx * 100.0 / (N - 1))
check(bool((s[inside] == 0).all()), "excluded area scores 0")
check(float(np.abs(s[~inside] - exp[~inside]).max()) < 1e-3, "allowed area equals the plain weighted sum")

print("=== 6) Without a reference, background 1 / NoData off still works ===")
out = processing.run(rast, {"INPUT": zone, "FIELD": None, "BURN": 0.0, "PIXEL": RES, "BACKGROUND": 1.0,
                            "BG_NODATA": False, "OUTPUT": P("vecext.tif")})["OUTPUT"]
v, nd, _, size = read(out)
check(size == (20, 20) and set(np.unique(v)) <= {0.0, 1.0}, f"vector extent, values {np.unique(v)}")

print("\nFAILURES:", len(failures))
sys.exit(1 if failures else 0)
