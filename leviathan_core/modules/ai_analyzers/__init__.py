#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN AI ANALYZERS - Módulos de Análisis con IA
===================================================
Paquete de analizadores de IA.
"""

from .object_detection import ObjectDetectionAnalyzer
from .anomaly_detector import AnomalyDetectorAnalyzer
from .behavior_analyzer import BehaviorAnalyzer
from .threat_scoring import ThreatScoringAnalyzer

__all__ = [
    "ObjectDetectionAnalyzer",
    "AnomalyDetectorAnalyzer",
    "BehaviorAnalyzer",
    "ThreatScoringAnalyzer"
]


def register_all():
    """Registra todos los analizadores."""
    return [
        ObjectDetectionAnalyzer(),
        AnomalyDetectorAnalyzer(),
        BehaviorAnalyzer(),
        ThreatScoringAnalyzer()
    ]
