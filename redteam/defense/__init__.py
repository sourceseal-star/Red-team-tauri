"""
defense — Arquitectura Unificada de Ciberseguridad Defensiva de Grado Enterprise
===============================================================================
Zero Trust + Defense in Depth.

Componentes:
    rasp         — Runtime Application Self-Protection
    attestation  — Hardware Keystore + Attestation
    ndr          — Network Detection and Response (proxy TLS + motor comportamental)
    ztna         — Zero Trust Network Access (ABAC + Posture + JWT + BOLA)
    deception    — Dynamic Deception Mesh (decoy tokens, db, endpoints, STIX)
    xdr          — Extended Detection and Response (event bus + correlator + MITRE)
    soar         — Security Orchestration, Automation and Response (playbooks)
    integration  — DefenseMesh (bus central)
    api_gateway  — API Gateway con @protect(action, resource)
    dashboard    — Endpoints del dashboard defensivo

Uso básico:
    from defense import DefenseMesh
    mesh = DefenseMesh()
    print(mesh.health_check())
    mesh.ingest(signal)
"""
from .integration import DefenseMesh
from .rasp import RASPProbe, RASPEnforcer, ThreatSignal
from .attestation import HardwareKeystore, AttestationVerifier
from .ndr import NDREngine, TLSInterceptionProxy, NDRFinding
from .ztna import ZTNAContext, PolicyEngine, PostureScorer, JWTIssuer, JWTValidator, BOLAProtector
from .deception import DecoyToken, DecoyDB, DecoyEndpoint, STIXExporter
from .xdr import EventBus, Correlator, MITREMapper, IncidentStore, XdrEvent
from .soar import PlaybookEngine, ActionRegistry, default_playbooks, ActionResult

__all__ = [
    "DefenseMesh",
    "RASPProbe", "RASPEnforcer", "ThreatSignal",
    "HardwareKeystore", "AttestationVerifier",
    "NDREngine", "TLSInterceptionProxy", "NDRFinding",
    "ZTNAContext", "PolicyEngine", "PostureScorer", "JWTIssuer", "JWTValidator", "BOLAProtector",
    "DecoyToken", "DecoyDB", "DecoyEndpoint", "STIXExporter",
    "EventBus", "Correlator", "MITREMapper", "IncidentStore", "XdrEvent",
    "PlaybookEngine", "ActionRegistry", "default_playbooks", "ActionResult",
]
__version__ = "1.0.0"
