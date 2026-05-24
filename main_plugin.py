# -*- coding: utf-8 -*-
from __future__ import annotations

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import QAction

from .dashboard import SuitabilityDashboard
from .provider import PlanXSuitabilityLabProvider


class PlanXSuitabilityLabPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dialog = None

    def initGui(self):
        self.provider = PlanXSuitabilityLabProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)
        if self.iface:
            self.action = QAction(self.provider.icon(), 'PlanX Suitability Lab', self.iface.mainWindow())
            self.action.triggered.connect(self.open_dashboard)
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToMenu('&PlanX Suitability Lab', self.action)

    def open_dashboard(self):
        if self.dialog is None:
            self.dialog = SuitabilityDashboard(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def unload(self):
        if self.iface and self.action:
            self.iface.removePluginMenu('&PlanX Suitability Lab', self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
