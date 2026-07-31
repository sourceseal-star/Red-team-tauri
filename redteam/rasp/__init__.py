# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - RASP Module
Runtime Application Self-Protection — agent + mobile attestation.
"""
# Existing remote modules
from .agent import RASPAgent, RASPAlert, HookingDetector, EmulatorDetector, TamperDetector, AttestationChecker
# New modules from mobile toolkit
from .attestation_client import SourceSealAttestationClient

__all__ = [
    # From agent.py (existing)
    "RASPAgent",
    "RASPAlert",
    "HookingDetector",
    "EmulatorDetector",
    "TamperDetector",
    "AttestationChecker",
    # New (attestation)
    "SourceSealAttestationClient",
]
