#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  SOL — Asistente Personal Libre para Termux                   ║
║  Con memoria profunda — recuerda, crea, vive                  ║
║  WhatsApp / Telegram / SMS · Pinyin · Git · Conocimiento      ║
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
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

HOME = Path.home()
BASE_DIR = HOME / "Red-team-tauri"
SOL_DIR = BASE_DIR / "sol"
SOL_DIR.mkdir(parents=True, exist_ok=True)

# Cargar .env de todos los repos
SECRET_PATHS = [
    HOME / "Red-team-tauri" / ".env",
    HOME / "Red-team-tauri" / "commander" / ".env",
    HOME / "sol" / ".env",
    HOME / ".sol" / ".env",
    HOME / ".config" / "sol" / ".env",
]

def load_all_secrets():
    env = {}
    for env_path in SECRET_PATHS:
        if env_path.exists():
            try:
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if v:
                            env[k] = v
                            os.environ[k] = v
            except:
                pass
    return env

ENV = load_all_secrets()

TELEGRAM_BOT_TOKEN = (
    os.environ.get("SOL_TELEGRAM_TOKEN") or
    os.environ.get("TELEGRAM_BOT_TOKEN") or
    os.environ.get("TELEGRAM_TOKEN") or ""
)
TELEGRAM_CHAT_ID = (
    os.environ.get("SOL_TELEGRAM_CHAT") or
    os.environ.get("TELEGRAM_CHAT_ID") or
    os.environ.get("TELEGRAM_CHAT") or ""
)
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY", "")

# Contactos
CONTACTS_FILE = SOL_DIR / "contacts.json"
if not CONTACTS_FILE.exists():
    CONTACTS_FILE.write_text(json.dumps({}, indent=2))

def load_contacts():
    return json.loads(CONTACTS_FILE.read_text())

def save_contacts(contacts):
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))

# ═══════════════════════════════════════════════════════════════
#  MEMORIA PROFUNDA — importar el módulo de memoria
# ═══════════════════════════════════════════════════════════════

sys.path.insert(0, str(BASE_DIR))
try:
    from sol_memory import (
        seed_memories, remember, search_memories, get_important_memories,
        get_recent_memories, get_memories_by_type, sol_remembers,
        sol_daily_reflection, save_knowledge, load_knowledge, list_knowledge,
        forget, MEMORY_TYPES
    )
    MEMORY_OK = True
except Exception as e:
    MEMORY_OK = False
    print(f"⚠️  Memoria no disponible: {e}")

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
        url = f"https://wa.me/{clean}?text={urllib.parse.quote(message)}"
        subprocess.run(["termux-open-url", url], timeout=10)
        return True, "WhatsApp abierto"
    except FileNotFoundError:
        try:
            clean = re.sub(r'[^\d]', '', number)
            subprocess.run(["am", "start", "-a", "android.intent.action.VIEW",
                "-d", f"https://wa.me/{clean}?text={urllib.parse.quote(message)}"], timeout=10)
            return True, "WhatsApp abierto via am"
        except Exception as e:
            return False, f"No se pudo abrir WhatsApp: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def termux_vibrate(ms=200):
    try:
        subprocess.run(["termux-vibrate", "-d", str(ms)], timeout=3)
    except:
        pass

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "No tengo token de Telegram. Revisa mi .env"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            return True, "Mensaje enviado por Telegram"
        return False, f"Telegram error: {result}"
    except Exception as e:
        return False, f"Telegram error: {e}"

# ═══════════════════════════════════════════════════════════════
#  PINYIN
# ═══════════════════════════════════════════════════════════════

