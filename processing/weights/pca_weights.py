# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import Qgis, QgsProcessingException, QgsFeature, QgsFields, QgsField, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterMultipleLayers, QgsProcessingParameterFeatureSink, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QMetaType

from .._mcda_utils import ensure_list, pca_proxy_weights_from_rasters


class PCAWeightsAlgorithm(QgsProcessingAlgorithm):
    INPUT_RASTERS = 'INPUT_RASTERS'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'pca_derived_weights'

    def displayName(self):
        return 'Weights: PCA-derived Weights (variance proxy)'

    def group(self):
        return 'Weights'

    def groupId(self):
        return 'weights'

    def shortHelpString(self):
        return (
            "<p><b>Derive objective criterion weights from the first principal component loading, "
            "weighted by its explained variance ratio.</b></p>"
            "<p><b>Inputs:</b> Criterion rasters - all rasters must share the same extent and cell size. "
            "Values are sampled from a regular grid of up to ~8000 cells across the stack.<br>"
            "<b>Output:</b> A table with criterion_id and weight (0-1, summing to 1). "
            "Weights reflect each criterion's contribution to the dominant axis of spatial variance.<br>"
            "<b>Method:</b> Standardises each raster layer (z-score), then computes the covariance matrix "
            "from the spatially sampled cells. Eigendecomposition of the covariance matrix yields principal components; "
            "the absolute loadings of PC1 are taken and scaled by PC1's explained variance ratio. "
            "This variance-proxy approach assigns higher weight to criteria driving the largest differences across the study area. "
            "If fewer than 3 valid sample cells exist, equal weights are returned.<br>"
            "<b>Typical use:</b> Data-driven weighting when pairwise judgments are unavailable and the analyst "
            "wants criteria with high spatial variability to dominate the suitability model.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return PCAWeightsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(self.INPUT_RASTERS, 'Criterion rasters', QgsProcessing.SourceType.TypeRaster))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, 'PCA weights table', QgsProcessing.SourceType.TypeVector))

    def processAlgorithm(self, parameters, context, feedback):
        layers = ensure_list(self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context))
        weights = pca_proxy_weights_from_rasters([lyr.source() for lyr in layers])
        fields = QgsFields()
        fields.append(QgsField('criterion_id', QMetaType.Type.Int))
        fields.append(QgsField('weight', QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        for i, wi in enumerate(weights, start=1):
            f = QgsFeature(fields)
            f['criterion_id'] = i
            f['weight'] = float(wi)
            sink.addFeature(f)
        return {self.OUTPUT: dest}
