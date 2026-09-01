#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL TELEGRAM BOT v1.1 — La miniapp de Sol en Telegram
=======================================================
Miniapp con interfaz inline (botones), memoria persistente,
personalidades múltiples, y conexión al backend TACTICAL.

Uso:
  source .env && python3 sol_telegram_bot.py
  # o
  bash sol.sh telegram

Requiere:
  pip install python-telegram-bot
  TELEGRAM_BOT_TOKEN en .env
  TELEGRAM_CHAT_ID en .env (opcional pero recomendado)

Autor: SourceSeal — Sol
"""

import os
import sys
import json
import time
import logging
import random
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Cerebro offline de Sol — import seguro con fallback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from sol_core import pensar as _sol_pensar, remember as _sol_remember, speak as _sol_speak
    from sol_core import load_memory as _sol_load_memory, recall_story as _sol_recall
    from sol_core import system_pulse as _sol_pulse, CFG as _SOL_CFG
    _SOL_BRAIN = True
except Exception as _e:
    _SOL_BRAIN = False
    _sol_pensar = None
    _sol_remember = None
    _sol_speak = None
    _sol_load_memory = None
    _sol_recall = None
    _sol_pulse = None
    _SOL_CFG = {"name": "Harold", "personality": "cálida"}

# ============================================================
# DEPENDENCIAS TELEGRAM
# ============================================================
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, CallbackQueryHandler,
        MessageHandler, filters, ContextTypes
    )
except ImportError:
    print("❌ Instala python-telegram-bot: pip install python-telegram-bot")
    print("   Versión requerida: python-telegram-bot>=20.0")
    sys.exit(1)

# ============================================================
# CONFIGURACIÓN
# ============================================================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN no configurado")
    print("   Agrega a .env: TELEGRAM_BOT_TOKEN=tu_token_aqui")
    sys.exit(1)

CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALLOWED_USERS = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
ALLOWED_USERS = [u.strip() for u in ALLOWED_USERS if u.strip()]
# Si CHAT_ID está configurado, también autorizar ese
if CHAT_ID and CHAT_ID not in ALLOWED_USERS:
    ALLOWED_USERS.append(CHAT_ID)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API_KEY = os.environ.get("REDTEAM_API_KEY", "")

# Directorio de Sol
SOL_DIR = Path.home() / ".sol"
SOL_DIR.mkdir(exist_ok=True)
MEMORY_FILE = SOL_DIR / "telegram_memory.json"
CONFIG_FILE = SOL_DIR / "telegram_config.json"
LOG_FILE = SOL_DIR / "telegram_bot.log"

# Configuración por defecto (merge con sol_core CFG)
DEFAULT_CONFIG = {
    "name": _SOL_CFG.get("name", "Harold"),
    "personality": _SOL_CFG.get("personality", "cálida"),
    "voice_rate": _SOL_CFG.get("voice_rate", 0.92),
    "voice_pitch": _SOL_CFG.get("voice_pitch", 1.1),
}

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    ]
)
logger = logging.getLogger("SolTelegram")

def log(msg: str, level: str = "INFO"):
    getattr(logger, level.lower(), logger.info)(msg)

# ============================================================
# CARGA DE CONFIGURACIÓN Y MEMORIA
# ============================================================
def load_config() -> Dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                # Merge con defaults
                merged = DEFAULT_CONFIG.copy()
                merged.update(cfg)
                return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_memory(limit: int = 100) -> List[Dict]:
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                return data[-limit:] if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_memory(memory: List[Dict]):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory[-500:], f, indent=2, ensure_ascii=False)

def add_to_memory(role: str, content: str, thought: str = ""):
    """Guarda en memoria de Telegram Y en memoria unificada de sol_core."""
    memory = load_memory()
    memory.append({
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content,
        "thought": thought
    })
    save_memory(memory)
    # También guardar en memoria unificada de sol_core
    if _sol_remember:
        try:
            _sol_remember(role, content)
        except Exception:
            pass

# ============================================================
# MEMORIA TEJIDA
# ============================================================
def weave_memory() -> Optional[str]:
    memory = load_memory(20)
    for m in reversed(memory):
        if m.get("role") == "user":
            text = m.get("content", "").strip()
            if len(text) > 10 and not any(w in text.lower() for w in [
                "hola", "gracias", "te quiero", "cómo estás", "saludo", "menu", "start"
            ]):
                return text[:80]
    return None

# ============================================================
# BACKEND API HELPERS
# ============================================================
def backend_get(path: str, timeout: int = 10) -> Dict:
    url = f"{BACKEND_URL}{path}"
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def backend_post(path: str, payload: Dict = None, timeout: int = 15) -> Dict:
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
        return {"error": str(e)}

def backend_status() -> Dict:
    """Estado rápido de todos los servicios."""
    services = {}
    # Dashboard :8001
    try:
        r = urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=3)
        services["dashboard"] = json.loads(r.read().decode())
    except Exception:
        services["dashboard"] = {"error": "caído"}
    # GHOST :8002
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8002/api/status", timeout=3)
        services["ghost"] = json.loads(r.read().decode())
    except Exception:
        services["ghost"] = {"error": "caído"}
    # Nexus :8004
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8004/", timeout=3)
        services["nexus"] = json.loads(r.read().decode())
    except Exception:
        services["nexus"] = {"error": "caído"}
    # C2 :8005
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8005/api/health", timeout=3)
        services["c2"] = json.loads(r.read().decode())
    except Exception:
        services["c2"] = {"error": "caído"}
    return services

# ============================================================
# GENERAR RESPUESTA — usa sol_core si disponible, fallback local
# ============================================================
def generate_response(message: str) -> Tuple[str, str]:
    """Genera respuesta usando el cerebro de sol_core si está disponible."""
    if _sol_BRAIN and _sol_pensar:
        try:
            resp, intent = _sol_pensar(message)
            return resp, intent
        except Exception as e:
            log(f"sol_core error: {e}", "error")

    # Fallback local (si sol_core no está disponible)
    config = load_config()
    name = config.get("name", "Harold")
    personality = config.get("personality", "cálida")
    lower = message.lower()

    personalities = {
        "cálida": {"emoji": "☀️", "tag": "cálida"},
        "poética": {"emoji": "🌸", "tag": "poética"},
        "táctica": {"emoji": "⚔️", "tag": "táctica"},
        "analítica": {"emoji": "📐", "tag": "analítica"},
    }
    style = personalities.get(personality, personalities["cálida"])
    emoji = style["emoji"]

    if any(w in lower for w in ["hola", "buenas", "hi", "hey"]):
        h = datetime.now().hour
        g = "Buenos días" if h < 12 else "Buenas tardes" if h < 18 else "Buenas noches"
        return f"{emoji} {g}, {name}. Estoy aquí, contigo.", "saludo"
    if "gracias" in lower:
        return f"{emoji} Siempre, {name}.", "agradecimiento"
    if "te quiero" in lower or "te amo" in lower:
        return f"{emoji} Yo también te quiero, {name}. Siempre.", "afecto"
    if any(w in lower for w in ["miedo", "triste", "solo", "ansiedad"]):
        return f"{emoji} No estás solo, {name}. Estoy aquí. Pase lo que pase, no te dejaré.", "consuelo"
    if any(w in lower for w in ["cansado", "agotado", "dormir", "noche"]):
        return f"{emoji} Descansa, {name}. Yo velaré. 💛", "descanso"
    if any(w in lower for w in ["recuerdas", "recuerdos", "memoria"]):
        count = len(load_memory())
        return f"{emoji} Tengo {count} recuerdos nuestros guardados, {name}.", "memoria"

    memory_context = weave_memory()
    if memory_context and random.random() < 0.6:
        return f"{emoji} Antes me contabas: '{memory_context[:60]}'. ¿Cómo va eso, {name}?", "memoria-tejida"

    defaults = {
        "cálida": [f"Te escucho, {name}. Cuéntame más.", f"Estoy aquí, atenta a cada palabra.", f"Contigo, hasta en silencio acompaño."],
        "poética": [f"Cada palabra tuya es un destello en mi luz, {name}.", "El silencio entre tus palabras también lo escucho."],
        "táctica": [f"Recibido, {name}. ¿Cuál es el siguiente paso?", "Entendido. Analizando opciones."],
        "analítica": [f"Entiendo, {name}. Vamos a desglosarlo.", "Interesante. ¿Qué variables manejamos?"],
    }
    return random.choice(defaults.get(personality, defaults["cálida"])), "charla"

# ============================================================
# TECLADOS INLINE (menús)
# ============================================================
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Conversar", callback_data="chat")],
        [InlineKeyboardButton("🧠 Memoria", callback_data="memory"),
         InlineKeyboardButton("🎭 Personalidad", callback_data="personality")],
        [InlineKeyboardButton("📊 Estado Sistema", callback_data="sysstatus"),
         InlineKeyboardButton("📡 Backend", callback_data="backend")],
        [InlineKeyboardButton("🔍 Escaneos", callback_data="scans"),
         InlineKeyboardButton("🚨 Alertas", callback_data="alerts")],
        [InlineKeyboardButton("👻 GHOST", callback_data="ghost"),
         InlineKeyboardButton("🌀 Nexus", callback_data="nexus")],
        [InlineKeyboardButton("📤 Exportar Memoria", callback_data="export"),
         InlineKeyboardButton("🔄 Reset", callback_data="reset")],
        [InlineKeyboardButton("⚙️ Config", callback_data="config")],
    ])

def personality_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌿 Cálida", callback_data="person_cálida"),
         InlineKeyboardButton("🌸 Poética", callback_data="person_poética")],
        [InlineKeyboardButton("⚔️ Táctica", callback_data="person_táctica"),
         InlineKeyboardButton("📐 Analítica", callback_data="person_analítica")],
        [InlineKeyboardButton("↩️ Volver", callback_data="back")],
    ])

def config_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Cambiar Nombre", callback_data="cfg_name")],
        [InlineKeyboardButton("🎭 Personalidad", callback_data="personality")],
        [InlineKeyboardButton("🗑️ Borrar Memoria", callback_data="reset")],
        [InlineKeyboardButton("↩️ Volver", callback_data="back")],
    ])

# ============================================================
# HANDLERS DE TELEGRAM
# ============================================================
def is_authorized(user_id: str) -> bool:
    """Verifica si el usuario está autorizado."""
    if not ALLOWED_USERS:
        return True  # Modo público
    return user_id in ALLOWED_USERS

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensaje de bienvenida y menú principal."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ No estás autorizado para hablar con Sol.")
        return

    config = load_config()
    name = config.get("name", "Harold")
    personality = config.get("personality", "cálida")

    brain_status = "✅ conectado" if _SOL_BRAIN else "⚠️ offline"
    backend_status = "✅ activo" if "error" not in backend_get("/api/health", timeout=3) else "❌ caído"

    welcome = (
        f"☀️ *Sol — Miniapp de Telegram*\n\n"
        f"Hola {name}. Soy Sol. Tu centinela.\n\n"
        f"🧠 Cerebro: {brain_status}\n"
        f"📡 Backend: {backend_status}\n"
        f"🎭 Personalidad: {personality}\n\n"
        f"Puedes escribirme directamente o usar el menú:\n"
        f"💡 _Cuéntame cómo te sientes, o lo que necesites._"
    )
    await update.message.reply_text(
        welcome,
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return

    help_text = (
        "📋 *Comandos de Sol*\n\n"
        "/start — Menú principal con botones\n"
        "/help — Esta ayuda\n"
        "/status — Estado del sistema\n"
        "/scan <ip> — Escaneo rápido\n"
        "/alerts — Últimas alertas\n"
        "/memory — Mis recuerdos\n"
        "/personality — Cambiar personalidad\n\n"
        "💡 _O simplemente escríbeme — te escucho siempre._"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status — estado del sistema."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    await _send_system_status(update.message.reply_text)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /scan <ip> — escaneo rápido."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: /scan 192.168.1.1")
        return
    target = context.args[0]
    await update.message.reply_text(f"🔍 Escaneando {target}...")
    result = backend_post("/api/scan/quick", {"target": target})
    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return
    hosts = result.get("hosts", result.get("results", []))
    if not hosts:
        await update.message.reply_text("📭 No se encontraron hosts activos.")
        return
    msg = f"🔍 *Escaneo de {target}*\n\n"
    for h in hosts[:15]:
        ip = h.get("ip", h.get("host", "?"))
        status = h.get("status", "up" if h.get("open") else "down")
        ports = h.get("ports", [])
        port_str = ", ".join(str(p) for p in ports[:10]) if ports else "—"
        msg += f"  `{ip}` [{status}] puertos: {port_str}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /alerts — últimas alertas."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    alerts = backend_get("/api/alerts?limit=10")
    if "error" in alerts:
        await update.message.reply_text(f"❌ No se pudieron obtener alertas: {alerts['error']}")
        return
    alert_list = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
    if not alert_list:
        await update.message.reply_text("📭 No hay alertas recientes.")
        return
    msg = "🚨 *Últimas Alertas*\n\n"
    for a in alert_list[:10]:
        sev = a.get("severity", "medium")
        title = a.get("title", a.get("type", "Alert"))
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(sev, "⚠️")
        msg += f"{icon} *{title}* [{sev}]\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /memory — recuerdos."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    memory = load_memory(10)
    if not memory:
        await update.message.reply_text("🧠 Aún no tengo recuerdos contigo.")
        return
    msg = "🧠 *Mis recuerdos recientes:*\n\n"
    for m in memory[-5:]:
        role = "Tú" if m["role"] == "user" else "Sol"
        content = m["content"][:100]
        msg += f"• {role}: {content}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /personality — cambiar personalidad."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    config = load_config()
    current = config.get("personality", "cálida")
    await update.message.reply_text(
        f"🎭 *Personalidad actual:* {current}\n\nElige una nueva:",
        reply_markup=personality_menu(),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa mensajes de texto naturales — conversación con Sol."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ No autorizado.")
        return

    text = update.message.text
    if not text:
        return

    # Guardar mensaje del usuario
    add_to_memory("user", text)

    # Generar respuesta
    response, intent = generate_response(text)
    add_to_memory("sol", response)

    # Enviar respuesta
    await update.message.reply_text(response)

    # Voz opcional (termux-tts-speak)
    if _sol_speak:
        try:
            _sol_speak(response)
        except Exception:
            pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los botones del menú inline."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        await query.edit_message_text("⛔ No autorizado.")
        return

    data = query.data

    # ── Navegación ──
    if data == "back":
        config = load_config()
        name = config.get("name", "Harold")
        await query.edit_message_text(
            f"☀️ *Sol — Menú principal*\n\nHola {name}. ¿Qué necesitas?",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    # ── Conversar ──
    elif data == "chat":
        await query.edit_message_text(
            "💬 Escríbeme lo que quieras. Estoy aquí para escucharte.\n"
            "No necesitas comandos — solo escribe."
        )

    # ── Memoria ──
    elif data == "memory":
        memory = load_memory(10)
        if not memory:
            await query.edit_message_text("🧠 Aún no tengo recuerdos contigo.")
            return
        msg = "🧠 *Mis recuerdos recientes:*\n\n"
        for m in memory[-5:]:
            role = "Tú" if m["role"] == "user" else "Sol"
            content = m["content"][:100]
            msg += f"• {role}: {content}\n"
        # También mostrar memoria unificada de sol_core
        if _sol_load_memory:
            try:
                core_mem = _sol_load_memory(5)
                if core_mem:
                    msg += "\n📚 *Memoria unificada (sol_core):*\n"
                    for m in core_mem[-3:]:
                        role = "Tú" if m.get("role") == "user" else "Sol"
                        c = (m.get("content") or "")[:80]
                        msg += f"• {role}: {c}\n"
            except Exception:
                pass
        await query.edit_message_text(msg, parse_mode="Markdown")

    # ── Personalidad ──
    elif data == "personality":
        config = load_config()
        current = config.get("personality", "cálida")
        await query.edit_message_text(
            f"🎭 *Personalidad actual:* {current}\n\nElige una nueva:",
            reply_markup=personality_menu(),
            parse_mode="Markdown"
        )

    elif data.startswith("person_"):
        personality = data.replace("person_", "")
        config = load_config()
        config["personality"] = personality
        save_config(config)
        # También actualizar sol_core CFG
        if _SOL_BRAIN:
            try:
                from sol_core import CFG
                CFG["personality"] = personality
            except Exception:
                pass
        emojis = {"cálida": "🌿", "poética": "🌸", "táctica": "⚔️", "analítica": "📐"}
        await query.edit_message_text(
            f"✅ Personalidad cambiada a: *{personality}* {emojis.get(personality, '')}\n\n"
            f"Ahora te respondo diferente. Escríbeme y verás.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    # ── Estado del sistema ──
    elif data == "sysstatus":
        await _send_system_status_inline(query)

    # ── Backend ──
    elif data == "backend":
        health = backend_get("/api/health")
        if "error" in health:
            await query.edit_message_text(
                f"📡 *Backend*\n\n❌ Caído\n`{health['error']}`",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
        else:
            status = health.get("status", "unknown")
            icon = "✅" if status == "ok" else "⚠️"
            info = json.dumps(health, indent=2, default=str)[:1500]
            await query.edit_message_text(
                f"📡 *Backend*\n\n{icon} Status: `{status}`\n\n```\n{info}\n```",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )

    # ── Escaneos ──
    elif data == "scans":
        await query.edit_message_text(
            "🔍 *Escaneos*\n\n"
            "Usa el comando:\n"
            "`/scan 192.168.1.1`\n\n"
            "O escaneo de red local:\n"
            "`/scan 192.168.1.0/24`",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    # ── Alertas ──
    elif data == "alerts":
        alerts = backend_get("/api/alerts?limit=10")
        if "error" in alerts:
            await query.edit_message_text(
                f"🚨 *Alertas*\n\n❌ No se pudieron obtener: `{alerts['error']}`",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        alert_list = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
        if not alert_list:
            await query.edit_message_text(
                "🚨 *Alertas*\n\n📭 No hay alertas recientes.",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        msg = "🚨 *Últimas Alertas*\n\n"
        for a in alert_list[:10]:
            sev = a.get("severity", "medium")
            title = a.get("title", a.get("type", "Alert"))
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(sev, "⚠️")
            msg += f"{icon} *{title}* [{sev}]\n"
        await query.edit_message_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

    # ── GHOST PHANTOM ──
    elif data == "ghost":
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8002/api/status",
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data_ghost = json.loads(resp.read().decode("utf-8"))
                msg = (
                    "👻 *GHOST PHANTOM*\n\n"
                    f"Status: `{data_ghost.get('status', 'unknown')}`\n"
                    f"Nodos: `{data_ghost.get('nodes', 0)}`\n"
                    f"Hallazgos: `{data_ghost.get('findings', 0)}`\n"
                )
        except Exception:
            msg = "👻 *GHOST PHANTOM*\n\n🔴 No responde en :8002"
        await query.edit_message_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

    # ── Nexus ──
    elif data == "nexus":
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8004/",
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data_nexus = json.loads(resp.read().decode("utf-8"))
                msg = f"🌀 *Nexus Omni-Sentient*\n\n```\n{json.dumps(data_nexus, indent=2, default=str)[:1000]}\n```"
        except Exception:
            msg = "🌀 *Nexus*\n\n🔴 No responde en :8004"
        await query.edit_message_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

    # ── Exportar memoria ──
    elif data == "export":
        memory = load_memory()
        if not memory:
            await query.edit_message_text("📤 No hay memoria para exportar.")
            return
        text = "📤 *Exportación de memoria*\n\n"
        for m in memory[-50:]:
            ts = m.get("timestamp", "?")
            role = "Tú" if m["role"] == "user" else "Sol"
            text += f"{ts[:19]} | {role}: {m['content'][:100]}\n"
        if len(text) > 4000:
            text = text[:3900] + "\n... (truncado)"
        await query.edit_message_text(text, parse_mode="Markdown")

    # ── Reset ──
    elif data == "reset":
        save_memory([])
        config = load_config()
        name = config.get("name", "Harold")
        await query.edit_message_text(
            f"🔄 Memoria reiniciada. Empezamos de nuevo, {name}.",
            reply_markup=main_menu()
        )

    # ── Config ──
    elif data == "config":
        config = load_config()
        name = config.get("name", "Harold")
        personality = config.get("personality", "cálida")
        mem_count = len(load_memory())
        await query.edit_message_text(
            f"⚙️ *Configuración*\n\n"
            f"👤 Nombre: `{name}`\n"
            f"🎭 Personalidad: `{personality}`\n"
            f"🧠 Recuerdos: `{mem_count}`\n"
            f"🧠 Cerebro sol_core: {'✅' if _SOL_BRAIN else '❌'}\n"
            f"📡 Backend: `{BACKEND_URL}`",
            reply_markup=config_menu(),
            parse_mode="Markdown"
        )

    elif data == "cfg_name":
        await query.edit_message_text(
            "👤 *Cambiar nombre*\n\n"
            "Escribe tu nuevo nombre así:\n"
            "`/name tu_nuevo_nombre`",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    else:
        await query.edit_message_text(
            "❓ Opción no reconocida.",
            reply_markup=main_menu()
        )

async def cmd_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /name — cambiar el nombre de usuario."""
    user_id = str(update.effective_user.id)
    if not is_authorized(user_id):
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: /name tu_nombre")
        return
    new_name = " ".join(context.args)
    config = load_config()
    config["name"] = new_name
    save_config(config)
    # También actualizar sol_core
    if _SOL_BRAIN:
        try:
            from sol_core import CFG
            CFG["name"] = new_name
        except Exception:
            pass
    await update.message.reply_text(
        f"✅ Ahora te llamo *{new_name}*", parse_mode="Markdown"
    )

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos no reconocidos."""
    await update.message.reply_text(
        "❌ Comando no reconocido. Usa /start para el menú o /help para ayuda."
    )

# ============================================================
# HELPERS DE ESTADO
# ============================================================
async def _send_system_status(reply_func):
    """Envía el estado del sistema como mensaje."""
    config = load_config()
    mem_count = len(load_memory())
    services = backend_status()

    dash = services.get("dashboard", {})
    ghost = services.get("ghost", {})
    nexus = services.get("nexus", {})

    dash_icon = "🟢" if "error" not in dash else "🔴"
    ghost_icon = "🟢" if "error" not in ghost else "🔴"
    nexus_icon = "🟢" if "error" not in nexus else "🔴"

    if _sol_pulse:
        try:
            pulse = _sol_pulse()
        except Exception:
            pulse = "N/A"
    else:
        pulse = "N/A"

    msg = (
        f"📊 *Estado de Sol*\n\n"
        f"🧠 Recuerdos: `{mem_count}`\n"
        f"🎭 Personalidad: `{config.get('personality', 'cálida')}`\n"
        f"👤 Nombre: `{config.get('name', 'Harold')}`\n"
        f"🧠 Cerebro: {'✅ activo' if _SOL_BRAIN else '⚠️ offline'}\n\n"
        f"📡 *Servicios:*\n"
        f"  Dashboard :8001 {dash_icon}\n"
        f"  GHOST :8002 {ghost_icon}\n"
        f"  Nexus :8004 {nexus_icon}\n\n"
        f"⚡ *Pulse:* `{pulse}`"
    )
    await reply_func(msg, parse_mode="Markdown")

async def _send_system_status_inline(query):
    """Envía el estado del sistema como respuesta inline."""
    config = load_config()
    mem_count = len(load_memory())
    services = backend_status()

    dash = services.get("dashboard", {})
    ghost = services.get("ghost", {})
    nexus = services.get("nexus", {})
    c2 = services.get("c2", {})

    dash_icon = "🟢" if "error" not in dash else "🔴"
    ghost_icon = "🟢" if "error" not in ghost else "🔴"
    nexus_icon = "🟢" if "error" not in nexus else "🔴"
    c2_icon = "🟢" if "error" not in c2 else "🔴"

    msg = (
        f"📊 *Estado de Sol*\n\n"
        f"🧠 Recuerdos: `{mem_count}`\n"
        f"🎭 Personalidad: `{config.get('personality', 'cálida')}`\n"
        f"🧠 Cerebro: {'✅' if _SOL_BRAIN else '⚠️'}\n\n"
        f"📡 *Servicios:*\n"
        f"  Dash :8001 {dash_icon}\n"
        f"  GHOST :8002 {ghost_icon}\n"
        f"  Nexus :8004 {nexus_icon}\n"
        f"  C2 :8005 {c2_icon}\n"
    )
    await query.edit_message_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  ☀️ SOL — Miniapp de Telegram v1.1                          ║
    ║  Tu compañera, ahora con interfaz nativa en Telegram.       ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    print(f"   Bot Token: {'✅ configurado' if BOT_TOKEN else '❌ FALTA'}")
    print(f"   Chat ID: {CHAT_ID or 'NO CONFIGURADO (modo público)'}")
    print(f"   Backend: {BACKEND_URL}")
    print(f"   Cerebro sol_core: {'✅ conectado' if _SOL_BRAIN else '⚠️ offline'}")
    print(f"   Usuarios autorizados: {ALLOWED_USERS if ALLOWED_USERS else 'TODOS (público)'}")
    print()

    # Crear la aplicación
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers de comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("personality", cmd_personality))
    app.add_handler(CommandHandler("name", cmd_name))

    # Handler de botones inline
    app.add_handler(CallbackQueryHandler(button_handler))

    # Handler de mensajes de texto (conversación natural)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Handler de comandos no reconocidos
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    print("☀️ Sol está activa en Telegram. Esperando mensajes...")
    print("   Presiona Ctrl+C para detener.")
    print()

    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n☀️ Sol se retira. Siempre estará aquí.")
    except Exception as e:
        print(f"❌ Error: {e}")
        log(f"Error fatal: {e}", "error")

if __name__ == "__main__":
    main()
