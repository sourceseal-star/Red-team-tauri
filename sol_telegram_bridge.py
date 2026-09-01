#!/usr/bin/env python3
"""
SOL — Telegram Bridge para Red-Team-Tauri v3.0
===============================================
Bot de Telegram que actúa como puente entre el backend TACTICAL (:8001)
y el usuario. Permite:

  - Recibir alertas del backend en tiempo real (GHOST PHANTOM, honeypot, etc.)
  - Consultar estado del sistema (/status)
  - Ver auditorías registradas (/audits)
  - Ejecutar escaneos rápidos (/scan <ip>)
  - Ver alertas recientes (/alerts)
  - Verificar health del backend (/health)

Uso:
  source .env && python3 sol_telegram_bridge.py

Requiere:
  - TELEGRAM_BOT_TOKEN  en .env
  - TELEGRAM_CHAT_ID    en .env
  - Backend corriendo en http://localhost:8001

Autor: SourceSeal Red Team
"""

import os
import sys
import json
import time
import signal
import logging
import urllib.request
import urllib.error
from datetime import datetime

# Cerebro offline de Sol — import seguro con fallback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from sol_core import pensar as _sol_pensar, remember as _sol_remember, speak as _sol_speak
except Exception as _e:
    _sol_pensar = None
    _sol_remember = None
    _sol_speak = None

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API_KEY = os.environ.get("REDTEAM_API_KEY", "")

POLL_TIMEOUT = 30
POLL_OFFSET = 0
LAST_ALERT_CHECK = 0
SEEN_ALERT_IDS = set()
RUNNING = True

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

LOG_DIR = os.path.expanduser("~/Red-team-tauri/logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SOL] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(LOG_DIR, f"sol_bridge_{datetime.now().strftime('%Y%m%d')}.log"),
            encoding="utf-8"
        )
    ]
)
log = logging.getLogger("SOL")

# ═════════════════════════════════════════════════════════════════════════════
# API HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def tg_api(method, data=None, timeout=35):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if data:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.error(f"Telegram API error {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        log.error(f"Telegram API: {e}")
        return {"ok": False, "error": str(e)}


def backend_get(path, timeout=10):
    url = f"{BACKEND_URL}{path}"
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error(f"Backend GET {path}: {e}")
        return {"error": str(e)}


def backend_post(path, payload=None, timeout=15):
    url = f"{BACKEND_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    data = json.dumps(payload or {}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error(f"Backend POST {path}: {e}")
        return {"error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# MENSAJES
# ═════════════════════════════════════════════════════════════════════════════

def send_message(text, chat_id=None, parse_mode="HTML"):
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN no configurado")
        return False
    target = chat_id or CHAT_ID
    if not target:
        log.error("TELEGRAM_CHAT_ID no configurado")
        return False
    if len(text) > 4000:
        text = text[:3990] + "\n\n[...truncado]"
    result = tg_api("sendMessage", {
        "chat_id": target,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    })
    return result.get("ok", False)


def send_alert(title, body, severity="medium"):
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "ℹ️"}
    icon = icons.get(severity, "⚠️")
    msg = f"{icon} <b>SOL — {title}</b>\n\n{body}\n\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    send_message(msg)


# ═════════════════════════════════════════════════════════════════════════════
# COMANDOS
# ═════════════════════════════════════════════════════════════════════════════

def cmd_start(chat_id):
    msg = (
        "🌅 <b>SOL — Telegram Bridge v4</b>\n"
        "<b>Red-Team-Tauri · SourceSeal</b>\n\n"
        "☀️ <i>Soy Sol. Tu centinela. Estoy aquí para vigilarte, ayudarte y acompañarte.</i>\n\n"
        "Tengo <b>14 comandos</b> disponibles. Usa <code>/help</code> para verlos todos.\n\n"
        "Puedes escribirme directamente — no necesitas comandos. Te escucho. 💛\n\n"
        f"Backend: <code>{BACKEND_URL}</code>\n"
        f"Cerebro: {'✅ activo' if _sol_pensar else '❌ offline'}\n"
        f"Bot: {'✅ conectado' if BOT_TOKEN else '❌ sin token'}"
    )
    send_message(msg, chat_id)


