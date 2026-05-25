# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
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
    QgsProcessingParameterRasterLayer,
    QgsCoordinateReferenceSystem,
)


class PriorityTransitionMatrixAlgorithm(QgsProcessingAlgorithm):
    FROM_ZONE = "FROM_ZONE"
    TO_ZONE = "TO_ZONE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "priority_transition_matrix"

    def displayName(self):
        return "Reporting: Priority Transition Matrix"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def createInstance(self):
        return PriorityTransitionMatrixAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.FROM_ZONE, "Baseline priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterRasterLayer(self.TO_ZONE, "Scenario priority zone raster (0..4)"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Priority transition matrix", QgsProcessing.TypeVector))

    @staticmethod
    def _transition_label(delta: int) -> str:
        if delta >= 2:
            return "STRONG_UPGRADE"
        if delta == 1:
            return "UPGRADE"
        if delta == 0:
            return "STABLE"
        if delta == -1:
            return "DOWNGRADE"
        return "STRONG_DOWNGRADE"

    def processAlgorithm(self, parameters, context, feedback):
        from_rl = self.parameterAsRasterLayer(parameters, self.FROM_ZONE, context)
        to_rl = self.parameterAsRasterLayer(parameters, self.TO_ZONE, context)

        ds_a = gdal.Open(from_rl.source(), gdal.GA_ReadOnly)
        ds_b = gdal.Open(to_rl.source(), gdal.GA_ReadOnly)
        if ds_a is None or ds_b is None:
            raise QgsProcessingException("Cannot open baseline/scenario priority rasters.")
        if ds_a.RasterXSize != ds_b.RasterXSize or ds_a.RasterYSize != ds_b.RasterYSize:
            raise QgsProcessingException("Baseline/scenario rasters must have same dimensions.")

        ba = ds_a.GetRasterBand(1)
        bb = ds_b.GetRasterBand(1)
        nda = ba.GetNoDataValue()
        ndb = bb.GetNoDataValue()

        a = ba.ReadAsArray().astype(np.float32)
        b = bb.ReadAsArray().astype(np.float32)
        valid = np.isfinite(a) & np.isfinite(b)
        if nda is not None:
            valid &= a != nda
        if ndb is not None:
            valid &= b != ndb
        if not np.any(valid):
            raise QgsProcessingException("No overlapping valid cells in baseline/scenario rasters.")

        a_i = np.clip(np.rint(a[valid]), 0, 4).astype(np.int32)
        b_i = np.clip(np.rint(b[valid]), 0, 4).astype(np.int32)
        total = float(a_i.size)

        gt = ds_a.GetGeoTransform()
        cell_area = abs(float(gt[1] * gt[5])) if gt else 1.0

        fields = QgsFields()
        fields.append(QgsField("from_zone", QVariant.Int))
        fields.append(QgsField("to_zone", QVariant.Int))
        fields.append(QgsField("cells", QVariant.LongLong))
        fields.append(QgsField("pct_total", QVariant.Double))
        fields.append(QgsField("pct_from", QVariant.Double))
        fields.append(QgsField("area", QVariant.Double))
        fields.append(QgsField("transition", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        from_counts = np.bincount(a_i, minlength=5).astype(np.float64)
        mat = np.zeros((5, 5), dtype=np.float64)
        for fz in range(5):
            for tz in range(5):
                mat[fz, tz] = np.sum((a_i == fz) & (b_i == tz))

        for fz in range(5):
            for tz in range(5):
                cells = mat[fz, tz]
                if cells <= 0:
                    continue
                pct_total = 100.0 * (cells / total)
                pct_from = 100.0 * (cells / from_counts[fz]) if from_counts[fz] > 0 else 0.0
                feat = QgsFeature(fields)
                feat["from_zone"] = int(fz)
                feat["to_zone"] = int(tz)
                feat["cells"] = int(cells)
                feat["pct_total"] = float(pct_total)
                feat["pct_from"] = float(pct_from)
                feat["area"] = float(cells * cell_area)
                feat["transition"] = self._transition_label(int(tz - fz))
                sink.addFeature(feat)

        return {self.OUTPUT: dest}