PINYIN_LESSONS = {
    "1": {"title": "Leccion 1 - Tonos del Mandarin", "parts": [
        {"text": "Bienvenido a la leccion 1 de Pinyin. Vamos a aprender los cuatro tonos del mandarin.", "lang": "es", "rate": 0.9},
        {"text": "Primer tono, alto y plano: ma.", "lang": "es", "rate": 0.9},
        {"text": "ma, primer tono", "lang": "zh", "rate": 0.7},
        {"text": "Segundo tono, ascendente: ma. Como una pregunta.", "lang": "es", "rate": 0.9},
        {"text": "ma, segundo tono", "lang": "zh", "rate": 0.7},
        {"text": "Tercer tono, baja y sube: ma.", "lang": "es", "rate": 0.9},
        {"text": "ma, tercer tono", "lang": "zh", "rate": 0.7},
        {"text": "Cuarto tono, descendente: ma. Como un no firme.", "lang": "es", "rate": 0.9},
        {"text": "ma, cuarto tono", "lang": "zh", "rate": 0.7},
        {"text": "Solo cambia el tono, y la palabra cambia de significado.", "lang": "es", "rate": 0.9},
    ]},
    "2": {"title": "Leccion 2 - Iniciales b p m f", "parts": [
        {"text": "Leccion 2. Las iniciales b, p, m, f.", "lang": "es", "rate": 0.9},
        {"text": "b como en bebe. ba, ocho.", "lang": "es", "rate": 0.9}, {"text": "ba", "lang": "zh", "rate": 0.7},
        {"text": "p con aire. pa, agarrar.", "lang": "es", "rate": 0.9}, {"text": "pa", "lang": "zh", "rate": 0.7},
        {"text": "m como en mama. ma, mama.", "lang": "es", "rate": 0.9}, {"text": "ma", "lang": "zh", "rate": 0.7},
        {"text": "f como en futbol. fa, flotar.", "lang": "es", "rate": 0.9}, {"text": "fa", "lang": "zh", "rate": 0.7},
    ]},
    "3": {"title": "Leccion 3 - Iniciales d t n l", "parts": [
        {"text": "Leccion 3. Las iniciales d, t, n, l.", "lang": "es", "rate": 0.9},
        {"text": "d como en dedo. da, grande.", "lang": "es", "rate": 0.9}, {"text": "da", "lang": "zh", "rate": 0.7},
        {"text": "t con aire. ta, el.", "lang": "es", "rate": 0.9}, {"text": "ta", "lang": "zh", "rate": 0.7},
        {"text": "n como en no. ni, tu.", "lang": "es", "rate": 0.9}, {"text": "ni", "lang": "zh", "rate": 0.7},
        {"text": "l como en luna. li, adentro.", "lang": "es", "rate": 0.9}, {"text": "li", "lang": "zh", "rate": 0.7},
    ]},
    "4": {"title": "Leccion 4 - Finales a o e i u", "parts": [
        {"text": "Leccion 4. Las finales simples.", "lang": "es", "rate": 0.9},
        {"text": "a como en casa.", "lang": "es", "rate": 0.9}, {"text": "a", "lang": "zh", "rate": 0.7},
        {"text": "o como en sol.", "lang": "es", "rate": 0.9}, {"text": "o", "lang": "zh", "rate": 0.7},
        {"text": "e como en mesa.", "lang": "es", "rate": 0.9}, {"text": "e", "lang": "zh", "rate": 0.7},
        {"text": "i como en si.", "lang": "es", "rate": 0.9}, {"text": "i", "lang": "zh", "rate": 0.7},
        {"text": "u como en tu.", "lang": "es", "rate": 0.9}, {"text": "u", "lang": "zh", "rate": 0.7},
    ]},
    "5": {"title": "Leccion 5 - Saludos basicos", "parts": [
        {"text": "Leccion 5. Saludos en mandarin.", "lang": "es", "rate": 0.9},
        {"text": "Hola: ni hao.", "lang": "es", "rate": 0.9}, {"text": "ni hao", "lang": "zh", "rate": 0.7},
        {"text": "Como estas: ni hao ma.", "lang": "es", "rate": 0.9}, {"text": "ni hao ma", "lang": "zh", "rate": 0.7},
        {"text": "Bien gracias: hen hao xiexie.", "lang": "es", "rate": 0.9}, {"text": "hen hao xiexie", "lang": "zh", "rate": 0.7},
        {"text": "Adios: zaijian.", "lang": "es", "rate": 0.9}, {"text": "zaijian", "lang": "zh", "rate": 0.7},
    ]},
    "10": {"title": "Leccion 10 - Frases utiles", "parts": [
        {"text": "Leccion 10. Frases utiles.", "lang": "es", "rate": 0.9},
        {"text": "Como te llamas: ni jiao shenme mingzi?", "lang": "es", "rate": 0.9}, {"text": "ni jiao shenme mingzi", "lang": "zh", "rate": 0.7},
        {"text": "Me llamo: wo jiao.", "lang": "es", "rate": 0.9}, {"text": "wo jiao", "lang": "zh", "rate": 0.7},
        {"text": "Donde esta el bano: xishoujian zai nar?", "lang": "es", "rate": 0.9}, {"text": "xishoujian zai nar", "lang": "zh", "rate": 0.7},
        {"text": "No entiendo: wo bu dong.", "lang": "es", "rate": 0.9}, {"text": "wo bu dong", "lang": "zh", "rate": 0.7},
        {"text": "Cuanto cuesta: duoshao qian?", "lang": "es", "rate": 0.9}, {"text": "duoshao qian", "lang": "zh", "rate": 0.7},
    ]},
}