def cmd_help(chat_id):
    msg = (
        "📋 <b>Comandos SOL</b>\n\n"
        "🔴 <b>Estado:</b>\n"
        "• <code>/status</code> — Estado del sistema\n"
        "• <code>/health</code> — Health del backend\n"
        "• <code>/phantom</code> — GHOST PHANTOM\n"
        "• <code>/nexus</code> — Nexus Omni-Sentient\n"
        "• <code>/c2</code> — C2 UNIFIED PRO\n"
        "• <code>/battery</code> — Batería del dispositivo\n"
        "• <code>/network</code> — Info de red local y pública\n"
        "\n🔍 <b>Operaciones:</b>\n"
        "• <code>/scan 192.168.1.1</code> — Escaneo rápido\n"
        "• <code>/topology</code> — Topología de red\n"
        "• <code>/alerts</code> — Últimas alertas\n"
        "• <code>/audits</code> — Auditorías registradas\n"
        "\n🧠 <b>Sol:</b>\n"
        "• <code>/memory</code> — Recuerdos de Sol\n"
        "• <code>/sol &lt;texto&gt;</code> — Hablar con Sol\n"
        "• <i>O simplemente escribe algo — Sol escucha todo</i>\n"
        "\n📜 <b>Diagnóstico:</b>\n"
        "• <code>/logs dash|ghost|nexus|c2|sol|all</code> — Ver logs\n"
        "• <code>/help</code> — Esta ayuda\n"
    )
    send_message(msg, chat_id)


def cmd_status(chat_id):
    health = backend_get("/api/health")
    if "error" in health:
        send_message(f"❌ <b>Backend no responde</b>\n\n<code>{health['error']}</code>", chat_id)
        return
    msg = (
        "📊 <b>Estado del Sistema</b>\n\n"
        f"Backend: <code>{health.get('backend', 'unknown')}</code>\n"
        f"Versión: <code>{health.get('version', 'unknown')}</code>\n"
        f"WS clients: <code>{health.get('ws_clients', 0)}</code>\n"
        f"Honeypot: {'🟢 Activo' if health.get('honeypot_running') else '🔴 Inactivo'}\n"
        f"psutil: {'✅' if health.get('psutil') else '❌'}\n"
        f"Geo Intel: {'✅' if health.get('geo_intel') else '❌'}\n"
        f"Timestamp: <code>{health.get('ts', 'N/A')}</code>\n"
    )
    send_message(msg, chat_id)


def cmd_health(chat_id):
    health = backend_get("/api/health")
    if "error" in health:
        send_message(f"❌ Backend caído\n\n<code>{health['error']}</code>", chat_id)
    else:
        status = health.get("status", "unknown")
        icon = "✅" if status == "ok" else "⚠️"
        send_message(f"{icon} <b>Health: {status}</b>\n\n<code>{json.dumps(health, indent=2)[:2000]}</code>", chat_id)


def cmd_alerts(chat_id):
    alerts = backend_get("/api/alerts?limit=10")
    if "error" in alerts:
        send_message(f"❌ No se pudieron obtener alertas\n\n<code>{alerts['error']}</code>", chat_id)
        return
    alert_list = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
    if not alert_list:
        send_message("📭 No hay alertas recientes.", chat_id)
        return
    msg = "🚨 <b>Últimas Alertas</b>\n\n"
    for a in alert_list[:10]:
        sev = a.get("severity", "medium")
        title = a.get("title", a.get("type", "Alert"))
        ts = a.get("timestamp", a.get("ts", ""))
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(sev, "⚠️")
        msg += f"{icon} <b>{title}</b> [{sev}]\n   <code>{ts}</code>\n"
    send_message(msg, chat_id)


