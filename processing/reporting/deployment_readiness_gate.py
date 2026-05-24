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
)


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

    def createInstance(self):
        return DeploymentReadinessGateAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.SCORECARD, "Actionability scorecard table", [QgsProcessing.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SCENARIO_SELECTION, "Scenario selection recommender table", [QgsProcessing.TypeVector]
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSource(self.MINIMAX, "Minimax regret selector table", [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.WAVE_PLAN, "Implementation wave planner table", [QgsProcessing.TypeVector]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REGRET_STATS, "Regret fragility area stats table", [QgsProcessing.TypeVector]
            )
        )
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Deployment readiness gate", QgsProcessing.TypeVector))

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
            try:
                if str(f["selected"]).upper() == "YES":
                    mm_top = f
                    break
            except Exception:
                continue
        if mm_top is None:
            mm_top = mm_rows[0]

        try:
            mm_top_regret = float(mm_top["max_regret"])
        except Exception:
            mm_top_regret = primary_mm_regret

        wave1_pct = 0.0
        wave2_pct = 0.0
        for f in wave_rows:
            try:
                wid = int(f["wave_id"])
                pct = float(f["pct"])
            except Exception:
                continue
            if wid == 1:
                wave1_pct = pct
            elif wid == 2:
                wave2_pct = pct

        fragile_pct = 0.0
        for f in reg_rows:
            try:
                cid = int(f["class_id"])
                pct = float(f["pct"])
            except Exception:
                continue
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
        fields.append(QgsField("decision", QVariant.String))
        fields.append(QgsField("confidence", QVariant.String))
        fields.append(QgsField("action_grade", QVariant.String))
        fields.append(QgsField("readiness", QVariant.String))
        fields.append(QgsField("overall", QVariant.Double))
        fields.append(QgsField("primary_scn", QVariant.String))
        fields.append(QgsField("minimax_scn", QVariant.String))
        fields.append(QgsField("primary_mm_rk", QVariant.Double))
        fields.append(QgsField("primary_mm_rg", QVariant.Double))
        fields.append(QgsField("top_max_regret", QVariant.Double))
        fields.append(QgsField("wave1_pct", QVariant.Double))
        fields.append(QgsField("wave2_pct", QVariant.Double))
        fields.append(QgsField("fragile_pct", QVariant.Double))
        fields.append(QgsField("flag_count", QVariant.Int))
        fields.append(QgsField("flags", QVariant.String))
        fields.append(QgsField("note", QVariant.String))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields, Qgis.WkbType.NoGeometry, None)

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

