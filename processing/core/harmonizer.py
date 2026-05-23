# -*- coding: utf-8 -*-
from __future__ import annotations

import os

import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
)

from .._mcda_utils import ensure_list, temp_tif


class DataHarmonizerAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    TARGET_EXTENT = 'TARGET_EXTENT'
    TARGET_RES = 'TARGET_RES'
    OUTPUT_RASTER = 'OUTPUT_RASTER'
    OUTPUT_MANIFEST = 'OUTPUT_MANIFEST'

    def name(self):
        return 'data_harmonizer'

    def displayName(self):
        return 'Core: Data Harmonizer'

    def group(self):
        return 'Core'

    def groupId(self):
        return 'core'

    def createInstance(self):
        return DataHarmonizerAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Input rasters', QgsProcessing.TypeRaster))
        self.addParameter(QgsProcessingParameterExtent(self.TARGET_EXTENT, 'Target extent'))
        self.addParameter(QgsProcessingParameterNumber(self.TARGET_RES, 'Target resolution', type=QgsProcessingParameterNumber.Double, defaultValue=10.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_RASTER, 'Preview aligned raster'))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_MANIFEST, 'Alignment manifest (txt)', fileFilter='Text files (*.txt)'))

    def processAlgorithm(self, parameters, context, feedback):
        rasters = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        extent = self.parameterAsExtent(parameters, self.TARGET_EXTENT, context)
        res = self.parameterAsDouble(parameters, self.TARGET_RES, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        manifest = self.parameterAsFileOutput(parameters, self.OUTPUT_MANIFEST, context)
        if not rasters:
            raise Exception('No input rasters provided')

        src = rasters[0].source()
        processing.run('gdal:warpreproject', {
            'INPUT': src,
            'SOURCE_CRS': None,
            'TARGET_CRS': rasters[0].crs(),
            'RESAMPLING': 0,
            'NODATA': -9999,
            'TARGET_RESOLUTION': res,
            'OPTIONS': '',
            'DATA_TYPE': 0,
            'TARGET_EXTENT': extent,
            'TARGET_EXTENT_CRS': rasters[0].crs(),
            'MULTITHREADING': True,
            'EXTRA': '',
            'OUTPUT': out,
        }, context=context, feedback=feedback)

        lines = [
            'PlanX Suitability Lab - Harmonizer Manifest',
            f'Input count: {len(rasters)}',
            f'Target resolution: {res}',
            f'Target extent: {extent.toString()}',
        ]
        for i, rl in enumerate(rasters, start=1):
            lines.append(f'[{i}] {rl.name()} | {rl.source()}')
        with open(manifest, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return {self.OUTPUT_RASTER: out, self.OUTPUT_MANIFEST: manifest}
