# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
)
from .._mcda_utils import smart_output_path


class RasterizerAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELD = 'FIELD'
    BURN = 'BURN'
    PIXEL = 'PIXEL'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'vector_rasterizer'

    def displayName(self):
        return 'Core: Vector Rasterizer'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def shortHelpString(self):
        return (
            "<p><b>Converts vector features to a single-band raster, burning attribute values "
            "or a fixed burn value into each cell.</b></p>"
            "<p><b>Inputs:</b> Vector input (any geometry type); optional numeric value field "
            "(when provided, cell value = feature attribute; otherwise the burn value is used); "
            "burn value (default 1.0); pixel size in map units (>=0.01, default 10.0).<br>"
            "<b>Output:</b> Single-band Float32 GeoTIFF covering the input layer extent at the specified pixel size, "
            "nodata = 0 for cells not intersected by any feature.<br>"
            "<b>Method:</b> Wraps GDAL Rasterize (gdal:rasterize) with pixel-sized units. "
            "When a value field is selected, each cell receives the attribute value of the feature covering "
            "its center. Otherwise, all cells intersecting any feature receive the burn value. "
            "Output extent is derived from the input layer bounds; output data type is fixed to Float32.<br>"
            "<b>Typical use:</b> Converting land-use polygons, zoning boundaries, building footprints, "
            "or facility points into raster criteria for suitability analysis or constraint masking.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return RasterizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, 'Vector input', [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD,
                'Value field (optional, overrides burn value)',
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterNumber(self.BURN, 'Burn value', type=QgsProcessingParameterNumber.Type.Double, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(self.PIXEL, 'Pixel size', type=QgsProcessingParameterNumber.Type.Double, defaultValue=10.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Rasterized output'))

    def processAlgorithm(self, parameters, context, feedback):
        vlayer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if vlayer is None:
            raise QgsProcessingException(
                "Could not load source layer for INPUT. Please select a valid vector layer."
            )
        field = self.parameterAsString(parameters, self.FIELD, context).strip()
        burn = self.parameterAsDouble(parameters, self.BURN, context)
        pix = self.parameterAsDouble(parameters, self.PIXEL, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, vlayer, "vector_rasterizer")
        processing.run('gdal:rasterize', {
            'INPUT': vlayer,
            'FIELD': field if field else None,
            'BURN': burn,
            'USE_Z': False,
            'UNITS': 1,
            'WIDTH': pix,
            'HEIGHT': pix,
            'EXTENT': vlayer.extent(),
            'NODATA': 0,
            'OPTIONS': '',
            'DATA_TYPE': 5,
            'INIT': 0,
            'INVERT': False,
            'EXTRA': '',
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