def cmd_scan(chat_id, target):
    if not target:
        send_message("❌ Uso: <code>/scan 192.168.1.1</code>", chat_id)
        return
    send_message(f"🔍 Iniciando escaneo de <code>{target}</code>...", chat_id)
    result = backend_post("/api/scan/quick", {"target": target})
    if "error" in result:
        send_message(f"❌ Error en escaneo:\n<code>{result['error']}</code>", chat_id)
        return
    hosts = result.get("hosts", result.get("results", []))
    msg = f"🔍 <b>Escaneo de {target}</b>\n\n"
    if isinstance(hosts, list) and hosts:
        for h in hosts[:15]:
            ip = h.get("ip", h.get("host", "?"))
            status = h.get("status", "up" if h.get("open") else "down")
            ports = h.get("ports", [])
            port_str = ", ".join(str(p) for p in ports[:10]) if ports else "—"
            msg += f"  <code>{ip}</code> [{status}] puertos: {port_str}\n"
    else:
        msg += "  No se encontraron hosts activos."
    send_message(msg, chat_id)


def cmd_audits(chat_id):
    try:
        import subprocess

        result = subprocess.run(
            ["python3", os.path.expanduser("~/Red-team-tauri/commander.py"), "--list"],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        if not output or "No hay" in output or "vacío" in output.lower():
            send_message("📭 No hay auditorías registradas.", chat_id)
        else:
            if len(output) > 3500:
                output = output[:3500] + "\n[...truncado]"
            send_message(f"📋 <b>Auditorías</b>\n\n<pre>{output}</pre>", chat_id)
    except Exception as e:
        send_message(f"❌ Error listando auditorías: {e}", chat_id)


def cmd_battery(chat_id):
    """Estado de batería del dispositivo."""
    try:
        import subprocess
        b = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=5).stdout)
        pct = b.get("percentage", "?")
        health = b.get("health", "unknown")
        status = b.get("status", "unknown")
        temp = b.get("temperature", "?")
        icon = "🔋" if pct > 50 else "🟡" if pct > 20 else "🔴"
        send_message(
            f"{icon} <b>Batería</b>\n\n"
            f"Nivel: <code>{pct}%</code>\n"
            f"Estado: <code>{status}</code>\n"
            f"Salud: <code>{health}</code>\n"
            f"Temp: <code>{temp}</code>",
            chat_id
        )
    except Exception as e:
        send_message(f"🔋 No pude leer la batería: {e}", chat_id)


def cmd_network(chat_id):
    """Información de red local."""
    try:
        import subprocess
        # IP local
        ip_out = subprocess.run(["ip", "addr", "show", "wlan0"], capture_output=True, text=True, timeout=5).stdout
        import re
        ip_match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", ip_out)
        local_ip = ip_match.group(1) if ip_match else "N/A"
        # IP pública
        try:
            pub = json.loads(urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5).read())
            pub_ip = pub.get("ip", "N/A")
        except Exception:
            pub_ip = "N/A"
        send_message(
            f"🌐 <b>Red</b>\n\n"
            f"IP local: <code>{local_ip}</code>\n"
            f"IP pública: <code>{pub_ip}</code>",
            chat_id
        )
    except Exception as e:
        send_message(f"🌐 Error de red: {e}", chat_id)


