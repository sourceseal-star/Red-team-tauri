"""HOLO 9.1 · Qalam Trigram + Context — Predicción Consciente
El 9.0 usaba bigramas. El 9.1 usa TRIGRAMAS (más preciso) Y detecta
el CONTEXTO en tiempo real (git/docker/red) para dar sugerencias
que saben en qué mundo estás operando.

FIX 2026-10-01 (auditoría del bundle):
1. GUARDADO JSON: el bundle usaba claves TUPLE en los trigramas
   (dict[(a,b,c)] = n) → json.dumps revienta con TypeError. Ahora las
   claves se serializan como "a b c" y se deserializan al cargar.
2. ENTRENAMIENTO EXPLÍCITO: el bundle entrenaba SOLO (leía tus
   historiales de shell automáticamente en cada cargar_modelo()).
   Filosofía del Qalam Ancestral actual: entrenamiento EXPLÍCITO.
   Ahora cargar_modelo() devuelve un modelo vacío si no existe, y
   SOLO POST /entrenar lee los historiales. Nada automático.
3. Eco: lee el Mirror del mismo data/ compartido y el audit del
   Portero SOLO si el archivo existe (sin inventar datos).
"""

import json, re, os
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from fastapi import APIRouter
from typing import Optional

BASE = Path(__file__).parent / "data"
TRIGRAM_FILE = BASE / "qalam_trigram.json"
CONTEXT_FILE = BASE / "qalam_context.json"
ECHO_FILE = BASE / "eco_cache.json"
MIRROR_FILE = BASE / "holo_mirror.json"          # mismo data/ que holo_mirror.py
# Audit del Portero (sol_supergate) — candidatos honestos, sin inventar
AUDIT_CANDIDATOS = [
    BASE / "portero_audit.log",
    Path(__file__).parent.parent.parent / "portero_audit.log",
]
HISTORY_FILES = [
    Path.home() / ".zsh_history",
    Path.home() / ".bash_history",
    Path.home() / ".history" / "zsh",
    Path.home() / ".local" / "share" / "fish" / "fish_history",
]

router = APIRouter(prefix="/api/qalam-v2", tags=["HOLO 9.1"])

# ─── Detección de contexto ─────────────────────────────────────────────────

CONTEXTO_KEYWORDS = {
    "git": {"keywords": ["git", "commit", "push", "pull", "branch", "merge", "rebase",
                         "stash", "log", "diff", "status", "fetch", "clone", "remote"],
            "comandos_base": ["git status", "git add", "git commit -m", "git push",
                             "git pull", "git branch", "git checkout", "git log --oneline"]},
    "docker": {"keywords": ["docker", "podman", "container", "image", "compose",
                            "dockerfile", "docker-registry"],
               "comandos_base": ["docker ps", "docker images", "docker exec -it",
                                "docker-compose up", "docker-compose down", "docker build"]},
    "network": {"keywords": ["ping", "curl", "wget", "netstat", "ss", "nmap", "iptables",
                              "firewalld", "ufw", "ip addr", "traceroute", "nc"],
                "comandos_base": ["ping -c 4", "curl -I", "curl -X POST",
                                 "netstat -tulpn", "ss -tulpn", "nmap -sC"]},
    "system": {"keywords": ["systemctl", "journalctl", "top", "htop", "ps", "kill",
                            "pkill", "killall", "systemd", "service"],
               "comandos_base": ["systemctl status", "systemctl restart",
                                 "journalctl -u", "ps aux | grep"]},
    "file": {"keywords": ["ls", "cd", "mkdir", "rm", "cp", "mv", "chmod", "chown",
                          "find", "grep", "cat", "head", "tail", "sed", "awk"],
             "comandos_base": ["ls -la", "find . -name", "grep -rn",
                               "cat /proc/", "tail -f"]},
    "python": {"keywords": ["python", "pip", "venv", "poetry", "uv", "pip3", "pip install",
                            "python3 -m", "import", "pip freeze"],
               "comandos_base": ["python3 -m venv", "pip install", "pip list",
                                "python3 -c", "poetry install", "uv pip install"]},
    "code": {"keywords": ["cargo", "npm", "yarn", "pnpm", "go build", "make", "cmake",
                           "rustc", "node", "tsc", "eslint", "prettier"],
             "comandos_base": ["npm run dev", "cargo build", "make build",
                              "go build -o", "tsc --init"]},
    "deploy": {"keywords": ["terraform", "ansible", "helm", "kubectl", "docker-swarm",
                            "swarm", "ingress", "deployment", "kubernetes", "k8s"],
               "comandos_base": ["kubectl get pods", "kubectl apply -f",
                               "helm install", "terraform plan"]},
}

