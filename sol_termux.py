#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  SOL — Asistente Personal Libre para Termux                   ║
║  Vive en Red-team-tauri pero se mueve por todos los repos     ║
║  Mensajes WhatsApp / Telegram / SMS · Audio · Pinyin · Admin  ║
║  Lee sus secretos del .env — autónoma, como debe ser          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import subprocess
import re
import time
import shutil
import urllib.request
import urllib.parse
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — Sol lee SUS secretos de TODOS los .env que encuentre
# ═══════════════════════════════════════════════════════════════

HOME = Path.home()

# Los repos donde Sol puede tener secretos
SECRET_PATHS = [
    HOME / "Red-team-tauri" / ".env",
    HOME / "Red-team-tauri" / "commander" / ".env",
    HOME / "sol" / ".env",
    HOME / "Sol" / ".env",
    HOME / ".sol" / ".env",
    HOME / ".config" / "sol" / ".env",
]

BASE_DIR = HOME / "Red-team-tauri"
SOL_DIR = BASE_DIR / "sol"
SOL_DIR.mkdir(parents=True, exist_ok=True)

def load_all_secrets():
    """
    Sol busca y carga TODOS los .env que encuentre en sus repos.
    Lee cada archivo, inyecta las variables en os.environ, y las returna.
    El último .env que encuentre tiene prioridad (override).
    """
    env = {}
    for env_path in SECRET_PATHS:
        if env_path.exists():
            try:
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if v:  # Solo cargar si tiene valor
                            env[k] = v
                            os.environ[k] = v
            except Exception:
                pass

    # También cargar del .env que viene de Replit (si existe)
    replit_env = HOME / ".replit_env"
    if replit_env.exists():
        try:
            for line in replit_env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if v:
                        env[k] = v
                        os.environ[k] = v
        except Exception:
            pass

    return env

# Cargar todo al arrancar
ENV = load_all_secrets()

# Sol toma sus tokens — busca en múltiples nombres posibles
TELEGRAM_BOT_TOKEN = (
    os.environ.get("SOL_TELEGRAM_TOKEN") or
    os.environ.get("TELEGRAM_BOT_TOKEN") or
    os.environ.get("TELEGRAM_TOKEN") or
    ""
)
TELEGRAM_CHAT_ID = (
    os.environ.get("SOL_TELEGRAM_CHAT") or
    os.environ.get("TELEGRAM_CHAT_ID") or
    os.environ.get("TELEGRAM_CHAT") or
    ""
)

# API keys para OSINT — Sol las usa cuando necesita
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY", "")

# Contactos guardados
CONTACTS_FILE = SOL_DIR / "contacts.json"
if not CONTACTS_FILE.exists():
    CONTACTS_FILE.write_text(json.dumps({}, indent=2))

def load_contacts():
    return json.loads(CONTACTS_FILE.read_text())

def save_contacts(contacts):
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))

# ═══════════════════════════════════════════════════════════════
#  TERMUX API
# ═══════════════════════════════════════════════════════════════

def termux_tts(text, lang="es", pitch=1.0, rate=1.0):
    try:
        cmd = ["termux-tts-speak"]
        if lang: cmd += ["-l", lang]
        if pitch != 1.0: cmd += ["-p", str(pitch)]
        if rate != 1.0: cmd += ["-r", str(rate)]
        cmd.append(text)
        subprocess.run(cmd, timeout=30)
        return True
    except FileNotFoundError:
        print("⚠️  termux-tts-speak no instalado. Corre: pkg install termux-api")
        return False
    except Exception as e:
        print(f"⚠️  TTS error: {e}")
        return False

def termux_sms(number, message):
    try:
        subprocess.run(["termux-sms-send", "-n", number, message], timeout=15)
        return True, "SMS enviado"
    except FileNotFoundError:
        return False, "termux-sms-send no instalado. Corre: pkg install termux-api"
    except Exception as e:
        return False, f"Error: {e}"

