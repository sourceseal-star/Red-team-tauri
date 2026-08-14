#!/usr/bin/env python3
"""
Deception Mesh — Malla de Engaño Dinámica
==========================================
Despliega elementos trampa activos en la infraestructura:
  - Tokens de sesión sintéticos en memoria
  - Bases de datos señuelo con datos falsos
  - Endpoints no documentados
  - Canary files y DNS canary

Cuando un atacante interactúa con cualquier elemento trampa,
se genera una alerta crítica inmediata (movimiento lateral confirmado).
"""
import time
import json
import hashlib
import secrets
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class CanaryToken:
    id: str
    token: str
    type: str              # jwt | api_key | session | cookie | dns
    context: str           # dónde fue plantado
    created_at: str
    consumed: bool = False
    consumed_at: str = ""
    consumed_by_ip: str = ""
    consumed_by_user: str = ""


@dataclass
class DecoyEndpoint:
    path: str              # /v1/keys, /admin/secret
    method: str            # GET, POST
    tarpit_seconds: float  # retraso intencional
    returns_fake_data: Dict[str, Any]
    hit_count: int = 0
    last_hit: str = ""
    last_hit_ip: str = ""


@dataclass
class SyntheticSession:
    id: str
    jwt: str
    user_hash: str         # hash ficticio
    ip_seed: str
    created_at: str
    consumed: bool = False


class DeceptionMesh:
    """Malla de engaño dinámica con tokens, decoys y sesiones sintéticas."""

    DECOY_ENDPOINTS = [
        DecoyEndpoint(
            path="/v1/keys", method="GET", tarpit_seconds=2.0,
            returns_fake_data={"keys": ["FAKE_KEY_AES256_0001", "FAKE_KEY_AES256_0002"]},
        ),
        DecoyEndpoint(
            path="/v1/auth", method="POST", tarpit_seconds=1.5,
            returns_fake_data={"token": "DECOY_TOKEN_SHOULD_NEVER_WORK", "expires": "never"},
        ),
        DecoyEndpoint(
            path="/v1/transactions", method="POST", tarpit_seconds=1.5,
            returns_fake_data={"status": "pending", "tx_id": "DECOY_TX_000"},
        ),
        DecoyEndpoint(
            path="/admin/secret", method="GET", tarpit_seconds=3.0,
            returns_fake_data={"secret": "CANARY_SECRET_VALUE_12345"},
        ),
        DecoyEndpoint(
            path="/.env", method="GET", tarpit_seconds=0.5,
            returns_fake_data={
                "DATABASE_URL": "postgresql://decoy:decoy@10.99.0.99/decoy",
                "JWT_SECRET": "DECOY_JWT_SECRET_56789",
                "STRIPE_KEY": "sk_live_DECOY_0000000000",
            },
        ),
        DecoyEndpoint(
            path="/api/internal/debug", method="GET", tarpit_seconds=1.0,
            returns_fake_data={"debug": True, "internal_state": "DECOY_STATE"},
        ),
    ]

    def __init__(self):
        self.tokens: List[CanaryToken] = []
        self.sessions: List[SyntheticSession] = []
        self.decoys: List[DecoyEndpoint] = list(self.DECOY_ENDPOINTS)
        self.alerts: List[Dict] = []

    def deploy_token(self, token_type: str, context: str) -> CanaryToken:
        """Planta un nuevo token canary."""
        if token_type == "jwt":
            value = "eyJhbGciOiJIUzI1NiJ9." + secrets.token_urlsafe(32) + ".decoy"
        elif token_type == "api_key":
            value = "ss_decoy_" + secrets.token_hex(16)
        elif token_type == "dns":
            value = f"canary-{secrets.token_hex(4)}.deception.sourceseal.local"
        else:
            value = "canary_" + secrets.token_hex(16)

        token = CanaryToken(
            id=hashlib.sha256(value.encode()).hexdigest()[:16],
            token=value, type=token_type, context=context,
            created_at=datetime.datetime.utcnow().isoformat() + "Z",
        )
        self.tokens.append(token)
        return token

    def deploy_synthetic_session(self) -> SyntheticSession:
        """Crea una sesión JWT sintética en memoria."""
        session = SyntheticSession(
            id=hashlib.sha256(secrets.token_bytes(16)).hexdigest()[:16],
            jwt="eyJhbGciOiJIUzI1NiJ9." + secrets.token_urlsafe(48) + ".synthetic",
            user_hash=hashlib.sha256(secrets.token_bytes(8)).hexdigest()[:32],
            ip_seed=f"10.99.{secrets.randbelow(255)}.{secrets.randbelow(255)}",
            created_at=datetime.datetime.utcnow().isoformat() + "Z",
        )
        self.sessions.append(session)
        return session

    def check_token_consumed(self, token_value: str, ip: str = "", user: str = "") -> Optional[Dict]:
        """Verifica si un token canary fue consumido (compromiso confirmado)."""
        for t in self.tokens:
            if t.token == token_value and not t.consumed:
                t.consumed = True
                t.consumed_at = datetime.datetime.utcnow().isoformat() + "Z"
                t.consumed_by_ip = ip
                t.consumed_by_user = user
                alert = {
                    "type": "canary_consumed",
                    "severity": "critical",
                    "title": "MOVIMIENTO LATERAL CONFIRMADO — Canary token consumido",
                    "description": f"Token {t.type} en '{t.context}' fue consumido por {ip or user or 'unknown'}",
                    "evidence": asdict(t),
                    "timestamp": t.consumed_at,
                    "mitre": "T1550",
                    "recommended_actions": ["isolate_endpoint", "block_ip", "alert_soc", "revoke_tokens"],
                }
                self.alerts.append(alert)
                return alert
        return None

    def check_decoy_hit(self, path: str, method: str, ip: str = "") -> Optional[Dict]:
        """Verifica si un endpoint señuelo fue accedido."""
        for d in self.decoys:
            if d.path == path and d.method == method:
                d.hit_count += 1
                d.last_hit = datetime.datetime.utcnow().isoformat() + "Z"
                d.last_hit_ip = ip
                alert = {
                    "type": "decoy_accessed",
                    "severity": "critical",
                    "title": f"Decoy endpoint accedido: {method} {path}",
                    "description": f"Endpoint no documentado {path} fue accedido por {ip}",
                    "evidence": {"path": path, "method": method, "hits": d.hit_count,
                                 "tarpit_seconds": d.tarpit_seconds},
                    "timestamp": d.last_hit,
                    "mitre": "T1046",
                    "recommended_actions": ["block_ip", "alert_soc", "isolate_endpoint"],
                }
                self.alerts.append(alert)
                return alert
        return None

    def get_alerts(self) -> List[Dict]:
        return self.alerts

    def get_summary(self) -> Dict:
        return {
            "total_tokens": len(self.tokens),
            "consumed_tokens": sum(1 for t in self.tokens if t.consumed),
            "active_sessions": len(self.sessions),
            "decoy_endpoints": len(self.decoys),
            "decoy_hits": sum(d.hit_count for d in self.decoys),
            "total_alerts": len(self.alerts),
        }


