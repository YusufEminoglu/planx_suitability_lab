# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dashboard import SuitabilityDashboard
from .provider import PlanXSuitabilityLabProvider


def _icon_path() -> str:
    base = os.path.join(os.path.dirname(__file__), "icons")
    for name in ("icon.png", "icon.svg"):
        path = os.path.join(base, name)
        if os.path.exists(path):
            return path
    return ""


class PlanXSuitabilityLabPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dialog = None

    def initProcessing(self):
        if self.provider is not None:
            return
        self.provider = PlanXSuitabilityLabProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        if self.iface:
            icon = self.provider.icon() if self.provider else QIcon(_icon_path())
            self.action = QAction(icon, 'PlanX Suitability Lab', self.iface.mainWindow())
            self.action.triggered.connect(self.open_dashboard)
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToMenu('&PlanX Suitability Lab', self.action)

            # Direct AHP Studio Action
            self.ahp_action = QAction('✨ AHP Studio (Interactive Weight Designer)', self.iface.mainWindow())
            self.ahp_action.triggered.connect(self.open_ahp_studio)
            self.iface.addPluginToMenu('&PlanX Suitability Lab', self.ahp_action)

    def open_dashboard(self):
        if self.dialog is None:
            self.dialog = SuitabilityDashboard(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def open_ahp_studio(self):
        from .ahp_studio import open_ahp_studio
        return open_ahp_studio(self.iface, self.iface.mainWindow())

    def unload(self):
        if self.iface and self.action:
            self.iface.removePluginMenu('&PlanX Suitability Lab', self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.iface and hasattr(self, 'ahp_action') and self.ahp_action:
            self.iface.removePluginMenu('&PlanX Suitability Lab', self.ahp_action)
        if self.iface:
            from qgis.PyQt.QtWidgets import QDockWidget
            dock = self.iface.mainWindow().findChild(QDockWidget, "PlanX_AHP_Studio_Dock")
            if dock is not None:
                self.iface.removeDockWidget(dock)
                dock.deleteLater()
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