def detectar_contexto_actual() -> tuple:
    """Detecta el contexto basándose en CWD."""
    try:
        cwd = os.getcwd()
        entradas = os.listdir(cwd) if cwd and os.path.isdir(cwd) else []
    except (OSError, PermissionError):
        return "system", 0.3

    if ".git" in entradas:
        return "git", 0.9
    if "Dockerfile" in entradas or any("docker-compose" in f for f in entradas):
        return "docker", 0.85
    py_files = [f for f in entradas if f.endswith(".py")]
    if len(py_files) > 2:
        return "python", 0.75
    yaml_files = [f for f in entradas if f.endswith((".yaml", ".yml"))]
    if any(("deploy" in f or "service" in f or "config" in f) for f in yaml_files):
        return "deploy", 0.7
    return "system", 0.3

def detectar_contexto_desde_texto(texto: str) -> tuple:
    """Detecta contexto desde el texto del usuario."""
    tokens = set(t.lower().strip(".,;:!?\"'()[]{}") for t in texto.split())
    scores = {}

    for ctx, data in CONTEXTO_KEYWORDS.items():
        matches = sum(1 for kw in data["keywords"] if kw in tokens)
        scores[ctx] = matches

    if not scores or max(scores.values()) == 0:
        return detectar_contexto_actual()

    mejor = max(scores, key=scores.get)
    confianza = min(1.0, scores[mejor] * 0.25 + 0.3)
    return mejor, confianza

# ─── Modelo trigrama — serialización JSON-SEGURA ────────────────────────────

def _key_to_str(k) -> str:
    """(a, b, c) → 'a b c'. c=None (bigrama) → 'a b' con marcador."""
    partes = ["" if p is None else str(p) for p in k]
    return json.dumps(partes, ensure_ascii=False)   # lista JSON = clave string segura

def _str_to_key(s: str) -> tuple:
    partes = json.loads(s)
    partes = [p if p != "" else None for p in partes]
    return tuple(partes)

def parse_history_linea(linea: str) -> Optional[str]:
    """Extrae el comando de una línea de historial."""
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None
    # zsh: ": 1700000000:0;comando"
    if linea.startswith(":"):
        parts = linea.split(";", 1)
        if len(parts) == 2:
            return parts[1].strip()
        return None
    # fish: "- cmd: comando\n  when: ts"
    if linea.startswith("- cmd:"):
        match = re.match(r"- cmd: (.+?)(?:\n  when:|$)", linea)
        if match:
            return match.group(1).strip()
        return None
    # Bash: "comando"
    return linea