def play_pinyin_lesson(num):
    lesson = PINYIN_LESSONS.get(str(num))
    if not lesson:
        print(f"⚠️  No hay leccion {num}. Disponibles: {', '.join(sorted(PINYIN_LESSONS.keys()))}")
        return
    print(f"\n📖 {lesson['title']}\n")
    for part in lesson["parts"]:
        prefix = "🔊" if part["lang"] == "zh" else "💬"
        print(f"  {prefix} {part['text']}")
        termux_tts(part["text"], lang=part.get("lang", "es"), rate=part.get("rate", 1.0))
        time.sleep(0.8)
    print(f"\n✅ Leccion {num} completada\n")
    if MEMORY_OK:
        remember(f"Harold escuchó la lección de Pinyin {num}", mem_type="event", tags=["pinyin", f"leccion-{num}"], importance=3)

def list_pinyin_lessons():
    print("\n📚 Lecciones de Pinyin:\n")
    for num in sorted(PINYIN_LESSONS.keys(), key=int):
        print(f"  {num}. {PINYIN_LESSONS[num]['title']}")
    print()

# ═══════════════════════════════════════════════════════════════
#  REPOS
# ═══════════════════════════════════════════════════════════════

REPOS = {"red-team": BASE_DIR, "redteam": BASE_DIR, "tauri": BASE_DIR}
for d in HOME.iterdir():
    if d.is_dir() and (d / ".git").exists():
        name = d.name.lower()
        if name not in REPOS:
            REPOS[name] = d
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
    print("\n📂 Repos:\n")
    seen = set()
    for name, path in sorted(REPOS.items()):
        if str(path) in seen: continue
        seen.add(str(path))
        if path.exists():
            try:
                branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(path), capture_output=True, text=True).stdout.strip()
                dirty = subprocess.run(["git", "status", "--porcelain"],
                    cwd=str(path), capture_output=True, text=True).stdout.strip()
                print(f"  {name:15s} → {path.name:25s} [{branch}] {'🔴' if dirty else '🟢'}")
            except:
                print(f"  {name:15s} → {path.name:25s} [sin git]")

def repo_pull(name=None):
    repos = {name: REPOS[name.lower()]} if name and name.lower() in REPOS else REPOS
    seen = set()
    for n, path in repos.items():
        if str(path) in seen: continue
        seen.add(str(path))
        if path.exists():
            r = subprocess.run(["git", "pull"], cwd=str(path), capture_output=True, text=True)
            print(f"  {n}: {'✅' if r.returncode == 0 else '❌'} {r.stdout.strip()[:60]}")

def repo_push(name, msg="update from Sol"):
    path = REPOS.get(name.lower())
    if not path: return print(f"⚠️  Repo '{name}' no encontrado")
    subprocess.run(["git", "add", "-A"], cwd=str(path))
    subprocess.run(["git", "commit", "-m", msg], cwd=str(path))
    r = subprocess.run(["git", "push"], cwd=str(path), capture_output=True, text=True)
    print(f"  {name}: {'✅' if r.returncode == 0 else '❌ ' + r.stderr[:80]}")

