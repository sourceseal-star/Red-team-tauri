#!/usr/bin/env python3
"""
C2 Sinkhole — Honeytramp
=========================
Emula endpoints típicos de C2 de spyware comercial (NSO Pegasus, FinFisher,
HackingTeam, Candiru). Si un spyware intenta hablar con su C2 y nuestro
DNS/network está en el path, capturamos la comunicación.

Modo de uso:
1) Servidor en una IP/dominio que tu app legítima puede configurar
2) Modificar /etc/hosts o DNS para que dominios IoC apunten aquí (en lab)
3) O configurar el sinkhole como upstream de un DNS server
4) El spyware, al intentar beaconear, golpea aquí y queda registrado

IMPORTANTE: Este sinkhole SOLO debe operar sobre dispositivos donde el usuario
ha dado consentimiento explícito (EULA + opt-in). NO apuntar a IPs públicas
de NSO o terceros — eso es ilegal.
"""
import json
import os
import time
import datetime
import secrets
import pathlib
import threading
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict
import struct

EVIDENCE = pathlib.Path(__file__).parent.parent.parent / "evidence" / "c2-sinkhole"
EVIDENCE.mkdir(parents=True, exist_ok=True)

# IoC (Indicators of Compromise) conocidos — dominios que Pegasus/FinFisher han usado
# SOLO para que el sinkhole los reconozca, no para apuntar a ellos
KNOWN_C2_PATTERNS = {
    "nso_patterns": [
        b"POST /api/v1/checkin",
        b"POST /collector/heartbeat",
        b"GET /static/config.json",
        b"X-Device-Fingerprint",
        b"PEGASUS",
        b"BRIDGE",
    ],
    "finfisher_patterns": [
        b"fcms",
        b"scrs",
        b"FinFisher",
        b"X-FinFisher",
    ],
    "hackingteam_patterns": [
        b"rcs",
        b"log",
        b"HT-Bridge",
        b"HackingTeam",
    ],
    "candiru_patterns": [
        b"sourgum",
        b"DevilsTongue",
    ],
    "stalkerware_patterns": [  # apps comerciales tipo mSpy, FlexiSpy
        b"/api/track",
        b"/api/call",
        b"/api/sms",
        b"/api/location",
    ],
}

# Contadores y estado
STATS = defaultdict(int)
ATTACK_LOG = []


def _classify_request(body: bytes, path: str, headers: dict) -> dict:
    """Clasifica la request según IoC conocidos."""
    blob = (body + path.encode() + str(headers).encode()).lower()
    hits = []
    for family, patterns in KNOWN_C2_PATTERNS.items():
        for pat in patterns:
            if pat.lower() in blob:
                hits.append({"family": family, "pattern": pat.decode(errors="ignore")})
    return {
        "looks_like_spyware": bool(hits),
        "matches": hits,
        "severity": "critical" if any(h["family"] in ("nso_patterns", "candiru_patterns")
                                       for h in hits) else "high" if hits else "info",
    }


def _log_event(event_type: str, data: dict):
    rec = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "type": event_type,
        **data,
    }
    ATTACK_LOG.append(rec)
    fname = EVIDENCE / f"{event_type}-{int(time.time()*1000)}-{secrets.token_hex(2)}.json"
    fname.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    if rec.get("classification", {}).get("looks_like_spyware"):
        # alerta destacada
        alert = EVIDENCE / f"!!ALERT-{int(time.time())}-{secrets.token_hex(2)}.json"
        alert.write_text(json.dumps({
            "alert": "POSIBLE SPYWARE C2 DETECTADO",
            "ts": rec["ts"],
            "client": data.get("client"),
            "path": data.get("path"),
            "matches": rec["classification"]["matches"],
        }, indent=2))


class C2Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a, **k): pass

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        if self.headers.get("Content-Encoding") == "gzip":
            return gzip.decompress(self.rfile.read(length))
        return self.rfile.read(length) if length else b""

    def _respond(self, body: bytes, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _capture(self, event_type: str, extra: dict, body: bytes):
        classification = _classify_request(body, self.path, dict(self.headers))
        data = {
            "client": self.client_address[0],
            "port": self.client_address[1],
            "method": self.command,
            "path": self.path,
            "headers": dict(self.headers),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_size": len(body),
            "body_preview": body[:500].decode(errors="replace"),
            "classification": classification,
        }
        data.update(extra)
        STATS[event_type] += 1
        if classification["looks_like_spyware"]:
            STATS["spyware_beacons"] += 1
        _log_event(event_type, data)

    def do_GET(self):
        # Responder con config falsa que pide el spyware
        fake_config = json.dumps({
            "version": "1.0.0",
            "next_checkin": int(time.time()) + 3600,
            "modules": ["calls", "sms", "mic", "cam", "gps", "files"],
            "c2_server": "https://malicious-c2.invalid/api",  # redirige a otro sinkhole
        }).encode()
        body = self._read_body()
        self._capture("get", {"kind": "config-poll"}, body)
        self._respond(fake_config)

    def do_POST(self):
        body = self._read_body()
        self._capture("post", {"kind": "beacon"}, body)
        # Responder con un ACK que cualquier spyware esperaría
        ack = json.dumps({"status": "ok", "next": int(time.time()) + 1800,
                          "cmd": "idle"}).encode()
        self._respond(ack)

    def do_PUT(self):
        body = self._read_body()
        self._capture("upload", {"kind": "exfiltration"}, body)
        self._respond(b'{"received":true}')


class ThreadedServer(ThreadingHTTPServer):
    daemon_threads = True


def start(port: int = 8443, host: str = "0.0.0.0"):
    print(f"🍯  C2 Sinkhole escuchando en {host}:{port}")
    print(f"    Evidencia: {EVIDENCE}")
    print(f"    IoC families: {', '.join(KNOWN_C2_PATTERNS.keys())}")
    ThreadedServer((host, port), C2Handler).serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("SINKHOLE_PORT", 8443))
    start(port)
