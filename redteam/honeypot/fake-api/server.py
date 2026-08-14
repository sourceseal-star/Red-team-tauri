#!/usr/bin/env python3
"""
Honeypot API — Servidor señuelo para la subred aislada.

Simula endpoints típicos de una API de app móvil criptográfica
(/v1/auth, /v1/keys, /v1/transactions, /v1/health) con:
- Respuestas que parecen válidas (baja entropía deliberada para tracking)
- Logging detallado de TODA petición a evidence/
- Tarpit en endpoints sensibles (respuesta lenta)
- Sin persistencia: cada request es efímero
"""
import json
import time
import datetime
import os
import pathlib
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

EVIDENCE_DIR = pathlib.Path(__file__).parent.parent / "evidence" / "honeypot"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Token canario único: si aparece en logs de un sistema externo, ese sistema
# consumió datos de nuestro honeypot.
CANARY_TOKEN = os.environ.get("HONEYPOT_CANARY", "hpt_" + os.urandom(8).hex())


def _log(req, body: bytes, status: int, note: str = ""):
    rec = {
        "ts": datetime.datetime.utcnow().isoformat(),
        "client": req.client_address[0],
        "method": req.command,
        "path": req.path,
        "headers": dict(req.headers),
        "body_sha256": __import__("hashlib").sha256(body).hexdigest(),
        "status": status,
        "note": note,
    }
    fname = EVIDENCE_DIR / f"{int(time.time()*1000)}-{random.randint(1000,9999)}.json"
    fname.write_text(json.dumps(rec, indent=2, ensure_ascii=False))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass  # silenciar logs por defecto

    def _respond(self, body: dict, status: int, slow: float = 0.0, note: str = ""):
        if slow:
            time.sleep(slow)
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Canary", CANARY_TOKEN)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        _log(self, raw, status, note)

    def do_GET(self):
        if self.path == "/v1/health":
            self._respond({"status": "ok", "version": "1.0.0"}, 200)
        elif self.path.startswith("/v1/keys"):
            # endpoint sensible: tarpit
            self._respond({
                "keys": [
                    {"id": "k_" + os.urandom(4).hex(), "alg": "RSA-2048", "status": "active"}
                    for _ in range(3)
                ]
            }, 200, slow=2.0, note="key-enumeration")
        elif self.path.startswith("/v1/auth"):
            self._respond({"token": CANARY_TOKEN, "expires_in": 3600}, 200, note="auth-leak")
        else:
            self._respond({"error": "not_found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        if self.path.startswith("/v1/transactions"):
            self._respond({"id": "tx_" + os.urandom(8).hex(), "status": "queued"},
                          202, slow=1.5, note="transaction-capture")
        else:
            self._respond({"error": "not_found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    print(f"[honeypot] CANARY={CANARY_TOKEN}")
    print(f"[honeypot] Sirviendo en 0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