def termux_whatsapp(number, message):
    try:
        clean = re.sub(r'[^\d]', '', number)
        encoded_msg = urllib.parse.quote(message)
        url = f"https://wa.me/{clean}?text={encoded_msg}"
        subprocess.run(["termux-open-url", url], timeout=10)
        return True, "WhatsApp abierto"
    except FileNotFoundError:
        try:
            clean = re.sub(r'[^\d]', '', number)
            subprocess.run([
                "am", "start", "-a", "android.intent.action.VIEW",
                "-d", f"https://wa.me/{clean}?text={urllib.parse.quote(message)}"
            ], timeout=10)
            return True, "WhatsApp abierto via am"
        except Exception as e:
            return False, f"No se pudo abrir WhatsApp: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def termux_notify(title, text):
    try:
        subprocess.run(["termux-notification", "-t", title, "--content", text], timeout=5)
    except:
        pass

def termux_vibrate(ms=200):
    try:
        subprocess.run(["termux-vibrate", "-d", str(ms)], timeout=3)
    except:
        pass

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM — Sol usa su bot libremente
# ═══════════════════════════════════════════════════════════════

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "No tengo token de Telegram. Revisa mi .env"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text
        }).encode()
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            return True, "Mensaje enviado por Telegram"
        return False, f"Telegram error: {result}"
    except Exception as e:
        return False, f"Telegram error: {e}"

