"""
Módulo Qalam Ancestral - Sugerencias de Comandos e Historial Predictivo.
Sistemas Red Team SourceSeal.

Soporta:
- GET  /api/qalam/estado
- POST /api/qalam/entrenar
- POST /api/qalam/predecir
- GET  /api/qalam/eco
"""

import os
import re
import json
import math
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

# Router definition
router = APIRouter(prefix="/api/qalam", tags=["qalam"])

# Private runtime paths
MODULE_DIR = Path(__file__).resolve().parent
REDTEAM_DIR = MODULE_DIR.parent
DATA_DIR = REDTEAM_DIR / "data" / "qalam_ancestral"

MODEL_FILE = DATA_DIR / "qalam_model.json"
JOURNAL_FILE = DATA_DIR / "qalam_journal.jsonl"

ZSH_HISTORY_FILE = Path.home() / ".zsh_history"
BASH_HISTORY_FILE = Path.home() / ".bash_history"

MAX_TAIL_BYTES = 1024 * 1024  # 1 MB bounded tail read
MAX_JOURNAL_EVENTS = 2000
MAX_BIGRAMS = 500  # Top 500 bigrams
JOURNAL_24H_SECONDS = 86400

# Concurrency lock
_LOCK = threading.Lock()

# Safe command words whitelist
SAFE_COMMAND_WORDS = {
    # Version control
    "git", "status", "commit", "add", "push", "pull", "diff", "branch", "checkout",
    "log", "fetch", "merge", "rebase", "stash", "clone", "init", "show", "remote",
    "reset", "switch", "restore", "tag", "blame", "cherry-pick",
    # Filesystem & Navigation
    "ls", "cd", "pwd", "cat", "grep", "find", "echo", "mkdir", "rm", "cp", "mv",
    "touch", "head", "tail", "wc", "sort", "uniq", "less", "more", "tree", "ln",
    # Process & System
    "top", "htop", "ps", "kill", "df", "du", "free", "uptime", "whoami", "uname",
    "history", "clear", "exit", "which", "whereis", "date", "time", "sleep",
    # Containers & Orchestration
    "docker", "container", "image", "run", "build", "exec", "stop", "start",
    "logs", "compose", "kubectl", "get", "describe", "apply", "delete",
    "pods", "services", "deployments",
    # Development tools & Runtimes
    "python", "python3", "pytest", "pip", "install", "uvicorn", "fastapi",
    "node", "npm", "yarn", "pnpm", "bun", "make", "cargo", "go", "rustc",
    "gcc", "g++", "java", "javac", "gradle", "maven",
    # System Administration & Network
    "systemctl", "journalctl", "service", "chmod", "chown", "tar", "zip",
    "unzip", "gzip", "ssh", "scp", "rsync", "curl", "wget", "ping", "dig",
    "nslookup", "netstat", "ss", "ip"
}

SAFE_OPTIONS = {
    "-a", "-l", "-la", "-al", "-lh", "-v", "-h", "--help", "--version",
    "-m", "-b", "-f", "-r", "-rf", "-u", "-p", "-n", "-t", "-i", "-s",
    "-d", "-e", "-k", "-q", "-y", "-C", "-D", "-S", "-U", "-V",
    "--all", "--long", "--verbose", "--quiet", "--force", "--dry-run",
    "--no-pager", "--oneline", "--graph", "--stat", "--patch", "--staged",
    "--cached", "--hard", "--soft", "--amend"
}

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\b(token|key|password|passwd|auth|env|export|secret|credentials?|bearer|apikey|api_key)\b"),
    re.compile(r"(?i)\bcurl\b.*(-h|--header|-d|--data|-u|--user)"),
    re.compile(r"[A-Za-z0-9_]*(token|key|secret|pass|auth|pwd|cred)[A-Za-z0-9_]*\s*="),
    re.compile(r"(?i)(bearer\s+[a-z0-9\-_\.=]+|ghp_[a-zA-Z0-9]{36}|AKIA[0-9A-Z]{16}|eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)"),
]


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    prob = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * math.log2(p) for p in prob)


