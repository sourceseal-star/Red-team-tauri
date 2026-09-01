#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL TELEGRAM BRIDGE — Sol en Telegram v2
=========================================
Poller de Telegram que expone a Sol, la asistente operativa de Red-team-tauri,
como interfaz conversacional. Motor de escaneo/reportes: Seal IA (por debajo).

IMPORTANTE: usa un TELEGRAM_BOT_TOKEN DEDICADO, creado con @BotFather solo
para este bot. NUNCA reutilices el token del SealBot de negocio (origenprogreso/
sourceseal.co) — correr dos pollers de getUpdates sobre el mismo token causa
respuestas mezcladas e impredecibles (Telegram reparte los updates entre
quien pida primero, sin coordinación entre procesos).

Características:
- Escaneos asíncronos (Telegram no se bloquea)
- Candado global: un solo escaneo a la vez
- Whitelist de user_ids autorizados
- Cadena de custodia (ledger SourceSeal)
- Memoria conversacional (~/.sourceseal/seal_chat.json)
- Cambio de alcance con confirmación (30s)
- Entrega de reportes HTML con hash SHA-256 en el caption

Autor: Harold Paredes / SourceSeal Red Team
Uso: nohup python3 sol_telegram_bridge.py > ~/tg.log 2>&1 &
"""

import os
import sys
import json
import time
import hashlib
import threading
import subprocess
import pathlib
import requests
from datetime import datetime
from typing import Dict, Optional, Any

# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = pathlib.Path(__file__).resolve().parent
SEAL_ORCH = ROOT / "seal" / "orchestrator" / "seal_orchestrator.py"
SEAL_SWEEP = ROOT / "seal" / "scanners" / "network_sweep_ultimate.py"
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHAT_MEM_FILE = pathlib.Path.home() / ".sourceseal" / "seal_chat.json"
CHAT_MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
LEDGER_FILE = pathlib.Path.home() / ".sourceseal" / "seal_ledger.json"
LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)

# Env vars (cargadas desde .env por el launcher)
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
ALLOWED_USERS_RAW = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
SEAL_NETWORK = os.environ.get("SEAL_NETWORK", "192.168.1.0/24")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
ENV_FILE = ROOT / ".env"

# Whitelist de usuarios
ALLOWED_USERS: set = set()
for u in ALLOWED_USERS_RAW.replace(",", " ").split():
    u = u.strip()
    if u.lstrip("-").isdigit():
        ALLOWED_USERS.add(int(u))

# Candado global de escaneos
SCAN_LOCK = threading.Lock()

# Pendientes de confirmación de engagement
ENGAGEMENT_PENDING: Dict[int, Dict] = {}  # {uid: {net, ts}}

# ============================================================
# UTILIDADES
# ============================================================

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def is_allowed(uid: int) -> bool:
    """Verifica si un user_id está en la whitelist."""
    if not ALLOWED_USERS:
        # Si no hay whitelist configurada, permitir solo al chat_id default
        if TG_CHAT and str(uid) == str(TG_CHAT):
            return True
        return False
    return uid in ALLOWED_USERS


def load_env() -> None:
    """Carga variables desde .env si no están ya en el entorno."""
    global TG_TOKEN, TG_CHAT, ALLOWED_USERS_RAW, SEAL_NETWORK, LLM_API_KEY, ALLOWED_USERS
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    # Recargar config
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
    ALLOWED_USERS_RAW = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    SEAL_NETWORK = os.environ.get("SEAL_NETWORK", "192.168.1.0/24")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    ALLOWED_USERS = set()
    for u in ALLOWED_USERS_RAW.replace(",", " ").split():
        u = u.strip()
        if u.lstrip("-").isdigit():
            ALLOWED_USERS.add(int(u))


def send_message(text: str, chat_id: Optional[int] = None) -> bool:
    """Envía un mensaje de texto por Telegram."""
    cid = str(chat_id) if chat_id else str(TG_CHAT)
    if not TG_TOKEN or not cid:
        log(f"[send] Sin token o chat_id configurado — texto: {text[:80]}")
        return False
    try:
        # Telegram limita a 4096 chars
        for i in range(0, len(text), 4000):
            chunk = text[i:i+4000]
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": cid, "text": chunk, "parse_mode": "HTML"},
                timeout=15,
            )
            if not r.ok:
                # Reintentar sin parse_mode
                requests.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": cid, "text": chunk},
                    timeout=15,
                )
        return True
    except Exception as e:
        log(f"[send] Error: {e}")
        return False


def send_document(filepath: pathlib.Path, chat_id: Optional[int] = None,
                  caption: str = "") -> bool:
    """Envía un documento por Telegram."""
    cid = str(chat_id) if chat_id else str(TG_CHAT)
    if not TG_TOKEN or not cid:
        return False
    try:
        with open(filepath, "rb") as fh:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                data={"chat_id": cid, "caption": caption[:1024]},
                files={"document": (filepath.name, fh, "text/html")},
                timeout=60,
            )
        return r.ok
    except Exception as e:
        log(f"[send_document] Error: {e}")
        return False


# ============================================================
# LEDGER (cadena de custodia SourceSeal)
# ============================================================

def seal_ledger(action: str, data: Dict[str, Any]) -> str:
    """
    Sella un evento al ledger local de SourceSeal.
    Cada sello encadena con el hash anterior (cadena de custodia).
    Devuelve el hash del sello creado.
    """
    ledger = []
    if LEDGER_FILE.exists():
        try:
            with open(LEDGER_FILE) as f:
                ledger = json.load(f)
        except Exception:
            ledger = []

    # Hash anterior (cadena)
    prev_hash = ledger[-1]["seal_hash"] if ledger else "0" * 64

    # Datos del sello
    entry = {
        "action": action,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prev_hash": prev_hash,
    }

    # Hash del sello
    seal_str = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    seal_hash = hashlib.sha256(seal_str.encode()).hexdigest()
    entry["seal_hash"] = seal_hash

    ledger.append(entry)

    # Guardar (mantener últimos 500)
    if len(ledger) > 500:
        ledger = ledger[-500:]
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

    log(f"[ledger] Sello {action} → {seal_hash[:16]}…")
    return seal_hash


def get_ledger_summary() -> Dict[str, Any]:
    """Resumen del ledger."""
    if not LEDGER_FILE.exists():
        return {"count": 0, "last_hash": None, "actions": {}}
    try:
        with open(LEDGER_FILE) as f:
            ledger = json.load(f)
    except Exception:
        return {"count": 0, "last_hash": None, "actions": {}}

    actions = {}
    for e in ledger:
        a = e.get("action", "?")
        actions[a] = actions.get(a, 0) + 1

    return {
        "count": len(ledger),
        "last_hash": ledger[-1]["seal_hash"] if ledger else None,
        "actions": actions,
    }


def get_last_seal_by_action(action: str) -> Optional[Dict]:
    """Último sello de un tipo específico."""
    if not LEDGER_FILE.exists():
        return None
    try:
        with open(LEDGER_FILE) as f:
            ledger = json.load(f)
    except Exception:
        return None
    for e in reversed(ledger):
        if e.get("action") == action:
            return e
    return None


# ============================================================
# MEMORIA CONVERSACIONAL
# ============================================================

def load_chat_memory() -> list:
    """Carga el historial de chat (últimos 8 mensajes)."""
    if not CHAT_MEM_FILE.exists():
        return []
    try:
        with open(CHAT_MEM_FILE) as f:
            return json.load(f)[-8:]
    except Exception:
        return []


def save_chat_memory(messages: list) -> None:
    """Guarda el historial de chat (últimos 16 mensajes)."""
    try:
        with open(CHAT_MEM_FILE, "w") as f:
            json.dump(messages[-16:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"[chat_mem] Error guardando: {e}")


# ============================================================
# RESPUESTA OFFLINE (sin LLM)
# ============================================================

def offline_response(text: str, uid: int) -> str:
    """
    Genera una respuesta desde la base de conocimiento local de Seal IA.
    No usa LLM — usa el knowledge.py + respuestas pre-estructuradas.
    """
    text_lower = text.lower().strip()

    # Saludos
    if any(w in text_lower for w in ["hola", "buenas", "hey", "saludos", "qué tal", "que tal"]):
        return ("☀️ ¡Hola! Soy Sol, la asistente operativa de Red-team-tauri.\n\n"
                "Manejo escaneos de red, reportes sellados y cadena de custodia.\n"
                "Por debajo corre el motor Seal IA 🦭 — Usa /seal para ver mis comandos.")

    # Quién eres
    if any(w in text_lower for w in ["quién eres", "quien eres", "qué eres", "que eres", "tu nombre"]):
        return ("☀️ Soy Sol, tu asistente operativa de Red-team-tauri.\n"
                "Vigilo tu red, escaneo dispositivos, genero reportes con cadena de custodia,\n"
                "y converso contigo sobre seguridad ofensiva y defensiva.\n\n"
                "Por debajo uso el motor Seal IA 🦭. Sin LLM_API_KEY trabajo con\n"
                "reflejos tácticos — con ella, pienso con contexto MITRE ATT&CK.\n\n"
                "(Si buscas planes, precios o el sello Ciudadano/Pro, eso lo maneja\n"
                "otro bot — @SealBot en sourceseal.co, no yo.)")

    # Ayuda
    if any(w in text_lower for w in ["ayuda", "help", "comandos", "qué puedes hacer", "que puedes hacer"]):
        return _help_text()

    # Sobre SourceSeal
    if "sourceseal" in text_lower or "source seal" in text_lower:
        return ("🔐 SourceSeal Global Protocol — plataforma de sellos de integridad digital\n"
                "basada en SHA-256, ZKP y anclaje Bitcoin (OpenTimestamps).\n\n"
                "Cada operación que hago (escaneos, cambios de alcance, reportes)\n"
                "se sella a una cadena de custodia local verificable con /chain.")

    # Red / red
    if text_lower in ["red", "la red", "mi red", "estado de red", "estado red"]:
        return f"🌐 Alcance actual autorizado: {SEAL_NETWORK}\nUsa /seal scan para escanear."

    # Default — respuesta táctica con personalidad
    # Intentar importar knowledge para contexto
    try:
        sys.path.insert(0, str(ROOT / "commander"))
        from seal_ia_knowledge import build_system_prompt
        # No ejecutar el LLM, solo indicar el modo
        has_llm = "con IA" if LLM_API_KEY else "offline (reflejos tácticos)"
        return (f"☀️ Recibido. Estoy en modo {has_llm}.\n\n"
                f"No puedo procesar texto libre en profundidad sin una clave IA configurada,\n"
                f"pero mis comandos operativos están todos disponibles:\n\n"
                f"• /seal scan — escaneo de tu red\n"
                f"• /seal status — estado del orquestador\n"
                f"• /reporte — último reporte HTML\n"
                f"• /chain — cadena de custodia\n"
                f"• /engagement — alcance autorizado\n"
                f"• /cliente — texto para reenviar al cliente\n\n"
                f"Configura LLM_API_KEY en .env para activar razonamiento con contexto MITRE.")
    except Exception:
        return ("☀️ Modo offline. Usa /seal para ver comandos disponibles.\n"
                "Configura LLM_API_KEY en .env para activar IA conversacional.")


def llm_response(text: str, uid: int) -> str:
    """
    Genera una respuesta usando la API de Anthropic si hay LLM_API_KEY.
    """
    if not LLM_API_KEY:
        return offline_response(text, uid)

    try:
        sys.path.insert(0, str(ROOT / "commander"))
        from seal_ia_knowledge import build_system_prompt
        system_prompt = build_system_prompt()

        # Cargar memoria
        history = load_chat_memory()
        history.append({"role": "user", "content": text})

        # Llamar a Anthropic
        import urllib.request

        messages_for_api = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-8:]
        ]

        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages_for_api,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": LLM_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            reply = result["content"][0]["text"]

        # Guardar memoria
        history.append({"role": "assistant", "content": reply})
        save_chat_memory(history)

        return reply

    except Exception as e:
        log(f"[llm] Error: {e} — fallback a offline")
        return offline_response(text, uid)


# ============================================================
# GENERADOR DE REPORTE HTML
# ============================================================

def generate_html_report(scan_file: pathlib.Path, network: str) -> Optional[pathlib.Path]:
    """
    Genera un reporte HTML profesional desde el JSON del escaneo.
    """
    if not scan_file.exists():
        return None

    try:
        with open(scan_file) as f:
            data = json.load(f)
    except Exception:
        return None

    scan = data.get("scan", {})
    targets = data.get("targets", [])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_name = f"reporte_{timestamp}.html"
    report_path = REPORTS_DIR / report_name

    # Estadísticas
    total = scan.get("total_devices", len(targets))
    cameras = scan.get("camera_count", 0)
    routers = scan.get("router_count", 0)
    vulns = scan.get("vulnerable_count", 0)

    # Construir HTML
    rows = ""
    for i, t in enumerate(targets, 1):
        ip = t.get("ip", "?")
        info = t.get("info", {})
        vendor = info.get("vendor", "Unknown")
        dtype = info.get("type", "Unknown")
        os_name = info.get("os", "Unknown")
        model = info.get("model", "")
        services_html = ""
        for s in t.get("services", []):
            port = s.get("port", "?")
            svc = s.get("service", "?")
            vuln = " ⚠️" if s.get("vulnerable") else ""
            services_html += f"<span class='svc'>{port}/{svc}{vuln}</span> "

        row_class = "vuln" if any(s.get("vulnerable") for s in t.get("services", [])) else "ok"
        rows += f"""
        <tr class="{row_class}">
            <td>{i}</td>
            <td><strong>{ip}</strong></td>
            <td>{vendor}</td>
            <td>{dtype}</td>
            <td>{os_name}</td>
            <td>{model}</td>
            <td>{services_html}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte de Auditoría — Seal IA</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0e1a; color: #e0e6ed; padding: 20px; }}