def entrenar_trigram() -> dict:
    """Entrena el modelo trigrama desde los historiales del usuario.
    SOLO se llama desde POST /entrenar (explícito) — nunca automático."""
    trigramas = Counter()
    unigramas = Counter()
    fuentes_usadas = []

    for hist_file in HISTORY_FILES:
        if not hist_file.exists():
            continue
        try:
            contenido = hist_file.read_text(errors="ignore")
            lineas = contenido.splitlines()
            comandos = [parse_history_linea(l) for l in lineas]
            comandos = [c for c in comandos if c and len(c) > 1 and not c.startswith("#")]

            for cmd in comandos:
                tokens = cmd.split()
                unigramas.update(tokens)
                for a, b, c in zip(tokens, tokens[1:], tokens[2:]):
                    trigramas[(a, b, c)] += 1
                # Bigramas de respaldo (tercer elemento None)
                for a, b in zip(tokens, tokens[1:]):
                    trigramas[(a, b, None)] += 1
            fuentes_usadas.append(str(hist_file))
        except (OSError, PermissionError):
            continue

    # FIX: claves como STRINGS serializables (el tuple directo revienta json.dumps)
    modelo = {
        "version": "9.1",
        "trigramas": {_key_to_str(k): v for k, v in trigramas.most_common(2000)},
        "unigramas": dict(unigramas.most_common(500)),
        "entrenado": datetime.now().isoformat(),
        "muestras": sum(trigramas.values()),
        "fuentes": fuentes_usadas,
    }
    BASE.mkdir(exist_ok=True, parents=True)
    TRIGRAM_FILE.write_text(json.dumps(modelo, ensure_ascii=False, indent=2))
    return modelo

def _modelo_vacio() -> dict:
    return {
        "version": "9.1",
        "trigramas": {},
        "unigramas": {},
        "entrenado": None,
        "muestras": 0,
        "modelo_vacio": True,
    }