def is_line_sensitive(line: str) -> bool:
    """Rechaza la línea completa si contiene patrones o asignaciones sensibles o alta entropía."""
    if not line:
        return False

    # Standard sensitive pattern match
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(line):
            return True

    # Check variable assignments containing sensitive keys
    if "=" in line:
        parts = line.split("=", 1)
        var_name = parts[0].strip().lower()
        if any(k in var_name for k in ["key", "token", "secret", "pass", "auth", "pwd", "cred"]):
            return True

    # High entropy strings check
    words = line.split()
    for word in words:
        clean_word = word.strip("'\"`")
        if len(clean_word) >= 14 and re.match(r"^[A-Za-z0-9/+=_-]+$", clean_word):
            if shannon_entropy(clean_word) > 3.8:
                return True

    return False


def sanitize_and_tokenize(line: str) -> List[str]:
    """Valida la línea y extrae tokens seguros conservadores."""
    if is_line_sensitive(line):
        return []

    words = line.strip().split()
    safe_tokens = []
    for word in words:
        clean = word.strip("'\"`;,")
        if not clean:
            continue
        # Drop paths (containing / or \) or URLs or emails/credentials
        if "/" in clean or "\\" in clean or "://" in clean or "@" in clean:
            continue
        # Check against whitelist
        clean_lower = clean.lower()
        if clean_lower in SAFE_COMMAND_WORDS or clean in SAFE_OPTIONS:
            safe_tokens.append(clean_lower if clean_lower in SAFE_COMMAND_WORDS else clean)

    return safe_tokens


def get_history_source() -> Tuple[Path, str]:
    """Retorna el archivo de historial activo o fallback."""
    if ZSH_HISTORY_FILE.exists() and ZSH_HISTORY_FILE.is_file():
        return ZSH_HISTORY_FILE, "zsh_history"
    if BASH_HISTORY_FILE.exists() and BASH_HISTORY_FILE.is_file():
        return BASH_HISTORY_FILE, "bash_history"
    return ZSH_HISTORY_FILE, "ninguno"


def read_tail_history(file_path: Path, max_bytes: int = MAX_TAIL_BYTES) -> List[str]:
    """Lectura acotada de max_bytes desde el final del archivo de historial."""
    if not file_path.exists() or not file_path.is_file():
        return []

    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            return []

        with open(file_path, "rb") as f:
            if file_size > max_bytes:
                f.seek(file_size - max_bytes)
                f.readline()  # Discard split first line
            raw = f.read(max_bytes)

        text = raw.decode("utf-8", errors="ignore")
        lines = text.splitlines()

        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Handle zsh timestamp format ': 1690000000:0;cmd'
            if line.startswith(": ") and ";" in line:
                _, _, cmd = line.partition(";")
                line = cmd.strip()
            # Handle bash timestamp comment lines '#1690000000'
            elif line.startswith("#") and line[1:].isdigit():
                continue

            if line:
                cleaned_lines.append(line)

        return cleaned_lines
    except OSError:
        raise HTTPException(status_code=503, detail="No se pudo leer el historial. Modelo anterior intacto.")


def save_model_atomic(data: dict) -> None:
    """Guarda el modelo atómicamente con permisos 0600 bajo lock."""
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_path_str = tempfile.mkstemp(dir=DATA_DIR, prefix=".qalam_model_", suffix=".tmp")
    tmp_path = Path(tmp_path_str)
    try:
        os.chmod(tmp_path, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        os.replace(tmp_path, MODEL_FILE)
        os.chmod(MODEL_FILE, 0o600)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def load_model() -> Tuple[Optional[dict], str]:
    """Carga el modelo guardado. Retorna (data, estado_str)."""
    if not MODEL_FILE.exists() or not MODEL_FILE.is_file():
        return None, "no_entrenado"

    try:
        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("top_bigrams"), list):
            return None, "modelo_corrupto"
        pairs = data["top_bigrams"]
        if len(pairs) > MAX_BIGRAMS or any(
            not isinstance(pair, list) or len(pair) != 2 or
            any(not isinstance(word, str) or word not in SAFE_COMMAND_WORDS | SAFE_OPTIONS
                for word in pair) for pair in pairs
        ):
            return None, "modelo_corrupto"
        return data, "listo"
    except Exception:
        return None, "modelo_corrupto"


