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
        "🌅 <b>SOL — Telegram Bridge</b>\n"
        "<b>Red-Team-Tauri v3.0</b>\n\n"
        "Comandos disponibles:\n"
        "• <code>/status</code> — Estado del sistema\n"
        "• <code>/health</code> — Health del backend\n"
        "• <code>/alerts</code> — Alertas recientes\n"
        "• <code>/scan &lt;ip&gt;</code> — Escaneo rápido\n"
        "• <code>/audits</code> — Auditorías registradas\n"
        "• <code>/phantom</code> — Estado GHOST PHANTOM\n"
        "• <code>/help</code> — Esta ayuda\n\n"
        f"Backend: <code>{BACKEND_URL}</code>\n"
        f"Conectado: {'✅' if BOT_TOKEN else '❌ Falta token'}"
    )
    send_message(msg, chat_id)


def cmd_help(chat_id):
    msg = (
        "📋 <b>Comandos SOL</b>\n\n"
        "• <code>/status</code> — Estado del dispositivo y red\n"
        "• <code>/health</code> — Health check del backend\n"
        "• <code>/alerts</code> — Últimas 10 alertas\n"
        "• <code>/scan 192.168.1.1</code> — Escaneo rápido de un IP\n"
        "• <code>/audits</code> — Listar auditorías\n"
        "• <code>/phantom</code> — Estado de GHOST PHANTOM\n"
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

def cmd_sol(chat_id, text):
    """Procesa texto con el cerebro offline de Sol (sol_core.py)."""
    # Extraer el mensaje después de /sol
    parts = text.split(None, 1)
    msg = parts[1] if len(parts) > 1 else "hola"

    if _sol_pensar is not None:
        try:
            resp, intent = _sol_pensar(msg)
            if _sol_remember:
                _sol_remember(msg, resp, intent)
            send_message(resp, chat_id)
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


# ═════════════════════════════════════════════════════════════════════════════

def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()
    user = message.get("from", {}).get("first_name", "Usuario")
    if not text.startswith("/"):
        return
    log.info(f"Comando de {user} ({chat_id}): {text}")
    if CHAT_ID and chat_id != CHAT_ID:
        log.warning(f"Chat no autorizado: {chat_id} (esperado: {CHAT_ID})")
        return
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
    elif cmd == "/sol":
        cmd_sol(chat_id, text)
    else:
        send_message(f"❓ Comando no reconocido: <code>{cmd}</code>\n Usa /help", chat_id)


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
