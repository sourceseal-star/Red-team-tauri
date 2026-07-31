# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - NDR Module
Network Detection & Response — engine + capture + ML detector.
"""
# Existing remote modules
from .engine import NDREngine, TrafficFlow, AnomalyAlert, C2Detector, ExfilDetector
# New modules from NDR toolkit
from .behavioral import AnomalyDetector

__all__ = [
    # From engine.py (existing)
    "NDREngine",
    "TrafficFlow",
    "AnomalyAlert",
    "C2Detector",
    "ExfilDetector",
    # New (ML detector)
    "AnomalyDetector",
]
