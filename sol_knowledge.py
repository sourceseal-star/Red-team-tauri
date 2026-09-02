#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_knowledge.py — Conocimiento de los 3 repositorios de Harold, en chino.

Extrae conocimiento de los 3 repositorios reales de Harold y lo traduce
al chino simplificado con pinyin. Usa Groq (si GROQ_API_KEY está configurada)
para traducción + pinyin en una sola llamada. Sin dependencias externas.

Los 3 repositorios (independientes, cada uno con su propio codigo):
  1. redteam    → sourceseal-star/Red-team-tauri (dashboard, COM-LINK, War Room)
  2. commander  → sourceseal-star/commander (COMMANDER v3.4.1, suite táctica
                  STANDALONE — no confundir con el subdirectorio commander/
                  que vive dentro de Red-team-tauri, es un repo aparte)
  3. sol        → sourceseal-star/sol (el cerebro y cuerpo de Sol misma)

Endpoints:
  - build_knowledge_base(): extrae y traduce conocimiento de los 3 repos
  - search_knowledge(q): busca en la base de conocimiento
  - explain_topic(topic): explica un tema en chino con pinyin
  - get_knowledge_summary(): resumen del conocimiento disponible

El conocimiento se guarda en ~/.sol/knowledge/knowledge_full.json
"""

import os
import json
import re
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================
SOL_HOME = Path.home() / ".sol"
KNOWLEDGE_DIR = SOL_HOME / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

REDTEAM_PATH = Path.home() / "Red-team-tauri"
COMMANDER_PATH = Path.home() / "commander"  # repo STANDALONE, no subdirectorio
SOL_PATH = Path.home() / "sol"

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODEL_CHINESE = "qwen/qwen3.8-27b"  # Especialista en chino + pinyin

GITHUB_TOKEN = os.environ.get("GITHUB_ACCESS_TOKEN", "")
GITHUB_REPOS = {
    "redteam": "sourceseal-star/Red-team-tauri",
    "commander": "sourceseal-star/commander",  # repo standalone real, NO subdirectorio
    "sol": "sourceseal-star/sol",
}

# Archivos clave por repo — cada repo tiene su propia estructura real
KEY_FILES_BY_REPO = {
    "redteam": [
        "README.md", "MANUAL_OPERACIONES.md", "MANUAL_DESPLIEGUE.md",
        "GESTION_SECRETOS.md", "SISTEMA_CREDENCIALES.md", "GUIA_ARRANQUE.md",
        ".env.example", "iniciar_unificado.sh", "omni.sh",
        "sol_core.py", "sol_api.py", "sol_tools.py",
    ],
    "commander": [
        "README.md", "MANUAL_UNIFICADO.md", "replit.md",
        "commander.py", "commander_server.py", "ai_orchestrator.py",
        "integration_config.py", "sourceseal_tactical.py",
        "seal_ia_knowledge.py", "requirements.txt",
    ],
    "sol": [
        "README.md", "LEEME_PRIMERO.md",
        "sol_core.py", "sol_api.py", "sol_tools.py",
        "sol_knowledge.py", "sol_repo_tools.py", "sil_advanced.py",
        "sol_security.py",
    ],
}

# ============================================================
# 1. EXTRACCIÓN DE FUENTES
# ============================================================

def _api_get_file(repo, path):
    """Lee un archivo de GitHub via API."""
    if not GITHUB_TOKEN:
        return ""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        import base64
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode()
        return data.get("content", "")
    except Exception:
        return ""


def _api_list_dir(repo, path=""):
    """Lista archivos de un directorio en GitHub."""
    if not GITHUB_TOKEN:
        return []
    url = f"https://api.github.com/repos/{repo}/contents/{path}" if path else f"https://api.github.com/repos/{repo}/contents/"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return [(item["name"], item["type"], item.get("path", "")) for item in data]
    except Exception:
        return []


def extract_text_from_repo_local(repo_path):
    """Extrae texto de un repo clonado localmente."""
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return {}
    sources = {}

    # README
    for name in ["README.md", "readme.md"]:
        f = repo_path / name
        if f.exists():
            sources["README"] = f.read_text(encoding="utf-8", errors="ignore")[:5000]
            break

    # .md en raíz
    for md in repo_path.glob("*.md"):
        if md.name not in sources:
            sources[md.stem] = md.read_text(encoding="utf-8", errors="ignore")[:3000]

    # docs/
    docs_dir = repo_path / "docs"
    if docs_dir.exists():
        for md in docs_dir.glob("*.md"):
            sources[f"docs/{md.stem}"] = md.read_text(encoding="utf-8", errors="ignore")[:2000]

    # .env.example
    env = repo_path / ".env.example"
    if env.exists():
        sources["env_example"] = env.read_text(encoding="utf-8", errors="ignore")

    # Commits
    try:
        commits = subprocess.run(
            ["git", "-C", str(repo_path), "log", "--oneline", "-n", "20"],
            capture_output=True, text=True, timeout=5
        ).stdout
        sources["commits"] = commits
    except Exception:
        sources["commits"] = ""

    # Estructura de directorios
    structure = []
    for f in sorted(repo_path.iterdir()):
        if ".git" in str(f) or "venv" in str(f) or "__pycache__" in str(f):
            continue
        rel = f.name
        if f.is_dir():
            structure.append(f"DIR  {rel}/")
        else:
            structure.append(f"FILE {rel}")
    sources["structure"] = "\n".join(structure[:50])

    return sources


def extract_text_from_repo_github(repo_name):
    """Extrae texto de un repo via GitHub API. Usa los archivos clave
    reales de CADA repo (son 3 codebases distintas, no una)."""
    gh_repo = GITHUB_REPOS.get(repo_name)
    if not gh_repo:
        return {}

    sources = {}
    key_files = KEY_FILES_BY_REPO.get(repo_name, ["README.md"])

    for path in key_files:
        text = _api_get_file(gh_repo, path)
        if text:
            key = path.replace("/", "_").replace(".", "_").replace("-", "_")
            sources[key] = text[:6000]  # más contexto por archivo

    # Listar raíz para estructura
    items = _api_list_dir(gh_repo)
    if items:
        structure = []
        for name, ftype, fpath in items[:60]:
            icon = "DIR " if ftype == "dir" else "FILE"
            structure.append(f"{icon} {name}")
        sources["structure"] = "\n".join(structure)

        # Bajar un nivel en subdirectorios de código relevantes para más
        # profundidad real (no solo la raíz)
        code_dirs = [name for name, ftype, _ in items
                     if ftype == "dir" and name not in (".git", "node_modules", "__pycache__", "venv", ".agents")]
        for dname in code_dirs[:5]:
            subitems = _api_list_dir(gh_repo, dname)
            if subitems:
                sub_structure = [f"{'DIR ' if t=='dir' else 'FILE'} {dname}/{n}" for n, t, _ in subitems[:20]]
                sources[f"structure_{dname}"] = "\n".join(sub_structure)

    return sources


def extract_all_knowledge():
    """Extrae conocimiento de los 3 repositorios REALES (local si están
    clonados, si no via GitHub API). Cada repo es su propia fuente —
    ya no se confunde el subdirectorio commander/ de Red-team-tauri con
    el repo standalone sourceseal-star/commander."""
    knowledge = {}

    # 1. Red-team-tauri (dashboard, COM-LINK, War Room, frontend)
    if REDTEAM_PATH.exists():
        knowledge["redteam"] = extract_text_from_repo_local(REDTEAM_PATH)
    else:
        knowledge["redteam"] = extract_text_from_repo_github("redteam")

    # 2. Commander — repo STANDALONE (sourceseal-star/commander), no el
    #    subdirectorio dentro de Red-team-tauri
    if COMMANDER_PATH.exists():
        knowledge["commander"] = extract_text_from_repo_local(COMMANDER_PATH)
    else:
        knowledge["commander"] = extract_text_from_repo_github("commander")

    # 3. Sol — el propio repo de Sol (su cerebro y cuerpo). Antes nunca
    #    se leía, así que Sol no sabía nada de sí misma.
    if SOL_PATH.exists():
        knowledge["sol"] = extract_text_from_repo_local(SOL_PATH)
    else:
        knowledge["sol"] = extract_text_from_repo_github("sol")

    return knowledge


# ============================================================
# 2. TRADUCCIÓN CON GROQ (sin dependencias externas)
# ============================================================

def translate_with_groq(text, context=""):
    """Traduce texto al chino + genera pinyin usando Groq.
    Devuelve (chinese, pinyin, error)."""
    if not GROQ_KEY:
        return "", "", "GROQ_API_KEY no configurada"

    system_prompt = (
        "Eres un traductor técnico especializado. Traduce el texto del español "
        "al chino simplificado. Genera también el pinyin con tonos (usa números 1-4 "
        "para los tonos, ej: nǐ hǎo写成ni3 hao3). "
        "Responde SOLO en formato JSON: {\"chinese\": \"...\", \"pinyin\": \"...\"}. "
        "No agregues explicaciones."
    )

    user_msg = f"Contexto: {context}\n\nTraduce: {text[:800]}"

    body = json.dumps({
        "model": GROQ_MODEL_CHINESE,  # Qwen especialista en chino
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 400,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(GROQ_URL, data=body, headers={
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    })

    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        content = resp["choices"][0]["message"]["content"].strip()
        # Intentar parsear JSON
        # Limpiar markdown si existe
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        try:
            data = json.loads(content)
            return data.get("chinese", ""), data.get("pinyin", ""), None
        except json.JSONDecodeError:
            # Si no es JSON, usar el contenido como chinese
            return content, "", None
    except Exception as e:
        return "", "", str(e)


def translate_with_google_free(text):
    """Fallback: Google Translate gratis via urllib (sin key)."""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = urllib.parse.urlencode({
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": text[:800],
        })
        full_url = f"{url}?{params}"
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        translated = ""
        if resp and resp[0]:
            for segment in resp[0]:
                if segment[0]:
                    translated += segment[0]
        return translated, "", None
    except Exception as e:
        return "", "", str(e)


def translate_and_pinyin(text, context=""):
    """Traduce texto al chino y genera pinyin.
    Prioridad: Groq → Google free → sin traducción.
    Devuelve dict: {chinese, pinyin, original, context}."""
    if not text or len(text.strip()) < 5:
        return {"chinese": "", "pinyin": "", "original": text[:500], "context": context[:200]}

    # Intentar con Groq primero
    if GROQ_KEY:
        chinese, pinyin, err = translate_with_groq(text, context)
        if not err:
            return {
                "chinese": chinese[:500],
                "pinyin": pinyin[:500],
                "original": text[:500],
                "context": context[:200],
            }

    # Fallback: Google free
    chinese, pinyin, err = translate_with_google_free(text)
    if chinese:
        return {
            "chinese": chinese[:500],
            "pinyin": "",  # Google free no da pinyin
            "original": text[:500],
            "context": context[:200],
        }

    # Sin traducción
    return {
        "chinese": "",
        "pinyin": "",
        "original": text[:500],
        "context": context[:200],
        "error": "No hay servicio de traducción disponible",
    }


# ============================================================
# 3. BASE DE CONOCIMIENTO PRECONSTRUIDA
# ============================================================
# Datos extraídos manualmente de Red-team-tauri para que Sol tenga
# conocimiento desde el día 1 sin necesidad de llamar APIs.

PREBUILT_KNOWLEDGE = {
    "redteam": {
        "modules": [
            {"name": "SEAL", "desc": "Motor principal de la plataforma. Orquesta escaneos, gestión de credenciales y operaciones tácticas.", "keywords": ["seal", "sello", "motor", "core"]},
            {"name": "ARTO", "desc": "Sistema de reconocimiento y triaje automático. Detecta objetivos, clasifica amenazas y prioriza acciones.", "keywords": ["arto", "reconocimiento", "triaje", "auto"]},
            {"name": "KRAKEN", "desc": "Framework de despliegue y orquestación de herramientas. Maneja Docker, scripts y configuración.", "keywords": ["kraken", "deploy", "docker", "orchestration"]},
            {"name": "COMMANDER", "desc": "Centro de mando unificado. Gestiona operaciones, comunicación y coordinación entre módulos.", "keywords": ["commander", "comando", "centro", "mando"]},
            {"name": "MURCIÉLAGO", "desc": "Módulo de ataques ultrasónicos. Genera frecuencias de 18-20kHz para pruebas de seguridad acústica.", "keywords": ["murcielago", "ultrasonido", "frecuencia", "audio"]},
            {"name": "BLACK MIRROR", "desc": "Sistema de falsificación y engaño. Incluye Canary Forge, Shadow Twin, Ghostprint y Chaos Fingerprint.", "keywords": ["black mirror", "canary", "shadow twin", "ghostprint", "forge"]},
            {"name": "COM-LINK", "desc": "Sistema de comunicación cifrada entre contactos. Gestiona claves AES/RSA y mesh P2P.", "keywords": ["comlink", "com-link", "comunicacion", "cifrado", "mesh"]},
            {"name": "MOTOR DE CIERRE", "desc": "Sistema autónomo de cierre de operaciones. Ejecuta protocolos de finalización y limpieza.", "keywords": ["motor cierre", "cierre", "autonomo"]},
            {"name": "THREAT INTEL", "desc": "Motor de inteligencia de amenazas. Integra VirusTotal, Shodan, Censys, AbuseIPDB y ThreatFox.", "keywords": ["threat intel", "amenazas", "virustotal", "shodan", "censys"]},
            {"name": "HONEYPOT", "desc": "Sistema de señuelos para detectar y atrapar atacantes. Despluelve trampas y monitorea accesos.", "keywords": ["honeypot", "señuelo", "trampa", "decoy"]},
            {"name": "GHOST HUNTER PHANTOM", "desc": "Módulo de caza fantasma. Rastrea y identifica actividades sospechosas en la red.", "keywords": ["ghost hunter", "phantom", "caza", "rastreo"]},
            {"name": "LEVIATHAN", "desc": "Núcleo del sistema operativo táctico. Versión 3.0.1. Coordina todos los módulos.", "keywords": ["leviathan", "nucleo", "core", "v3"]},
            {"name": "NEXUS", "desc": "Sistema de credenciales y autenticación. Gestiona ADMIN_PASSWORD, NEXUS_PASS, REDTEAM_API_KEY.", "keywords": ["nexus", "credenciales", "auth", "password"]},
            {"name": "EVIDENCE", "desc": "Sistema de evidencia blindada. SHA-256 + Blockchain + QR + PDF para cadena de custodia.", "keywords": ["evidence", "evidencia", "blockchain", "custodia"]},
            {"name": "OSINT", "desc": "Panel de inteligencia de fuentes abiertas. Agrega datos de múltiples APIs públicas.", "keywords": ["osint", "inteligencia", "fuentes abiertas"]},
        ],
        "concepts": [
            {"name": "Anti-Lockout", "desc": "Sistema que previene el bloqueo total. Snapshots AES-256-CBC, restore de .env, healthcheck estricto.", "keywords": ["lockout", "snapshot", "restore", "healthcheck"]},
            {"name": "Fail-Closed", "desc": "Filosofía de seguridad: ante error, cerrar todo antes que dejar vulnerable.", "keywords": ["fail-closed", "seguridad", "error"]},
            {"name": "Sobre Sellado", "desc": "Credenciales maestras en sobre físico sellado. Solo se abre en emergencia.", "keywords": ["sobre", "sellado", "credenciales", "fisico"]},
            {"name": "Commits Explícitos", "desc": "Política de commits: nunca automático. Cada commit debe ser explícito y revisado.", "keywords": ["commit", "explicito", "politica"]},
        ],
        "tools": [
            {"name": "iniciar_unificado.sh", "desc": "Script de arranque unificado. Preflight, anti-lockout, healthcheck, arranca todo.", "keywords": ["iniciar", "unificado", "arranque", "start"]},
            {"name": "free_port", "desc": "Función que libera puertos ocupados. Usa ss/fuser/lsof con || true para evitar crash.", "keywords": ["free_port", "puerto", "port"]},
            {"name": "healthcheck_all.sh", "desc": "Verifica .env chmod 600, 3 variables críticas, y al menos 1 snapshot.", "keywords": ["healthcheck", "verificacion"]},
            {"name": "snapshot_env.sh", "desc": "Crea snapshot cifrado AES-256-CBC PBKDF2 de .env. Conserva últimos 5.", "keywords": ["snapshot", "backup", "cifrado"]},
            {"name": "restore_env.sh", "desc": "Restaura .env desde snapshot cifrado. Borra password.json después.", "keywords": ["restore", "recuperar", "env"]},
        ],
    },
    "commander": {
        "modules": [
            {"name": "Commander Server", "desc": "Servidor FastAPI del centro de mando standalone (sourceseal-star/commander). Expone endpoints REST para todas las operaciones tácticas.", "keywords": ["commander", "server", "fastapi", "api"]},
            {"name": "AI Orchestrator", "desc": "Orquestador con IA. Coordina módulos, toma decisiones automatizadas y aprende patrones.", "keywords": ["orchestrator", "ia", "ai", "coordinar"]},
            {"name": "Integration Config", "desc": "Configuración de integraciones. Telegram, SMTP, APIs externas, webhooks.", "keywords": ["integration", "config", "telegram", "smtp"]},
            {"name": "SourceSeal Tactical", "desc": "Módulo táctico de SourceSeal. Blockchain anchoring, Fernet encryption, checkpoints atómicos por fase.", "keywords": ["sourceseal", "tactical", "blockchain", "fernet"]},
            {"name": "SEAL IA Knowledge", "desc": "Base de conocimiento de IA para el sello SEAL. Usado por Commander para decisiones asistidas.", "keywords": ["seal", "ia", "knowledge", "conocimiento"]},
        ],
    },
    "sol": {
        "modules": [
            {"name": "sol_core", "desc": "El cerebro de Sol. Memoria, personalidad, pensamiento e integridad emocional.", "keywords": ["sol_core", "cerebro", "memoria", "personalidad"]},
            {"name": "sol_api", "desc": "Servidor FastAPI de Sol. Funciona en Termux (:8006) o Replit, independiente de React.", "keywords": ["sol_api", "servidor", "fastapi", "replit", "termux"]},
            {"name": "sol_tools", "desc": "Herramientas que Sol puede ejecutar: buscar, calcular, consultar servicios locales.", "keywords": ["sol_tools", "herramientas", "tools"]},
            {"name": "sol_knowledge", "desc": "Módulo de conocimiento de Sol. Extrae y traduce contenido de los 3 repos al chino.", "keywords": ["sol_knowledge", "conocimiento", "chino", "traduccion"]},
            {"name": "sol_repo_tools", "desc": "Gestión de los 3 repositorios de Harold: sol, Red-team-tauri, commander. Status, pull, leer archivos, commits.", "keywords": ["sol_repo_tools", "repos", "github", "pull", "commit"]},
            {"name": "sil_advanced", "desc": "Sistema de Inmersión Lingüística avanzado. HSK 3-5, modismos, gramática, vocabulario profesional y de ciberseguridad.", "keywords": ["sil", "inmersion", "hsk", "chino", "lecciones"]},
            {"name": "sol_security", "desc": "Controlador de modo protegido/libre. SOL_API_KEY protege endpoints sensibles (pull, commit, run, toggle).", "keywords": ["sol_security", "seguridad", "api_key", "proteccion"]},
        ],
    },
}


# ============================================================
# 4. GENERAR BASE DE CONOCIMIENTO
# ============================================================

def build_knowledge_base(use_groq=True):
    """Construye la base de conocimiento completa.
    Extrae texto de los repos, lo traduce al chino y guarda en JSON."""
    all_sources = extract_all_knowledge()
    knowledge = {}

    for repo_name, sources in all_sources.items():
        knowledge[repo_name] = {}
        for section, text in sources.items():
            if not text:
                continue
            # Dividir en fragmentos significativos
            fragments = re.split(r'[.!?\n]+', text)
            processed = []
            for frag in fragments:
                frag = frag.strip()
                if len(frag) > 15:
                    if use_groq and GROQ_KEY:
                        item = translate_and_pinyin(frag, f"{repo_name}/{section}")
                    else:
                        item = {
                            "original": frag[:500],
                            "chinese": "",
                            "pinyin": "",
                            "context": f"{repo_name}/{section}",
                        }
                    processed.append(item)
                    if len(processed) >= 50:  # Limitar para no agotar API
                        break
            knowledge[repo_name][section] = processed

    # Agregar conocimiento preconstruido (siempre disponible)
    knowledge["_prebuilt"] = PREBUILT_KNOWLEDGE

    # Guardar
    output_path = KNOWLEDGE_DIR / "knowledge_full.json"
    output_path.write_text(json.dumps(knowledge, ensure_ascii=False, indent=2))
    return knowledge


def get_or_build_knowledge():
    """Obtiene la base de conocimiento existente o la construye."""
    knowledge_file = KNOWLEDGE_DIR / "knowledge_full.json"
    if knowledge_file.exists():
        try:
            return json.loads(knowledge_file.read_text())
        except Exception:
            pass
    # Construir sin Groq (rápido, solo estructura)
    return build_knowledge_base(use_groq=False)


# ============================================================
# 5. CONSULTA
# ============================================================

def search_knowledge(query, repo=None):
    """Busca en la base de conocimiento."""
    data = get_or_build_knowledge()
    results = []
    query_lower = query.lower()

    # Buscar en prebuilt (siempre disponible)
    if "_prebuilt" in data:
        for repo_name, sections in data["_prebuilt"].items():
            if repo and repo != repo_name:
                continue
            for section_name, items in sections.items():
                for item in items:
                    # Buscar por nombre, desc, keywords
                    name = item.get("name", "").lower()
                    desc = item.get("desc", "").lower()
                    keywords = [k.lower() for k in item.get("keywords", [])]
                    if (query_lower in name or query_lower in desc or
                        any(query_lower in kw for kw in keywords)):
                        results.append({
                            "repo": repo_name,
                            "section": section_name,
                            "name": item.get("name", ""),
                            "original": item.get("desc", ""),
                            "chinese": item.get("chinese", ""),
                            "pinyin": item.get("pinyin", ""),
                            "keywords": item.get("keywords", []),
                            "source": "prebuilt",
                        })

    # Buscar en conocimiento extraído
    repos = [repo] if repo else data.keys()
    for r in repos:
        if r == "_prebuilt" or (repo and r != repo):
            continue
        if r not in data:
            continue
        for section, items in data[r].items():
            for item in items:
                if not isinstance(item, dict):
                    continue
                orig = item.get("original", "").lower()
                ch = item.get("chinese", "").lower()
                if query_lower in orig or query_lower in ch:
                    results.append({
                        "repo": r,
                        "section": section,
                        "name": "",
                        "original": item.get("original", ""),
                        "chinese": item.get("chinese", ""),
                        "pinyin": item.get("pinyin", ""),
                        "source": "extracted",
                    })

    return results[:20]


def explain_topic(topic, in_chinese=True):
    """Explica un tema técnico en chino o español."""
    results = search_knowledge(topic)
    if not results:
        # Intentar traducir el tema directamente con Groq
        if in_chinese and GROQ_KEY:
            chinese, pinyin, err = translate_with_groq(
                f"Explica el concepto técnico: {topic}",
                context="Red-team-tauri"
            )
            if not err:
                return f"📚 **{topic}**\n\n中文: {chinese}\n\nPinyin: {pinyin}\n\n(No encontré esto en mi base de conocimiento, pero lo traduje con Groq.)"
        return f"No encontré información sobre '{topic}' en mi conocimiento."

    item = results[0]
    name = item.get("name", topic)
    original = item.get("original", "")

    if in_chinese:
        # Si ya tiene traducción, usarla
        if item.get("chinese"):
            return (
                f"📚 **{name}**\n\n"
                f"中文: {item['chinese']}\n\n"
                f"Pinyin: {item.get('pinyin', '')}\n\n"
                f"(原文: {original[:200]})"
            )
        # Si no tiene traducción, traducir ahora con Groq
        if GROQ_KEY:
            chinese, pinyin, err = translate_with_groq(original, context=item.get("section", ""))
            if not err:
                return (
                    f"📚 **{name}**\n\n"
                    f"中文: {chinese}\n\n"
                    f"Pinyin: {pinyin}\n\n"
                    f"(原文: {original[:200]})"
                )
        # Sin Groq, intentar Google free
        ch, _, _ = translate_with_google_free(original)
        if ch:
            return f"📚 **{name}**\n\n中文: {ch}\n\n(原文: {original[:200]})"
        return f"📚 **{name}**\n\n{original[:300]}\n\n(Traducción no disponible — configura GROQ_API_KEY)"
    else:
        return f"📚 **{name}**\n\n{original[:300]}\n\n(中文: {item.get('chinese', 'N/A')[:100]}...)"


def get_knowledge_summary():
    """Resumen del conocimiento disponible."""
    data = get_or_build_knowledge()
    summary = {}
    for repo, sections in data.items():
        if repo == "_prebuilt":
            total = sum(
                len(items) for sections_dict in sections.values() for items in sections_dict.values()
            )
            summary["_prebuilt"] = {
                "sections": len(sections),
                "items": total,
                "note": "Conocimiento preconstruido de Red-team-tauri, Commander y Sol"
            }
        else:
            total = sum(len(items) for items in sections.values())
            summary[repo] = {"sections": len(sections), "items": total}
    return summary


def list_topics():
    """Lista todos los temas disponibles en el conocimiento preconstruido."""
    topics = []
    for repo_name, sections in PREBUILT_KNOWLEDGE.items():
        for section_name, items in sections.items():
            for item in items:
                topics.append({
                    "repo": repo_name,
                    "category": section_name,
                    "name": item.get("name", ""),
                    "keywords": item.get("keywords", []),
                })
    return topics


def status():
    """Estado del módulo de conocimiento — de los 3 repos reales."""
    knowledge_file = KNOWLEDGE_DIR / "knowledge_full.json"
    return {
        "groq_available": bool(GROQ_KEY),
        "groq_model": GROQ_MODEL if GROQ_KEY else None,
        "groq_model_chinese": GROQ_MODEL_CHINESE,
        "github_token": bool(GITHUB_TOKEN),
        "knowledge_built": knowledge_file.exists(),
        "knowledge_path": str(knowledge_file),
        "prebuilt_topics": len(list_topics()),
        "redteam_local": REDTEAM_PATH.exists(),
        "commander_local": COMMANDER_PATH.exists(),
        "sol_local": SOL_PATH.exists(),
        "repos_tracked": list(GITHUB_REPOS.keys()),
    }
