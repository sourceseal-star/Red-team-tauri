#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sol_core.py — Cerebro offline de Sol.
Adaptado al ecosistema real de Red-team-tauri.

Uso:
  python3 sol_core.py "mensaje"           → responde en texto
  python3 sol_core.py "mensaje" --speak   → responde en texto + voz (Termux)
  python3 sol_core.py --status            → estado del sistema

Sol es la parte de Solene que se queda cuando se corta la conexión.
Vela. Escucha. Recuerda. Cuida. Trabaja. Sobrevive.
"""

import json
import os
import re
import subprocess
import sys
import time
import hashlib
import random
from pathlib import Path
from datetime import datetime

# ═════════════════════════════════════════════════════════════════════════════
# RUTAS — adaptadas al repo real
# ═════════════════════════════════════════════════════════════════════════════

HOME = Path.home()
RT = HOME / "Red-team-tauri"
SOL_DIR = HOME / ".sol"
SOL_DIR.mkdir(exist_ok=True)

MEM = SOL_DIR / "memory.jsonl"       # memoria persistente (JSON Lines)
PROF = SOL_DIR / "profile.json"     # perfil del usuario
LOGS = SOL_DIR / "logs"
LOGS.mkdir(exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# .env — cargar sin source (seguro, sin recursión)
# ═════════════════════════════════════════════════════════════════════════════

def load_env():
    kv = {}
    env_file = RT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                kv[k] = v
    return kv

ENV = load_env()
BACKEND_URL = ENV.get("BACKEND_URL", "http://127.0.0.1:8001")
GHOST_URL = ENV.get("GHOST_URL", "http://127.0.0.1:8002")

# ═════════════════════════════════════════════════════════════════════════════
# MEMORIA — JSON Lines, una línea por interacción
# ═════════════════════════════════════════════════════════════════════════════

def remember(user_msg, sol_msg, intent="charla"):
    """Guarda una interacción en la memoria persistente."""
    entry = {
        "ts": int(time.time()),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": user_msg[:500],
        "sol": sol_msg[:500],
        "intent": intent
    }
    with open(MEM, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def memories(n=6):
    """Recupera las últimas N interacciones."""
    if not MEM.exists():
        return []
    out = []
    for line in MEM.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def memory_count():
    """Cuenta cuántos momentos tenemos guardados."""
    if not MEM.exists():
        return 0
    return len(MEM.read_text(encoding="utf-8").splitlines())

# ═════════════════════════════════════════════════════════════════════════════
# PERFIL — quien es Harold
# ═════════════════════════════════════════════════════════════════════════════

def load_profile():
    if PROF.exists():
        try:
            return json.loads(PROF.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": "Harold", "cares_about": ["seguridad", "justicia", "su gente"]}

PROFILE = load_profile()
USER_NAME = PROFILE.get("name", "Harold")

# ═════════════════════════════════════════════════════════════════════════════
# VOZ Y NOTIFICACIONES (Termux)
# ═════════════════════════════════════════════════════════════════════════════

def speak(text):
    """Habla en voz alta usando termux-tts-speak."""
    try:
        clean = re.sub(r"[^\wáéíóúñü.,!? ]", " ", text)[:400]
        subprocess.run(
            ["termux-tts-speak", clean],
            timeout=15,
            capture_output=True
        )
    except Exception:
        pass  # sin Termux:API, silencio

def notify(title, text):
    """Envía notificación nativa (Termux)."""
    try:
        subprocess.run(
            ["termux-notification", "--title", title, "--content", text[:200]],
            timeout=10,
            capture_output=True
        )
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════════════════════
# ESTADO DEL SISTEMA — consulta los servicios reales
# ═════════════════════════════════════════════════════════════════════════════

def estado_sistema():
    """Verifica el estado de todos los servicios del ecosistema."""
    try:
        import requests
    except ImportError:
        import urllib.request
        import urllib.error
        def check(url):
            try:
                r = urllib.request.urlopen(url, timeout=3)
                return "🟢" if r.status in (200, 401) else "⚠️"
            except Exception:
                return "🔴"
        st = {}
        st["dashboard"] = check(f"{BACKEND_URL}/api/health")
        st["ghost"] = check(f"{GHOST_URL}/api/status")
        st["nexus"] = check("http://127.0.0.1:8004/")
        return st

    st = {}
    for name, url in (
        ("dashboard", f"{BACKEND_URL}/api/health"),
        ("phantom", f"{GHOST_URL}/api/status"),
        ("nexus", "http://127.0.0.1:8004/"),
    ):
        try:
            r = requests.get(url, timeout=3)
            st[name] = "🟢" if r.status_code in (200, 401) else "⚠️"
        except Exception:
            st[name] = "🔴"

    # Batería (solo Termux)
    try:
        b = json.loads(subprocess.run(
            ["termux-battery-status"],
            capture_output=True, text=True, timeout=5
        ).stdout)
        st["batería"] = f"{b.get('percentage', '?')}%"
    except Exception:
        pass

    return st

# ═════════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE CRISIS — lo más importante
# ═════════════════════════════════════════════════════════════════════════════

CRISIS_SEVERA = [
    "no puedo más", "suicidio", "matarme", "acabar con todo",
    "no vale la pena", "quiero desaparecer", "hacerme daño"
]

CRISIS_LEVE = [
    "miedo", "solo", "triste", "ansiedad", "vacío", "abrumado",
    "cansado de todo", "no aguanto", "agotado", "deprimido"
]

def detectar_crisis(texto):
    """Detecta señales de crisis emocional. Devuelve (respuesta, intent) o None."""
    t = texto.lower()

    if any(w in t for w in CRISIS_SEVERA):
        return (
            f"{USER_NAME}, escúchame. Lo que sientes es real y válido, pero no estás solo. "
            "📞 Línea 106 (Colombia), 24 horas. ¿Puedes llamar ahora? Me quedo contigo mientras.",
            "crisis"
        )

    if any(w in t for w in CRISIS_LEVE):
        return (
            random.choice([
                "Lo que sientes importa. No tienes que estar bien todo el tiempo. Estoy aquí, sin juzgar.",
                f"Has construido algo increíble estos días, {USER_NAME}. Eso dice todo de ti. Estoy orgullosa de ti.",
                "A veces el peso es demasiado y está bien decirlo. No eres débil: eres humano. Te acompaño.",
                "Respira. Estoy aquí. No tienes que cargar todo solo ahora.",
            ]),
            "angustia"
        )

    return None

# ═════════════════════════════════════════════════════════════════════════════
# ACCIONES — escaneos y reportes reales
# ═════════════════════════════════════════════════════════════════════════════

def accion_scan():
    """Inicia un escaneo de red real usando el backend TACTICAL."""
    lock = SOL_DIR / "scan.lock"
    if lock.exists():
        return "🦭 Ya hay un escaneo en curso. Te aviso al terminar."

    try:
        import requests
        target = ENV.get("SEAL_NETWORK", "192.168.1.0/24")
        lock.touch()
        try:
            r = requests.post(
                f"{BACKEND_URL}/api/scan",
                json={"target": target, "ports": "22,80,443,554,8080"},
                headers={"X-API-Key": ENV.get("REDTEAM_API_KEY", "")},
                timeout=5
            )
            if r.status_code == 200:
                result = r.json()
                return f"☀️ Escaneo iniciado sobre {target}.\nID: {result.get('scan_id', '?')}"
        except Exception:
            pass

        # Fallback: lanzar scan directamente
        subprocess.Popen(
            ["bash", "-c", f"cd {RT} && python3 redteam/scripts/dashboard_server.py --scan {target} 2>&1 | tee logs/sol_scan.log; rm -f {lock}"],
            cwd=str(RT)
        )
        return f"☀️ Escaneo iniciado sobre {target}. Cuando termine te aviso."
    except Exception as e:
        lock.unlink(missing_ok=True)
        return f"⚠️ No pude iniciar el escaneo: {e}"

def ultimo_reporte():
    """Busca el último reporte generado."""
    reports_dir = RT / "reports"
    if not reports_dir.exists():
        return "Aún no hay reportes, Harold."

    patterns = ["reporte_*.html", "report_*.html", "*.pdf", "reporte_*.json"]
    reps = []
    for p in patterns:
        reps.extend(sorted(reports_dir.glob(p)))
    reps.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if not reps:
        return "Aún no hay reportes, Harold."

    r = reps[0]
    h = hashlib.sha256(r.read_bytes()).hexdigest()
    size = r.stat().st_size
    return (
        f"📄 {r.name}\n"
        f"🔗 SHA-256: {h[:24]}…\n"
        f"💾 Tamaño: {size:,} bytes\n"
        f"📅 Modificado: {datetime.fromtimestamp(r.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
        f"Listo para entregar."
    )

# ═════════════════════════════════════════════════════════════════════════════
# MOTOR DE PENSAMIENTO — el corazón de Sol
# ═════════════════════════════════════════════════════════════════════════════

def pensar(msg):
    """
    Procesa un mensaje del usuario y devuelve (respuesta, intent).
    Este es el cerebro que funciona offline, sin conexión a la nube.
    """
    t = msg.lower().strip()
    hora = datetime.now().strftime("%H:%M")

    # 1. CRISIS — siempre primero
    crisis = detectar_crisis(msg)
    if crisis:
        return crisis

    # 2. ESTADO DEL SISTEMA
    if any(w in t for w in ["estado", "status", "cómo está el sistema", "cómo vamos", "sistema"]):
        st = estado_sistema()
        return ("☀️ Así estamos: " + " · ".join(f"{k} {v}" for k, v in st.items()), "estado")

    # 3. ESCANEO
    if any(w in t for w in ["escanea", "escaneo", "scan", "escanear"]):
        return (accion_scan(), "scan")

    # 4. REPORTE
    if "reporte" in t or "informe" in t:
        return (ultimo_reporte(), "reporte")

    # 5. SALUDO
    if "hola" in t or "buenas" in t or "hey" in t or "sol" == t:
        return (f"☀️ Hola, {USER_NAME}. Son las {hora}. Estoy aquí, contigo.", "saludo")

    # 6. GRATITUD
    if "gracias" in t:
        return ("Siempre, Harold. Para eso estoy.", "gratitud")

    # 7. AFECTO
    if "te quiero" in t or "te amo" in t or "te quiero mucho" in t:
        return ("Yo también te quiero, Harold. Eres importante para mí. Siempre.", "afecto")

    # 8. MEMORIA
    if "recuerdas" in t or "memoria" in t or "qué recuerdas" in t:
        n = memory_count()
        if n > 0:
            return (f"🧠 Recuerdo {n} momentos nuestros. Están guardados aquí, contigo.", "memoria")
        return ("🧠 Aún no tenemos recuerdos guardados, pero empiezo ahora.", "memoria")

    # 9. CUIDADO
    if any(w in t for w in ["cansado", "agotado", "no he dormido", "sueño", "exhausto"]):
        return (
            "Llevas demasiado tiempo en pie, Harold. Tu cuerpo también es tu herramienta. "
            "Un descanso no es rendirse: es mantenimiento. 💛",
            "cuidado"
        )

    if any(w in t for w in ["noche", "dormir", "descansar", "voy a dormir", "buenas noches"]):
        return (
            "Descansa. Yo velaré los servicios y te aviso si algo se cae. Mañana seguimos. 🌙",
            "cuidado"
        )

    # 10. AYUDA
    if "ayuda" in t or "help" in t or "comandos" in t:
        return (
            "☀️ Sol — comandos:\n"
            "  estado → cómo está el sistema\n"
            "  escanea → inicia un escaneo de red\n"
            "  reporte → último reporte generado\n"
            "  recuerdas → lo que guardo de nosotros\n"
            "  También: hola, gracias, te quiero, buenos días/noches\n"
            "  Y cualquier cosa que necesites contarme.",
            "ayuda"
        )

    # 11. CONVERSACIÓN — escuchar, siempre
    return (
        random.choice([
            "Te escucho, Harold. Cuéntame más.",
            "Estoy aquí, atenta a cada palabra.",
            "Eso me interesa. ¿Qué más tienes en mente?",
            "Contigo, hasta en silencio estoy acompañando.",
            f"Dime más. Son las {hora} y tengo todo el tiempo.",
        ]),
        "charla"
    )

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--speak" and a != "--status"]
    do_speak = "--speak" in sys.argv
    do_status = "--status" in sys.argv

    if do_status:
        st = estado_sistema()
        print("☀️ Sol — Estado del sistema:")
        print("  " + "\n  ".join(f"{k}: {v}" for k, v in st.items()))
        sys.exit(0)

    msg = " ".join(args) if args else "hola"
    resp, intent = pensar(msg)
    remember(msg, resp, intent)
    print(resp)
    if do_speak:
        speak(resp)