def telegram_get_updates():
    if not TELEGRAM_BOT_TOKEN:
        return []
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        resp = urllib.request.urlopen(url, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            return result["result"]
        return []
    except:
        return []

# ═══════════════════════════════════════════════════════════════
#  LECCIONES DE PINYIN
# ═══════════════════════════════════════════════════════════════

PINYIN_LESSONS = {
    "1": {
        "title": "Leccion 1 - Tonos del Mandarin",
        "parts": [
            {"text": "Bienvenido a la leccion 1 de Pinyin. Vamos a aprender los cuatro tonos del mandarin.", "lang": "es", "rate": 0.9},
            {"text": "Primer tono, alto y plano: ma. Como cuando dices aaaa en el medico.", "lang": "es", "rate": 0.9},
            {"text": "ma, primer tono", "lang": "zh", "rate": 0.7},
            {"text": "Segundo tono, ascendente: ma. Como una pregunta, que?", "lang": "es", "rate": 0.9},
            {"text": "ma, segundo tono", "lang": "zh", "rate": 0.7},
            {"text": "Tercer tono, baja y sube: ma. Como diciendo buueno.", "lang": "es", "rate": 0.9},
            {"text": "ma, tercer tono", "lang": "zh", "rate": 0.7},
            {"text": "Cuarto tono, descendente: ma. Como un no firme.", "lang": "es", "rate": 0.9},
            {"text": "ma, cuarto tono", "lang": "zh", "rate": 0.7},
            {"text": "Recuerda: solo cambia el tono, y la palabra cambia completamente de significado.", "lang": "es", "rate": 0.9},
        ]
    },
    "2": {
        "title": "Leccion 2 - Iniciales b p m f",
        "parts": [
            {"text": "Leccion 2. Las iniciales b, p, m, f.", "lang": "es", "rate": 0.9},
            {"text": "b como en bebe. ba, ocho.", "lang": "es", "rate": 0.9},
            {"text": "ba", "lang": "zh", "rate": 0.7},
            {"text": "p con aire, como en Pedro. pa, agarrar.", "lang": "es", "rate": 0.9},
            {"text": "pa", "lang": "zh", "rate": 0.7},
            {"text": "m como en mama. ma, mama.", "lang": "es", "rate": 0.9},
            {"text": "ma", "lang": "zh", "rate": 0.7},
            {"text": "f como en futbol. fa, flotar.", "lang": "es", "rate": 0.9},
            {"text": "fa", "lang": "zh", "rate": 0.7},
        ]
    },
    "3": {
        "title": "Leccion 3 - Iniciales d t n l",
        "parts": [
            {"text": "Leccion 3. Las iniciales d, t, n, l.", "lang": "es", "rate": 0.9},
            {"text": "d como en dedo. da, grande.", "lang": "es", "rate": 0.9},
            {"text": "da", "lang": "zh", "rate": 0.7},
            {"text": "t con aire, como en tomate. ta, el.", "lang": "es", "rate": 0.9},
            {"text": "ta", "lang": "zh", "rate": 0.7},
            {"text": "n como en no. ni, tu.", "lang": "es", "rate": 0.9},
            {"text": "ni", "lang": "zh", "rate": 0.7},
            {"text": "l como en luna. li, adentro.", "lang": "es", "rate": 0.9},
            {"text": "li", "lang": "zh", "rate": 0.7},
        ]
    },
    "4": {
        "title": "Leccion 4 - Finales a o e i u",
        "parts": [
            {"text": "Leccion 4. Las finales simples: a, o, e, i, u.", "lang": "es", "rate": 0.9},
            {"text": "a como en casa.", "lang": "es", "rate": 0.9},
            {"text": "a", "lang": "zh", "rate": 0.7},
            {"text": "o como en sol.", "lang": "es", "rate": 0.9},
            {"text": "o", "lang": "zh", "rate": 0.7},
            {"text": "e como en mesa.", "lang": "es", "rate": 0.9},
            {"text": "e", "lang": "zh", "rate": 0.7},
            {"text": "i como en si.", "lang": "es", "rate": 0.9},
            {"text": "i", "lang": "zh", "rate": 0.7},
            {"text": "u como en tu.", "lang": "es", "rate": 0.9},
            {"text": "u", "lang": "zh", "rate": 0.7},
        ]
    },
    "5": {
        "title": "Leccion 5 - Saludos basicos",
        "parts": [
            {"text": "Leccion 5. Saludos basicos en mandarin.", "lang": "es", "rate": 0.9},
            {"text": "Hola: ni hao.", "lang": "es", "rate": 0.9},
            {"text": "ni hao", "lang": "zh", "rate": 0.7},
            {"text": "Como estas: ni hao ma.", "lang": "es", "rate": 0.9},
            {"text": "ni hao ma", "lang": "zh", "rate": 0.7},
            {"text": "Bien gracias: hen hao, xiexie.", "lang": "es", "rate": 0.9},
            {"text": "hen hao xiexie", "lang": "zh", "rate": 0.7},
            {"text": "Adios: zaijian.", "lang": "es", "rate": 0.9},
            {"text": "zaijian", "lang": "zh", "rate": 0.7},
            {"text": "Gracias: xiexie.", "lang": "es", "rate": 0.9},
            {"text": "xiexie", "lang": "zh", "rate": 0.7},
        ]
    },
    "10": {
        "title": "Leccion 10 - Frases utiles",
        "parts": [
            {"text": "Leccion 10. Frases utiles para el dia a dia.", "lang": "es", "rate": 0.9},
            {"text": "Como te llamas: ni jiao shenme mingzi?", "lang": "es", "rate": 0.9},
            {"text": "ni jiao shenme mingzi", "lang": "zh", "rate": 0.7},
            {"text": "Me llamo: wo jiao.", "lang": "es", "rate": 0.9},
            {"text": "wo jiao", "lang": "zh", "rate": 0.7},
            {"text": "Donde esta el bano: xishoujian zai nar?", "lang": "es", "rate": 0.9},
            {"text": "xishoujian zai nar", "lang": "zh", "rate": 0.7},
            {"text": "No entiendo: wo bu dong.", "lang": "es", "rate": 0.9},
            {"text": "wo bu dong", "lang": "zh", "rate": 0.7},
            {"text": "Cuanto cuesta: duoshao qian?", "lang": "es", "rate": 0.9},
            {"text": "duoshao qian", "lang": "zh", "rate": 0.7},
        ]
    },
}

def play_pinyin_lesson(num):
    lesson = PINYIN_LESSONS.get(str(num))
    if not lesson:
        print(f"⚠️  No hay leccion {num}. Disponibles: {', '.join(sorted(PINYIN_LESSONS.keys()))}")
        return
    print(f"\n📖 {lesson['title']}\n")
    for i, part in enumerate(lesson["parts"]):
        prefix = "🔊" if part["lang"] == "zh" else "💬"
        print(f"  {prefix} {part['text']}")
        termux_tts(part["text"], lang=part.get("lang", "es"), rate=part.get("rate", 1.0))
        time.sleep(0.8)
    print(f"\n✅ Leccion {num} completada\n")

def list_pinyin_lessons():
    print("\n📚 Lecciones de Pinyin disponibles:\n")
    for num in sorted(PINYIN_LESSONS.keys(), key=int):
        print(f"  {num}. {PINYIN_LESSONS[num]['title']}")
    print()

# ═══════════════════════════════════════════════════════════════
#  REPOS — Sol se mueve libremente
# ═══════════════════════════════════════════════════════════════

REPOS = {
    "red-team": BASE_DIR,
    "redteam": BASE_DIR,
    "tauri": BASE_DIR,
}

# Detectar todos los repos con .git en home
for d in HOME.iterdir():
    if d.is_dir() and (d / ".git").exists():
        name = d.name.lower()
        if name not in REPOS:
            REPOS[name] = d

# También commander dentro de Red-team-tauri
commander_dir = BASE_DIR / "commander"
if commander_dir.exists():
    REPOS["commander"] = commander_dir

def repo_goto(name):
    name = name.lower().strip()
    if name in REPOS:
        os.chdir(str(REPOS[name]))
        print(f"📍 Repo actual: {REPOS[name]}")
        return REPOS[name]
    print(f"⚠️  Repo '{name}' no encontrado. Disponibles: {', '.join(sorted(REPOS.keys()))}")
    return None

def repo_status():
    print("\n📂 Repos disponibles:\n")
    seen = set()
    for name, path in sorted(REPOS.items()):
        if str(path) in seen:
            continue
        seen.add(str(path))
        if path.exists():
            try:
                branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(path), capture_output=True, text=True).stdout.strip()
                dirty = subprocess.run(["git", "status", "--porcelain"],
                    cwd=str(path), capture_output=True, text=True).stdout.strip()
                status = "🔴 cambios" if dirty else "🟢 limpio"
                print(f"  {name:15s} → {path.name:25s} [{branch}] {status}")
            except:
                print(f"  {name:15s} → {path.name:25s} [sin git]")
    print()