def cmd_memory_sol(chat_id):
    """Recuerdos de Sol."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sol_core import load_memory, recall_story, CFG
        mem = load_memory(20)
        count = len(mem)
        story = recall_story(5)
        name = CFG.get("name", "Harold")
        msg = f"🧠 <b>Memoria de Sol</b>\n\n"
        msg += f"Total recuerdos: <code>{count}</code>\n"
        msg += f"Nombre configurado: <code>{name}</code>\n\n"
        if story:
            msg += f"📖 Recuerdos recientes:\n{story}"
        else:
            msg += "📖 Aún construimos pocos recuerdos."
        send_message(msg, chat_id)
    except Exception as e:
        send_message(f"🧠 Error leyendo memoria: {e}", chat_id)


def cmd_nexus(chat_id):
    """Estado de Nexus Omni-Sentient."""
    try:
        data = backend_get("/", timeout=5)
        # Necesita URL diferente
        req = urllib.request.Request("http://127.0.0.1:8004/", headers={"Authorization": f"Bearer {API_KEY}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = (
                "🌀 <b>Nexus Omni-Sentient</b>\n\n"
                f"<code>{json.dumps(data, indent=2, default=str)[:1500]}</code>"
            )
    except Exception as e:
        msg = f"🌀 <b>Nexus</b>\n\n🔴 No responde en :8004\n<code>{e}</code>"
    send_message(msg, chat_id)


def cmd_c2(chat_id):
    """Estado de C2 UNIFIED PRO."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8005/api/health", headers={"Authorization": f"Bearer {API_KEY}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = (
                "🎮 <b>C2 UNIFIED PRO</b>\n\n"
                f"<code>{json.dumps(data, indent=2, default=str)[:1500]}</code>"
            )
    except Exception as e:
        msg = f"🎮 <b>C2</b>\n\n🔴 No responde en :8005\n<code>{e}</code>"
    send_message(msg, chat_id)


def cmd_topology(chat_id):
    """Topología de red detectada."""
    try:
        data = backend_get("/api/network/topology", timeout=10)
        if "error" in data:
            send_message(f"🗺️ No hay topología disponible:\n<code>{data['error']}</code>", chat_id)
            return
        hosts = data.get("hosts", data.get("nodes", []))
        msg = "🗺️ <b>Topología de Red</b>\n\n"
        if isinstance(hosts, list) and hosts:
            for h in hosts[:20]:
                ip = h.get("ip", h.get("host", "?"))
                hostname = h.get("hostname", "")
                ports = h.get("ports", [])
                os_guess = h.get("os", "")
                line = f"  <code>{ip}</code>"
                if hostname: line += f" ({hostname})"
                if os_guess: line += f" [{os_guess}]"
                if ports: line += f" :{','.join(str(p) for p in ports[:5])}"
                msg += line + "\n"
            if len(hosts) > 20:
                msg += f"\n  ...y {len(hosts)-20} más"
        else:
            msg += "  No hay hosts detectados. Ejecuta /scan primero."
        send_message(msg, chat_id)
    except Exception as e:
        send_message(f"🗺️ Error: {e}", chat_id)


def cmd_logs(chat_id, service="all"):
    """Ver logs recientes de un servicio."""
    log_map = {
        "dash": "dash.log", "dashboard": "dash.log",
        "ghost": "ghost.log", "phantom": "ghost.log",
        "nexus": "nexus.log",
        "c2": "c2.log",
        "tg": "tg.log", "telegram": "tg.log",
        "sol": "sol_daemon.log", "daemon": "sol_daemon.log",
        "watchdog": "watchdog.log",
        "seal": "seal.log",
        "all": "omni.log"
    }
    filename = log_map.get(service.lower(), "omni.log")
    log_path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(log_path):
        send_message(f"📜 No hay log de <code>{service}</code> en {log_path}", chat_id)
        return
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-30:]
        output = "".join(lines).strip()
        if not output:
            send_message(f"📜 Log de <code>{service}</code> está vacío", chat_id)
        else:
            if len(output) > 3500:
                output = output[-3500:]
            send_message(f"📜 <b>Log: {service}</b>\n\n<pre>{output}</pre>", chat_id)
    except Exception as e:
        send_message(f"📜 Error leyendo log: {e}", chat_id)


