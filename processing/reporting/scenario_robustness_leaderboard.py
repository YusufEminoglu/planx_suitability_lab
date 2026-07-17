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


class ScenarioRobustnessLeaderboardAlgorithm(QgsProcessingAlgorithm):
    BENCHMARK = "BENCHMARK"
    DOMINANCE = "DOMINANCE"
    MINIMAX = "MINIMAX"
    PORTFOLIO = "PORTFOLIO"
    OUTPUT = "OUTPUT"

    def name(self):
        return "scenario_robustness_leaderboard"

    def displayName(self):
        return "Reporting: Scenario Robustness Leaderboard"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Fuses benchmark, dominance, minimax-regret, and diversity scores into a single robustness ranking.</b></p>"
            "<p><b>Inputs:</b> Method benchmark leaderboard table, Scenario dominance matrix table, "
            "Minimax regret selector table, Scenario portfolio diversity table.<br>"
            "<b>Output:</b> Feature sink with scenario, rank, tier (HIGH >=80, STRONG >=67, WATCH >=54, WEAK), "
            "robustness score, composite, stability, net_dom, max_regret, minimax_rk, uniq_score, "
            "and per-dimension normalized scores.<br>"
            "<b>Method:</b> Reads all four input tables and intersects scenarios by name. "
            "Normalizes each dimension to [0,100] via min-max (regret inverted so lower is better). "
            "Robustness = 0.34*composite + 0.24*dominance + 0.26*regret_avoidance + 0.16*diversity. "
            "Ranks by descending robustness, breaking ties on regret, composite, dominance, uniqueness.<br>"
            "<b>Typical use:</b> Final scenario comparison for decision-makers: "
            "which scenario is most robust across all criteria?</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return ScenarioRobustnessLeaderboardAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.BENCHMARK, "Method benchmark leaderboard table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.DOMINANCE, "Scenario dominance matrix table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.MINIMAX, "Minimax regret selector table", [QgsProcessing.TypeVector])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.PORTFOLIO, "Scenario portfolio diversity table", [QgsProcessing.TypeVector])
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Scenario robustness leaderboard", QgsProcessing.TypeVector))

    @staticmethod
    def _read_rows(src):
        return [f for f in src.getFeatures(QgsFeatureRequest())]

    @staticmethod
    def _norm_minmax(value, vmin, vmax, fallback=50.0):
        if vmax - vmin < 1e-9:
            return float(fallback)
        return float(100.0 * (value - vmin) / (vmax - vmin))

    def processAlgorithm(self, parameters, context, feedback):
        benchmark_src = self.parameterAsSource(parameters, self.BENCHMARK, context)
        dominance_src = self.parameterAsSource(parameters, self.DOMINANCE, context)
        minimax_src = self.parameterAsSource(parameters, self.MINIMAX, context)
        portfolio_src = self.parameterAsSource(parameters, self.PORTFOLIO, context)
        if benchmark_src is None or dominance_src is None or minimax_src is None or portfolio_src is None:
            raise QgsProcessingException("Could not read one or more input tables.")

        benchmark_rows = self._read_rows(benchmark_src)
        dominance_rows = self._read_rows(dominance_src)
        minimax_rows = self._read_rows(minimax_src)
        portfolio_rows = self._read_rows(portfolio_src)
        if not benchmark_rows or not dominance_rows or not minimax_rows:
            raise QgsProcessingException("Benchmark, dominance, and minimax tables must be non-empty.")

        composite = {}
        stability = {}
        for f in benchmark_rows:
            with suppress(Exception):
                scenario = str(f["scenario"])
                composite[scenario] = float(f["composite"])
                stability[scenario] = float(f["stability"])
        if not composite:
            raise QgsProcessingException("Benchmark table missing required scenario/composite fields.")

        net_dom = {}
        for f in dominance_rows:
            with suppress(Exception):
                if str(f["row_type"]) != "SCENARIO":
                    continue
                scenario = str(f["scenario_a"])
                net_dom[scenario] = float(f["net_dom"])
        if not net_dom:
            raise QgsProcessingException("Dominance table missing SCENARIO rows (scenario_a/net_dom).")

        minimax_regret = {}
        minimax_rank = {}
        for f in minimax_rows:
            with suppress(Exception):
                scenario = str(f["scenario"])
                minimax_regret[scenario] = float(f["max_regret"])
                minimax_rank[scenario] = int(f["rank"])
        if not minimax_regret:
            raise QgsProcessingException("Minimax table missing scenario/max_regret fields.")

        uniq_score = {}
        for f in portfolio_rows:
            with suppress(Exception):
                if str(f["row_type"]) != "SCENARIO":
                    continue
                uniq_score[str(f["scenario"])] = float(f["uniq_score"])

        scenarios = sorted(set(composite.keys()) & set(minimax_regret.keys()))
        if not scenarios:
            raise QgsProcessingException("No common scenarios between benchmark and minimax tables.")

        c_vals = [composite[s] for s in scenarios]
        d_vals = [net_dom.get(s, 0.0) for s in scenarios]
        r_vals = [minimax_regret[s] for s in scenarios]
        u_vals = [uniq_score.get(s, 0.0) for s in scenarios]

        c_min, c_max = min(c_vals), max(c_vals)
        d_min, d_max = min(d_vals), max(d_vals)
        r_min, r_max = min(r_vals), max(r_vals)
        u_min, u_max = min(u_vals), max(u_vals)

        rows = []
        for s in scenarios:
            c_norm = self._norm_minmax(composite[s], c_min, c_max)
            d_norm = self._norm_minmax(net_dom.get(s, 0.0), d_min, d_max)
            # Lower regret is better -> invert min-max.
            r_norm = 100.0 - self._norm_minmax(minimax_regret[s], r_min, r_max)
            u_norm = self._norm_minmax(uniq_score.get(s, 0.0), u_min, u_max)
            robust = (0.34 * c_norm) + (0.24 * d_norm) + (0.26 * r_norm) + (0.16 * u_norm)
            if robust >= 80.0:
                tier = "HIGH"
            elif robust >= 67.0:
                tier = "STRONG"
            elif robust >= 54.0:
                tier = "WATCH"
            else:
                tier = "WEAK"
            rows.append(
                {
                    "scenario": s,
                    "composite": composite[s],
                    "stability": stability.get(s, 0.0),
                    "net_dom": net_dom.get(s, 0.0),
                    "max_regret": minimax_regret[s],
                    "minimax_rank": minimax_rank.get(s, 0),
                    "uniq_score": uniq_score.get(s, 0.0),
                    "c_norm": c_norm,
                    "d_norm": d_norm,
                    "r_norm": r_norm,
                    "u_norm": u_norm,
                    "robustness": robust,
                    "tier": tier,
                }
            )

        rows.sort(
            key=lambda r: (
                -r["robustness"],
                r["max_regret"],
                -r["composite"],
                -r["net_dom"],
                -r["uniq_score"],
                r["scenario"],
            )
        )
        for i, row in enumerate(rows, start=1):
            row["rank"] = i

        fields = QgsFields()
        fields.append(QgsField("scenario", QVariant.String))
        fields.append(QgsField("rank", QVariant.Int))
        fields.append(QgsField("tier", QVariant.String))
        fields.append(QgsField("robustness", QVariant.Double))
        fields.append(QgsField("composite", QVariant.Double))
        fields.append(QgsField("stability", QVariant.Double))
        fields.append(QgsField("net_dom", QVariant.Double))
        fields.append(QgsField("max_regret", QVariant.Double))
        fields.append(QgsField("minimax_rk", QVariant.Int))
        fields.append(QgsField("uniq_score", QVariant.Double))
        fields.append(QgsField("score_comp", QVariant.Double))
        fields.append(QgsField("score_dom", QVariant.Double))
        fields.append(QgsField("score_reg", QVariant.Double))
        fields.append(QgsField("score_div", QVariant.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        for row in rows:
            feat = QgsFeature(fields)
            feat["scenario"] = row["scenario"]
            feat["rank"] = int(row["rank"])
            feat["tier"] = row["tier"]
            feat["robustness"] = float(row["robustness"])
            feat["composite"] = float(row["composite"])
            feat["stability"] = float(row["stability"])
            feat["net_dom"] = float(row["net_dom"])
            feat["max_regret"] = float(row["max_regret"])
            feat["minimax_rk"] = int(row["minimax_rank"])
            feat["uniq_score"] = float(row["uniq_score"])
            feat["score_comp"] = float(row["c_norm"])
            feat["score_dom"] = float(row["d_norm"])
            feat["score_reg"] = float(row["r_norm"])
            feat["score_div"] = float(row["u_norm"])
            sink.addFeature(feat)

        if rows:
            top = rows[0]
            feedback.pushInfo(
                f"Robustness leader: {top['scenario']} (score={top['robustness']:.2f}, tier={top['tier']}, regret={top['max_regret']:.2f})"
            )
        return {self.OUTPUT: dest}