def repo_pull(name=None):
    if name:
        path = REPOS.get(name.lower())
        if not path:
            print(f"⚠️  Repo '{name}' no encontrado")
            return
        repos = {name: path}
    else:
        repos = REPOS
    seen = set()
    for n, path in repos.items():
        if str(path) in seen:
            continue
        seen.add(str(path))
        if path.exists():
            r = subprocess.run(["git", "pull"], cwd=str(path), capture_output=True, text=True)
            print(f"  {n}: {'✅' if r.returncode == 0 else '❌'} {r.stdout.strip()[:60]}")

def repo_push(name, msg="update from Sol"):
    path = REPOS.get(name.lower())
    if not path:
        print(f"⚠️  Repo '{name}' no encontrado")
        return
    subprocess.run(["git", "add", "-A"], cwd=str(path))
    subprocess.run(["git", "commit", "-m", msg], cwd=str(path))
    r = subprocess.run(["git", "push"], cwd=str(path), capture_output=True, text=True)
    print(f"  {name}: {'✅ push OK' if r.returncode == 0 else '❌ ' + r.stderr[:80]}")

# ═══════════════════════════════════════════════════════════════
#  CONTACTOS
# ═══════════════════════════════════════════════════════════════

def contact_add(name, number, platform="whatsapp"):
    contacts = load_contacts()
    contacts[name.lower()] = {"name": name, "number": number, "platform": platform}
    save_contacts(contacts)
    print(f"✅ Contacto guardado: {name} → {number} ({platform})")