.header {{ text-align: center; padding: 30px; background: linear-gradient(135deg, #1a1f3a, #0d1225); border-radius: 12px; margin-bottom: 20px; }}
.header h1 {{ color: #00d4ff; font-size: 24px; }}
.header .meta {{ color: #7a8a9e; margin-top: 8px; font-size: 14px; }}
.stats {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
.stat {{ flex: 1; min-width: 140px; background: #131a2e; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #1e2845; }}
.stat .num {{ font-size: 28px; font-weight: bold; color: #00d4ff; }}
.stat .lbl {{ font-size: 12px; color: #7a8a9e; margin-top: 4px; }}
.stat.vuln .num {{ color: #ff4757; }}
.stat.cam .num {{ color: #ffa502; }}
table {{ width: 100%; border-collapse: collapse; background: #131a2e; border-radius: 10px; overflow: hidden; }}
th {{ background: #1e2845; padding: 12px; text-align: left; font-size: 13px; color: #7a8a9e; text-transform: uppercase; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #1e2845; font-size: 13px; }}
tr.vuln {{ background: rgba(255,71,87,0.08); }}
.svc {{ display: inline-block; background: #1e2845; padding: 2px 8px; border-radius: 4px; margin: 1px; font-size: 11px; }}
.footer {{ text-align: center; padding: 20px; color: #4a5568; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="header">
    <h1>☀️ Reporte de Auditoría de Seguridad</h1>
    <div class="meta">SourceSeal Red Team — {datetime.now().strftime("%Y-%m-%d %H:%M")} | Alcance: {network}</div>
</div>
<div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="lbl">Dispositivos</div></div>
    <div class="stat cam"><div class="num">{cameras}</div><div class="lbl">Cámaras/DVR</div></div>
    <div class="stat"><div class="num">{routers}</div><div class="lbl">Routers/AP</div></div>
    <div class="stat vuln"><div class="num">{vulns}</div><div class="lbl">Vulnerables</div></div>
</div>
<table>
<thead><tr><th>#</th><th>IP</th><th>Vendor</th><th>Tipo</th><th>OS</th><th>Modelo</th><th>Servicios</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="7" style="text-align:center;padding:40px;color:#7a8a9e">No se encontraron dispositivos con servicios abiertos</td></tr>'}
</tbody>
</table>
<div class="footer">SourceSeal Intelligence — Cadena de custodia verificable con SHA-256</div>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    return report_path


# ============================================================
# COMANDOS
# ============================================================

def _help_text() -> str:
    return (
        "☀️ <b>Sol — Comandos</b>\n\n"
        "/seal — Esta ayuda\n"
        "/seal status — Estado del orquestador\n"
        "/seal scan — Escaneo asíncrono + reporte HTML\n"
        "/seal ultimo — Último sello TG_SCAN\n"
        "/reporte — Enviar último reporte HTML\n"
        "/engagement — Ver alcance autorizado\n"
        "/engagement set X — Cambiar alcance (confirma en 30s)\n"
        "/chain — Cadena de custodia\n"
        "/cliente — Texto listo para reenviar al cliente\n\n"
        "Texto libre — Conversa conmigo, Sol ☀️"
    )


def cmd_seal(uid: int, args: list) -> str:
    """Maneja /seal y subcomandos."""
    if not args:
        return _help_text()

    sub = args[0].lower()

    if sub == "status":
        return _seal_status()

    if sub == "scan":
        return _seal_scan(uid)

    if sub == "ultimo":
        return _seal_ultimo()

    return _help_text()


def _seal_status() -> str:
    """Ejecuta --status del orquestador."""
    try:
        r = subprocess.run(
            [sys.executable, str(SEAL_ORCH), "--status"],
            capture_output=True, text=True, timeout=5,
        )
        out = r.stdout.strip()
        if not out:
            out = r.stderr.strip() or "Sin respuesta"
        # Truncar
        if len(out) > 800:
            out = out[:800] + "\n…"
        return f"```\n{out}\n```"
    except subprocess.TimeoutExpired:
        return "⏱️ Seal IA no respondió en 5s — puede estar iniciándose."
    except Exception as e:
        return f"❌ Error: {str(e)[:200]}"


def _seal_scan(uid: int) -> str:
    """Inicia escaneo asíncrono con candado."""
    if not SCAN_LOCK.acquire(blocking=False):
        return "☀️ Ya hay un escaneo en curso. Te aviso al terminar."

    send_message("☀️ Escaneo iniciado sobre el alcance autorizado. Aviso al terminar (2-5 min).", uid)

    threading.Thread(target=_run_scan, args=(uid,), daemon=True).start()
    return ""  # Ya respondimos con send_message


def _run_scan(uid: int):
    """Ejecuta el escaneo en background."""
    try:
        net = os.environ.get("SEAL_NETWORK", SEAL_NETWORK)
        log(f"[scan] Iniciando escaneo sobre {net}")

        # Escaneo con network_sweep_ultimate
        r = subprocess.run(
            [sys.executable, str(SEAL_SWEEP), "--network", net],
            capture_output=True, text=True, timeout=900,
            cwd=str(ROOT),
        )

        if r.returncode != 0:
            send_message(f"☀️ El escaneo tuvo problemas: {r.stderr[:300]}", uid)
            return

        # Buscar el JSON de salida generado por el escaneo
        json_files = sorted(ROOT.glob("seal_intel_*.json"))
        if not json_files:
            # El escaneo puede no haber encontrado dispositivos
            send_message("☀️ Escaneo completado. No se encontraron dispositivos con servicios abiertos.", uid)
            seal_ledger("TG_SCAN", {"net": net, "status": "no_devices", "report": None})
            return

        scan_file = json_files[-1]

        # Generar reporte HTML
        report_path = generate_html_report(scan_file, net)

        if report_path and report_path.exists():
            h = hashlib.sha256(report_path.read_bytes()).hexdigest()
            send_message("☀️ Escaneo completo. Reporte generado y sellado.", uid)
            caption = (
                f"📄 {report_path.name}\n"
                f"🔗 SHA-256: {h[:32]}…\n"
                f"⚖️ Alcance: {net}"
            )
            send_document(report_path, uid, caption=caption)
            seal_ledger("TG_SCAN", {
                "net": net,
                "report": report_path.name,
                "sha256": h,
            })
        else:
            send_message("☀️ Escaneo completado pero no se pudo generar el reporte.", uid)
            seal_ledger("TG_SCAN", {"net": net, "status": "report_failed"})

    except subprocess.TimeoutExpired:
        send_message("☀️ El escaneo superó los 15 min — cancelado.", uid)
    except Exception as e:
        send_message(f"☀️ Error en escaneo: {str(e)[:300]}", uid)
    finally:
        SCAN_LOCK.release()
        log("[scan] Candado liberado")


def _seal_ultimo() -> str:
    """Muestra el último sello TG_SCAN."""
    last = get_last_seal_by_action("TG_SCAN")
    if not last:
        return "☀️ No hay sellos TG_SCAN aún. Ejecuta /seal scan."

    d = last.get("data", {})
    ts = last.get("timestamp", "?")
    h = last.get("seal_hash", "?")
    return (
        f"☀️ <b>Último sello TG_SCAN</b>\n\n"
        f"📅 {ts}\n"
        f"🌐 Alcance: {d.get('net', '?')}\n"
        f"📄 Reporte: {d.get('report', '—')}\n"
        f"🔗 SHA-256: {h[:32]}…"
    )


def cmd_reporte(uid: int) -> str:
    """Envía el último reporte HTML."""
    reports = sorted(REPORTS_DIR.glob("reporte_*.html"))
    if not reports:
        return "☀️ No hay reportes generados aún. Ejecuta /seal scan primero."

    last = reports[-1]
    h = hashlib.sha256(last.read_bytes()).hexdigest()
    caption = f"📄 {last.name}\n🔗 SHA-256: {h[:32]}…"
    sent = send_document(last, uid, caption=caption)
    if sent:
        return ""
    return "☀️ No se pudo enviar el reporte. Verifica conexión."


def cmd_engagement(uid: int, args: list) -> str:
    """Gestiona el alcance de escaneo."""
    if not args:
        return (
            f"☀️ <b>Alcance autorizado actual</b>\n\n"
            f"🌐 {os.environ.get('SEAL_NETWORK', SEAL_NETWORK)}\n\n"
            f"Para cambiar: /engagement set <red/CIDR>\n"
            f"Ejemplo: /engagement set 10.0.0.0/24"
        )

    if args[0].lower() == "set":
        if len(args) < 2:
            return "☀️ Uso: /engagement set <red/CIDR>\nEjemplo: /engagement set 10.0.0.0/24"

        new_net = args[1]
        # Validar formato básico de CIDR
        if "/" not in new_net:
            return "☀️ Formato inválido. Usa notación CIDR: 192.168.1.0/24"

        # Guardar pendiente y pedir confirmación
        ENGAGEMENT_PENDING[uid] = {"net": new_net, "ts": time.time()}
        return (
            f"☀️ <b>Confirmación requerida</b>\n\n"
            f"Cambio de alcance: {os.environ.get('SEAL_NETWORK', SEAL_NETWORK)} → <code>{new_net}</code>\n\n"
            f"⚠️ Esto se sellará al ledger como ENGAGEMENT_CHANGE.\n"
            f"Responde <b>si</b> en los próximos 30 segundos para confirmar."
        )

    return "☀️ Uso: /engagement o /engagement set <red/CIDR>"


def _check_engagement_confirm(uid: int, text: str) -> Optional[str]:
    """Verifica si el texto es confirmación de engagement pendiente."""
    if uid not in ENGAGEMENT_PENDING:
        return None

    pending = ENGAGEMENT_PENDING[uid]
    elapsed = time.time() - pending["ts"]

    if elapsed > 30:
        del ENGAGEMENT_PENDING[uid]
        return "☀️ La confirmación expiró (30s). El alcance NO cambió."

    if text.strip().lower() == "si":
        new_net = pending["net"]
        del ENGAGEMENT_PENDING[uid]

        # Escribir en .env (sed seguro)
        try:
            if ENV_FILE.exists():
                content = ENV_FILE.read_text()
                if "SEAL_NETWORK=" in content:
                    # Reemplazar línea existente
                    import re
                    content = re.sub(
                        r'^SEAL_NETWORK=.*$',
                        f'SEAL_NETWORK={new_net}',
                        content,
                        flags=re.MULTILINE,
                    )
                    ENV_FILE.write_text(content)
                else:
                    # Añadir si no existe
                    with open(ENV_FILE, "a") as f:
                        f.write(f"\nSEAL_NETWORK={new_net}\n")

                # Asegurar permisos 600
                os.chmod(ENV_FILE, 0o600)
                os.environ["SEAL_NETWORK"] = new_net
            else:
                return "☀️ .env no encontrado. No se pudo cambiar el alcance."

        except Exception as e:
            return f"☀️ Error escribiendo .env: {str(e)[:200]}"

        # Sellar al ledger
        seal_ledger("ENGAGEMENT_CHANGE", {
            "old": os.environ.get("SEAL_NETWORK", new_net),
            "new": new_net,
            "user_id": uid,
        })

        return f"☀️ Alcance actualizado y sellado: {new_net}"

    if text.strip().lower() in ["no", "cancelar", "cancel"]:
        del ENGAGEMENT_PENDING[uid]
        return "☀️ Cambio cancelado. El alcance NO cambió."

    return None


def cmd_chain() -> str:
    """Muestra la cadena de custodia."""
    summary = get_ledger_summary()
    if summary["count"] == 0:
        return "☀️ No hay sellos en el ledger. Ejecuta /seal scan para generar el primero."

    actions_str = "\n".join(
        f"  • {k}: {v}" for k, v in summary["actions"].items()
    )
    last_hash = summary["last_hash"][:32] + "…" if summary["last_hash"] else "—"

    return (
        f"☀️ <b>Cadena de Custodia SourceSeal</b>\n\n"
        f"📦 Total de sellos: {summary['count']}\n"
        f"🔗 Último hash: <code>{last_hash}</code>\n\n"
        f"<b>Por tipo:</b>\n{actions_str}"
    )


def cmd_cliente(uid: int) -> str:
    """Genera texto profesional listo para reenviar al cliente."""
    net = os.environ.get("SEAL_NETWORK", SEAL_NETWORK)
    reports = sorted(REPORTS_DIR.glob("reporte_*.html"))

    if reports:
        last = reports[-1]
        h = hashlib.sha256(last.read_bytes()).hexdigest()
        h_short = h[:16]
    else:
        h_short = "(sin reporte aún)"

    return (
        f"☀️ <b>Texto para el cliente</b> (copia y reenvía):\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Hola. Adjunto el reporte de auditoría de seguridad de su infraestructura.\n"
        f"Alcance autorizado: {net}.\n"
        f"Integridad verificable: SHA-256 {h_short}….\n"
        f"Quedo atento para revisar hallazgos y recomendaciones.\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )


# ============================================================
# POLLER PRINCIPAL
# ============================================================

def process_message(text: str, uid: int, update_id: int) -> bool:
    """
    Procesa un mensaje entrante. Devuelve True si se manejó.
    """
    text = text.strip()
    if not text:
        return False

    # Whitelist
    if not is_allowed(uid):
        log(f"[auth] User {uid} no autorizado — ignorando")
        return False

    # Verificar confirmación de engagement pendiente primero
    eng_response = _check_engagement_confirm(uid, text)
    if eng_response:
        send_message(eng_response, uid)
        return True

    # Comandos
    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/seal":
        response = cmd_seal(uid, args)
        if response:
            send_message(response, uid)
        return True

    if cmd == "/reporte":
        response = cmd_reporte(uid)
        if response:
            send_message(response, uid)
        return True

    if cmd == "/engagement":
        response = cmd_engagement(uid, args)
        if response:
            send_message(response, uid)
        return True

    if cmd == "/chain":
        send_message(cmd_chain(), uid)
        return True

    if cmd == "/cliente":
        send_message(cmd_cliente(uid), uid)
        return True

    if cmd.startswith("/"):
        # Comando no reconocido
        send_message("☀️ Comando no reconocido. Usa /seal para ver los disponibles.", uid)
        return True

    # Texto libre — conversación con Seal IA
    response = llm_response(text, uid)
    send_message(response, uid)

    # Guardar en memoria
    history = load_chat_memory()
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    save_chat_memory(history)

    return True


def run_poller():
    """Bucle principal del poller de Telegram."""
    if not TG_TOKEN:
        log("❌ TELEGRAM_BOT_TOKEN no configurado. Carga .env primero:")
        log("   set -a; . ./.env; set +a")
        sys.exit(1)

    log("☀️ Sol Telegram Bridge v2 iniciando...")
    log(f"   Alcance: {os.environ.get('SEAL_NETWORK', SEAL_NETWORK)}")
    log(f"   LLM: {'activado' if LLM_API_KEY else 'offline (reflejos tácticos)'}")
    log(f"   Whitelist: {len(ALLOWED_USERS)} usuarios" if ALLOWED_USERS else "   Whitelist: chat_id default")

    # Verificar que el orquestador existe
    if not SEAL_ORCH.exists():
        log(f"⚠️  Orquestador no encontrado en {SEAL_ORCH}")

    if not SEAL_SWEEP.exists():
        log(f"⚠️  Scanner no encontrado en {SEAL_SWEEP}")

    BASE_URL = f"https://api.telegram.org/bot{TG_TOKEN}"
    offset = 0
    log("✅ Poller activo. Esperando mensajes...")

    while True:
        try:
            r = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )

            if not r.ok:
                log(f"[poller] Error HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(5)
                continue

            data = r.json()
            if not data.get("ok"):
                log(f"[poller] Respuesta no ok: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])
            for update in updates:
                offset = update["update_id"] + 1

                msg = update.get("message")
                if not msg:
                    continue

                text = msg.get("text", "")
                uid = msg.get("from", {}).get("id", 0)
                uname = msg.get("from", {}).get("first_name", "?")

                if not text:
                    continue

                log(f"📩 [{uname}({uid})] {text[:80]}")

                try:
                    process_message(text, uid, update["update_id"])
                except Exception as e:
                    log(f"[process] Error: {e}")
                    send_message(f"☀️ Error procesando: {str(e)[:200]}", uid)

        except requests.exceptions.Timeout:
            # Normal — long polling
            continue
        except requests.exceptions.ConnectionError:
            log("[poller] Sin conexión — reintentando en 10s...")
            time.sleep(10)
        except KeyboardInterrupt:
            log("☀️ Deteniendo poller...")
            break
        except Exception as e:
            log(f"[poller] Error inesperado: {e}")
            time.sleep(5)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Cargar .env
    load_env()

    # Re-verificar token después de load_env
    if not TG_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado.")
        print("   Carga .env primero: set -a; . ./.env; set +a")
        sys.exit(1)

    run_poller()
