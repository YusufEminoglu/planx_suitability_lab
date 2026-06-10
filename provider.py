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
from .processing.weights.critic_weights import CriticWeightsAlgorithm
from .processing.weights.weight_consolidator import WeightConsolidatorAlgorithm
from .processing.weights.scenario_weight_pack import ScenarioWeightPackAlgorithm
from .processing.weights.weight_consensus_audit import WeightConsensusAuditAlgorithm
from .processing.compose.wlc_suitability import WLCSuitabilityAlgorithm
from .processing.compose.owa_suitability import OWASuitabilityAlgorithm
from .processing.compose.topsis_suitability import TOPSISSuitabilityAlgorithm
from .processing.compose.vikor_suitability import VIKORSuitabilityAlgorithm
from .processing.compose.ensemble_suitability import EnsembleSuitabilityAlgorithm
from .processing.compose.opportunity_loss_map import OpportunityLossMapAlgorithm
from .processing.compose.candidate_site_extractor import CandidateSiteExtractorAlgorithm
from .processing.compose.priority_zoning_from_suitability import PriorityZoningFromSuitabilityAlgorithm
from .processing.compose.scenario_consensus_zone import ScenarioConsensusZoneAlgorithm
from .processing.compose.scenario_disagreement_attention import ScenarioDisagreementAttentionAlgorithm
from .processing.compose.decision_quadrant_map import DecisionQuadrantMapAlgorithm
from .processing.compose.intervention_conflict_matrix import InterventionConflictMatrixAlgorithm
from .processing.compose.risk_opportunity_matrix_map import RiskOpportunityMatrixMapAlgorithm
from .processing.compose.regret_fragility_map import RegretFragilityMapAlgorithm
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
from .processing.reporting.scenario_similarity_matrix import ScenarioSimilarityMatrixAlgorithm
from .processing.reporting.scenario_dominance_matrix import ScenarioDominanceMatrixAlgorithm
from .processing.reporting.scenario_robustness_leaderboard import ScenarioRobustnessLeaderboardAlgorithm
from .processing.reporting.scenario_governance_audit import ScenarioGovernanceAuditAlgorithm
from .processing.reporting.method_benchmark_leaderboard import MethodBenchmarkLeaderboardAlgorithm
from .processing.reporting.scenario_portfolio_diversity import ScenarioPortfolioDiversityAlgorithm
from .processing.reporting.minimax_regret_selector import MinimaxRegretSelectorAlgorithm
from .processing.reporting.policy_sensitivity_frontier import PolicySensitivityFrontierAlgorithm
from .processing.reporting.action_playbook_generator import ActionPlaybookGeneratorAlgorithm
from .processing.reporting.intervention_budget_phasing import InterventionBudgetPhasingAlgorithm
from .processing.reporting.release_narrative_builder import ReleaseNarrativeBuilderAlgorithm
from .processing.reporting.criterion_redundancy_diagnostics import CriterionRedundancyDiagnosticsAlgorithm
from .processing.reporting.constraint_impact_audit import ConstraintImpactAuditAlgorithm
from .processing.reporting.alignment_audit import AlignmentAuditAlgorithm
from .processing.reporting.priority_transition_matrix import PriorityTransitionMatrixAlgorithm
from .processing.reporting.spatial_fragmentation_audit import SpatialFragmentationAuditAlgorithm
from .processing.reporting.consensus_zone_area_stats import ConsensusZoneAreaStatsAlgorithm
from .processing.reporting.threshold_coverage_curve import ThresholdCoverageCurveAlgorithm
from .processing.reporting.attention_class_area_stats import AttentionClassAreaStatsAlgorithm
from .processing.reporting.executive_kpi_snapshot import ExecutiveKpiSnapshotAlgorithm
from .processing.reporting.policy_gate_recommender import PolicyGateRecommenderAlgorithm
from .processing.reporting.decision_quadrant_area_stats import DecisionQuadrantAreaStatsAlgorithm
from .processing.reporting.intervention_conflict_area_stats import InterventionConflictAreaStatsAlgorithm
from .processing.reporting.risk_opportunity_area_stats import RiskOpportunityAreaStatsAlgorithm
from .processing.reporting.regret_fragility_area_stats import RegretFragilityAreaStatsAlgorithm
from .processing.reporting.scenario_selection_recommender import ScenarioSelectionRecommenderAlgorithm
from .processing.reporting.implementation_wave_planner import ImplementationWavePlannerAlgorithm
from .processing.reporting.deployment_readiness_gate import DeploymentReadinessGateAlgorithm
from .processing.reporting.actionability_scorecard import ActionabilityScorecardAlgorithm


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
        base = os.path.join(os.path.dirname(__file__), 'icons')
        for name in ('icon.png', 'icon.svg'):
            path = os.path.join(base, name)
            if os.path.exists(path):
                return QIcon(path)
        return super().icon()

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
        self.addAlgorithm(CriticWeightsAlgorithm())
        self.addAlgorithm(WeightConsolidatorAlgorithm())
        self.addAlgorithm(ScenarioWeightPackAlgorithm())
        self.addAlgorithm(WeightConsensusAuditAlgorithm())
        self.addAlgorithm(WLCSuitabilityAlgorithm())
        self.addAlgorithm(OWASuitabilityAlgorithm())
        self.addAlgorithm(TOPSISSuitabilityAlgorithm())
        self.addAlgorithm(VIKORSuitabilityAlgorithm())
        self.addAlgorithm(EnsembleSuitabilityAlgorithm())
        self.addAlgorithm(OpportunityLossMapAlgorithm())
        self.addAlgorithm(PriorityZoningFromSuitabilityAlgorithm())
        self.addAlgorithm(CandidateSiteExtractorAlgorithm())
        self.addAlgorithm(ScenarioConsensusZoneAlgorithm())
        self.addAlgorithm(ScenarioDisagreementAttentionAlgorithm())
        self.addAlgorithm(DecisionQuadrantMapAlgorithm())
        self.addAlgorithm(InterventionConflictMatrixAlgorithm())
        self.addAlgorithm(RiskOpportunityMatrixMapAlgorithm())
        self.addAlgorithm(RegretFragilityMapAlgorithm())
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
        self.addAlgorithm(ScenarioSimilarityMatrixAlgorithm())
        self.addAlgorithm(ScenarioDominanceMatrixAlgorithm())
        self.addAlgorithm(ScenarioRobustnessLeaderboardAlgorithm())
        self.addAlgorithm(ScenarioGovernanceAuditAlgorithm())
        self.addAlgorithm(MethodBenchmarkLeaderboardAlgorithm())
        self.addAlgorithm(ScenarioPortfolioDiversityAlgorithm())
        self.addAlgorithm(MinimaxRegretSelectorAlgorithm())
        self.addAlgorithm(PolicySensitivityFrontierAlgorithm())
        self.addAlgorithm(ActionPlaybookGeneratorAlgorithm())
        self.addAlgorithm(InterventionBudgetPhasingAlgorithm())
        self.addAlgorithm(ReleaseNarrativeBuilderAlgorithm())
        self.addAlgorithm(CriterionRedundancyDiagnosticsAlgorithm())
        self.addAlgorithm(ConstraintImpactAuditAlgorithm())
        self.addAlgorithm(AlignmentAuditAlgorithm())
        self.addAlgorithm(PriorityTransitionMatrixAlgorithm())
        self.addAlgorithm(SpatialFragmentationAuditAlgorithm())
        self.addAlgorithm(ConsensusZoneAreaStatsAlgorithm())
        self.addAlgorithm(ThresholdCoverageCurveAlgorithm())
        self.addAlgorithm(AttentionClassAreaStatsAlgorithm())
        self.addAlgorithm(ExecutiveKpiSnapshotAlgorithm())
        self.addAlgorithm(PolicyGateRecommenderAlgorithm())
        self.addAlgorithm(DecisionQuadrantAreaStatsAlgorithm())
        self.addAlgorithm(InterventionConflictAreaStatsAlgorithm())
        self.addAlgorithm(RiskOpportunityAreaStatsAlgorithm())
        self.addAlgorithm(RegretFragilityAreaStatsAlgorithm())
        self.addAlgorithm(ScenarioSelectionRecommenderAlgorithm())
        self.addAlgorithm(ImplementationWavePlannerAlgorithm())
        self.addAlgorithm(DeploymentReadinessGateAlgorithm())
        self.addAlgorithm(ActionabilityScorecardAlgorithm())