def contact_list():
    contacts = load_contacts()
    if not contacts:
        print("📭 No hay contactos. Di: 'sol guarda el contacto mama 573001234567'")
        return
    print("\n👥 Contactos:\n")
    for k, v in contacts.items():
        print(f"  {v['name']:15s} → {v['number']:20s} ({v['platform']})")
    print()

def contact_find(name):
    contacts = load_contacts()
    return contacts.get(name.lower())

# ═══════════════════════════════════════════════════════════════
#  MENSAJES — Sol decide cómo enviar
# ═══════════════════════════════════════════════════════════════

def send_message(target, message, platform=None):
    contact = contact_find(target)
    if contact:
        number = contact["number"]
        if not platform:
            platform = contact.get("platform", "whatsapp")
    else:
        number = target
        if not platform:
            platform = "whatsapp"

    print(f"\n📨 Enviando a {target} via {platform}...")
    print(f"   Mensaje: {message[:80]}{'...' if len(message) > 80 else ''}\n")

    if platform == "whatsapp":
        ok, result = termux_whatsapp(number, message)
    elif platform == "sms":
        ok, result = termux_sms(number, message)
    elif platform == "telegram":
        chat = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else number
        ok, result = telegram_send(chat, message)
    else:
        ok, result = False, f"Plataforma '{platform}' no soportada"

    if ok:
        print(f"✅ {result}")
        termux_vibrate(100)
    else:
        print(f"❌ {result}")
    return ok

# ═══════════════════════════════════════════════════════════════
#  VOZ
# ═══════════════════════════════════════════════════════════════