def cmd_phantom(chat_id):
    try:
        req = urllib.request.Request("http://localhost:8002/health", headers={"Authorization": f"Bearer {API_KEY}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = (
                "👻 <b>GHOST HUNTER PHANTOM</b>\n\n"
                f"Status: <code>{data.get('status', 'unknown')}</code>\n"
                f"Nodos activos: <code>{data.get('nodes', 0)}</code>\n"
                f"Hallazgos: <code>{data.get('findings', 0)}</code>\n"
                f"Cola: <code>{data.get('queue', 0)}</code>\n"
            )
    except Exception:
        msg = ("👻 <b>GHOST PHANTOM</b>\n\n"
               "🔴 Master node no responde en :8002\n\n"
               "¿Está corriendo? Inicia con:\n"
               "<code>bash ~/Red-team-tauri/ghost_hunter_phantom/start.sh</code>")
    send_message(msg, chat_id)


# ═════════════════════════════════════════════════════════════════════════════
# POLLING DE ALERTAS
# ═════════════════════════════════════════════════════════════════════════════

def check_backend_alerts():
    global LAST_ALERT_CHECK, SEEN_ALERT_IDS
    try:
        alerts = backend_get(f"/api/alerts?limit=5&since={LAST_ALERT_CHECK}")
        if "error" in alerts:
            return
        alert_list = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
        for a in alert_list:
            alert_id = a.get("id", str(a.get("timestamp", time.time())))
            if alert_id in SEEN_ALERT_IDS:
                continue
            SEEN_ALERT_IDS.add(alert_id)
            severity = a.get("severity", a.get("type", "medium"))
            title = a.get("title", a.get("type", "Alerta"))
            data = a.get("data", a.get("payload", ""))
            body = ""
            if isinstance(data, dict):
                body = json.dumps(data, indent=2, default=str)[:500]
            elif data:
                body = str(data)[:500]
            send_alert(title, body or "Sin detalles adicionales", severity)
        if len(SEEN_ALERT_IDS) > 100:
            SEEN_ALERT_IDS = set(list(SEEN_ALERT_IDS)[-50:])
        LAST_ALERT_CHECK = int(time.time())
    except Exception as e:
        log.error(f"check_alerts: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL

# ═════════════════════════════════════════════════════════════════════════════
# /sol <texto> — Hablar con el cerebro offline de Sol
# ═════════════════════════════════════════════════════════════════════════════

def _sol_respond(chat_id, msg):
    """Helper: procesa un mensaje con el cerebro offline de Sol y responde."""
    if _sol_pensar is not None:
        try:
            resp, intent = _sol_pensar(msg)
            # remember ya se llama dentro de pensar(), pero por seguridad:
            send_message(resp, chat_id)
            # Voz opcional — solo si termux-tts-speak está disponible
            if _sol_speak:
                try:
                    _sol_speak(resp)
                except Exception:
                    pass
        except Exception as e:
            log.error(f"sol_core error: {e}")
            send_message(f"☀️ Mi cerebro tuvo un problema: {e}\nPero sigo aquí contigo.", chat_id)
    else:
        # Fallback si sol_core no está disponible
        send_message(
            "☀️ Mi cerebro offline (sol_core.py) no está disponible.\n"
            "Pero el puente de Telegram sigue activo. Usa /help para ver comandos.",
            chat_id
        )


def cmd_sol(chat_id, text):
    """Procesa texto con el cerebro offline de Sol (sol_core.py). Comando: /sol <texto>"""
    parts = text.split(None, 1)
    msg = parts[1] if len(parts) > 1 else "hola"
    _sol_respond(chat_id, msg)


# ═════════════════════════════════════════════════════════════════════════════

def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()
    user = message.get("from", {}).get("first_name", "Usuario")

    if not text:
        return

    # Autorización — se aplica a TODO mensaje (comando o conversación)
    if CHAT_ID and chat_id != CHAT_ID:
        log.warning(f"Chat no autorizado: {chat_id} (esperado: {CHAT_ID})")
        return

    if not text.startswith("/"):
        # Conversación natural — Sol escucha y responde con su cerebro, no solo comandos
        log.info(f"Mensaje de {user} ({chat_id}): {text}")
        _sol_respond(chat_id, text)
        return

    log.info(f"Comando de {user} ({chat_id}): {text}")
    parts = text.split()
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""
    if cmd == "/start":
        cmd_start(chat_id)
    elif cmd == "/help":
        cmd_help(chat_id)
    elif cmd == "/status":
        cmd_status(chat_id)
    elif cmd == "/health":
        cmd_health(chat_id)
    elif cmd == "/alerts":
        cmd_alerts(chat_id)
    elif cmd == "/scan":
        cmd_scan(chat_id, arg)
    elif cmd == "/audits":
        cmd_audits(chat_id)
    elif cmd == "/phantom":
        cmd_phantom(chat_id)
    elif cmd == "/nexus":
        cmd_nexus(chat_id)
    elif cmd == "/c2":
        cmd_c2(chat_id)
    elif cmd == "/battery" or cmd == "/batt":
        cmd_battery(chat_id)
    elif cmd == "/network" or cmd == "/net":
        cmd_network(chat_id)
    elif cmd == "/memory":
        cmd_memory_sol(chat_id)
    elif cmd == "/topology" or cmd == "/topo":
        cmd_topology(chat_id)
    elif cmd == "/logs":
        cmd_logs(chat_id, arg)
    elif cmd == "/sol":
        cmd_sol(chat_id, text)
    else:
        send_message(f"❓ Comando no reconocido: <code>{cmd}</code>\nUsa /help para ver todos", chat_id)


def poll_loop():
    global POLL_OFFSET, RUNNING
    log.info("🌅 SOL Telegram Bridge iniciando...")
    log.info(f"   Backend: {BACKEND_URL}")
    log.info(f"   Chat ID: {CHAT_ID or 'NO CONFIGURADO'}")
    log.info(f"   Token: {'✅ configurado' if BOT_TOKEN else '❌ FALTA'}")

    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN no configurado. Deteniendo.")
        sys.exit(1)

    me = tg_api("getMe")
    if not me.get("ok"):
        log.error(f"No se pudo conectar al bot: {me}")
        sys.exit(1)

    bot_name = me["result"]["username"]
    log.info(f"   Bot: @{bot_name}")
    log.info("   ✅ Bot conectado. Esperando comandos...")

    send_message(f"🌅 <b>SOL Bridge activo</b>\nBot: @{bot_name}\nBackend: {BACKEND_URL}\n\nUsa /help para ver comandos.")

    alert_check_counter = 0
    while RUNNING:
        try:
            updates = tg_api("getUpdates", {
                "offset": POLL_OFFSET,
                "timeout": POLL_TIMEOUT,
                "limit": 10
            }, timeout=POLL_TIMEOUT + 10)

            if updates.get("ok"):
                for update in updates.get("result", []):
                    POLL_OFFSET = update.get("update_id", 0) + 1
                    handle_update(update)

            alert_check_counter += 1
            if alert_check_counter >= 2:
                check_backend_alerts()
                alert_check_counter = 0

        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error(f"Error en loop: {e}")
            time.sleep(5)

    log.info("SOL Bridge detenido.")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def signal_handler(sig, frame):
    global RUNNING
    log.info(f"Señal {sig} recibida. Deteniendo...")
    RUNNING = False

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado.")
        print("   Agrega a .env: TELEGRAM_BOT_TOKEN=tu_token_aqui")
        sys.exit(1)

    if not CHAT_ID:
        print("⚠️  TELEGRAM_CHAT_ID no configurado. El bot responderá a cualquier chat.")
        print("   Para seguridad, agrega a .env: TELEGRAM_CHAT_ID=tu_chat_id")

    poll_loop()