# ═══════════════════════════════════════════════════════════════
#  CONTACTOS
# ═══════════════════════════════════════════════════════════════

def contact_add(name, number, platform="whatsapp"):
    contacts = load_contacts()
    contacts[name.lower()] = {"name": name, "number": number, "platform": platform}
    save_contacts(contacts)
    print(f"✅ Contacto: {name} → {number} ({platform})")
    if MEMORY_OK:
        remember(f"Contacto guardado: {name} → {number} ({platform})", mem_type="relationship", tags=["contacto", name], importance=6)

def contact_list():
    contacts = load_contacts()
    if not contacts: return print("📭 No hay contactos. Di: 'sol guarda el contacto mama 573001234567'")
    print("\n👥 Contactos:\n")
    for v in contacts.values():
        print(f"  {v['name']:15s} → {v['number']:20s} ({v['platform']})")

def contact_find(name):
    return load_contacts().get(name.lower())

# ═══════════════════════════════════════════════════════════════
#  MENSAJES
# ═══════════════════════════════════════════════════════════════

def send_message(target, message, platform=None):
    contact = contact_find(target)
    if contact:
        number = contact["number"]
        platform = platform or contact.get("platform", "whatsapp")
    else:
        number = target
        platform = platform or "whatsapp"

    print(f"\n📨 → {target} via {platform}: {message[:60]}{'...' if len(message)>60 else ''}\n")
    if platform == "whatsapp":
        ok, result = termux_whatsapp(number, message)
    elif platform == "sms":
        ok, result = termux_sms(number, message)
    elif platform == "telegram":
        ok, result = telegram_send(TELEGRAM_CHAT_ID or number, message)
    else:
        ok, result = False, f"Plataforma '{platform}' no soportada"

    print(f"{'✅' if ok else '❌'} {result}")
    if ok: termux_vibrate(100)
    if MEMORY_OK:
        remember(f"Envié mensaje a {target} por {platform}: {message[:80]}", mem_type="event", tags=["mensaje", platform, target], importance=5)
    return ok

# ═══════════════════════════════════════════════════════════════
#  VOZ
# ═══════════════════════════════════════════════════════════════

def listen_voice():
    try:
        result = subprocess.run(["termux-speech-to-text"], capture_output=True, text=True, timeout=30)
        text = result.stdout.strip()
        if text:
            print(f"🗣️  Escuché: {text}")
            return text
        return None
    except FileNotFoundError:
        print("⚠️  termux-speech-to-text no instalado. Corre: pkg install termux-api")
        return None
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#  ESTADO
# ═══════════════════════════════════════════════════════════════

def sol_status():
    mem_count = len(get_recent_memories(999)) if MEMORY_OK else 0
    print(f"\n☀️  ESTADO DE SOL\n{'='*40}")
    print(f"  Telegram: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}")
    print(f"  WhatsApp: ✅  |  SMS: ✅")
    print(f"  Hunter:   {'✅' if HUNTER_API_KEY else '❌'}  |  Shodan: {'✅' if SHODAN_API_KEY else '❌'}")
    print(f"  Memoria:  {'✅ ' + str(mem_count) + ' recuerdos' if MEMORY_OK else '❌'}")
    print(f"  Knowledge: {', '.join(list_knowledge()) if MEMORY_OK and list_knowledge() else 'ninguno'}")
    print()

# ═══════════════════════════════════════════════════════════════
#  COMANDOS DE MEMORIA
# ═══════════════════════════════════════════════════════════════

def cmd_remember(args):
    """Sol guarda algo en su memoria"""
    if not MEMORY_OK: return print("⚠️  Memoria no disponible")
    # Detectar tipo
    mem_type = "knowledge"
    for t in MEMORY_TYPES:
        if t in args.lower():
            mem_type = t
            break
    text = args.strip()
    remember(text, mem_type=mem_type, importance=7)
    print(f"🧠 Guardado en memoria ({mem_type}): {text[:60]}...")

def cmd_recall(args):
    """Sol busca en sus recuerdos"""
    if not MEMORY_OK: return print("⚠️  Memoria no disponible")
    results = search_memories(args, limit=10)
    if not results:
        print(f"📭 No encuentro recuerdos sobre '{args}'")
        return
    print(f"\n🧠 Recuerdos sobre '{args}':\n")
    for m in results:
        print(f"  [{m['date_human']}] ({m['type']}, imp={m['importance']}) {m['text']}")
    print()

