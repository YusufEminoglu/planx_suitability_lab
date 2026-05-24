# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
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

    def createInstance(self):
        return RasterizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, 'Vector input', [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD,
                'Value field (optional, overrides burn value)',
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterNumber(self.BURN, 'Burn value', type=QgsProcessingParameterNumber.Double, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(self.PIXEL, 'Pixel size', type=QgsProcessingParameterNumber.Double, defaultValue=10.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Rasterized output'))

    def processAlgorithm(self, parameters, context, feedback):
        src = self.parameterAsSource(parameters, self.INPUT, context)
        field = self.parameterAsString(parameters, self.FIELD, context).strip()
        burn = self.parameterAsDouble(parameters, self.BURN, context)
        pix = self.parameterAsDouble(parameters, self.PIXEL, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, src, "vector_rasterizer")
        processing.run('gdal:rasterize', {
            'INPUT': src,
            'FIELD': field if field else None,
            'BURN': burn,
            'USE_Z': False,
            'UNITS': 1,
            'WIDTH': pix,
            'HEIGHT': pix,
            'EXTENT': src.sourceExtent(),
            'NODATA': 0,
            'OPTIONS': '',
            'DATA_TYPE': 5,
            'INIT': 0,
            'INVERT': False,
            'EXTRA': '',
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
