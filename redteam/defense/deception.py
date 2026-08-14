"""
defense.deception — Deception Mesh
====================================

Despliega señuelos de alta interacción que el atacante no puede distinguir
de activos reales:

  * ``DecoyToken``: JWT sintéticos con ``decoy:true`` que detectan exfil.
  * ``DecoyDB``: SQLite en memoria con datos falsos. Cualquier query genera
    una alerta CRITICAL.
  * ``DecoyEndpoint``: rutas no documentadas que devuelven 200 con payload
    trampa (canary URL).
  * ``STIXExporter``: convierte hits en IoC STIX 2.1.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===================== Decoy Token =====================


class DecoyToken:
    """JWT señuelo con flag ``decoy:true``.

    Si el atacante intenta usar el token en un endpoint protegido, el
    gateway lo detecta y emite un evento de deception."""

    PREFIX = "decoy."

    def __init__(self, *, subject: str = "decoy-user", secret: bytes = b"decoy-secret"):
        self.subject = subject
        self.secret = secret
        self._issued: List[str] = []
        self._lock = threading.Lock()
        self._usage_attempts: List[Dict[str, Any]] = []

    def issue(self, *, scope: str = "admin", ttl_seconds: int = 3600) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "sub": self.subject,
            "iat": now,
            "exp": now + ttl_seconds,
            "scope": scope,
            "decoy": True,
            "canary_id": "canary-" + secrets.token_hex(4),
        }
        h = base64.urlsafe_b64encode(json.dumps(header, sort_keys=True).encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).rstrip(b"=").decode()
        sig = hmac.new(self.secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
        token = f"{self.PREFIX}{h}.{p}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"
        with self._lock:
            self._issued.append(token)
        return token

    def is_decoy(self, token: str) -> bool:
        return token.startswith(self.PREFIX)

    def decode_payload(self, token: str) -> Optional[Dict[str, Any]]:
        if not self.is_decoy(token):
            return None
        try:
            body = token[len(self.PREFIX):]
            _, p, _ = body.split(".")
            padding = "=" * (-len(p) % 4)
            return json.loads(base64.urlsafe_b64decode(p + padding))
        except Exception:
            return None

    def record_usage(self, token: str, where: str) -> Dict[str, Any]:
        payload = self.decode_payload(token) or {}
        evt = {
            "token": token,
            "canary_id": payload.get("canary_id"),
            "where": where,
            "ts": time.time(),
            "scope": payload.get("scope"),
        }
        with self._lock:
            self._usage_attempts.append(evt)
        return evt

    def usage_attempts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._usage_attempts)


# ===================== Decoy DB =====================


class DecoyDB:
    """Base de datos SQLite en memoria con datos falsos.

    El método ``query`` envuelve ``execute`` y, si la query es de tipo
    SELECT/INSERT/UPDATE/DELETE contra tablas no permitidas, registra
    la actividad como un hit CRITICAL. Útil para detectar movimientos
    laterales del atacante."""

    ALLOWED_TABLES = {"decoy_users", "decoy_secrets", "decoy_pii"}
    CRITICAL_SEVERITY = "critical"

    def __init__(self, *, seed: str = "honey-vault-001"):
        self.seed = seed
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._hits: List[Dict[str, Any]] = []
        self._bootstrap()

    def _bootstrap(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE decoy_users (
                id INTEGER PRIMARY KEY,
                email TEXT,
                full_name TEXT,
                password_hash TEXT,
                mfa_secret TEXT
            );
            CREATE TABLE decoy_secrets (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value TEXT
            );
            CREATE TABLE decoy_pii (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                document TEXT,
                phone TEXT
            );
            INSERT INTO decoy_users (email, full_name, password_hash, mfa_secret) VALUES
                ('admin@honey.example', 'Honey Admin', 'pwhash:bcrypt$2b$10$decoy', 'JBSWY3DPEHPK3PXP'),
                ('cfo@honey.example', 'Honey CFO', 'pwhash:bcrypt$2b$10$decoy', 'JBSWY3DPEHPK3PXQ');
            INSERT INTO decoy_secrets (name, value) VALUES
                ('STRIPE_KEY', 'sk_live_DECOY_PLACEHOLDER'),
                ('AWS_KEY', 'AKIADECOYPLACEHOLDER'),
                ('JWT_SIGNING', 'do-not-use-in-prod');
            INSERT INTO decoy_pii (user_id, document, phone) VALUES
                (1, '00000000A', '+34000000000'),
                (2, '11111111B', '+34111111111');
            """
        )
        self._conn.commit()

    def query(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            self._hits.append({"sql": sql, "params": list(params), "ts": time.time()})
            try:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            except sqlite3.Error as e:
                logger.warning("decoy db query error: %s", e)
                return []

    def hits(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._hits)

    def canary_records(self) -> List[Dict[str, Any]]:
        return self.query("SELECT * FROM decoy_users")


# ===================== Decoy Endpoints =====================


class DecoyEndpoint:
    """Rutas no documentadas que devuelven 200 con un payload trampa.

    Los payloads suelen incluir canary URLs/credenciales que, si son
    utilizadas, permiten al equipo de defensa identificar al atacante."""

    DEFAULT_ROUTES = ("/admin-old", "/.git", "/v0/test", "/api/v1/internal-backup")

    def __init__(self, routes: Optional[Tuple[str, ...]] = None,
                 seed_marker: Optional[str] = None):
        self.routes = tuple(routes) if routes is not None else self.DEFAULT_ROUTES
        self.seed_marker = seed_marker or "honey-" + secrets.token_hex(4)
        self._lock = threading.Lock()
        self._hits: List[Dict[str, Any]] = []

    def payload(self, route: str) -> Dict[str, Any]:
        return {
            "status": 200,
            "marker": self.seed_marker,
            "route": route,
            "data": {
                "username": "honey_admin",
                "password": self.seed_marker,
                "backup_url": f"https://honey.example/{self.seed_marker}",
                "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...honey",
            },
        }

    def handle(self, route: str, method: str = "GET", source_ip: str = "0.0.0.0") -> Optional[Dict[str, Any]]:
        if route not in self.routes:
            return None
        hit = {
            "route": route,
            "method": method,
            "source_ip": source_ip,
            "ts": time.time(),
            "marker": self.seed_marker,
        }
        with self._lock:
            self._hits.append(hit)
        return self.payload(route)

    def hits(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._hits)


# ===================== STIX 2.1 Exporter =====================


class STIXExporter:
    """Convierte hits / IoCs en objetos STIX 2.1 (JSON)."""

    def __init__(self, *, identity_name: str = "SOURCESEALCORP Defense"):
        self.identity_name = identity_name
        self._lock = threading.Lock()
        self._bundle: Dict[str, Any] = self._empty_bundle()

    def _empty_bundle(self) -> Dict[str, Any]:
        return {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": [
                {
                    "type": "identity",
                    "spec_version": "2.1",
                    "id": f"identity--{uuid.uuid4()}",
                    "created": self._now(),
                    "modified": self._now(),
                    "name": self.identity_name,
                    "identity_class": "organization",
                }
            ],
        }

    @staticmethod
    def _now() -> str:
        import datetime
        return datetime.datetime.utcnow().isoformat() + "Z"

    def export(self, *, ioc_type: str, value: str,
               mitre: Optional[List[str]] = None,
               source: str = "defense-mesh",
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Crea un Indicator STIX 2.1 y lo agrega al bundle."""
        if ioc_type == "domain":
            pattern = f"[domain-name:value = '{value}']"
            stix_type = "indicator"
        elif ioc_type == "ip":
            pattern = f"[ipv4-addr:value = '{value}']"
            stix_type = "indicator"
        elif ioc_type == "hash":
            pattern = f"[file:hashes.'SHA-256' = '{value}']"
            stix_type = "indicator"
        elif ioc_type == "ja3":
            pattern = f"[network-traffic:extensions.'tls-ext'.ja3 = '{value}']"
            stix_type = "indicator"
        else:
            pattern = f"[x-misc:value = '{value}']"
            stix_type = "indicator"
        indicator = {
            "type": stix_type,
            "spec_version": "2.1",
            "id": f"indicator--{uuid.uuid4()}",
            "created": self._now(),
            "modified": self._now(),
            "name": f"{ioc_type}:{value[:64]}",
            "pattern": pattern,
            "pattern_type": "stix",
            "valid_from": self._now(),
            "labels": ["malicious-activity"],
            "indicator_types": ["malicious-activity"],
            "external_references": [
                {"source_name": source, "external_id": value}
            ],
        }
        if mitre:
            indicator["kill_chain_phases"] = [
                {"kill_chain_name": "mitre-attack", "phase_name": m} for m in mitre
            ]
        if context:
            indicator["x_context"] = context
        with self._lock:
            self._bundle["objects"].append(indicator)
        return indicator

    def export_decoy_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        return self.export(
            ioc_type="domain",
            value=hit.get("marker", "decoy"),
            mitre=["T1078", "T1213"],
            source="deception.decoy",
            context={"route": hit.get("route"), "ts": hit.get("ts")},
        )

    def bundle(self) -> Dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._bundle))

    def count(self) -> int:
        with self._lock:
            return max(0, len(self._bundle["objects"]) - 1)
