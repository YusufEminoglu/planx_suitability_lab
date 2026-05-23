# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing.core.harmonizer import DataHarmonizerAlgorithm
from .processing.core.rasterizer import RasterizerAlgorithm
from .processing.core.proximity_builder import ProximityBuilderAlgorithm
from .processing.core.normalizer import NormalizerAlgorithm
from .processing.core.constraint_builder import ConstraintBuilderAlgorithm
from .processing.core.synthetic_sample_raster import SyntheticSampleRasterAlgorithm
from .processing.core.synthetic_pipeline_runner import SyntheticPipelineRunnerAlgorithm
from .processing.weights.ahp_weights import AHPWeightsAlgorithm
from .processing.weights.pca_weights import PCAWeightsAlgorithm
from .processing.weights.entropy_weights import EntropyWeightsAlgorithm
from .processing.weights.weight_consolidator import WeightConsolidatorAlgorithm
from .processing.weights.scenario_weight_pack import ScenarioWeightPackAlgorithm
from .processing.compose.wlc_suitability import WLCSuitabilityAlgorithm
from .processing.compose.owa_suitability import OWASuitabilityAlgorithm
from .processing.compose.topsis_suitability import TOPSISSuitabilityAlgorithm
from .processing.compose.uncertainty_adjusted_suitability import UncertaintyAdjustedSuitabilityAlgorithm
from .processing.compose.scenario_comparator import ScenarioComparatorAlgorithm
from .processing.uncertainty.montecarlo_suitability import MonteCarloSuitabilityAlgorithm
from .processing.xai.global_sensitivity import GlobalSensitivityAlgorithm
from .processing.xai.local_contribution import LocalContributionAlgorithm
from .processing.xai.geoshapley_lite import GeoShapleyLiteAlgorithm
from .processing.reporting.suitability_html_report import SuitabilityHtmlReportAlgorithm
from .processing.reporting.numerical_qa_check import NumericalQACheckAlgorithm
from .processing.reporting.beta_evidence_report import BetaEvidenceReportAlgorithm
from .processing.reporting.scenario_markdown_brief import ScenarioMarkdownBriefAlgorithm
from .processing.reporting.suitability_class_area_stats import SuitabilityClassAreaStatsAlgorithm


class PlanXSuitabilityLabProvider(QgsProcessingProvider):
    PROVIDER_ID = 'planx_suitability_lab'
    PROVIDER_NAME = 'PlanX Suitability Lab'

    def id(self):
        return self.PROVIDER_ID

    def name(self):
        return self.PROVIDER_NAME

    def longName(self):
        return self.PROVIDER_NAME

    def icon(self):
        path = os.path.join(os.path.dirname(__file__), 'icons', 'icon.png')
        return QIcon(path) if os.path.exists(path) else super().icon()

    def loadAlgorithms(self):
        self.addAlgorithm(DataHarmonizerAlgorithm())
        self.addAlgorithm(RasterizerAlgorithm())
        self.addAlgorithm(ProximityBuilderAlgorithm())
        self.addAlgorithm(NormalizerAlgorithm())
        self.addAlgorithm(ConstraintBuilderAlgorithm())
        self.addAlgorithm(SyntheticSampleRasterAlgorithm())
        self.addAlgorithm(SyntheticPipelineRunnerAlgorithm())
        self.addAlgorithm(AHPWeightsAlgorithm())
        self.addAlgorithm(PCAWeightsAlgorithm())
        self.addAlgorithm(EntropyWeightsAlgorithm())
        self.addAlgorithm(WeightConsolidatorAlgorithm())
        self.addAlgorithm(ScenarioWeightPackAlgorithm())
        self.addAlgorithm(WLCSuitabilityAlgorithm())
        self.addAlgorithm(OWASuitabilityAlgorithm())
        self.addAlgorithm(TOPSISSuitabilityAlgorithm())
        self.addAlgorithm(UncertaintyAdjustedSuitabilityAlgorithm())
        self.addAlgorithm(ScenarioComparatorAlgorithm())
        self.addAlgorithm(MonteCarloSuitabilityAlgorithm())
        self.addAlgorithm(GlobalSensitivityAlgorithm())
        self.addAlgorithm(LocalContributionAlgorithm())
        self.addAlgorithm(GeoShapleyLiteAlgorithm())
        self.addAlgorithm(SuitabilityHtmlReportAlgorithm())
        self.addAlgorithm(NumericalQACheckAlgorithm())
        self.addAlgorithm(BetaEvidenceReportAlgorithm())
        self.addAlgorithm(ScenarioMarkdownBriefAlgorithm())
        self.addAlgorithm(SuitabilityClassAreaStatsAlgorithm())