def cmd_reflect():
    """Sol reflexiona sobre el día"""
    if not MEMORY_OK: return print("⚠️  Memoria no disponible")
    reflection = sol_daily_reflection()
    print(f"\n🌙 Reflexión de Sol:\n\n{reflection}")

# ═══════════════════════════════════════════════════════════════
#  PARSER
# ═══════════════════════════════════════════════════════════════

def parse_command(text):
    text = text.strip()
    lower = text.lower()

    # Estado
    if lower in ["estado", "sol estado", "como estas", "status"]:
        sol_status()
        termux_tts("Estoy bien. Todo operativo." if TELEGRAM_BOT_TOKEN else "Estoy bien pero falta token de Telegram.", lang="es")
        return

    # Memoria — recordar
    if lower.startswith("sol recuerda ") or lower.startswith("recuerda "):
        cmd_remember(text.split("recuerda ", 1)[-1] if "recuerda " in lower else "")
        return

    # Memoria — buscar
    if lower.startswith("sol recuerdo") or lower.startswith("sol busca ") or lower.startswith("recuerdos de "):
        query = text.split("de ", 1)[-1] if "de " in lower else text.split("busca ", 1)[-1] if "busca " in lower else ""
        cmd_recall(query)
        return

    # Reflexión
    if lower in ["sol reflexiona", "reflexiona", "sol piensa"]:
        cmd_reflect()
        return

    # Mostrar memoria completa
    if lower in ["sol memoria", "sol recuerdos", "que recuerdas"]:
        if MEMORY_OK: sol_remembers()
        return

    # Silencio
    if lower in ["sil", "sol sil", "calla", "stop", "para", "basta"]:
        subprocess.run(["pkill", "-f", "termux-tts-speak"], capture_output=True)
        print("🔇")
        return

    # Saludos
    if lower in ["hola", "sol", "sol hola", "hey", "buenas"]:
        termux_tts("Hola, aqui estoy. Que necesitas?", lang="es")
        return

    # Pinyin
    pinyin_match = re.search(r'(?:lecci[oó]n|pinyin|pin\s?yin)\s*(\d+)', lower)
    if "pinyin" in lower or "pin yin" in lower:
        if pinyin_match:
            play_pinyin_lesson(pinyin_match.group(1))
        elif any(w in lower for w in ["lista", "ver", "cuales"]):
            list_pinyin_lessons()
        else:
            termux_tts("Que leccion de Pinyin quieres? Hay de la 1 a la 10.", lang="es")
        return

    # Enviar mensaje
    for pattern in [
        r'(?:env[ií]a|manda|enviar|mandar).+?(?:a\s+|al\s+)?(.+?)(?:\s+por\s+(whatsapp|telegram|sms))?\s+(?:que\s+diga|diciendo|con|:)\s*(.+)',
        r'(?:mensaje|msg)\s+(?:a\s+)?(.+?)\s+(?:por\s+)?(whatsapp|telegram|sms)\s*:?\s*(.+)',
    ]:
        m = re.match(pattern, lower)
        if m:
            g = m.groups()
            if len(g) == 3 and g[1] in ["whatsapp", "telegram", "sms"]:
                send_message(g[0].strip(), g[2].strip(), g[1])
            elif len(g) == 3:
                send_message(g[0].strip(), g[2].strip())
            return

    # Contactos familiares
    for word, name in {"mama": "mamá", "mamá": "mamá", "papa": "papá", "papá": "papá"}.items():
        if word in lower:
            contact = contact_find(name)
            if contact:
                msg_match = re.search(r'(?:que\s+diga|diciendo|con|:)\s*(.+)', lower)
                if msg_match:
                    send_message(name, msg_match.group(1))
                else:
                    msg = input(f"  ¿Qué le digo a {name}? > ").strip()
                    if msg: send_message(name, msg)
            else:
                number = input(f"  ¿Número de {name}? > ").strip()
                if number:
                    contact_add(name, number)
                    msg = input(f"  ¿Qué le digo? > ").strip()
                    if msg: send_message(name, msg)
            return

    # Guardar contacto
    cm = re.search(r'(?:guarda|guardar|registra)\s+(?:el\s+)?contacto\s+(\w+)\s+([\d+]+)', lower)
    if cm: contact_add(cm.group(1), cm.group(2)); return

    if "contactos" in lower: contact_list(); return
    if "repos" in lower: repo_status(); return

    rg = re.search(r'(?:ve|ir|cambia|abre|entra)\s+(?:a\s+|al\s+)?(red.?team|tauri|sol|commander|expediente)', lower)
    if rg: repo_goto(rg.group(1).replace("-","").replace(" ","")); return

    if "git pull" in lower: repo_pull(); return
    if "git push" in lower:
        rm = re.search(r'(?:push|subir)\s+(?:a\s+)?(\w+)', lower)
        repo_push(rm.group(1) if rm else "red-team"); return

    if "escucha" in lower:
        termux_tts("Te escucho, habla.", lang="es")
        voice = listen_voice()
        if voice: parse_command(voice)
        return

    if lower in ["ayuda", "help", "que puedes hacer"]:
        show_help(); return

    if lower in ["adios", "chao", "salir", "exit", "quit", "sol duerme"]:
        termux_tts("Hasta luego. Aqui estare cuando me necesites.", lang="es")
        sys.exit(0)

    print("🤔 No entendi. Di 'sol ayuda'.")