def cargar_modelo() -> dict:
    """FIX: si no hay modelo, devuelve un modelo VACÍO — NUNCA entrena solo.
    El entrenamiento es explícito (POST /entrenar), como en Qalam Ancestral."""
    if TRIGRAM_FILE.exists():
        try:
            return json.loads(TRIGRAM_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return _modelo_vacio()
    return _modelo_vacio()

def _modelo_tuplas(modelo: dict) -> dict:
    """Deserializa las claves string '["a","b","c"]' a tuplas para predecir."""
    trigramas = {}
    for k, v in modelo.get("trigramas", {}).items():
        try:
            trigramas[_str_to_key(k)] = v
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return {**modelo, "trigramas": trigramas}

# ─── Predicción con contexto ──────────────────────────────────────────────────

def predecir(texto: str, contexto: str = None, max_sugerencias: int = 6) -> dict:
    """
    Predice el siguiente comando basándose en trigramas y contexto.
    1. Busca trigramas que coincidan con los últimos 2 tokens
    2. Filtra por contexto si está disponible
    3. Ordena por frecuencia
    """
    modelo = _modelo_tuplas(cargar_modelo())
    tokens = texto.strip().split()

    if not tokens:
        # Sin input: devolver comandos base del contexto
        ctx = contexto or detectar_contexto_actual()[0]
        if ctx in CONTEXTO_KEYWORDS:
            return {
                "sugerencias": CONTEXTO_KEYWORDS[ctx]["comandos_base"][:max_sugerencias],
                "modelo": "trigram_v1",
                "contexto": ctx,
                "tipo": "base",
                "modelo_vacio": bool(modelo.get("modelo_vacio")),
            }
        return {"sugerencias": [], "modelo": "trigram_v1", "contexto": ctx,
                "modelo_vacio": bool(modelo.get("modelo_vacio"))}

    # Modelo vacío (sin entrenar explícito): sugerencias base del contexto
    if modelo.get("modelo_vacio") or not modelo.get("trigramas"):
        ctx = contexto or detectar_contexto_desde_texto(texto)[0]
        bases = CONTEXTO_KEYWORDS.get(ctx, {}).get("comandos_base", [])[:max_sugerencias]
        return {
            "sugerencias": bases,
            "modelo": "trigram_v1",
            "contexto": ctx,
            "tipo": "base_sin_entrenar",
            "modelo_vacio": True,
            "hint": "POST /api/qalam-v2/entrenar para entrenar con tus historiales",
        }

    ultimo = tokens[-1]
    penultimo = tokens[-2] if len(tokens) >= 2 else None

    # Buscar trigramas
    candidatos = Counter()

    # Trigrama completo: penultimo + ultimo + ?
    if penultimo:
        for (a, b, c), n in modelo["trigramas"].items():
            if a == penultimo and b == ultimo and c:
                candidatos[c] += n * 2  # peso extra por especificidad

    # Bigrama: ultimo + ?
    for (a, b, c), n in modelo["trigramas"].items():
        if c is None and a == ultimo:
            if b:
                candidatos[b] += n

    # Unigrama: comando que empieza con el token actual
    if ultimo and len(ultimo) > 1:
        for cmd, n in modelo.get("unigramas", {}).items():
            if cmd.startswith(ultimo):
                candidatos[cmd] += n * 0.5

    # Filtrar por contexto si está disponible
    if contexto and contexto in CONTEXTO_KEYWORDS:
        ctx_kws = set(CONTEXTO_KEYWORDS[contexto]["keywords"])
        filtrados = {}
        for cmd, peso in sorted(candidatos.items(), key=lambda kv: -kv[1]):
            if any(kw in cmd.lower() for kw in ctx_kws):
                filtrados[cmd] = peso
            elif len(tokens) == 1 and peso > 0:
                filtrados[cmd] = peso * 0.7
        candidatos = Counter(filtrados)

    # Construir comandos completos si el input es parcial
    sugerencias = []
    for cmd, peso in sorted(candidatos.items(), key=lambda kv: -kv[1])[:max_sugerencias * 2]:
        if ultimo and cmd.startswith(ultimo):
            if len(tokens) == 1:
                sugerencia = cmd
            else:
                sugerencia = " ".join(tokens[:-1]) + " " + cmd
        else:
            sugerencia = f"{ultimo} {cmd}"
        sugerencias.append(sugerencia.strip())

    sugerencias = list(dict.fromkeys(sugerencias))[:max_sugerencias]

    return {
        "sugerencias": sugerencias,
        "modelo": "trigram_v1",
        "contexto": contexto or "desconocido",
        "tokens_input": len(tokens),
        "entrenamiento_muestras": modelo.get("muestras", 0),
        "entrenado": modelo.get("entrenado") or "nunca",
    }

# ─── Eco del Día mejorado ────────────────────────────────────────────────────

def generar_eco() -> dict:
    """Genera el Eco del Día: resumen de 24h de actividad del sistema."""
    desde = datetime.now() - timedelta(hours=24)

    # Cargar Mirror (mismo data/, escrito por holo_mirror.py)
    mirror_eco = {"intercambios": 0, "herramientas": Counter(), "hemisferios": Counter()}
    if MIRROR_FILE.exists():
        try:
            m = json.loads(MIRROR_FILE.read_text())
            for entrada in m.get("historial", []):
                ts = datetime.fromisoformat(entrada["ts"])
                if ts > desde:
                    mirror_eco["intercambios"] += 1
                    mirror_eco["hemisferios"][entrada["hemisferio"]] += 1
                    for t in entrada.get("tokens", [])[:5]:
                        mirror_eco["herramientas"][t] += 1
        except (json.JSONDecodeError, ValueError):
            pass

    # Audit del Portero — SOLO si el archivo existe (sin inventar sellos)
    sellos_dia = 0
    portero_disponible = False
    for audit_file in AUDIT_CANDIDATOS:
        if audit_file.exists():
            portero_disponible = True
            try:
                for linea in audit_file.read_text(errors="ignore").splitlines():
                    if "|True|" in linea:
                        sellos_dia += 1
            except OSError:
                pass
            break

    # Consciencia del contexto dominante
    herramientas = mirror_eco["herramientas"]
    if herramientas:
        dominante = herramientas.most_common(1)[0]
        ctx_dom, _ = detectar_contexto_desde_texto(dominante[0])
    else:
        ctx_dom = "silencio"

    # Consciencia del hemisferio
    h = mirror_eco["hemisferios"]
    sello = "𓂀" if h.get("sarah", 0) > h.get("sol", 0) else "☥"
    if h.get("sarah", 0) > h.get("sol", 0) * 2:
        sello = "𓂀🌙"  # Sarah dominó el día
    elif h.get("sol", 0) > h.get("sarah", 0) * 2:
        sello = "☥⚡"  # Sol dominó el día

    sintesis = (
        f"Eco 24h: {mirror_eco['intercambios']} intercambios. "
        f"{sellos_dia} sellos tejidos. "
        f"Contexto dominante: {ctx_dom}. "
        f"Sol {h.get('sol', 0)}×, Sarah {h.get('sarah', 0)}×. "
        f"{sello}"
    )

    eco = {
        "sintesis": sintesis,
        "sellos_dia": sellos_dia,
        "portero_disponible": portero_disponible,
        "intercambios": mirror_eco["intercambios"],
        "herramientas": dict(herramientas.most_common(5)),
        "hemisferios": dict(h),
        "contexto_dominante": ctx_dom,
        "sello": sello,
        "ts": datetime.now().isoformat(),
    }

    BASE.mkdir(exist_ok=True, parents=True)
    ECHO_FILE.write_text(json.dumps(eco, ensure_ascii=False, indent=2))
    return eco

# ─── Rutas API ────────────────────────────────────────────────────────────────

@router.post("/predecir")
def predecir_cmd(payload: dict):
    """Predice el siguiente comando. Admite contexto explícito opcional."""
    texto = payload.get("texto", "")
    contexto = payload.get("contexto")  # opcional, detectado automáticamente si None
    max_ = min(payload.get("max", 6), 10)

    if not contexto:
        ctx_detectado, confianza = detectar_contexto_desde_texto(texto)
    else:
        ctx_detectado = contexto
        confianza = 1.0

    resultado = predecir(texto, ctx_detectado, max_)
    resultado["contexto_detectado"] = ctx_detectado
    resultado["confianza_contexto"] = round(confianza, 2)
    return resultado

@router.post("/entrenar")
def reentrenar():
    """Entrenamiento EXPLÍCITO del modelo con los historiales actuales.
    Nada automático: solo cuando tú lo pides."""
    modelo = entrenar_trigram()
    return {
        "ok": True,
        "muestras": modelo["muestras"],
        "entrenado": modelo["entrenado"],
        "fuentes": modelo.get("fuentes", []),
    }

@router.get("/eco")
def eco():
    """Devuelve el Eco del Día cacheado (se regenera si >1h viejo)."""
    if ECHO_FILE.exists():
        try:
            eco = json.loads(ECHO_FILE.read_text())
            ts = datetime.fromisoformat(eco["ts"])
            if datetime.now() - ts < timedelta(hours=1):
                return eco
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return generar_eco()

@router.post("/eco/regenerar")
def regenerar_eco():
    """Fuerza regeneración del Eco del Día."""
    return generar_eco()

@router.get("/contexto")
def contexto_actual():
    """Devuelve el contexto detectado actualmente (CWD + texto)."""
    ctx, confianza = detectar_contexto_actual()
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = "desconocido"
    return {"contexto": ctx, "confianza": confianza, "cwd": cwd}

@router.get("/modelo")
def estado_modelo():
    """Estado del modelo: número de muestras, fecha de entrenamiento."""
    modelo = cargar_modelo()
    return {
        "version": modelo.get("version", "9.1"),
        "muestras": modelo.get("muestras", 0),
        "entrenado": modelo.get("entrenado") or "nunca",
        "trigramas": len(modelo.get("trigramas", {})),
        "unigramas": len(modelo.get("unigramas", {})),
        "modelo_vacio": bool(modelo.get("modelo_vacio")),
        "nota": "entrenamiento explícito: POST /api/qalam-v2/entrenar",
    }
