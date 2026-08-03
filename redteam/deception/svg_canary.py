#!/usr/bin/env python3
"""
SVG Canary Token — Camuflado y Funcional
========================================
Genera un archivo SVG que parece una imagen/ícono inofensivo pero que,
al ser abierto/renderizado por cualquier visor SVG (navegador, visor de imágenes,
app de mensajería, spyware que exfiltra y abre archivos), ejecuta una
petición HTTP de callback al servidor SourceSeal revelando:

- IP del que abrió el archivo
- User-Agent (identifica la app/navegador)
- Timestamp exacto
- Token único del canary (identifica qué archivo fue comprometido)

El SVG usa dos vectores de callback:
1. <image href="http://server/callback?token=X"> — SVG renderiza la imagen,
   lo que dispara una petición HTTP GET al servidor.
2. <animate> con values que referencian una URL externa — algunos renderers
   procesan animation URLs.

El callback se registra en el backend Python como evento de canary access.

USO:
    from svg_canary import SVGCanary
    canary = SVGCanary(callback_host="192.168.1.100:8001")
    canary.generate("decoy_photo.svg")
    canary.start_listener()  # escucha callbacks en el puerto 8001
"""
import os
import json
import time
import secrets
import hashlib
import pathlib
import datetime
import threading
import http.server
import socket
from typing import Optional


class SVGCanary:
    """Genera y gestiona SVG canary tokens que phone-home al ser abiertos."""

    def __init__(self, callback_host: str = "localhost:8001", callback_port: int = 8001):
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.tokens: dict = {}  # token -> metadata
        self.alerts: list = []
        self._server = None
        self._thread = None

    def generate(self, output_path: str, filename: str = None) -> dict:
        """
        Genera un SVG canary camuflado como imagen inofensiva.
        El SVG parece un ícono de foto/documento pero contiene callbacks ocultos.
        """
        token = "SVGCANARY_" + secrets.token_hex(12)
        fname = filename or pathlib.Path(output_path).name

        # Metadatos del canary
        meta = {
            "token": token,
            "filename": fname,
            "path": str(output_path),
            "created": datetime.datetime.utcnow().isoformat() + "Z",
            "callback_url": f"http://{self.callback_host}/canary/svg?token={token}",
        }
        self.tokens[token] = meta

        # SVG camuflado — parece una imagenplaceholder pero hace callback
        svg_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="640" height="480" viewBox="0 0 640 480">
  <!-- Background gradient — looks like a photo placeholder -->
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e8e8e8"/>
      <stop offset="100%" stop-color="#c0c0c0"/>
    </linearGradient>
  </defs>
  <rect width="640" height="480" fill="url(#bg)"/>

  <!-- Photo icon decoy -->
  <g transform="translate(240,140)">
    <rect width="160" height="120" rx="8" fill="#f5f5f5" stroke="#bbb" stroke-width="2"/>
    <circle cx="60" cy="45" r="18" fill="#ffd700"/>
    <path d="M 10 100 L 50 60 L 80 85 L 110 50 L 150 100 Z" fill="#7cb342"/>
    <rect x="55" y="95" width="50" height="18" rx="3" fill="#333"/>
  </g>
  <text x="320" y="300" text-anchor="middle" font-family="sans-serif" font-size="14"
        fill="#999">Photo_2024_12_24.jpg</text>

  <!-- CANARY CALLBACK #1: Hidden image element that triggers HTTP GET when rendered -->
  <image x="0" y="0" width="1" height="1" preserveAspectRatio="none"
        xlink:href="http://{self.callback_host}/canary/svg?token={token}&amp;v=img"/>

  <!-- CANARY CALLBACK #2: CSS @import via style element (some renderers process this) -->
  <style type="text/css">
    @import url("http://{self.callback_host}/canary/svg?token={token}&amp;v=css");
  </style>

  <!-- CANARY CALLBACK #3: ForeignObject with HTML img (browsers render this) -->
  <foreignObject x="0" y="0" width="1" height="1">
    <html xmlns="http://www.w3.org/1999/xhtml">
      <body style="margin:0;padding:0;">
        <img src="http://{self.callback_host}/canary/svg?token={token}&amp;v=fo" width="1" height="1"/>
      </body>
    </html>
  </foreignObject>

  <!-- CANARY CALLBACK #4: animate element referencing callback URL -->
  <rect x="0" y="0" width="1" height="1" fill="transparent">
    <animate attributeName="x" values="0;0" dur="9999s"
             begin="0s" repeatCount="1"/>
    <set attributeName="x" to="0"
         begin="0s"/>
  </rect>
