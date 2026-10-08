# -*- coding: utf-8 -*-
from __future__ import annotations

import processing
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)
from .._mcda_utils import smart_output_path


class RasterizerAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELD = 'FIELD'
    BURN = 'BURN'
    PIXEL = 'PIXEL'
    REFERENCE = 'REFERENCE'
    BACKGROUND = 'BACKGROUND'
    BG_NODATA = 'BG_NODATA'
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
            "burn value (default 1.0); pixel size in map units (>=0.01, default 10.0); "
            "optional <i>reference raster</i> (its extent, cell size and CRS replace the vector extent and the "
            "pixel size, so the result lies exactly on your analysis grid); "
            "background value (default 0.0: the value of cells no feature touches); "
            "<i>treat background as NoData</i> (default on).<br>"
            "<b>Output:</b> Single-band Float32 GeoTIFF. Default: covers the input layer extent at the specified "
            "pixel size, and cells not intersected by any feature are NoData (background 0).<br>"
            "<b>Method:</b> Wraps GDAL Rasterize (gdal:rasterize) with pixel-sized units. "
            "When a value field is selected, each cell receives the attribute value of the feature covering "
            "its center. Otherwise, all cells intersecting any feature receive the burn value. "
            "With a reference raster the vector is first reprojected to the reference CRS when they differ.<br>"
            "<b>Constraint mask recipe:</b> to turn exclusion polygons (protected areas, floodplains, ...) into a "
            "0/1 mask for the compose tools, set the reference raster to your analysis grid, "
            "<b>burn value = 0, background value = 1</b> and switch <b>treat background as NoData off</b>. "
            "The output is 0 inside the polygons and 1 everywhere else on the grid; feed it to the "
            "<i>Constraint mask</i> input of WLC and the other compose tools. (Constraint Builder is the tool for "
            "thresholding a criterion <i>raster</i>; it cannot invert a polygon layer.)<br>"
            "<b>Note:</b> with NoData background on, a burn value equal to the background value would erase the "
            "features.<br>"
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
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.REFERENCE,
                'Reference raster (optional: take extent, cell size and CRS from it)',
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BACKGROUND,
                'Background value (cells no feature touches)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.BG_NODATA,
                'Treat background as NoData',
                defaultValue=True,
            )
        )
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
        ref = self.parameterAsRasterLayer(parameters, self.REFERENCE, context)
        background = self.parameterAsDouble(parameters, self.BACKGROUND, context)
        bg_nodata = self.parameterAsBool(parameters, self.BG_NODATA, context)
        out = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        out = smart_output_path(out, vlayer, "vector_rasterizer")

        source = vlayer
        width = height = pix
        extent = vlayer.extent()
        if ref is not None:
            # Lie exactly on the reference grid: its extent and its cell size.
            if vlayer.crs().isValid() and ref.crs().isValid() and vlayer.crs() != ref.crs():
                feedback.pushInfo(
                    f"Reprojecting the vector from {vlayer.crs().authid()} to {ref.crs().authid()} (reference raster CRS)."
                )
                source = processing.run('native:reprojectlayer', {
                    'INPUT': vlayer,
                    'TARGET_CRS': ref.crs(),
                    'OUTPUT': 'TEMPORARY_OUTPUT',
                }, context=context, feedback=feedback)['OUTPUT']
            rect = ref.extent()
            extent = f"{rect.xMinimum()},{rect.xMaximum()},{rect.yMinimum()},{rect.yMaximum()} [{ref.crs().authid()}]"
            width = abs(ref.rasterUnitsPerPixelX())
            height = abs(ref.rasterUnitsPerPixelY())
            if width <= 0 or height <= 0:
                raise QgsProcessingException("The reference raster has no valid cell size.")

        # Default (background 0, NoData on) keeps the historical behaviour exactly:
        # INIT 0 / NODATA 0. With NoData off the background is a real value and the
        # output carries a nodata (-9999) that no cell uses.
        process_nodata = background if bg_nodata else -9999.0
        processing.run('gdal:rasterize', {
            'INPUT': source,
            'FIELD': field if field else None,
            'BURN': burn,
            'USE_Z': False,
            'UNITS': 1,
            'WIDTH': width,
            'HEIGHT': height,
            'EXTENT': extent,
            'NODATA': process_nodata,
            'OPTIONS': '',
            'DATA_TYPE': 5,
            'INIT': background,
            'INVERT': False,
            'EXTRA': '',
            'OUTPUT': out,
        }, context=context, feedback=feedback)
        return {self.OUTPUT: out}
