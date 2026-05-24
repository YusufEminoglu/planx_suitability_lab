# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)


class InterventionConflictMatrixAlgorithm(QgsProcessingAlgorithm):
    PRIORITY_ZONE = "PRIORITY_ZONE"
    ATTENTION_CLASS = "ATTENTION_CLASS"
    CONSTRAINT = "CONSTRAINT"
    OUTPUT = "OUTPUT"

    def name(self):
        return "intervention_conflict_matrix"

    def displayName(self):
        return "Compose: Intervention Conflict Matrix"

    def group(self):
        return "Compose"

    def groupId(self):
        return "compose"

    def createInstance(self):
        return InterventionConflictMatrixAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.PRIORITY_ZONE, "Priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.ATTENTION_CLASS, "Attention class raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.CONSTRAINT, "Optional hard constraint raster (0/1)", optional=True))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Output intervention conflict class raster"))

    def processAlgorithm(self, parameters, context, feedback):
        p_rl = self.parameterAsRasterLayer(parameters, self.PRIORITY_ZONE, context)
        a_rl = self.parameterAsRasterLayer(parameters, self.ATTENTION_CLASS, context)
        c_rl = self.parameterAsRasterLayer(parameters, self.CONSTRAINT, context)

        ds_p = gdal.Open(p_rl.source(), gdal.GA_ReadOnly)
        ds_a = gdal.Open(a_rl.source(), gdal.GA_ReadOnly)
        if ds_p is None or ds_a is None:
            raise QgsProcessingException("Cannot open priority/attention raster.")
        if ds_p.RasterXSize != ds_a.RasterXSize or ds_p.RasterYSize != ds_a.RasterYSize:
            raise QgsProcessingException("Priority and attention rasters must share identical dimensions.")

        bp = ds_p.GetRasterBand(1)
        ba = ds_a.GetRasterBand(1)
        ndp = bp.GetNoDataValue()
        nda = ba.GetNoDataValue()

        bc = None
        ndc = None
        if c_rl is not None:
            ds_c = gdal.Open(c_rl.source(), gdal.GA_ReadOnly)
            if ds_c is None:
                raise QgsProcessingException("Cannot open constraint raster.")
            if ds_c.RasterXSize != ds_p.RasterXSize or ds_c.RasterYSize != ds_p.RasterYSize:
                raise QgsProcessingException("Constraint raster must match priority/attention grid.")
            bc = ds_c.GetRasterBand(1)
            ndc = bc.GetNoDataValue()

        out_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        drv = gdal.GetDriverByName("GTiff")
        out = drv.Create(
            out_path,
            ds_p.RasterXSize,
            ds_p.RasterYSize,
            1,
            gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW"],
        )
        if out is None:
            raise QgsProcessingException("Could not create intervention conflict output raster.")
        out.SetProjection(ds_p.GetProjection())
        out.SetGeoTransform(ds_p.GetGeoTransform())
        bo = out.GetRasterBand(1)
        bo.SetNoDataValue(255)

        p = bp.ReadAsArray().astype(np.float32)
        a = ba.ReadAsArray().astype(np.float32)
        valid = np.isfinite(p) & np.isfinite(a)
        if ndp is not None:
            valid &= p != ndp
        if nda is not None:
            valid &= a != nda

        pz = np.clip(np.rint(p), 0, 4).astype(np.int32)
        ac = np.clip(np.rint(a), 0, 4).astype(np.int32)

        if bc is not None:
            c = bc.ReadAsArray().astype(np.float32)
            c_ok = np.isfinite(c)
            if ndc is not None:
                c_ok &= c != ndc
            c_ok &= c > 0.5
            valid &= c_ok

        # Output classes:
        # 0: Hold / low action
        # 1: Quick Win (high priority, low conflict)
        # 2: Deliberate Design (high priority, medium conflict)
        # 3: Resolve First (high priority, high conflict)
        # 4: Monitor (mid priority, low conflict)
        # 5: Co-Design (mid priority, high conflict)
        # 6: Re-screen (constraint/low priority with high conflict)
        out_cls = np.full(pz.shape, 255, dtype=np.uint8)
        if np.any(valid):
            cls = np.zeros(pz.shape, dtype=np.uint8)
            high_p = pz >= 3
            mid_p = pz == 2
            low_p = pz <= 1
            low_c = ac <= 1
            med_c = ac == 2
            high_c = ac >= 3

            cls = np.where(high_p & low_c, 1, cls)
            cls = np.where(high_p & med_c, 2, cls)
            cls = np.where(high_p & high_c, 3, cls)
            cls = np.where(mid_p & low_c, 4, cls)
            cls = np.where(mid_p & high_c, 5, cls)
            cls = np.where(low_p & high_c, 6, cls)
            out_cls[valid] = cls[valid]

        bo.WriteArray(out_cls)
        bo.FlushCache()
        out = None
        return {self.OUTPUT: out_path}
