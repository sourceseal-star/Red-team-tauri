# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - Deception Module
Deception mesh + STIX TIP + honeytoken rotation.
"""
# Existing remote modules
from .mesh import DeceptionMesh, CanaryToken, DecoyEndpoint, SyntheticSession
# New modules from deception toolkit
from .auto_rotation import HoneyTokenGenerator

__all__ = [
    # From mesh.py (existing)
    "DeceptionMesh",
    "CanaryToken",
    "DecoyEndpoint",
    "SyntheticSession",
    # New (honeytokens)
    "HoneyTokenGenerator",
]