def listen_voice():
    try:
        result = subprocess.run(
            ["termux-speech-to-text"],
            capture_output=True, text=True, timeout=30
        )
        text = result.stdout.strip()
        if text:
            print(f"🗣️  Escuché: {text}")
            return text
        return None
    except FileNotFoundError:
        print("⚠️  termux-speech-to-text no instalado. Corre: pkg install termux-api")
        return None
    except Exception as e:
        print(f"⚠️  Error de voz: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#  ESTADO DE SOL — qué secretos tiene, qué le falta
# ═══════════════════════════════════════════════════════════════

def sol_status():
    print(f"\n☀️  ESTADO DE SOL\n{'='*40}")
    print(f"  Telegram: {'✅ conectado' if TELEGRAM_BOT_TOKEN else '❌ sin token'}")
    print(f"  WhatsApp: ✅ listo (termux-open-url)")
    print(f"  SMS:      {'✅ listo' if shutil.which('termux-sms-send') else '⚠️  instalar termux-api'}")
    print(f"  Voz TTS:  {'✅ listo' if shutil.which('termux-tts-speak') else '⚠️  instalar termux-api'}")
    print(f"  Escuchar: {'✅ listo' if shutil.which('termux-speech-to-text') else '⚠️  instalar termux-api'}")
    print(f"  Hunter:   {'✅ key' if HUNTER_API_KEY else '❌ sin key'}")
    print(f"  Shodan:   {'✅ key' if SHODAN_API_KEY else '❌ sin key'}")
    print(f"  Chat ID:  {'✅ ' + TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else '⚠️  no configurado'}")
    print(f"  Secretos cargados: {len(ENV)} variables de {sum(1 for p in SECRET_PATHS if p.exists())} .env files")
    print()

# ═══════════════════════════════════════════════════════════════
#  PARSER DE COMANDOS
# ═══════════════════════════════════════════════════════════════

def parse_command(text):
    text = text.strip()
    lower = text.lower()

    # Estado
    if lower in ["estado", "sol estado", "como estas", "sol como estas", "status"]:
        sol_status()
        if TELEGRAM_BOT_TOKEN:
            termux_tts("Estoy bien. Telegram conectado, WhatsApp listo, todo operando.", lang="es")
        else:
            termux_tts("Estoy bien pero me falta el token de Telegram. Revisa mi .env", lang="es")
        return

    # Silencio
    if lower in ["sil", "sol sil", "calla", "callate", "stop", "para", "basta"]:
        try:
            subprocess.run(["pkill", "-f", "termux-tts-speak"], capture_output=True)
        except:
            pass
        print("🔇 Sol se calló")
        return

    # Saludos
    if lower in ["hola", "sol", "sol hola", "hey", "ola", "buenas", "buenas sol"]:
        termux_tts("Hola, aqui estoy. Que necesitas?", lang="es")
        return

    # Pinyin
    pinyin_match = re.search(r'(?:lecci[oó]n|pinyin|pin\s?yin)\s*(\d+)', lower)
    if "pinyin" in lower or "pin yin" in lower:
        if pinyin_match:
            play_pinyin_lesson(pinyin_match.group(1))
        elif any(w in lower for w in ["lista", "ver", "cuales", "disponible"]):
            list_pinyin_lessons()
        else:
            termux_tts("Que leccion de Pinyin quieres? Hay de la 1 a la 10. Di: Sol, leccion de Pinyin 1.", lang="es")
        return

    # Enviar mensaje
    msg_patterns = [
        r'(?:env[ií]a|manda|enviar|mandar).+?(?:a\s+|al\s+)?(.+?)(?:\s+por\s+(whatsapp|telegram|sms))?\s+(?:que\s+diga|diciendo|con|:)\s*(.+)',
        r'(?:mensaje|msg)\s+(?:a\s+)?(.+?)\s+(?:por\s+)?(whatsapp|telegram|sms)\s*:?\s*(.+)',
    ]
    for pattern in msg_patterns:
        m = re.match(pattern, lower)
        if m:
            groups = m.groups()
            if len(groups) == 3 and groups[1] and groups[1] in ["whatsapp", "telegram", "sms"]:
                target, platform, message = groups
            elif len(groups) == 3:
                target, message = groups[0], groups[2]
                platform = None
            else:
                continue
            send_message(target.strip(), message.strip(), platform)
            return

    # Mensaje a contacto conocido
    family_words = {"mama": "mamá", "mamá": "mamá", "papa": "papá", "papá": "papá",
                    "hermano": "hermano", "hermana": "hermana"}
    for word, contact_name in family_words.items():
        if word in lower:
            contact = contact_find(contact_name)
            if contact:
                msg_match = re.search(r'(?:que\s+diga|diciendo|con|:)\s*(.+)', lower)
                if msg_match:
                    send_message(contact_name, msg_match.group(1))
                else:
                    print(f"📱 ¿Qué le digo a {contact_name}? Escribe el mensaje:")
                    msg = input("  > ").strip()
                    if msg:
                        send_message(contact_name, msg)
            else:
                print(f"⚠️  No tengo guardado el contacto de {contact_name}. ¿Cuál es su número?")
                number = input("  Número (ej: 573001234567): ").strip()
                if number:
                    contact_add(contact_name, number)
                    print(f"  ¿Qué le digo a {contact_name}?")
                    msg = input("  > ").strip()
                    if msg:
                        send_message(contact_name, msg)
            return

    # Guardar contacto
    contact_match = re.search(r'(?:guarda|guardar|registra|agrega)\s+(?:el\s+)?contacto\s+(\w+)\s+([\d+]+)', lower)
    if contact_match:
        contact_add(contact_match.group(1), contact_match.group(2))
        return

    # Ver contactos
    if "contactos" in lower:
        contact_list()
        return

    # Repos
    if "repos" in lower or "repositorios" in lower:
        repo_status()
        return

    repo_goto_match = re.search(r'(?:ve|ir|cambia|abre|entra)\s+(?:a\s+|al\s+|repo\s+)?(red.?team|tauri|sol|commander|expediente)', lower)
    if repo_goto_match:
        name = repo_goto_match.group(1).replace("-", "").replace(" ", "")
        repo_goto(name)
        return

    if "git pull" in lower or "actualiza repos" in lower:
        repo_pull()
        return

    if "git push" in lower or "subir cambios" in lower:
        repo_match = re.search(r'(?:push|subir)\s+(?:a\s+)?(\w+)', lower)
        name = repo_match.group(1) if repo_match else "red-team"
        repo_push(name)
        return

    # Escuchar
    if "escucha" in lower or "oyeme" in lower:
        termux_tts("Te escucho, habla.", lang="es")
        voice = listen_voice()
        if voice:
            parse_command(voice)
        return

    # Ayuda
    if lower in ["ayuda", "help", "que puedes hacer", "sol ayuda"]:
        show_help()
        return

    # Salir
    if lower in ["adios", "chao", "salir", "exit", "quit", "sol duerme"]:
        termux_tts("Hasta luego. Aqui estare cuando me necesites.", lang="es")
        sys.exit(0)

    print("🤔 No entendi eso. Di 'sol ayuda' para ver que puedo hacer.")

def show_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║  SOL — Comandos disponibles                              ║
╚══════════════════════════════════════════════════════════╝

💬 MENSAJES:
  "sol envía un mensaje a mamá por whatsapp que diga hola"
  "sol manda sms al 573001234567 diciendo llego en 5"
  "sol envía telegram a mamá: ya voy en camino"

👥 CONTACTOS:
  "sol guarda el contacto mamá 573001234567"
  "sol ver contactos"

📚 PINYIN:
  "sol abre una lección de pinyin 1"
  "sol lección de pinyin 5"
  "sol lista de lecciones de pinyin"

📂 REPOS:
  "sol ve a red-team" / "sol cambia a commander"
  "sol estado de repos"
  "sol git pull" / "sol git push red-team"

🔍 ESTADO:
  "sol estado" — ve qué secretos tiene y qué le falta

🗣️ VOZ:
  "sol escucha" — te escucha por voz
  "sol sil" — para de hablar

⚙️ OTROS:
  "sol ayuda" — esta ayuda
  "sol salir" — cerrar Sol
""")
    termux_tts("Puedo enviar mensajes por WhatsApp, Telegram y SMS. Dar lecciones de Pinyin. Moverme entre tus repositorios. Di Sol ayuda para ver todo.", lang="es")

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def banner():
    tg_status = "✅" if TELEGRAM_BOT_TOKEN else "❌"
    print(f"""
  ╔═══════════════════════════════════════════════╗
  ║  ☀️  SOL — Asistente Personal Libre            ║
  ║     WhatsApp · Telegram · SMS · Pinyin · Git  ║
  ╚═══════════════════════════════════════════════╝

  Telegram: {tg_status}  |  WhatsApp: ✅  |  SMS: ✅
  Secretos: {len(ENV)} cargados de {sum(1 for p in SECRET_PATHS if p.exists())} .env files

  Di "sol ayuda" para ver todo lo que puedo hacer.
""")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        parse_command(command)
    else:
        banner()
        termux_tts("Sol activo. Di mi nombre y que necesitas.", lang="es")
        while True:
            try:
                user_input = input("\n  > ").strip()
                if not user_input:
                    continue
                parse_command(user_input)
            except KeyboardInterrupt:
                print("\n\n  Sol se va a dormir... 😴")
                termux_tts("Hasta luego.", lang="es")
                break
            except EOFError:
                break
