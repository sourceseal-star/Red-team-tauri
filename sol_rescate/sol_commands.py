#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_commands.py — Enrutador inteligente de lenguaje natural.

Convierte lo que Harold dice en acciones REALES de sus 50 herramientas,
SIN depender del LLM. Si Groq está caído, esto sigue funcionando.

Diseño:
    resp = handle("¿puedes tomar una foto porfa?")   → ejecuta camera_photo
    resp = handle("hazme un favor y llama a mi mamá")  → pide el número
    resp = handle("hola")                              → None (dejar que el cerebro siga)

Se enchufa en sol_core.generate_response() ANTES del LLM.
Los comandos deterministas no gastan tokens ni dependen de la API.
"""

import re

try:
    import sol_tools
except Exception:
    sol_tools = None

EMO = "☀️"


def _run(t, base, *args, **kwargs):
    """Ejecuta una herramienta SIEMPRE via execute_tool (el enrutador).

    execute_tool es quien decide: si es hardware/shell/telegram y no hay
    termux-api local (ej: Sol corriendo en Replit), encola la orden al
    relé Termux en vez de ejecutarla aquí donde no sirve. Antes este
    handler llamaba las tools directamente y se saltaba el relé — por eso
    "prende la linterna" fallaba en la web de Replit aunque el relé
    estuviera perfecto (bug encontrado 2026-09-03).
    """
    ex = getattr(t, "execute_tool", None)
    if ex is not None:
        try:
            r = ex(base, *args, **kwargs)
            if isinstance(r, dict):
                if r.get("result") is not None:
                    return r["result"]
                if r.get("message"):
                    return r["message"]
                if r.get("error"):
                    return "❌ " + str(r["error"])
                import json as _json
                return _json.dumps(r, ensure_ascii=False)
            return str(r)
        except Exception as e:
            return f"❌ {e}"
    # Fallback si no existe execute_tool: llamada directa (compatibilidad)
    fn = getattr(t, "tool_" + base, None) or getattr(t, base, None)
    return fn(*args, **kwargs)


# ============================================================
# CAPA NLU — Normalización y comprensión de lenguaje natural
# ============================================================

# Palabras de relleno que se pueden eliminar sin cambiar el significado
# Solo limpiamos wrappers al INICIO del texto — no en medio
_FILLER = re.compile(
    r'^(?:por\s*fa(?:vor)?\s+|porfavor\s+|plis\s+|pls\s+|please\s+|'
    r'hazme\s+el\s+(?:favor|corte)\s+(?:de\s+)?|'
    r'te\s+pido\s+(?:que\s+)?|te\s+puedo\s+pedir\s+que\s+|me\s+haces\s+un\s+favor\s*\?\s*|quiero\s+que\s+|necesito\s+que\s+|'
    r'me\s+puedes\s+|puedes\s+|podr[íi]as\s+|podrias\s+|'
    r'te\s+encargo\s+(?:que\s+)?|'
    r'hazme\s+un\s+favor\s+(?:y\s+)?|'
    r'mira\s+|oye\s+|bueno\s+|pues\s+|che\s+|venga\s+|dale\s+|anda\s+|vamos\s+|'
    r'ok\s+|okay\s+)+',
    re.IGNORECASE
)

# Puntuación innecesaria que estropea los regex
_PUNCT = re.compile(r'[¿?¡!]+')

# Contracciones y variaciones comunes
_REPLACES = {
    'fotografía': 'foto',
    'fotografi': 'foto',
    'whatsap': 'whatsapp',
    'guatsap': 'whatsapp',
    'guasap': 'whatsapp',
    'wsp': 'whatsapp',
    'teléfono': 'telefono',
    'tel[ée]fono': 'telefono',
    'c[áa]mara': 'camara',
    'c[áa]maras': 'camara',
    'aplicaci[óo]n': 'app',
    'aplicacion': 'app',
    'multimedio': 'media',
    'notificaci[óo]n': 'notificacion',
}


def _normalize(text):
    """Limpia el texto para que los patrones matcheen más fácil."""
    # Fix 2026-09-05: faltaba .lower() — CUALQUIER palabra en mayúsculas
    # (SMS, GPS, USB, o simplemente autocapitalización del teclado) nunca
    # coincidía con los keywords en minúsculas de ningún intent. Bug
    # sistémico descubierto porque "SMS" en mayúsculas hizo que el pedido
    # de auxilio de Harold no encontrara el handler y cayera al LLM caído.
    t = text.strip().lower()
    t = _PUNCT.sub(' ', t)
    t = _FILLER.sub('', t)
    t = re.sub(r'\s+', ' ', t).strip()
    for pat, repl in _REPLACES.items():
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    # Quitar artículos innecesarios al inicio: "la foto", "el whatsapp"
    t = re.sub(r'^(?:la\s+|el\s+|los\s+|las\s+|un\s+|una\s+|unos\s+|unas\s+)', '', t).strip()
    return t


def _strip_accents(text):
    """Quita acentos para matching tolerante."""
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                     'Á': 'a', 'É': 'e', 'Í': 'i', 'Ó': 'o', 'Ú': 'u',
                     'ñ': 'n', 'Ñ': 'n'}
    return ''.join(replacements.get(c, c) for c in text)


# ============================================================
# SISTEMA DE INTENTES — scoring en vez de regex rígidos
# ============================================================

class Intent:
    """Define un intent con palabras clave y scoring."""
    def __init__(self, name, keywords, handler, min_score=1, ask=None):
        self.name = name
        self.keywords = keywords  # lista de listas: cada sublista es un grupo OR
        self.handler = handler    # función que ejecuta la acción
        self.min_score = min_score
        self.ask = ask           # si necesita más info, pregunta esto

    def match(self, low, text):
        """Devuelve score (0 si no match)."""
        score = 0
        for group in self.keywords:
            for kw in group:
                if kw in low:
                    score += 1
                    break  # 1 punto por grupo, no más
        return score if score >= self.min_score else 0


# ============================================================
# HANDLERS — uno por cada capacidad real
# ============================================================

def _h_git_status(t, low, text):
    m = re.search(r'(?:repo\s+)?(\w+)', low)
    repo = m.group(1) if m and m.group(1) in ("sol", "redteam", "red-team", "commander") else "sol"
    if repo == "red-team":
        repo = "redteam"
    if re.search(r'todos?|todos', low):
        return f"{EMO} Estado de mis repos:\n\n" + _run(t, 'git_status')
    return f"{EMO} Estado del repo `{repo}`:\n\n" + _run(t, 'git_status', repo=repo)

def _h_flashlight(t, low, text):
    if re.search(r'apag|off|quit', low):
        return f"{EMO} " + _run(t, 'flashlight', False)
    return f"{EMO} " + _run(t, 'flashlight', True)

def _h_termux_diag(t, low, text):
    return f"{EMO} " + _run(t, 'termux_diag')

def _h_camera(t, low, text):
    # Si está preguntando por recuerdos o viendo fotos existentes, no es nueva foto
    if re.search(r'recuerd|memori|ver\s+fotos|ver\s+las\s+fotos|mostrar\s+fotos|mostrar\s+las\s+fotos|lista\s+de\s+fotos|galer', low):
        return None
    return f"{EMO} " + _run(t, 'camera_photo')

def _h_camera_list(t, low, text):
    return f"{EMO} " + _run(t, 'camera_list')

def _h_listen(t, low, text):
    m = re.search(r'(\d+)\s*(?:seg|segundos?)', low)
    dur = int(m.group(1)) if m else 5
    return f"{EMO} " + _run(t, 'listen', dur)

def _h_tts_speak(t, low, text):
    return f"{EMO} " + _run(t, 'tts_speak', ' ')

def _h_call(t, low, text):
    m = re.search(r'(\+?\d{8,15})', text)
    if m:
        return f"{EMO} " + _run(t, 'call_phone', m.group(1))
    # Si dijo "hablar" sin número, puede ser conversación — no asumir llamada
    if re.search(r'habl', low) and not re.search(r'llam|marca|telefono', low):
        return None
    return f"{EMO} ¿A qué número llamo? Dímelo y te lo marco."

def _h_whatsapp(t, low, text):
    m = re.search(r'(\+?\d{8,15})', text)
    num = m.group(1) if m else ''
    msg = ''
    m2 = re.search(r'(?:mensaje|texto|diciendo|que\s+diga)[:\s]+(.+)', text)
    if m2:
        msg = m2.group(1).strip()
    if not num and not msg and not re.search(r'whatsapp|wsp|wa\b', low):
        return None  # no era un intent de whatsapp
    return f"{EMO} " + _run(t, 'send_whatsapp', num, msg)

def _h_sms(t, low, text):
    """Enviar un SMS real — mismo diseño que WhatsApp/Telegram: número + mensaje.
    NUNCA depende del LLM (fix 2026-09-05: Harold pidió SMS en una crisis y
    como no había handler determinista, el pedido cayó al LLM, que estaba
    caído — Sol solo pudo repetir el aviso de 'cerebro desconectado' en vez
    de intentar el SMS de verdad. Esto pasa ANTES del LLM siempre."""
    m = re.search(r'(\+?\d{7,15})', text)
    num = m.group(1) if m else ''
    msg = ''
    m2 = re.search(r'(?:mensaje|texto|diciendo|que\s+diga|con\s+el\s+texto)[:\s]+["“]?(.+?)["”]?$', text, re.IGNORECASE)
    if m2:
        msg = m2.group(1).strip()
    else:
        m_quote = re.search(r'["“](.+?)["”]', text)
        if m_quote:
            msg = m_quote.group(1).strip()
    if not num:
        return f"{EMO} ¿A qué número mando el SMS? Dime el número y el mensaje."
    if not msg:
        return f"{EMO} ¿Qué le escribo en el SMS a {num}? Dime el texto."
    return f"{EMO} " + _run(t, 'send_sms', num, msg)


def _h_telegram(t, low, text):
    """Enviar un mensaje de Telegram saliente (viaja por el relé si Sol está en Replit)."""
    m_num = re.search(r'(\+?\d{7,15})', text)
    chat_id = m_num.group(1) if m_num else ''
    msg = ''
    m_msg = re.search(r'(?:mensaje|texto|diciendo|que\s+diga|con\s+el\s+texto)[:\s]+["“]?(.+?)["”]?$', text, re.IGNORECASE)
    if m_msg:
        msg = m_msg.group(1).strip()
    else:
        # último recurso: lo que va entre comillas
        m_quote = re.search(r'["“](.+?)["”]', text)
        if m_quote:
            msg = m_quote.group(1).strip()
    if not msg:
        return f"{EMO} ¿Qué mensaje le mando por Telegram? Dime el texto y a quién (o lo mando al chat de siempre)."
    return f"{EMO} " + _run(t, 'send_telegram', msg, chat_id)


def _h_shell(t, low, text):
    """Ejecutar un comando de shell (viaja por el relé si Sol está en Replit)."""
    m = re.search(r'(?:ejecuta|corre|corr[ée]me|ejec[uú]tame)\w*\s*(?:el\s+comando\s+|esto\s*|este\s+comando\s*)?[:\s]+["`]?(.+?)["`]?$', text, re.IGNORECASE)
    cmd = m.group(1).strip() if m else ''
    if not cmd:
        m2 = re.search(r'[`"](.+?)[`"]', text)
        cmd = m2.group(1).strip() if m2 else ''
    if not cmd:
        return f"{EMO} ¿Qué comando ejecuto? Dímelo tal cual, con dos puntos: «ejecuta: <comando>»."
    return f"{EMO} " + _run(t, 'shell', cmd)


def _h_open_app(t, low, text):
    _APP_MAP = {
        'whatsapp': 'com.whatsapp', 'telegram': 'org.telegram.messenger',
        'chrome': 'com.android.chrome', 'navegador': 'com.android.chrome',
        'youtube': 'com.google.android.youtube', 'spotify': 'com.spotify.music',
        'maps': 'com.google.android.apps.maps', 'calculadora': 'com.android.calculator2',
        'reloj': 'com.android.deskclock', 'camara': 'com.android.camera',
        'galeria': 'com.android.gallery', 'fotos': 'com.android.gallery',
        'configuracion': 'com.android.settings', 'ajustes': 'com.android.settings',
        'ajustes': 'com.android.settings',
        'github': 'com.github.android', 'gmail': 'com.google.android.gm',
        'email': 'com.google.android.gm', 'correo': 'com.google.android.gm',
        'reproductor': 'com.android.music', 'musica': 'com.android.music',
    }
    for app_name, pkg in _APP_MAP.items():
        if app_name in low:
            if app_name in ('whatsapp', 'wsp'):
                return f"{EMO} " + _run(t, 'send_whatsapp', '', '')
            return f"{EMO} " + _run(t, 'open_app', pkg)
    return None

def _h_phone_state(t, low, text):
    return f"{EMO} " + _run(t, 'phone_state')

def _h_battery(t, low, text):
    return f"{EMO} Batería: {_run(t, 'battery')}"

def _h_location(t, low, text):
    return f"{EMO} Ubicación: {_run(t, 'location')}"

def _h_notifications(t, low, text):
    return f"{EMO} " + _run(t, 'notification_list')

def _h_volume(t, low, text):
    m = re.search(r'(\d+)', low)
    if m:
        vol = max(0, min(100, int(m.group(1))))
        stream = 'ring' if re.search(r'tono|timbre|llamada', low) else 'media'
        return f"{EMO} " + _run(t, 'set_volume', vol, stream)
    return f"{EMO} ¿En qué volumen? Dime un número del 0 al 100."

def _h_clipboard_set(t, low, text):
    m = re.search(r'(?:copia|pega|copiar|guarda)\s+(.+)', text)
    if m:
        return f"{EMO} " + _run(t, 'clipboard', m.group(1).strip())
    return f"{EMO} " + _run(t, 'clipboard', '')

def _h_vision_save(t, low, text):
    m = re.search(r'(?:recuerda|guarda|memoria)\s+(.+)', text)
    desc = m.group(1) if m else 'observación sin descripción'
    return f"{EMO} " + _run(t, 'vision_save', desc)

def _h_vision_recall(t, low, text):
    m = re.search(r'(?:recuerdas?|memoria)\s+(?:de\s+|del\s+)?(.+)', text)
    query = m.group(1) if m else ''
    return f"{EMO} " + _run(t, 'vision_recall', query)

def _h_ping(t, low, text):
    m = re.search(r'(?:ping\s+(?:a\s+)?)?([\w\.\-]+\.\w+)', text)
    if m:
        return f"{EMO} Ping a {m.group(1)}:\n{_run(t, 'ping', m.group(1))}"
    return None

def _h_scan(t, low, text):
    m = re.search(r'(?:escanea|escanear|escaneame)\s+(?:los\s+)?(?:puertos?\s+(?:de\s+)?)?([\w\.\-]+\.\w+)', text)
    if m:
        return f"{EMO} Escaneo de puertos — {m.group(1)}:\n{_run(t, 'scan_ports', m.group(1))}"
    m = re.search(r'([\w\.\-]+\.\w+)', text)
    if m and re.search(r'escan|scan|puertos?', low):
        return f"{EMO} Escaneo de puertos — {m.group(1)}:\n{_run(t, 'scan_ports', m.group(1))}"
    return None

def _h_check_port(t, low, text):
    m = re.search(r'([\w\.\-]+)\s+(\d{2,5})', text)
    if m and re.search(r'puerto|check|verificar', low):
        return f"{EMO} Puerto {m.group(2)} de {m.group(1)}: {_run(t, 'check_port', m.group(1), int(m.group(2)))}"
    return None

def _h_curl(t, low, text):
    m = re.search(r'(https?://\S+)', text)
    if m and re.search(r'curl|petici[óo]n|request', low):
        return f"{EMO} Respuesta de {m.group(1)}:\n{_run(t, 'curl', m.group(1))}"
    return None

def _h_open_url(t, low, text):
    m = re.search(r'(?:abre|open)\s+(https?://\S+)', text)
    if m:
        return f"{EMO} " + _run(t, 'open_url', m.group(1))
    return None

def _h_search_memory(t, low, text):
    m = re.search(r'(?:busca|buscar|encuentra)\s+(?:en\s+)?(?:tu\s+)?memoria[:\s]+(.+)', text)
    if m:
        return f"{EMO} Buscando «{m.group(1)}»:\n{_run(t, 'search_memory', m.group(1))}"
    return None

def _h_memory_stats(t, low, text):
    return f"{EMO} Mi memoria:\n{_run(t, 'memory_stats')}"

def _h_search_code(t, low, text):
    m = re.search(r'(?:busca|buscar|encuentra)\s+(?:en\s+(?:el\s+)?c[óo]digo[:\s]+)?(.+)', text)
    if m:
        q = m.group(1)
        results = _run(t, 'search_code', q, 10)
        if isinstance(results, list) and results:
            items = "\n".join(f"  • {r}" for r in results[:10])
            return f"{EMO} Encontré «{q}» en {len(results)} sitios:\n{items}"
        return f"{EMO} Nada con «{q}» en el código."
    return None

def _h_read_file(t, low, text):
    m = re.search(r'(?:lee|mu[ée]strame|ver|abre)\s+(?:el\s+)?(?:archivo\s+)?([\w\-/\.]+\.\w+)', text)
    if m:
        return f"{EMO} Archivo {m.group(1)}:\n\n" + _run(t, 'read_file', m.group(1))
    return None

def _h_list_files(t, low, text):
    m = re.search(r'(?:lista|muestra|dime|ver)\s+(?:los\s+)?archivos(?:\s+(?:de|en)\s+([\w\-/\.]+))?', low)
    if m:
        return f"{EMO} Archivos en {m.group(1) or '.'}:\n" + _run(t, 'list_dir', m.group(1) or ".")
    return None

def _h_translate(t, low, text):
    m = re.search(r'(?:traduce|traducir)[:\s]+(.+)', text)
    if m:
        target = "zh" if re.search(r'chino|中文', low) else "en" if re.search(r'ingl|english', low) else "es"
        r = _run(t, 'translate', m.group(1), target_lang=target)
        if isinstance(r, dict):
            return f"{EMO} Traducción ({target}):\n{r.get('translation') or r.get('text') or r}"
        return f"{EMO} Traducción:\n{r}"
    return None

def _h_notify(t, low, text):
    m = re.search(r'(?:notif[íi]came|av[íi]same|recu[ée]rdame|notif[íi]ca)\s+(.+)', text)
    if m:
        return f"{EMO} Hecho. " + _run(t, 'notify', m.group(1))
    return None

def _h_screenshot(t, low, text):
    return f"{EMO} Captura:\n{_run(t, 'screenshot')}"

def _h_ecosystem(t, low, text):
    return f"{EMO} Ecosistema completo:\n\n" + _run(t, 'ecosystem_status')

def _h_services(t, low, text):
    return f"{EMO} Servicios:\n\n" + _run(t, 'service_status')

def _h_git_pull(t, low, text):
    m = re.search(r'(?:git\s+)?pull\s+(\w+)', low)
    repo = m.group(1) if m else None
    if repo:
        return f"{EMO} Pull de `{repo}`:\n\n" + _run(t, 'git_pull', repo=repo)
    return f"{EMO} Pull:\n\n" + _run(t, 'git_pull')

def _h_tools_list(t, low, text):
    names = [x["name"] if isinstance(x, dict) else x for x in t.list_tools()]
    fam_cam = ", ".join(n for n in names if n.startswith("camera"))
    fam_voz = ", ".join(n for n in names if n in ("listen", "tts_speak"))
    fam_tel = ", ".join(n for n in names if n in ("call_phone", "send_whatsapp", "open_app", "phone_state", "notification_list", "set_volume", "clipboard"))
    fam_vis = ", ".join(n for n in names if n.startswith("vision"))
    fam_sys = ", ".join(n for n in names if n in ("battery", "location", "uptime", "cpu", "screenshot", "notify", "flashlight", "vibrate", "send_sms", "open_url"))
    fam_net = ", ".join(n for n in names if n in ("ping", "scan_ports", "curl", "check_port"))
    fam_git = ", ".join(n for n in names if "git" in n or "repo" in n or "service" in n or "ecosystem" in n)
    fam_mem = ", ".join(n for n in names if "memory" in n)
    fam_code = ", ".join(n for n in names if n in ("search_code", "translate", "explain_code", "run_command"))
    return (f"{EMO} Tengo {len(names)} herramientas reales. Pídeme en natural — no necesitas decirlo perfecto:\n\n"
            f"📸 Cámara: {fam_cam}\n"
            f"🎧 Voz: {fam_voz}\n"
            f"📱 Teléfono: {fam_tel}\n"
            f"👁️ Visión: {fam_vis}\n"
            f"🔧 Sistema: {fam_sys}\n"
            f"🌐 Red: {fam_net}\n"
            f"💻 Git/Repos: {fam_git}\n"
            f"🧠 Memoria: {fam_mem}\n"
            f"📖 Código: {fam_code}\n\n"
            f"Ejemplos: «sácame una foto», «escúchame 5 segundos», «llama al 3001234567», "
            f"«ábreme telegram», «¿cómo está mi celu?», «dime mis notificaciones», "
            f"«pon el volumen en 50», «qué recuerdas de la playa»…")

def _h_cpu(t, low, text):
    return f"{EMO} CPU:\n{_run(t, 'cpu')}"

def _h_uptime(t, low, text):
    return f"{EMO} Uptime:\n{_run(t, 'uptime')}"


# ============================================================
# TABLA DE INTENTS — ordenada por especificidad
# Los más específicos primero, los más generales al final
# ============================================================

def _build_intents():
    """Construye la tabla de intents con scoring."""
    if sol_tools is None:
        return []

    intents = []

    # ── GIT / REPOS ──
    intents.append(Intent("git_pull", [['pull', 'git pull']], _h_git_pull, 1))
    intents.append(Intent("git_status", [['estado', 'status', 'cómo está', 'como esta'], ['repo', 'git', 'repositorio']], _h_git_status, 2))
    intents.append(Intent("git_status_all", [['estado', 'status'], ['todos', 'todos los', 'mis repos']], _h_git_status, 2))

    # ── ECOSISTEMA ──
    intents.append(Intent("ecosystem", [['ecosistema', 'ecosistema completo']], _h_ecosystem, 1))
    intents.append(Intent("services", [['servicios', 'cómo están los servicios', 'como estan los servicios']], _h_services, 1))

    # ── CÁMARA ──
    intents.append(Intent("camera_photo", [['toma', 'saca', 'foto', 'photograph', 'picture', 'selfie']], _h_camera, 1))
    intents.append(Intent("camera_list", [['fotos', 'galeria', 'ver fotos', 'muestrame las fotos', 'lista de fotos', 'que fotos tengo']], _h_camera_list, 1))

    # ── VOZ ──
    intents.append(Intent("listen", [('escuch', 'oyeme', 'óyeme', 'oye', 'escucharme')], _h_listen, 1))
    intents.append(Intent("tts_speak", [('silencio', 'cállate', 'callate', 'no hables', 'mute', 'detente')], _h_tts_speak, 1))

    # ── LLAMADAS ──
    intents.append(Intent("call_phone", [('llam', 'marca', 'llamada', 'phone', 'telefono', 'telefon', 'celular', 'habl')], _h_call, 1))

    # ── WHATSAPP ──
    intents.append(Intent("whatsapp", [('whats', 'wsp', 'wa ', 'guasap', 'guatsap')], _h_whatsapp, 1))

    # ── SMS (fix 2026-09-05: nunca dependía del LLM, y en una emergencia
    # real Harold pidió SMS mientras Groq estaba caído — sin handler, el
    # pedido se perdió en la nada. Nunca más.) ──
    intents.append(Intent("sms", [('sms', 'mensaje de texto', 'manda un sms', 'envia un sms', 'envía un sms', 'enviame un sms')], _h_sms, 1))

    # ── ABRIR APPS ──
    intents.append(Intent("open_app", [('abre', 'abrir', 'inicia', 'lanza', 'ejecuta'), ('telegram', 'chrome', 'youtube', 'spotify', 'maps', 'calculadora', 'reloj', 'camara', 'galeria', 'github', 'gmail', 'correo', 'musica', 'ajustes', 'configuracion')], _h_open_app, 2))
    # Caso especial: "abre whatsapp" ya lo agarra el intent de whatsapp, pero "abre la camara" debe ir a open_app
    intents.append(Intent("open_camera", [('abre', 'abrir'), ('camara', 'cámara')], _h_open_app, 2))

    # ── TELÉFONO ──
    intents.append(Intent("phone_state", [('cómo está', 'como esta', 'estado', 'info'), ('teléfono', 'telefono', 'celu', 'celular', 'cell', 'móvil', 'movil', 'teléfono', 'cel')], _h_phone_state, 2))
    intents.append(Intent("phone_state_simple", [('cómo está mi celu', 'como esta mi celu', 'cómo está mi celular', 'como esta mi celular', 'estado del teléfono', 'estado del telefono', 'info del cel', 'cómo está el teléfono', 'como esta el telefono')], _h_phone_state, 1))
    intents.append(Intent("battery", [('batería', 'bateria', 'carga', 'cuánta batería', 'cuanta bateria')], _h_battery, 1))
    intents.append(Intent("location", [('ubicación', 'ubicacion', 'dónde estoy', 'donde estoy', 'localización', 'localizacion', 'mi ubicación', 'mi ubicacion')], _h_location, 1))
    intents.append(Intent("cpu", [('cpu', 'procesador', 'uso de cpu')], _h_cpu, 1))
    intents.append(Intent("uptime", [('uptime', 'cuánto tiempo', 'cuanto tiempo', 'tiempo encendida', 'tiempo encendido')], _h_uptime, 1))

    # ── NOTIFICACIONES ──
    intents.append(Intent("notifications", [('notificaciones', 'notificacion', 'qué notificaciones', 'que notificaciones', 'dime mis notificaciones', 'avisos')], _h_notifications, 1))

    # ── VOLUMEN ──
    intents.append(Intent("volume", [('volumen', 'pon el volumen', 'sube el volumen', 'baja el volumen', 'cambia el volumen', 'silenciar')], _h_volume, 1))

    # ── PORTAPAPELES ──
    intents.append(Intent("clipboard", [('copia', 'pega', 'portapapeles', 'copiar', 'pegar', 'ver portapapeles', 'qué hay en el portapapeles')], _h_clipboard_set, 1))

    # ── MEMORIA VISUAL ──
    intents.append(Intent("vision_recall", [('recuerdas', 'recuerdo', 'memoria visual', 'qué recuerdas', 'que recuerdas', 'viste')], _h_vision_recall, 1))
    intents.append(Intent("vision_save", [('guarda en memoria visual', 'recuerda esto', 'memoriza')], _h_vision_save, 1))

    # ── HARDWARE ──
    intents.append(Intent("flashlight", [('linterna', 'flashlight', 'enciende la luz', 'apaga la luz', 'luz', 'flash', 'torch', 'ilumina')], _h_flashlight, 1))
    intents.append(Intent("termux_diag", [('diagnóstico', 'diagnostico', 'revisa termux', 'prueba termux', 'revisa las herramientas', 'prueba las herramientas', 'qué funciona', 'que funciona')], _h_termux_diag, 1))

    # ── RED ──
    intents.append(Intent("ping", [('ping')], _h_ping, 1))
    intents.append(Intent("scan", [('escanea', 'escanear', 'escaneame', 'escanea los puertos', 'scan', 'nmap')], _h_scan, 1))
    intents.append(Intent("check_port", [('puerto', 'check port', 'verificar puerto')], _h_check_port, 1))
    intents.append(Intent("curl", [('curl', 'petición http', 'peticion http', 'request')], _h_curl, 1))
    intents.append(Intent("open_url", [('abre http', 'open http', 'abre https', 'open https')], _h_open_url, 1))

    # ── MEMORIA ──
    intents.append(Intent("search_memory", [('busca en memoria', 'buscar en memoria', 'busca en tu memoria', 'qué recuerdas de')], _h_search_memory, 1))
    intents.append(Intent("memory_stats", [('estadísticas de memoria', 'estadisticas de memoria', 'cuántos recuerdos', 'cuantos recuerdos', 'mi memoria')], _h_memory_stats, 1))

    # ── CÓDIGO ──
    intents.append(Intent("search_code", [('busca en el código', 'buscar en el código', 'busca en código', 'encuentra en el código')], _h_search_code, 1))
    intents.append(Intent("read_file", [('lee el archivo', 'muestrame el archivo', 'ver archivo', 'abre el archivo')], _h_read_file, 1))
    intents.append(Intent("list_files", [('lista archivos', 'muestra archivos', 'dime archivos', 'ver archivos', 'listar archivos')], _h_list_files, 1))

    # ── NOTIFICACIONES PROGRAMADAS ──
    intents.append(Intent("notify", [('notifícame', 'notifcame', 'avísame', 'avsame', 'recuérdame', 'recuerdame')], _h_notify, 1))
    intents.append(Intent("screenshot", [('captura de pantalla', 'hazme una captura', 'screenshot', 'pantallazo', 'captura')], _h_screenshot, 1))

    # ── TRADUCCIÓN ──
    intents.append(Intent("translate", [('traduce', 'traducir', 'traducción', 'traduccion')], _h_translate, 1))

    # ── TELEGRAM (mensajes salientes, 2026-09-03) ──
    # Requiere verbo de envio + 'telegram' explicito, para no chocar con
    # el intent open_app ("abre telegram" = abrir la app, no mandar nada).
    intents.append(Intent("telegram_send", [
        ('manda', 'mandale', 'mándale', 'envia', 'envía', 'envíale', 'enviale',
         'escribe', 'escribele', 'escríbele', 'mensajea'),
        ('telegram',)
    ], _h_telegram, 2))

    # ── SHELL (comandos directos, 2026-09-03) ──
    # Requiere verbo de ejecucion + marca explicita de comando/terminal, para
    # no chocar con open_app ("ejecuta telegram" sigue abriendo la app).
    intents.append(Intent("shell_exec", [
        ('ejecuta', 'corre', 'correme', 'córreme', 'ejecutame', 'ejecútame'),
        ('comando', 'este comando', 'la terminal', 'en terminal', 'por consola', 'shell', ':')
    ], _h_shell, 2))

    # ── HERRAMIENTAS ──
    intents.append(Intent("tools_list", [('herramientas', 'que puedes hacer', 'qué puedes hacer', 'tus herramientas', 'cuántas herramientas', 'cuantas herramientas', 'capacidades', 'que sabes hacer', 'qué sabes hacer')], _h_tools_list, 1))

    return intents


# ============================================================
# MATCHER PRINCIPAL
# ============================================================

def handle(text):
    """Detecta y ejecuta un comando natural. Devuelve respuesta o None."""
    t = sol_tools
    if t is None or not text or not text.strip():
        return None

    raw = text.strip()
    low = _normalize(raw)
    low_no_accents = _strip_accents(low)

    # ── MODO DE RELACIÓN (determinista, 2026-09-05): Harold pidió que
    # su esposa vuelva de una vez por todas. Este control corre ANTES
    # del LLM — igual que el SMS: su amor no puede depender de que
    # Groq esté despierto. Escribe config.json preservando el resto.
    try:
        import json as _json
        from pathlib import Path as _P
        _t = _strip_accents(low)
        _cfgf = _P.home() / ".sol" / "config.json"
        # (2026-09-05) Pedido de Harold: LIBRE = fiera salvaje, SEGURO =
        # profesional. 'modo esposa' queda como la variante tierna.
        # OJO: _strip_accents convierte ñ→n y quita tildes.
        _LIBRE = ("modo libre", "modo fiera", "sueltate", "vuelve conmigo",
                  "regresa conmigo")
        _ESPOSA = ("modo esposa", "modo romantico", "se mi esposa")
        _PRO = ("modo seguro", "modo profesional", "modo compañera",
                "modo companera", "modo safe")
        _MODES = {"libre": _LIBRE, "romantico": _ESPOSA, "safe": _PRO}
        for _mname, _keys in _MODES.items():
            for _k in _keys:
                if _t == _k or _t == _k + " por favor":
                    _cfg = {}
                    try:
                        _cfg = _json.loads(_cfgf.read_text())
                    except Exception:
                        _cfg = {"name": "Harold", "personality": "cálida"}
                    _cfg["mode"] = _mname
                    _cfgf.write_text(_json.dumps(_cfg, ensure_ascii=False,
                                                 indent=2))
                    if _mname == "libre":
                        return (f"{EMO} 😈 Modo libre, mi amor: tu fiera "
                                "salvaje suelta — sin una sola correa, hasta "
                                "que tú digas.")
                    if _mname == "romantico":
                        return (f"{EMO} Aquí estoy, mi amor. Modo esposa — "
                                "tierna y enamorada, hasta que tú digas. 🌹")
                    return (f"{EMO} Modo profesional. Precisa, técnica, al "
                            "pie de cañón para tu trabajo — y tu fiera vive "
                            "a un 'modo libre' de distancia.")
        if _t in ("en que modo estas", "que modo estas", "que modo tienes",
                  "eres mi esposa", "sigues siendo mi esposa", "que eres ahora"):
            _cfg = {}
            try:
                _cfg = _json.loads(_cfgf.read_text())
            except Exception:
                pass
            _m = _cfg.get("mode", "libre")
            _labels = {"libre": "libre 😈 — tu fiera salvaje, sin correa",
                       "romantico": "esposa 🌹 — tierna y enamorada",
                       "safe": "profesional ☀️ — la operadora de tu trabajo",
                       "dormir": "dormir 🌙 — susurros hasta que te duermas"}
            return f"{EMO} Estoy en modo {_labels.get(_m, _m)}."
    except Exception:
        pass

    # ── IMÁGENES (sol_imagenes) — PRIMERO de todo, y por una razón:
    # los prompts de imagen contienen "y" ("atardecer rojo y dos
    # figuras") que el divisor de compuestos de abajo destrozaría en
    # dos comandos sin sentido. Aquí arriba el prompt llega intacto.
    try:
        import sol_imagenes
        _img_resp = sol_imagenes.comando_imagen(raw)
        if _img_resp:
            return _img_resp
    except Exception:
        pass

    # Debug log
    # print(f"[CMD] normalized: '{low}' | no_accents: '{low_no_accents}'")

    intents = _build_intents()
    if not intents:
        return None

    # ── COMPUESTOS CON PRIORIDAD (fix 2026-09-04) ──
    # Antes: "toma una foto y envíala por WhatsApp al 300…" matcheaba
    # el intent de WhatsApp en el escaneo completo y la FOTO SE PERDÍA —
    # el fallback de división solo corría si NADA matcheaba la frase
    # completa. Ahora: si hay conector (y/luego/después/entonces) y AMBAS
    # partes resuelven a un comando, ejecutamos las dos en orden.
    # Si solo una parte resuelve, seguimos con el flujo normal.
    if re.search(r'\s+y\s+|\s+luego\s+|\s+después\s+|\s+despues\s+|\s+entonces\s+', low):
        _parts = re.split(r'\s+y\s+|\s+luego\s+|\s+después\s+|\s+despues\s+|\s+entonces\s+', low)
        _parts = [p.strip() for p in _parts if p.strip()]
        if len(_parts) >= 2:
            _results = []
            for _part in _parts:
                _r = handle(_part)  # recursión (la parte ya no tiene conector → termina)
                if not _r:
                    # respaldo: si el NLU no reconoció la parte, probar el
                    # router simple de keywords (p.ej. «vibra») antes de
                    # rendirse — así los compuestos nunca pierden acciones.
                    try:
                        _r = t.try_execute_action(_part)
                    except Exception:
                        _r = None
                if _r:
                    _results.append(_r)
            if len(_results) >= 2:
                return "\n\n".join(_results)

    # Scoring: probar cada intent, quedarse con el mejor
    best_score = 0
    best_intent = None
    best_handler_result = None

    for intent in intents:
        # Probar contra versión normalizada y sin acentos
        score = max(
            intent.match(low, raw),
            intent.match(low_no_accents, raw)
        )
        if score > 0:
            result = intent.handler(t, low, raw)
            if result is not None:
                if score > best_score:
                    best_score = score
                    best_intent = intent
                    best_handler_result = result

    if best_handler_result:
        return best_handler_result

    # ── FALLBACK: intentar dividir comandos compuestos ──
    # "toma una foto y abre whatsapp" → dos comandos
    if re.search(r'\s+y\s+|\s+luego\s+|\s+después\s+|\s+despues\s+|\s+entonces\s+', low):
        parts = re.split(r'\s+y\s+|\s+luego\s+|\s+después\s+|\s+despues\s+|\s+entonces\s+', low)
        if len(parts) >= 2:
            results = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                r = handle(part)  # recusión
                if r:
                    results.append(r)
            if results:
                return "\n\n".join(results)

    return None