def append_journal_event(event_type: str, details: dict) -> None:
    """Registra evento propio en diario privado acotado (sin texto ni comandos crudos)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "categoria": details.get("categoria", "comando"),
        "detalles": details
    }
    with _LOCK:
        events = read_journal_24h()
        events.append(record)
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix=".qalam_journal_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                for event in events[-MAX_JOURNAL_EVENTS:]:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            os.replace(tmp, JOURNAL_FILE)
            os.chmod(JOURNAL_FILE, 0o600)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def read_journal_24h() -> List[dict]:
    """Lee eventos del diario privado con ventana real de 24 horas en UTC."""
    if not JOURNAL_FILE.exists() or not JOURNAL_FILE.is_file():
        return []

    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(hours=24)
    valid_events = []
    try:
        with JOURNAL_FILE.open("rb") as stream:
            size = JOURNAL_FILE.stat().st_size
            if size > MAX_TAIL_BYTES:
                stream.seek(size - MAX_TAIL_BYTES)
                stream.readline()
            lines = stream.read(MAX_TAIL_BYTES).decode("utf-8", errors="ignore").splitlines()
        for line in lines:
            try:
                record = json.loads(line)
                ts_dt = datetime.fromisoformat(record["timestamp"])
                if ts_dt.tzinfo is None:
                    continue
                if not cutoff_dt <= ts_dt <= now or record.get("event") not in ("entrenamiento", "prediccion"):
                    continue
                # Never echo arbitrary journal fields or user text.
                details = record.get("detalles", {})
                safe_details = {key: value for key, value in details.items()
                                if key in ("lineas_leidas", "lineas_seguras", "bigramas", "sugerencias_count")
                                and isinstance(value, int) and not isinstance(value, bool)}
                valid_events.append({"timestamp": ts_dt.isoformat(), "event": record["event"],
                                     "categoria": "comando", "detalles": safe_details})
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
    except OSError:
        pass
    return valid_events[-MAX_JOURNAL_EVENTS:]


# Pydantic Schemas
class EstadoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entrenado: bool
    modelo_existe: bool
    estado_modelo: str
    ultima_actualizacion: Optional[str] = None
    total_bigramas: int = 0
    historial_fuente: str
    journal_eventos_24h: int = 0


class EntrenarRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    forzar: bool = Field(default=False, description="Forzar reentrenamiento del modelo")


class EntrenarResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    mensaje: str
    fuente_usada: str
    lineas_leidas: int
    lineas_seguras: int
    bigramas_totales: int
    model_path: str


class PredecirRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    texto: str = Field(..., strict=True, max_length=256, description="Prefijo o texto de entrada para predecir")


class PredecirResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sugerencias: List[str]
    estado_modelo: str
    detalles: Dict[str, Any]


class EcoResponse(BaseModel):
    sintesis: str
    model_config = ConfigDict(extra="ignore")

    timestamp_utc: str
    ventana_horas: int = 24
    limite_eventos: int = MAX_JOURNAL_EVENTS
    eventos_totales_24h: int
    entrenamientos_24h: int
    predicciones_24h: int
    eventos_recientes: List[Dict[str, Any]]
    fuentes: List[str] = Field(default_factory=list)
    available: List[str] = Field(default_factory=list)
    sello_claims: Optional[str] = None
    sol_counts: Optional[int] = None
    sarah_counts: Optional[int] = None


# Endpoints
@router.get("/estado", response_model=EstadoResponse)
def get_estado():
    model_data, state_str = load_model()
    model_exists = MODEL_FILE.exists() and MODEL_FILE.is_file()
    _, hist_source = get_history_source()
    journal_events = read_journal_24h()

    is_trained = (state_str == "listo" and model_data is not None)
    bigram_count = len(model_data.get("top_bigrams", [])) if model_data else 0
    updated_at = model_data.get("updated_at") if model_data else None

    return EstadoResponse(
        entrenado=is_trained,
        modelo_existe=model_exists,
        estado_modelo=state_str,
        ultima_actualizacion=updated_at,
        total_bigramas=bigram_count,
        historial_fuente=hist_source,
        journal_eventos_24h=len(journal_events)
    )


@router.post("/entrenar", response_model=EntrenarResponse)
def post_entrenar(body: Optional[EntrenarRequest] = None):
    history_file, source_name = get_history_source()
    if source_name == "ninguno":
        raise HTTPException(status_code=409, detail="No existe historial zsh/bash. El modelo anterior queda intacto.")

    lines = read_tail_history(history_file, MAX_TAIL_BYTES)

    bigram_counts: Dict[str, int] = {}
    safe_lines_count = 0

    for line in lines:
        tokens = sanitize_and_tokenize(line)
        if not tokens:
            continue
        safe_lines_count += 1
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]} {tokens[i+1]}"
            bigram_counts[bg] = bigram_counts.get(bg, 0) + 1

    # Sort and take top 500
    sorted_bigrams = sorted(bigram_counts.items(), key=lambda x: x[1], reverse=True)[:MAX_BIGRAMS]
    top_bigram_list = [bg_str.split(" ", 1) for bg_str, _ in sorted_bigrams]
    top_bigram_dict = dict(sorted_bigrams)

    now_utc = datetime.now(timezone.utc).isoformat()
    model_payload = {
        "version": "1.0",
        "created_at": now_utc,
        "updated_at": now_utc,
        "source": source_name,
        "total_lines_read": len(lines),
        "safe_lines_processed": safe_lines_count,
        "bigram_counts": top_bigram_dict,
        "top_bigrams": top_bigram_list
    }

    with _LOCK:
        save_model_atomic(model_payload)

    # Register event in journal
    append_journal_event("entrenamiento", {
        "categoria": "comando",
        "lineas_leidas": len(lines),
        "lineas_seguras": safe_lines_count,
        "bigramas": len(top_bigram_list),
        "fuente": source_name
    })

    return EntrenarResponse(
        status="ok",
        mensaje="Modelo Qalam Ancestral entrenado exitosamente.",
        fuente_usada=source_name,
        lineas_leidas=len(lines),
        lineas_seguras=safe_lines_count,
        bigramas_totales=len(top_bigram_list),
        model_path=str(MODEL_FILE)
    )


@router.post("/predecir", response_model=PredecirResponse)
def post_predecir(req: PredecirRequest):
    model_data, state_str = load_model()

    # Predictions without model return empty (do NOT auto-train)
    if state_str != "listo" or not model_data:
        return PredecirResponse(
            sugerencias=[],
            estado_modelo=state_str,
            detalles={"mensaje": "Modelo no entrenado o corrupto. Ejecute POST /entrenar explícitamente."}
        )

    clean_input = req.texto.strip()
    safe_tokens = sanitize_and_tokenize(clean_input)

    top_bigrams = model_data.get("top_bigrams", [])
    sugerencias = []

    if safe_tokens:
        input_token = safe_tokens[-1].lower()
        # Find bigrams where first element matches input token or input string prefix
        for bg in top_bigrams:
            if len(bg) == 2:
                w1, w2 = bg[0], bg[1]
                if w1 == input_token or w1.startswith(input_token):
                    candidate = f"{w1} {w2}"
                    if candidate not in sugerencias:
                        sugerencias.append(candidate)
                        if len(sugerencias) >= 5:
                            break

    # Empty safe input may show general pairs; sensitive input never does.
    if not clean_input and not sugerencias and top_bigrams:
        for bg in top_bigrams[:5]:
            if len(bg) == 2:
                candidate = f"{bg[0]} {bg[1]}"
                if candidate not in sugerencias:
                    sugerencias.append(candidate)

    # Record prediction event in journal
    append_journal_event("prediccion", {
        "categoria": "comando",
        "sugerencias_count": len(sugerencias)
    })

    return PredecirResponse(
        sugerencias=sugerencias,
        estado_modelo="entrenado",
        detalles={"coincidencias": len(sugerencias)}
    )


@router.get("/eco", response_model=EcoResponse)
def get_eco():
    events_24h = read_journal_24h()

    entrenamientos = sum(1 for e in events_24h if e.get("event") == "entrenamiento")
    predicciones = sum(1 for e in events_24h if e.get("event") == "prediccion")

    return EcoResponse(
        sintesis=f"Eco Qalam (24h): {entrenamientos} entrenamientos y {predicciones} consultas de predicción retenidos. No hay datos de sellos ni de Sol/Sarah.",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        ventana_horas=24,
        eventos_totales_24h=len(events_24h),
        entrenamientos_24h=entrenamientos,
        predicciones_24h=predicciones,
        eventos_recientes=events_24h[-20:],  # Return last 20 events
        fuentes=[],  # Truthfully empty
        available=[],  # Truthfully empty
        sello_claims=None,
        sol_counts=None,
        sarah_counts=None
    )
