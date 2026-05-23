# -*- coding: utf-8 -*-
from .main_plugin import PlanXSuitabilityLabPlugin


def classFactory(iface):
    return PlanXSuitabilityLabPlugin(iface)