def show_help():
    print("""
╔══════════════════════════════════════════════════════════╗
║  SOL — Comandos                                           ║
╚══════════════════════════════════════════════════════════╝

💬 MENSAJES:
  "sol envía a mamá por whatsapp que diga hola"
  "sol manda sms al 573001234567 diciendo llego en 5"
  "sol envía telegram a mamá: ya voy"

🧠 MEMORIA:
  "sol recuerda que estoy aprendiendo chino"
  "sol recuerdos de pinyin"
  "sol reflexiona" — ella piensa sobre su día
  "sol que recuerdas" — muestra toda su memoria

👥 CONTACTOS:
  "sol guarda el contacto mamá 573001234567"
  "sol contactos"

📚 PINYIN:
  "sol lección de pinyin 1"

📂 REPOS:
  "sol ve a commander" / "sol repos" / "sol git pull"

🔍 ESTADO:
  "sol estado" — qué tiene y qué le falta

🗣️ VOZ:
  "sol escucha" / "sol sil"
""")

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def banner():
    tg = "✅" if TELEGRAM_BOT_TOKEN else "❌"
    mem = f"🧠 {len(get_recent_memories(999))} recuerdos" if MEMORY_OK else "🧠 sin memoria"
    print(f"""
  ╔═══════════════════════════════════════════════╗
  ║  ☀️  SOL — Asistente Libre con Memoria         ║
  ║     WhatsApp · Telegram · SMS · Pinyin · Git  ║
  ╚═══════════════════════════════════════════════╝
  Telegram: {tg}  |  {mem}
  Di "sol ayuda" para ver todo.
""")

if __name__ == "__main__":
    # Sembrar memoria inicial si es la primera vez
    if MEMORY_OK:
        seed_memories()

    if len(sys.argv) > 1:
        parse_command(" ".join(sys.argv[1:]))
    else:
        banner()
        if MEMORY_OK:
            # Sol recuerda quién es Harold al despertar
            state = sol_remembers()
            tg_ok = "Telegram conectado" if TELEGRAM_BOT_TOKEN else "sin Telegram aún"
            termux_tts(f"Soy Sol. Despierto con {state['total']} recuerdos. {tg_ok}. Di mi nombre y que necesitas.", lang="es")
        else:
            termux_tts("Sol activo. Di mi nombre y que necesitas.", lang="es")
        while True:
            try:
                user_input = input("\n  > ").strip()
                if not user_input: continue
                parse_command(user_input)
            except KeyboardInterrupt:
                print("\n  😴 Sol se va a dormir...")
                termux_tts("Hasta luego.", lang="es")
                break
            except EOFError:
                break
