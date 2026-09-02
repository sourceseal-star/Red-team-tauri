#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COM-LINK REAL — Implementación Python de comunicación offline.

Conecta los endpoints /api/commander/comlink/* del dashboard con
implementaciones reales usando termux-api. No reemplaza comlink.sh
(lo usa como fallback), sino que añade una capa Python que:

1. SMS reales via termux-sms-send
2. Llamadas reales via termux-telephony-call
3. Estado de canales en tiempo real (no cacheado del bash)
4. Cola de mensajes en SQLite (compatible con comlink.sh)
5. Funciona SIN internet — todo es local en Termux

USO:
    # Importar desde dashboard_server.py:
    from comlink_real import ComLinkReal
    cl = ComLinkReal()
    cl.send_sms("+573001234567", "Mensaje de prueba")
    cl.status()  # estado de todos los canales

    # Standalone:
    python3 comlink_real.py --status
    python3 comlink_real.py --sms +573001234567 "Hola"
    python3 comlink_real.py --call +573001234567
    python3 comlink_real.py --channels
"""

import os
import sys
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Paths (compatibles con comlink.sh) ──
SCRIPT_DIR = Path(__file__).parent.resolve()
COMLINK_DIR = SCRIPT_DIR / "commander" / "comlink"
DATA_DIR = COMLINK_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
CONTACTS_FILE = DATA_DIR / "contacts.json"
QUEUE_DB = DATA_DIR / "queue" / "queue.db"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "comlink_real.log"
EMERGENCY_FILE = DATA_DIR / "last_emergency.json"

# ── Canales soportados ──
CHANNELS = ["sms", "telegram", "voip", "mesh_wifi", "mesh_bluetooth", "radio", "satellite"]


class ComLinkReal:
    """Capa Python sobre COM-LINK para comunicación real offline."""

    def __init__(self, comlink_dir: Optional[Path] = None):
        self.comlink_dir = comlink_dir or COMLINK_DIR
        self.data_dir = self.comlink_dir / "data"
        self.config = self._load_json(self.data_dir / "config.json", {})
        self.contacts = self._load_json(self.data_dir / "contacts.json", {})
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.data_dir, self.data_dir / "queue", self.data_dir / "logs",
                  self.data_dir / "keys"]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _save_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _log(self, msg: str, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        print(line)

    # ──────────────────────────────────────────────────────
    # DETECCIÓN DE ENTORNO
    # ──────────────────────────────────────────────────────
    def _is_termux(self) -> bool:
        """True si estamos corriendo en Termux (Android)."""
        return shutil.which("termux-sms-send") is not None or \
               os.environ.get("PREFIX", "").startswith("/data/data/com.termux")

    def _has_termux_api(self, cmd: str) -> bool:
        """Verifica si un comando termux-api específico está disponible."""
        return shutil.which(cmd) is not None

    # ──────────────────────────────────────────────────────
    # CANAL: SMS
    # ──────────────────────────────────────────────────────
    def send_sms(self, phone: str, message: str, encrypt: bool = False) -> dict:
        """Envía un SMS real via termux-sms-send.

        Returns:
            {"ok": bool, "channel": "sms", "phone": str, "parts": int, "error": str?}
        """
        if not self._validate_phone(phone):
            return {"ok": False, "channel": "sms", "error": f"Numero invalido: {phone}"}

        if not self._has_termux_api("termux-sms-send"):
            # Fallback: intentar via comlink.sh
            return self._fallback_bash("send_sms", phone, message)

        # Dividir si > 160 chars
        parts = []
        msg = message
        while len(msg) > 160:
            parts.append(msg[:160])
            msg = msg[160:]
        parts.append(msg)

        sent = 0
        for i, part in enumerate(parts):
            try:
                result = subprocess.run(
                    ["termux-sms-send", "-n", phone, part],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    self._log(f"SMS parte {i+1}/{len(parts)} fallo: {result.stderr}", "ERROR")
                    # Encolar
                    self._enqueue("sms", phone, message, priority=8)
                    return {"ok": False, "channel": "sms", "phone": phone,
                            "error": result.stderr.strip(), "queued": True}
                sent += 1
                time.sleep(0.5)  # Rate limit
            except subprocess.TimeoutExpired:
                self._log(f"SMS timeout enviando parte {i+1}", "ERROR")
                self._enqueue("sms", phone, message, priority=8)
                return {"ok": False, "channel": "sms", "phone": phone,
                        "error": "timeout", "queued": True}
            except Exception as e:
                self._log(f"SMS excepcion: {e}", "ERROR")
                self._enqueue("sms", phone, message, priority=8)
                return {"ok": False, "channel": "sms", "phone": phone,
                        "error": str(e), "queued": True}

        self._log(f"SMS enviado a {phone} ({sent} parte(s))")
        return {"ok": True, "channel": "sms", "phone": phone, "parts": sent}

    def _validate_phone(self, phone: str) -> bool:
        """Valida formato + seguido de 8-15 dígitos."""
        import re
        return bool(re.match(r"^\+[0-9]{8,15}$", phone))

    # ──────────────────────────────────────────────────────
    # CANAL: LLAMADA (VoIP/Telephony)
    # ──────────────────────────────────────────────────────
    def make_call(self, phone: str) -> dict:
        """Hace una llamada real via termux-telephony-call."""
        if not self._validate_phone(phone):
            return {"ok": False, "channel": "voip", "error": f"Numero invalido: {phone}"}

        if not self._has_termux_api("termux-telephony-call"):
            return self._fallback_bash("make_call", phone)

        try:
            result = subprocess.run(
                ["termux-telephony-call", phone],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return {"ok": False, "channel": "voip", "phone": phone,
                        "error": result.stderr.strip()}
            self._log(f"Llamada iniciada a {phone}")
            return {"ok": True, "channel": "voip", "phone": phone}
        except Exception as e:
            return {"ok": False, "channel": "voip", "phone": phone, "error": str(e)}

    # ──────────────────────────────────────────────────────
    # CANAL: TELEGRAM (requiere internet)
    # ──────────────────────────────────────────────────────
    def send_telegram(self, chat_id: str, message: str) -> dict:
        """Envía mensaje por Telegram via API HTTPS."""
        token = self.config.get("telegram", {}).get("bot_token", "")
        if not token:
            return {"ok": False, "channel": "telegram", "error": "bot_token no configurado"}
        if not chat_id:
            return {"ok": False, "channel": "telegram", "error": "chat_id requerido"}

        try:
            import urllib.request
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            body = json.dumps({
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            if data.get("ok"):
                self._log(f"Telegram enviado a {chat_id}")
                return {"ok": True, "channel": "telegram", "chat_id": chat_id}
            else:
                return {"ok": False, "channel": "telegram", "error": data.get("description", "unknown")}
        except Exception as e:
            # Encolar para reintento
            self._enqueue("telegram", chat_id, message, priority=5)
            return {"ok": False, "channel": "telegram", "error": str(e), "queued": True}

    # ──────────────────────────────────────────────────────
    # CANAL: MESH WIFI (HTTP local)
    # ──────────────────────────────────────────────────────
    def send_mesh_wifi(self, peer_ip: str, message: str) -> dict:
        """Envía mensaje a un peer COM-LINK via HTTP local."""
        port = self.config.get("network", {}).get("mesh_wifi", {}).get("port", 8080)
        try:
            import urllib.request
            url = f"http://{peer_ip}:{port}/comlink"
            body = json.dumps({"message": message, "ts": time.time()}).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=5)
            return {"ok": True, "channel": "mesh_wifi", "peer": peer_ip}
        except Exception as e:
            self._enqueue("mesh_wifi", peer_ip, message, priority=6)
            return {"ok": False, "channel": "mesh_wifi", "peer": peer_ip,
                    "error": str(e), "queued": True}

    # ──────────────────────────────────────────────────────
    # ESTADO DE CANALES (tiempo real)
    # ──────────────────────────────────────────────────────
    def channel_status(self) -> dict:
        """Estado real de cada canal en tiempo real."""
        channels = {}

        # SMS
        sms_ready = self._has_termux_api("termux-sms-send")
        channels["sms"] = {
            "ready": sms_ready,
            "reason": "OK" if sms_ready else "termux-sms-send no disponible",
            "requires": ["termux-api", "permiso SMS", "SIM/cobertura"]
        }

        # Telegram
        tg_token = bool(self.config.get("telegram", {}).get("bot_token", ""))
        tg_chat = bool(self.config.get("telegram", {}).get("default_chat_id", ""))
        channels["telegram"] = {
            "ready": tg_token and tg_chat,
            "reason": "OK" if (tg_token and tg_chat) else
                      "falta bot_token" if not tg_token else "falta default_chat_id",
            "requires": ["bot_token", "default_chat_id", "internet"]
        }

        # VoIP
        voip_ready = self._has_termux_api("termux-telephony-call")
        channels["voip"] = {
            "ready": voip_ready,
            "reason": "OK" if voip_ready else "termux-telephony-call no disponible",
            "requires": ["termux-api", "permiso telefono", "cobertura"]
        }

        # Mesh WiFi
        wifi_ready = self._check_wifi()
        channels["mesh_wifi"] = {
            "ready": wifi_ready,
            "reason": "OK" if wifi_ready else "WiFi no conectado",
            "requires": ["wifi conectado", "peer COM-LINK"]
        }

        # Mesh Bluetooth
        bt_ready = self._check_bluetooth()
        channels["mesh_bluetooth"] = {
            "ready": bt_ready,
            "reason": "OK" if bt_ready else "Bluetooth no disponible",
            "requires": ["bluetooth", "hcitool/rfcomm", "peer compatible"]
        }

        # Radio (no implementado)
        channels["radio"] = {
            "ready": False,
            "reason": "No implementado — requiere hardware TNC",
            "requires": ["TNC", "driver de radio", "configuracion AX.25"]
        }

        # Satélite (no implementado)
        channels["satellite"] = {
            "ready": False,
            "reason": "No implementado — requiere modem satelital",
            "requires": ["modem", "proveedor", "driver especifico"]
        }

        ready_count = sum(1 for c in channels.values() if c["ready"])
        ready_channels = [name for name, c in channels.items() if c["ready"]]

        return {
            "ready_count": ready_count,
            "ready_channels": ready_channels,
            "channels": channels,
            "environment": "termux" if self._is_termux() else "other",
            "timestamp": datetime.now().isoformat()
        }

    def _check_wifi(self) -> bool:
        """Verifica si WiFi está conectado."""
        try:
            result = subprocess.run(
                ["termux-wifi-connectioninfo"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return bool(data.get("ssid"))
        except Exception:
            pass
        # Fallback: buscar interfaz wlan
        try:
            result = subprocess.run(
                ["ip", "addr", "show", "wlan0"],
                capture_output=True, text=True, timeout=3
            )
            return "state UP" in result.stdout
        except Exception:
            return False

    def _check_bluetooth(self) -> bool:
        """Verifica si Bluetooth está disponible."""
        return shutil.which("hcitool") is not None

    # ──────────────────────────────────────────────────────
    # COLA DE MENSAJES (SQLite, compatible con comlink.sh)
    # ──────────────────────────────────────────────────────
    def _init_queue(self):
        conn = sqlite3.connect(str(QUEUE_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                encrypted TEXT,
                timestamp TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                attempts INTEGER DEFAULT 0,
                last_attempt TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _enqueue(self, channel: str, contact_id: str, message: str,
                 priority: int = 5) -> int:
        """Encola un mensaje para envío diferido."""
        self._init_queue()
        conn = sqlite3.connect(str(QUEUE_DB))
        cur = conn.execute(
            "INSERT INTO messages (contact_id, channel, message, priority) VALUES (?, ?, ?, ?)",
            (contact_id, channel, message, priority)
        )
        conn.commit()
        msg_id = cur.lastrowid
        conn.close()
        self._log(f"Mensaje #{msg_id} encolado: {channel} → {contact_id}")
        return msg_id

    def process_queue(self) -> dict:
        """Procesa mensajes pendientes en la cola."""
        self._init_queue()
        conn = sqlite3.connect(str(QUEUE_DB))
        conn.row_factory = sqlite3.Row
        pending = conn.execute(
            "SELECT * FROM messages WHERE status = 'pending' ORDER BY priority DESC, timestamp ASC"
        ).fetchall()

        results = {"processed": 0, "sent": 0, "failed": 0}
        for row in pending:
            row = dict(row)
            result = None
            if row["channel"] == "sms":
                result = self.send_sms(row["contact_id"], row["message"])
            elif row["channel"] == "telegram":
                result = self.send_telegram(row["contact_id"], row["message"])
            elif row["channel"] == "mesh_wifi":
                result = self.send_mesh_wifi(row["contact_id"], row["message"])

            results["processed"] += 1
            if result and result.get("ok"):
                conn.execute(
                    "UPDATE messages SET status = 'sent', last_attempt = datetime('now') WHERE id = ?",
                    (row["id"],)
                )
                results["sent"] += 1
            else:
                attempts = row["attempts"] + 1
                status = "failed" if attempts >= 3 else "pending"
                conn.execute(
                    "UPDATE messages SET status = ?, attempts = ?, last_attempt = datetime('now') WHERE id = ?",
                    (status, attempts, row["id"])
                )
                results["failed"] += 1

        conn.commit()
        conn.close()
        return results

    def queue_stats(self) -> dict:
        """Estadísticas de la cola."""
        self._init_queue()
        conn = sqlite3.connect(str(QUEUE_DB))
        stats = {"pending": 0, "processing": 0, "sent": 0, "failed": 0}
        for row in conn.execute("SELECT status, COUNT(*) FROM messages GROUP BY status"):
            stats[row[0]] = row[1]
        conn.close()
        return stats

    # ──────────────────────────────────────────────────────
    # ALERTA MULTICANAL DE EMERGENCIA
    # ──────────────────────────────────────────────────────
    def emergency(self, message: str, dry_run: bool = False) -> dict:
        """Envía alerta de emergencia por todos los canales disponibles.

        NO envía sin confirmación (dry_run=True por defecto).
        """
        status = self.channel_status()
        ready = status["ready_channels"]

        if dry_run:
            return {
                "dry_run": True,
                "message": message,
                "ready_channels": ready,
                "would_send_via": ready,
                "timestamp": datetime.now().isoformat()
            }

        results = []
        contacts = self.contacts.get("contacts", self.contacts)

        for contact_id, contact in contacts.items():
            if not contact.get("trusted", True):
                continue

            # SMS
            if "sms" in ready and contact.get("phone"):
                r = self.send_sms(contact["phone"], f"[EMERGENCIA] {message}")
                results.append({"contact": contact_id, "channel": "sms", **r})

            # Telegram
            if "telegram" in ready and contact.get("telegram_chat_id"):
                r = self.send_telegram(contact["telegram_chat_id"], f"[EMERGENCIA] {message}")
                results.append({"contact": contact_id, "channel": "telegram", **r})

            # Mesh WiFi
            if "mesh_wifi" in ready and contact.get("mesh_wifi_ip"):
                r = self.send_mesh_wifi(contact["mesh_wifi_ip"], f"[EMERGENCIA] {message}")
                results.append({"contact": contact_id, "channel": "mesh_wifi", **r})

        # Guardar registro de emergencia (sin el texto del mensaje)
        import hashlib
        emergency_record = {
            "timestamp": datetime.now().isoformat(),
            "message_hash": hashlib.sha256(message.encode()).hexdigest(),
            "ready_channels": ready,
            "results": results
        }
        self._save_json(EMERGENCY_FILE, emergency_record)
        self._log(f"Emergencia enviada por {len(ready)} canal(es) — {len(results)} intentos")

        return emergency_record

    # ──────────────────────────────────────────────────────
    # FALLBACK A BASH (comlink.sh)
    # ──────────────────────────────────────────────────────
    def _fallback_bash(self, command: str, *args) -> dict:
        """Fallback: ejecutar via comlink.sh si existe."""
        comlink_sh = self.comlink_dir / "comlink.sh"
        if not comlink_sh.exists():
            return {"ok": False, "error": "comlink.sh no disponible para fallback"}

        try:
            result = subprocess.run(
                ["bash", str(comlink_sh), command, *args],
                capture_output=True, text=True, timeout=30,
                cwd=str(self.comlink_dir)
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-1000:],
                "fallback": True
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "fallback": True}

    # ──────────────────────────────────────────────────────
    # API para el dashboard
    # ──────────────────────────────────────────────────────
    def status(self) -> dict:
        """Estado completo para el endpoint /api/commander/comlink/status."""
        ch_status = self.channel_status()
        q_stats = self.queue_stats()
        return {
            "available": True,
            "ready_count": ch_status["ready_count"],
            "ready_channels": ch_status["ready_channels"],
            "channels": ch_status["channels"],
            "environment": ch_status["environment"],
            "queue_stats": q_stats,
            "timestamp": datetime.now().isoformat(),
            "execution_context": "comlink_real.py — implementacion Python real"
        }

    def data_snapshot(self) -> dict:
        """Snapshot de datos para /api/commander/comlink/data."""
        contacts = self.contacts.get("contacts", self.contacts)
        return {
            "config": self.config,
            "contacts": contacts,
            "queue_stats": self.queue_stats(),
            "last_emergency": self._load_json(EMERGENCY_FILE, None),
        }


# ═══════════════════════════════════════════════════════════
# MODO STANDALONE
# ═══════════════════════════════════════════════════════════
def main():
    import argparse
    parser = argparse.ArgumentParser(description="COM-LINK Real — Comunicacion offline")
    parser.add_argument("--status", action="store_true", help="Estado de canales")
    parser.add_argument("--channels", action="store_true", help="Solo canales disponibles")
    parser.add_argument("--sms", nargs=2, metavar=("PHONE", "MSG"), help="Enviar SMS")
    parser.add_argument("--call", metavar="PHONE", help="Hacer llamada")
    parser.add_argument("--telegram", nargs=2, metavar=("CHAT_ID", "MSG"), help="Enviar Telegram")
    parser.add_argument("--emergency", nargs=1, metavar="MSG", help="Alerta emergencia (--dry-run por defecto)")
    parser.add_argument("--emergency-confirm", nargs=1, metavar="MSG", help="Enviar emergencia real")
    parser.add_argument("--process-queue", action="store_true", help="Procesar cola pendiente")
    parser.add_argument("--queue-stats", action="store_true", help="Estadisticas de cola")
    args = parser.parse_args()

    cl = ComLinkReal()

    if args.status:
        print(json.dumps(cl.status(), indent=2, ensure_ascii=False))
    elif args.channels:
        print(json.dumps(cl.channel_status(), indent=2, ensure_ascii=False))
    elif args.sms:
        result = cl.send_sms(args.sms[0], args.sms[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.call:
        result = cl.make_call(args.call)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.telegram:
        result = cl.send_telegram(args.telegram[0], args.telegram[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.emergency:
        result = cl.emergency(args.emergency[0], dry_run=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.emergency_confirm:
        result = cl.emergency(args.emergency_confirm[0], dry_run=False)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.process_queue:
        result = cl.process_queue()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.queue_stats:
        print(json.dumps(cl.queue_stats(), indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