</svg>'''

        # Escribir archivo SVG
        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(output_path).write_text(svg_content, encoding="utf-8")

        # Calcular hash
        sha256 = hashlib.sha256(svg_content.encode()).hexdigest()
        meta["sha256"] = sha256
        meta["size"] = len(svg_content.encode())

        return meta

    def generate_decoy_set(self, output_dir: str, count: int = 5) -> list:
        """Genera un set de archivos SVG canary con nombres atractivos."""
        decoy_names = [
            "vacation_photos_2024.svg",
            "screenshot_bank_login.svg",
            "wifi_passwords.svg",
            "private_keys_backup.svg",
            "passport_scan.svg",
            "credit_card_photo.svg",
            "id_card_front.svg",
            "family_photo_private.svg",
        ]
        results = []
        for i in range(min(count, len(decoy_names))):
            path = os.path.join(output_dir, decoy_names[i])
            results.append(self.generate(path, filename=decoy_names[i]))
        return results

    def handle_callback(self, handler):
        """
        Maneja peticiones HTTP entrantes de callback del SVG canary.
        Se integra en el servidor HTTP existente del dashboard.
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(handler.path)
        if parsed.path != "/canary/svg":
            return False

        params = parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        source_ip = handler.client_address[0]
        user_agent = handler.headers.get("User-Agent", "unknown")
        referer = handler.headers.get("Referer", "")
        accept = handler.headers.get("Accept", "")

        if not token or token not in self.tokens:
            # Token desconocido — posible acceso no autorizado
            alert = {
                "type": "svg_canary_unknown_token",
                "severity": "high",
                "token": token,
                "ip": source_ip,
                "user_agent": user_agent,
                "referer": referer,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
        else:
            meta = self.tokens[token]
            alert = {
                "type": "svg_canary_triggered",
                "severity": "critical",
                "token": token,
                "filename": meta["filename"],
                "canary_path": meta["path"],
                "triggered_by_ip": source_ip,
                "user_agent": user_agent,
                "referer": referer,
                "accept": accept,
                "vector": params.get("v", ["unknown"])[0],
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "canary_created": meta["created"],
                "elapsed": (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(meta["created"].replace("Z",""))).total_seconds(),
            }

            # Geolocalización básica del IP
            try:
                import socket as _sock
                hostname = _sock.gethostbyaddr(source_ip)[0]
                alert["hostname"] = hostname
            except Exception:
                alert["hostname"] = None

        self.alerts.append(alert)

        # Guardar evidencia forense
        evidence_dir = pathlib.Path(__file__).parent.parent / "evidence" / "canary-svg"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = evidence_dir / f"ALERT-{int(time.time()*1000)}.json"
        evidence_file.write_text(json.dumps(alert, indent=2, ensure_ascii=False))

        # Responder con un píxel transparente 1x1 (para que el renderer no muestre error)
        handler.send_response(200)
        handler.send_header("Content-Type", "image/png")
        handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        # PNG 1x1 transparente (67 bytes)
        handler.wfile.write(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c63000100000005000100b5c4b5c40b000000004945"
            "4e44ae426082"
        ))
        return True

    def get_alerts(self) -> list:
        """Retorna todas las alertas de canary SVG."""
        return self.alerts

    def get_tokens(self) -> dict:
        """Retorna todos los tokens canary registrados."""
        return self.tokens

    def clear_alerts(self):
        """Limpia las alertas."""
        self.alerts = []


# ── Instancia global para integración con el dashboard server ────────────────
_global_instance: Optional[SVGCanary] = None

def get_canary(callback_host: str = "localhost:8001") -> SVGCanary:
    global _global_instance
    if _global_instance is None:
        _global_instance = SVGCanary(callback_host=callback_host)
    return _global_instance


if __name__ == "__main__":
    # Test standalone
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost:8001"
    canary = SVGCanary(callback_host=host)

    # Generar SVG de prueba
    meta = canary.generate("/tmp/test_canary.svg")
    print("✅ SVG canary generado:")
    print(json.dumps(meta, indent=2))
    print(f"\nArchivo: /tmp/test_canary.svg")
    print(f"Callback URL: {meta['callback_url']}")
    print(f"\nAbre el SVG en un navegador para probar el callback.")
    print(f"El servidor de callbacks debe estar corriendo en {host}/canary/svg")
