# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsCoordinateReferenceSystem,
)


from contextlib import suppress


class ScenarioSelectionRecommenderAlgorithm(QgsProcessingAlgorithm):
    BENCHMARK = "BENCHMARK"
    PORTFOLIO = "PORTFOLIO"
    MINIMAX = "MINIMAX"
    GATE = "GATE"
    SCORECARD = "SCORECARD"
    ROBUSTNESS = "ROBUSTNESS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_selection_recommender"

    def displayName(self):
        return "Reporting: Scenario Selection Recommender"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Recommends primary and challenger scenarios from an adjusted composite of benchmark, "
            "diversity, minimax, and robustness evidence.</b></p>"
            "<p><b>Inputs:</b> Method benchmark leaderboard, Scenario portfolio diversity, Minimax regret selector, "
            "Policy gate recommender, Actionability scorecard, Optional scenario robustness leaderboard.<br>"
            "<b>Output:</b> Feature sink with one row: primary_scn, challenger_scn, minimax_scn, "
            "primary_adj (adjusted score), challenger_adj, primary minimax rank/regret, primary/challenger robustness, "
            "strategy label, policy_mode, rec_threshold, rec_lambda, action_grade, readiness, overall, "
            "diversity_idx, portfolio_health, note.<br>"
            "<b>Method:</b> Computes adjusted score = 0.45*composite + 0.11*uniqueness + 0.07*(100-std) "
            "+ 0.16*minimax_bonus + 0.14*robustness + 0.07*robust_rank_bonus. "
            "Selects top two as primary and challenger. Strategy adapts to regret exposure, diversity, "
            "robustness, and policy strictness.<br>"
            "<b>Typical use:</b> Final scenario recommendation for planning committee decision packages.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ScenarioSelectionRecommenderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.BENCHMARK, "Method benchmark leaderboard table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.PORTFOLIO, "Scenario portfolio diversity table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.MINIMAX, "Minimax regret selector table", [QgsProcessing.TypeVector])
        )
        self.addParameter(QgsProcessingParameterFeatureSource(self.GATE, "Policy gate recommender table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.SCORECARD, "Actionability scorecard table", [QgsProcessing.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.ROBUSTNESS,
                "Optional scenario robustness leaderboard table",
                [QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario selection recommendation", QgsProcessing.TypeVector))

    @staticmethod
    def _rows(src):
        return [f for f in src.getFeatures(QgsFeatureRequest())]

    @staticmethod
    def _first(src):
        for f in src.getFeatures(QgsFeatureRequest()):
            return f
        return None

    def processAlgorithm(self, parameters, context, feedback):
        benchmark_src = self.parameterAsSource(parameters, self.BENCHMARK, context)
        portfolio_src = self.parameterAsSource(parameters, self.PORTFOLIO, context)
        minimax_src = self.parameterAsSource(parameters, self.MINIMAX, context)
        gate_src = self.parameterAsSource(parameters, self.GATE, context)
        score_src = self.parameterAsSource(parameters, self.SCORECARD, context)
        robustness_src = self.parameterAsSource(parameters, self.ROBUSTNESS, context)
        if benchmark_src is None or portfolio_src is None or minimax_src is None or gate_src is None or score_src is None:
            raise QgsProcessingException("Could not read one or more input tables.")

        benchmark_rows = self._rows(benchmark_src)
        if not benchmark_rows:
            raise QgsProcessingException("Method benchmark leaderboard is empty.")

        portfolio_rows = self._rows(portfolio_src)
        if not portfolio_rows:
            raise QgsProcessingException("Scenario portfolio diversity table is empty.")
        minimax_rows = self._rows(minimax_src)
        if not minimax_rows:
            raise QgsProcessingException("Minimax regret selector table is empty.")

        gate = self._first(gate_src)
        score = self._first(score_src)
        if gate is None:
            raise QgsProcessingException("Policy gate table is empty.")
        if score is None:
            raise QgsProcessingException("Actionability scorecard table is empty.")

        portfolio_summary = None
        uniq_by_scenario = {}
        for f in portfolio_rows:
            row_type = ""
            with suppress(Exception):
                row_type = str(f["row_type"])
            if row_type == "SUMMARY":
                portfolio_summary = f
            elif row_type == "SCENARIO":
                with suppress(Exception):
                    uniq_by_scenario[str(f["scenario"])] = float(f["uniq_score"])

        if portfolio_summary is None:
            raise QgsProcessingException("Portfolio diversity table is missing SUMMARY row.")

        minimax_rank = {}
        minimax_max = {}
        minimax_selected = None
        for f in minimax_rows:
            with suppress(Exception):
                scn = str(f["scenario"])
                minimax_rank[scn] = int(f["rank"])
                minimax_max[scn] = float(f["max_regret"])
                if str(f["selected"]).upper() == "YES":
                    minimax_selected = scn
        if not minimax_rank:
            raise QgsProcessingException("Minimax table missing scenario/rank/max_regret fields.")

        robust_score = {}
        robust_rank = {}
        if robustness_src is not None:
            for f in robustness_src.getFeatures(QgsFeatureRequest()):
                with suppress(Exception):
                    scenario = str(f["scenario"])
                    robust_score[scenario] = float(f["robustness"])
                    robust_rank[scenario] = int(f["rank"])

        ranked = []
        for f in benchmark_rows:
            with suppress(Exception):
                scenario = str(f["scenario"])
                composite = float(f["composite"])
                std_score = float(f["std_score"])
                uniq = float(uniq_by_scenario.get(scenario, 0.0))
                mm_rank = float(minimax_rank.get(scenario, max(2, len(minimax_rank))))
                mm_bonus = max(0.0, 100.0 - 8.0 * (mm_rank - 1.0))
                mm_reg = float(minimax_max.get(scenario, 100.0))
                robust_bonus = float(robust_score.get(scenario, 50.0))
                robust_rank_bonus = max(0.0, 100.0 - 7.0 * float(max(1, robust_rank.get(scenario, 8)) - 1))
                adjusted = (0.45 * composite) + (0.11 * uniq) + (0.07 * max(0.0, 100.0 - std_score)) + (0.16 * mm_bonus) + (0.14 * robust_bonus) + (0.07 * robust_rank_bonus)
                ranked.append((scenario, composite, std_score, uniq, mm_rank, mm_reg, robust_bonus, robust_rank_bonus, adjusted))

        if not ranked:
            raise QgsProcessingException("Benchmark table does not include required fields: scenario/composite/std_score.")
        ranked.sort(key=lambda x: (-x[8], x[4], x[5], -x[6], -x[1], x[2], -x[3], x[0]))

        primary = ranked[0]
        challenger = ranked[1] if len(ranked) > 1 else ranked[0]

        try:
            policy_mode = str(gate["policy_mode"])
            rec_threshold = float(gate["rec_threshold"])
            rec_lambda = float(gate["rec_lambda"])
        except Exception as exc:
            raise QgsProcessingException(f"Policy gate table missing expected fields: {exc}")

        try:
            readiness = str(score["readiness"])
            action_grade = str(score["grade"])
            overall = float(score["overall"])
        except Exception as exc:
            raise QgsProcessingException(f"Actionability scorecard missing expected fields: {exc}")

        diversity_idx = float(portfolio_summary["diversity_idx"]) if "diversity_idx" in portfolio_summary.fields().names() else 0.0
        portfolio_health = float(portfolio_summary["health_score"]) if "health_score" in portfolio_summary.fields().names() else 0.0

        if minimax_selected and minimax_selected != primary[0]:
            strategy = "REGRET_SAFE_DUAL_TRACK"
            note = (
                "Benchmark and minimax winners differ. Use benchmark winner as primary and minimax winner as safeguard track."
            )
        elif diversity_idx < 22.0:
            strategy = "PRIMARY_PLUS_STRESS_TEST"
            note = "Portfolio diversity is low; keep primary scenario but run sensitivity stress tests before publication."
        elif primary[6] < 62.0:
            strategy = "ROBUSTNESS_HARDENING"
            note = "Primary scenario has moderate robustness; run VIKOR and frontier checks before final release."
        elif policy_mode.upper() == "STRICT":
            strategy = "CONSERVATIVE_DUAL_TRACK"
            note = "Strict policy mode favors robust primary deployment with challenger retained as controlled alternative."
        else:
            strategy = "BALANCED_DUAL_TRACK"
            note = "Diversity and policy allow a primary-challenger two-track decision package."

        fields = QgsFields()
        fields.append(QgsField("primary_scn", QVariant.String))
        fields.append(QgsField("challenger_scn", QVariant.String))
        fields.append(QgsField("minimax_scn", QVariant.String))
        fields.append(QgsField("primary_adj", QVariant.Double))
        fields.append(QgsField("chall_adj", QVariant.Double))
        fields.append(QgsField("primary_mm_rk", QVariant.Double))
        fields.append(QgsField("primary_mm_rg", QVariant.Double))
        fields.append(QgsField("primary_rb", QVariant.Double))
        fields.append(QgsField("chall_rb", QVariant.Double))
        fields.append(QgsField("strategy", QVariant.String))
        fields.append(QgsField("policy_mode", QVariant.String))
        fields.append(QgsField("rec_threshold", QVariant.Double))
        fields.append(QgsField("rec_lambda", QVariant.Double))
        fields.append(QgsField("action_grade", QVariant.String))
        fields.append(QgsField("readiness", QVariant.String))
        fields.append(QgsField("overall", QVariant.Double))
        fields.append(QgsField("diversity_idx", QVariant.Double))
        fields.append(QgsField("portfolio_hlth", QVariant.Double))
        fields.append(QgsField("note", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        out = QgsFeature(fields)
        out["primary_scn"] = primary[0]
        out["challenger_scn"] = challenger[0]
        out["minimax_scn"] = str(minimax_selected) if minimax_selected else primary[0]
        out["primary_adj"] = float(primary[8])
        out["chall_adj"] = float(challenger[8])
        out["primary_mm_rk"] = float(primary[4])
        out["primary_mm_rg"] = float(primary[5])
        out["primary_rb"] = float(primary[6])
        out["chall_rb"] = float(challenger[6])
        out["strategy"] = strategy
        out["policy_mode"] = policy_mode
        out["rec_threshold"] = rec_threshold
        out["rec_lambda"] = rec_lambda
        out["action_grade"] = action_grade
        out["readiness"] = readiness
        out["overall"] = overall
        out["diversity_idx"] = diversity_idx
        out["portfolio_hlth"] = portfolio_health
        out["note"] = note
        sink.addFeature(out)

        feedback.pushInfo(
            f"Scenario recommendation: primary={primary[0]} minimax={minimax_selected or primary[0]} challenger={challenger[0]} strategy={strategy} readiness={readiness} robust={primary[6]:.1f}"
        )
        return {self.OUTPUT: dest}
