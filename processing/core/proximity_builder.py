# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)
from .._mcda_utils import smart_output_path


class ProximityBuilderAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    VALUES = 'VALUES'
    UNITS = 'UNITS'
    MAX_DISTANCE = 'MAX_DISTANCE'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'proximity_builder'

    def displayName(self):
        return 'Core: Proximity Builder'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def shortHelpString(self):
        return (
            "<p><b>Computes Euclidean distance from every cell to the nearest target pixel, "
            "creating a continuous proximity surface.</b></p>"
            "<p><b>Inputs:</b> Input raster (single-band); target pixel values as comma-separated integers "
            '(default "1" - cells with these values are distance sources); distance units: '
            "Georeferenced (map units) or Pixels; maximum distance (0 = unlimited, values >=0 in the "
            "chosen unit).<br>"
            "<b>Output:</b> Single-band Float32 GeoTIFF proximity raster, nodata = 0. "
            "Distance values are in the selected unit, capped at the maximum distance if set.<br>"
            "<b>Method:</b> Wraps GDAL Proximity (gdal:proximity), computing the Euclidean distance "
            "transform from each cell to the nearest cell whose band-1 value matches any of the "
            "target values. Nodata cells in the input are excluded from the distance calculation "
            "but output as 0. The REPLACE option is disabled so target cells retain their proximity "
            "distance (typically 0 or very small).<br>"
            "<b>Typical use:</b> Creating continuous distance-to-feature rasters - e.g., distance "
            "to roads, transit stops, water bodies, or hazard zones - for use as normalised "
            "suitability criteria.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ProximityBuilderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, 'Input raster'))
        self.addParameter(QgsProcessingParameterString(self.VALUES, 'Target pixel values (comma-separated)', defaultValue='1'))
        self.addParameter(QgsProcessingParameterEnum(self.UNITS, 'Distance units', options=['Georeferenced', 'Pixels'], defaultValue=0))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_DISTANCE,
                'Maximum distance (0 for unlimited)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
                minValue=0.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Proximity raster'))

    def processAlgorithm(self, parameters, context, feedback):
        rl = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        values = self.parameterAsString(parameters, self.VALUES, context).strip() or '1'
        units = int(self.parameterAsEnum(parameters, self.UNITS, context))
        maxd = float(self.parameterAsDouble(parameters, self.MAX_DISTANCE, context))
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, rl, "proximity_builder")
        processing.run('gdal:proximity', {
            'INPUT': rl.source(),
            'BAND': 1,
            'VALUES': values,
            'UNITS': units,
            'MAX_DISTANCE': maxd,
            'REPLACE': 0,
            'NODATA': 0,
            'OPTIONS': '',
            'EXTRA': '',
            'DATA_TYPE': 5,
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