# ─── TIP — Threat Intelligence Platform (STIX/TAXII) ───────────────────────

class ThreatIntelPlatform:
    """
    Procesa IoCs desde el honeypot, deception mesh y C2 sinkhole.
    Genera paquetes STIX 2.1 y los propaga a WAF/Firewall.
    """

    def __init__(self):
        self.iocs: List[Dict] = []
        self.stix_bundles: List[Dict] = []

    def add_ioc(self, ioc_type: str, value: str, source: str,
                confidence: int = 50, tags: List[str] = None) -> Dict:
        """Agrega un IoC. type: ip | domain | url | hash | email | cidr."""
        ioc = {
            "id": hashlib.sha256(f"{ioc_type}:{value}:{time.time()}".encode()).hexdigest()[:36],
            "type": ioc_type,
            "value": value,
            "source": source,
            "confidence": min(100, max(0, confidence)),
            "tags": tags or [],
            "first_seen": datetime.datetime.utcnow().isoformat() + "Z",
            "last_seen": datetime.datetime.utcnow().isoformat() + "Z",
        }
        self.iocs.append(ioc)
        return ioc

    def to_stix_bundle(self) -> Dict:
        """Convierte los IoCs a un bundle STIX 2.1."""
        objects = []
        for ioc in self.iocs:
            if ioc["type"] == "ip":
                obj = {
                    "type": "ipv4-addr",
                    "spec_version": "2.1",
                    "id": f"ipv4-addr--{ioc['id']}",
                    "value": ioc["value"],
                }
            elif ioc["type"] == "domain":
                obj = {
                    "type": "domain-name",
                    "spec_version": "2.1",
                    "id": f"domain-name--{ioc['id']}",
                    "value": ioc["value"],
                }
            elif ioc["type"] == "url":
                obj = {
                    "type": "url",
                    "spec_version": "2.1",
                    "id": f"url--{ioc['id']}",
                    "value": ioc["value"],
                }
            elif ioc["type"] == "hash":
                obj = {
                    "type": "file",
                    "spec_version": "2.1",
                    "id": f"file--{ioc['id']}",
                    "hashes": {"SHA-256": ioc["value"]},
                }
            else:
                continue

            # Indicator wrapper
            indicator = {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{ioc['id']}",
                "created": ioc["first_seen"],
                "modified": ioc["last_seen"],
                "pattern": f"[{obj['type']}:value = '{ioc['value']}']",
                "pattern_type": "stix",
                "valid_from": ioc["first_seen"],
                "labels": ioc["tags"] or ["malicious-activity"],
                "confidence": ioc["confidence"],
            }
            objects.append(obj)
            objects.append(indicator)

        bundle = {
            "type": "bundle",
            "id": f"bundle--{hashlib.sha256(str(time.time()).encode()).hexdigest()[:36]}",
            "objects": objects,
        }
        self.stix_bundles.append(bundle)
        return bundle

    def get_blocklist(self) -> List[str]:
        """Retorna lista de IPs/dominios para bloquear en WAF/Firewall."""
        return [ioc["value"] for ioc in self.iocs
                if ioc["type"] in ("ip", "domain") and ioc["confidence"] >= 50]

    def get_summary(self) -> Dict:
        by_type = {}
        for ioc in self.iocs:
            by_type[ioc["type"]] = by_type.get(ioc["type"], 0) + 1
        return {
            "total_iocs": len(self.iocs),
            "by_type": by_type,
            "stix_bundles": len(self.stix_bundles),
            "blocklist_size": len(self.get_blocklist()),
        }
