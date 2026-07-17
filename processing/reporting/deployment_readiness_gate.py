# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.PyQt.QtCore import QMetaType
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


class DeploymentReadinessGateAlgorithm(QgsProcessingAlgorithm):
    SCORECARD = "SCORECARD"
    SCENARIO_SELECTION = "SCENARIO_SELECTION"
    MINIMAX = "MINIMAX"
    WAVE_PLAN = "WAVE_PLAN"
    REGRET_STATS = "REGRET_STATS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "deployment_readiness_gate"

    def displayName(self):
        return "Reporting: Deployment Readiness Gate"

    def group(self):
        return "Reporting"

    def groupId(self):
        return "reporting"

    def shortHelpString(self):
        return (
            "<p><b>Produces a GO / CONDITIONAL_GO / HOLD deployment decision with evidence flags.</b></p>"
            "<p><b>Inputs:</b> Actionability scorecard, Scenario selection recommender, Minimax regret selector, "
            "Implementation wave planner, Regret fragility area stats.<br>"
            "<b>Output:</b> Feature sink with one row: decision (GO_LIVE, CONDITIONAL_GO, HOLD), "
            "confidence (HIGH/MEDIUM/LOW), action_grade, readiness, overall, primary_scn, minimax_scn, "
            "primary_mm_rk, primary_mm_rg, top_max_regret, wave1_pct, wave2_pct, fragile_pct, "
            "flag_count, flags (pipe-separated), note.<br>"
            "<b>Method:</b> Evaluates four evidence flags: LOW_ACTIONABILITY (overall<75), "
            "HIGH_WORST_CASE_REGRET (top max regret>35), HIGH_FRAGILITY_FOOTPRINT (fragile pct>22.5), "
            "LOW_IMMEDIATE_DELIVERY_WINDOW (wave1<8%). "
            "Decision logic: GO_LIVE if no flags AND overall>=82 AND regret<=28; "
            "CONDITIONAL_GO if overall>=70 AND regret<=40; otherwise HOLD. Reports flag count and joined flag string.<br>"
            "<b>Typical use:</b> Final deployment gate before publishing results to planning authorities.</p>"
        )

    def helpUrl(self):
        return "https://github.com/YusufEminoglu/planx_suitability_lab"

    def createInstance(self):
        return DeploymentReadinessGateAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.SCORECARD, "Actionability scorecard table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SCENARIO_SELECTION, "Scenario selection recommender table", [QgsProcessing.SourceType.TypeVector]
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSource(self.MINIMAX, "Minimax regret selector table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.WAVE_PLAN, "Implementation wave planner table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REGRET_STATS, "Regret fragility area stats table", [QgsProcessing.SourceType.TypeVector]
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Deployment readiness gate", QgsProcessing.SourceType.TypeVector))

    @staticmethod
    def _first(src):
        for f in src.getFeatures(QgsFeatureRequest()):
            return f
        return None

    @staticmethod
    def _all(src):
        return [f for f in src.getFeatures(QgsFeatureRequest())]

    def processAlgorithm(self, parameters, context, feedback):
        score_src = self.parameterAsSource(parameters, self.SCORECARD, context)
        pick_src = self.parameterAsSource(parameters, self.SCENARIO_SELECTION, context)
        mm_src = self.parameterAsSource(parameters, self.MINIMAX, context)
        wave_src = self.parameterAsSource(parameters, self.WAVE_PLAN, context)
        reg_src = self.parameterAsSource(parameters, self.REGRET_STATS, context)
        if score_src is None or pick_src is None or mm_src is None or wave_src is None or reg_src is None:
            raise QgsProcessingException("Could not read one or more gate input tables.")

        score = self._first(score_src)
        pick = self._first(pick_src)
        if score is None or pick is None:
            raise QgsProcessingException("Scorecard or scenario-selection table is empty.")

        mm_rows = self._all(mm_src)
        wave_rows = self._all(wave_src)
        reg_rows = self._all(reg_src)
        if not mm_rows:
            raise QgsProcessingException("Minimax table is empty.")
        if not wave_rows:
            raise QgsProcessingException("Implementation wave table is empty.")
        if not reg_rows:
            raise QgsProcessingException("Regret fragility stats table is empty.")

        try:
            overall = float(score["overall"])
            readiness = str(score["readiness"])
            action_grade = str(score["grade"])
        except Exception as exc:
            raise QgsProcessingException(f"Scorecard table missing expected fields: {exc}")

        try:
            primary = str(pick["primary_scn"])
            minimax = str(pick["minimax_scn"])
            strategy = str(pick["strategy"])
            primary_mm_rank = float(pick["primary_mm_rk"])
            primary_mm_regret = float(pick["primary_mm_rg"])
        except Exception as exc:
            raise QgsProcessingException(f"Scenario selection table missing expected fields: {exc}")

        mm_top = None
        for f in mm_rows:
            with suppress(Exception):
                if str(f["selected"]).upper() == "YES":
                    mm_top = f
                    break
        if mm_top is None:
            mm_top = mm_rows[0]

        try:
            mm_top_regret = float(mm_top["max_regret"])
        except Exception:
            mm_top_regret = primary_mm_regret

        wave1_pct = 0.0
        wave2_pct = 0.0
        for f in wave_rows:
            with suppress(Exception):
                wid = int(f["wave_id"])
                pct = float(f["pct"])
                if wid == 1:
                    wave1_pct = pct
                elif wid == 2:
                    wave2_pct = pct

        fragile_pct = 0.0
        for f in reg_rows:
            with suppress(Exception):
                cid = int(f["class_id"])
                pct = float(f["pct"])
                if cid == 2:
                    fragile_pct = pct
                    break

        flags = []
        if overall < 75.0:
            flags.append("LOW_ACTIONABILITY")
        if mm_top_regret > 35.0:
            flags.append("HIGH_WORST_CASE_REGRET")
        if fragile_pct > 22.5:
            flags.append("HIGH_FRAGILITY_FOOTPRINT")
        if wave1_pct < 8.0:
            flags.append("LOW_IMMEDIATE_DELIVERY_WINDOW")

        if not flags and overall >= 82.0 and mm_top_regret <= 28.0:
            decision = "GO_LIVE"
            confidence = "HIGH"
        elif overall >= 70.0 and mm_top_regret <= 40.0:
            decision = "CONDITIONAL_GO"
            confidence = "MEDIUM"
        else:
            decision = "HOLD"
            confidence = "LOW"

        note = (
            f"Primary={primary}; Minimax={minimax}; Strategy={strategy}. "
            f"Wave1={wave1_pct:.2f}%, Wave2={wave2_pct:.2f}%, Fragile={fragile_pct:.2f}%, "
            f"TopMaxRegret={mm_top_regret:.2f}. "
            f"Flags: {', '.join(flags) if flags else 'None'}."
        )

        fields = QgsFields()
        fields.append(QgsField("decision", QMetaType.Type.QString))
        fields.append(QgsField("confidence", QMetaType.Type.QString))
        fields.append(QgsField("action_grade", QMetaType.Type.QString))
        fields.append(QgsField("readiness", QMetaType.Type.QString))
        fields.append(QgsField("overall", QMetaType.Type.Double))
        fields.append(QgsField("primary_scn", QMetaType.Type.QString))
        fields.append(QgsField("minimax_scn", QMetaType.Type.QString))
        fields.append(QgsField("primary_mm_rk", QMetaType.Type.Double))
        fields.append(QgsField("primary_mm_rg", QMetaType.Type.Double))
        fields.append(QgsField("top_max_regret", QMetaType.Type.Double))
        fields.append(QgsField("wave1_pct", QMetaType.Type.Double))
        fields.append(QgsField("wave2_pct", QMetaType.Type.Double))
        fields.append(QgsField("fragile_pct", QMetaType.Type.Double))
        fields.append(QgsField("flag_count", QMetaType.Type.Int))
        fields.append(QgsField("flags", QMetaType.Type.QString))
        fields.append(QgsField("note", QMetaType.Type.QString))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, QgsCoordinateReferenceSystem())

        out = QgsFeature(fields)
        out["decision"] = decision
        out["confidence"] = confidence
        out["action_grade"] = action_grade
        out["readiness"] = readiness
        out["overall"] = overall
        out["primary_scn"] = primary
        out["minimax_scn"] = minimax
        out["primary_mm_rk"] = primary_mm_rank
        out["primary_mm_rg"] = primary_mm_regret
        out["top_max_regret"] = mm_top_regret
        out["wave1_pct"] = wave1_pct
        out["wave2_pct"] = wave2_pct
        out["fragile_pct"] = fragile_pct
        out["flag_count"] = int(len(flags))
        out["flags"] = "|".join(flags) if flags else "NONE"
        out["note"] = note
        sink.addFeature(out)

        feedback.pushInfo(f"Deployment gate: {decision} ({confidence}), flags={len(flags)}.")
        return {self.OUTPUT: dest}

