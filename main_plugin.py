# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dashboard import SuitabilityDashboard
from .provider import PlanXSuitabilityLabProvider


def _processing_provider_enabled() -> bool:
    return int(getattr(Qgis, "QGIS_VERSION_INT", 0)) < 40000


class PlanXSuitabilityLabPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dialog = None

    def initProcessing(self):
        if not _processing_provider_enabled():
            self.provider = None
            return
        if self.provider is not None:
            return
        self.provider = PlanXSuitabilityLabProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        if self.iface:
            icon = self.provider.icon() if self.provider else QIcon(
                os.path.join(os.path.dirname(__file__), "icons", "icon.png")
            )
            self.action = QAction(icon, 'PlanX Suitability Lab', self.iface.mainWindow())
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
