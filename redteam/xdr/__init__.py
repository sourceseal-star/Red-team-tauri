# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - XDR Module
Extended Detection & Response — exports for correlator, kill chain, attack surface.
"""
from .correlator import XDREvent, Incident, MITRE_TECHNIQUES
from .kill_chain import KillChainPhase, AttackPath, KillChainAnalyzer, KillChainVisualizer
from .attack_surface import AttackSurface, AttackSurfaceMapper

__all__ = [
    "XDREvent",
    "Incident",
    "MITRE_TECHNIQUES",
    "KillChainPhase",
    "AttackPath",
    "KillChainAnalyzer",
    "KillChainVisualizer",
    "AttackSurface",
    "AttackSurfaceMapper",
]
