"""HOLO 9.1 · Umbra Pulse — Monitor de Red con Consciencia Adaptativa
El 9.0 medía UN gateway con umbrales FIJOS. El 9.1 mide varios gateways
en paralelo, aprende el comportamiento normal de tu red, y calcula
anomalías estadísticas (no solo latencia — también jitter y pérdida).

FIX 2026-10-01 (auditoría del bundle):
1. "VERDE sin mediciones": el bundle nacía en nivel VERDE con score 1.0
   ANTES de medir nada (estado inicial y fallback de /estado). Ahora el
   nivel sin datos es "SIN_DATOS" con score 0.0 — el verde hay que
   ganárselo midiendo.
2. "Destinos predeterminados": el bundle hacía ping a 192.168.1.1,
   8.8.8.8 y 1.1.1.1 sin permiso (y los escribía a disco en el primer
   arranque). Ahora NO hay gateways por defecto: NINGÚN ping sale hasta
   que tú agregues gateways explícitamente (POST /api/umbra-pulse/gateways).
3. KeyError latente: gateways agregados en runtime mataban el hilo
   (self.historial[host] no existía). Ahora historial con setdefault.
4. EMA compartido: calcular_score guardaba el EMA en un atributo de la
   FUNCIÓN (todos los gateways compartían el mismo EMA). Ahora EMA
   por-gateway.
5. Contrato de despliegue: sin bloque __main__ en puerto 8003 — este
   router se integra al dashboard :8001.
"""

import json, re, subprocess, time, threading, statistics
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque
from fastapi import APIRouter

BASE = Path(__file__).parent / "data"
GATEWAYS_FILE = BASE / "gateways.json"
PULSE_FILE = BASE / "umbra_pulse.json"
COLA_FILE = BASE / "cola_sync.jsonl"       # compatible con 9.0
ANOMALY_FILE = BASE / "anomalias.jsonl"
HISTORY_FILE = BASE / "latido_history.jsonl"

router = APIRouter(prefix="/api/umbra-pulse", tags=["HOLO 9.1"])

# ─── Configuración de gateways ──────────────────────────────────────────────
# FIX: SIN destinos predeterminados. Ningún ping externo sin tu permiso
# explícito (POST /gateways). El 9.0 usaba 192.168.1.1/8.8.8.8/1.1.1.1 fijos.

def cargar_gateways():
    if GATEWAYS_FILE.exists():
        try:
            gws = json.loads(GATEWAYS_FILE.read_text())
            if isinstance(gws, list):
                return gws
        except (json.JSONDecodeError, ValueError):
            pass
    return []   # FIX: vacío — nada se escribe a disco, nada se hace ping

def guardar_gateways(gws):
    BASE.mkdir(exist_ok=True, parents=True)
    GATEWAYS_FILE.write_text(json.dumps(gws, ensure_ascii=False, indent=2))

# ─── Medición individual ─────────────────────────────────────────────────────

def ping_gateway(host, count=1, timeout=2):
    """Devuelve (latencia_ms, perdida_pct)"""
    try:
        out = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            capture_output=True, text=True, timeout=timeout + 1
        )
        latencias = re.findall(r"time[=<]([\d.]+)", out.stdout)
        if latencias:
            return float(latencias[-1]), 0.0
        # Fallo: no hubo respuesta
        if "100% packet loss" in out.stdout or out.returncode != 0:
            return None, 100.0
        return None, 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None, 100.0

# ─── EMA adaptativo con desviación estándar (POR GATEWAY) ──────────────────

_emas = {}  # host → EMA (FIX: antes un único EMA compartido en atributo de función)

def calcular_score(latencias_recientes, gateway_nombre=None):
    """
    Score 0.0–1.0 con anomalía estadística.
    - media móvil exponencial (EMA) como base, POR gateway
    - penalización por desviación estándar > umbral
    - penalización por tendencia creciente
    """
    if not latencias_recientes or all(l is None for l in latencias_recientes):
        return 0.0

    validas = [l for l in latencias_recientes[-15:] if l is not None]
    if not validas:
        return 0.0

    media = statistics.mean(validas)
    # Penalización por inestabilidad (jitter)
    if len(validas) >= 5:
        stdev = statistics.stdev(validas)
        jitter_penalty = min(0.25, stdev / 500)  # >200ms stdev = penalización max
    else:
        jitter_penalty = 0.0

    # Penalización por tendencia (últimos 4 vs los 4 anteriores)
    if len(validas) >= 8:
        reciente = statistics.mean(validas[-4:])
        anterior = statistics.mean(validas[-8:-4])
        tendencia = (reciente - anterior) / max(anterior, 1)
        tendencia_penalty = max(0.0, min(0.2, tendencia))
    else:
        tendencia_penalty = 0.0

    # Calidad base: normalizada contra 800ms (umbral de agonía)
    calidad = max(0.0, 1.0 - media / 800)

    ema_prev = _emas.get(gateway_nombre, 1.0)
    ema = 0.7 * ema_prev + 0.3 * calidad
    _emas[gateway_nombre] = ema
    score = round(ema - jitter_penalty - tendencia_penalty, 3)
    return max(0.0, min(1.0, score))

# ─── Historial y detección de anomalías ─────────────────────────────────────

def es_anomalia(gw_host, latencia_actual, historial_minutos=60):
    """Detecta si la latencia actual es estadísticamente anómala (>2 stdev)."""
    try:
        with open(HISTORY_FILE, "a+") as f:
            f.seek(0)
            lineas = f.readlines()
    except (FileNotFoundError, OSError):
        return False

    recientes = []
    cutoff = datetime.now() - timedelta(minutes=historial_minutos)
    for linea in reversed(lineas[-200:]):
        try:
            reg = json.loads(linea)
            if reg.get("host") != gw_host:
                continue
            ts = datetime.fromisoformat(reg["ts"])
            if ts > cutoff and reg["latencia"] is not None:
                recientes.append(reg["latencia"])
        except (json.JSONDecodeError, ValueError, KeyError):
            continue

    if len(recientes) < 10:
        return False

    media_h = statistics.mean(recientes)
    stdev_h = statistics.stdev(recientes)
    threshold = media_h + 2 * stdev_h
    return latencia_actual is not None and latencia_actual > threshold

# ─── Cola store-and-forward mejorada ────────────────────────────────────────

def encolar(tool, payload, prioridad=1):
    """Prioridad: 1=normal, 2=urgente (se envía primero al recovery)."""
    BASE.mkdir(exist_ok=True, parents=True)
    with open(COLA_FILE, "a") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "tool": tool,
            "prioridad": prioridad,
            "payload": payload,
        }, ensure_ascii=False) + "\n")

def drenar():
    """Burst-sync: devuelve (count, items) ordenados por prioridad."""
    if not COLA_FILE.exists():
        return 0, []
    items = []
    for linea in COLA_FILE.read_text().strip().splitlines():
        try:
            items.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    items.sort(key=lambda x: -x.get("prioridad", 1))
    COLA_FILE.unlink(missing_ok=True)
    return len(items), items

# ─── Hilo de watchdog ────────────────────────────────────────────────────────

class PulseWatchdog:
    def __init__(self):
        self._running = True
        # FIX: sin mediciones NO hay VERDE — se parte en SIN_DATOS
        self.estado = {
            "nivel_umbra": "SIN_DATOS",
            "score": 0.0,
            "version": "9.1",
            "gateways": {},
            "gateways_configurados": 0,
            "ultima_revision": None,
        }
        self.historial = {}   # host → deque — FIX: setdefault en tick, sin KeyError
        self.nivel_anterior = "SIN_DATOS"

    def tick(self):
        ahora = datetime.now()
        gateways = cargar_gateways()

        # FIX: sin gateways configurados NO se hace ping a nadie y NO se
        # inventa un nivel: el estado honesto es SIN_DATOS.
        if not gateways:
            self.estado = {
                "nivel_umbra": "SIN_DATOS",
                "score": 0.0,
                "version": "9.1",
                "gateways": {},
                "gateways_configurados": 0,
                "nota": "sin gateways configurados — POST /api/umbra-pulse/gateways para empezar a medir",
                "ts": ahora.isoformat(),
            }
            return self.estado

        resultado_gws = {}
        latencias_ponderadas = []

        for gw in gateways:
            host = gw["host"]
            lat, perdida = ping_gateway(host)
            # FIX: gateway nuevo en runtime → setdefault (antes: KeyError)
            hist = self.historial.setdefault(host, deque(maxlen=30))
            hist.append(lat)
            resultado_gws[host] = {
                "nombre": gw.get("nombre", host),
                "latencia": lat,
                "perdida": perdida,
                "score_gw": calcular_score(list(hist), gateway_nombre=host),
                "es_anomalia": es_anomalia(host, lat),
            }
            if lat is not None:
                latencias_ponderadas.append((lat, gw.get("peso", 1)))

        # Score global: promedio de scores individuales
        scores_gw = [r["score_gw"] for r in resultado_gws.values()]
        score_global = statistics.mean(scores_gw) if scores_gw else 0.0

        # Detectar anomalías y loguearlas
        for host, datos in resultado_gws.items():
            if datos["es_anomalia"]:
                self._registrar_anomalia(host, datos)

        # Nivel basado en score + anomalías
        num_anomalias = sum(1 for d in resultado_gws.values() if d["es_anomalia"])
        if num_anomalias >= 2 or score_global < 0.2:
            nivel = "ROJO"
        elif num_anomalias >= 1 or score_global < 0.55:
            nivel = "AMBAR"
        else:
            nivel = "VERDE"   # ganado con mediciones reales

        # Transición de estado
        if nivel != self.nivel_anterior:
            self._transicion(nivel, score_global, resultado_gws)
            self.nivel_anterior = nivel

        self.estado = {
            "nivel_umbra": nivel,
            "score": round(score_global, 3),
            "version": "9.1",
            "nivel_anterior": self.nivel_anterior,
            "gateways": resultado_gws,
            "gateways_configurados": len(gateways),
            "anomalias_activas": num_anomalias,
            "ts": ahora.isoformat(),
        }

        # Persistir
        BASE.mkdir(exist_ok=True, parents=True)
        PULSE_FILE.write_text(json.dumps(self.estado, ensure_ascii=False, indent=2))

        # Guardar historial para análisis
        for host, datos in resultado_gws.items():
            if datos["latencia"] is not None:
                with open(HISTORY_FILE, "a") as f:
                    f.write(json.dumps({
                        "ts": ahora.isoformat(), "host": host,
                        "latencia": datos["latencia"],
                        "score_gw": datos["score_gw"],
                    }, ensure_ascii=False) + "\n")

        return self.estado

    def _transicion(self, nuevo_nivel, score, gateways):
        """Se llama solo en transiciones VERDE→AMBAR→ROJO o viceversa."""
        if nuevo_nivel == "ROJO":
            encolar("umbra_pulse_offline", {"score": score, "gateways": gateways}, prioridad=2)
        elif nuevo_nivel == "VERDE" and self.nivel_anterior in ("AMBAR", "ROJO"):
            n, items = drenar()
            encolar("umbra_recovery_sync", {"items_recuperados": n, "items": items}, prioridad=2)

    def _registrar_anomalia(self, host, datos):
        BASE.mkdir(exist_ok=True, parents=True)
        with open(ANOMALY_FILE, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "host": host,
                "latencia": datos["latencia"],
                "score_gw": datos["score_gw"],
            }, ensure_ascii=False) + "\n")

    def iniciar(self):
        while self._running:
            try:
                self.tick()
            except Exception:
                pass  # No queremos que muera el watchdog
            time.sleep(20)  # 20s entre ticks

    def detener(self):
        self._running = False


# Instancia singleton del watchdog
_watchdog = None

def obtener_watchdog():
    global _watchdog
    if _watchdog is None:
        _watchdog = PulseWatchdog()
    return _watchdog

# ─── Rutas API ────────────────────────────────────────────────────────────────

@router.on_event("startup")
def startup():
    wd = obtener_watchdog()
    t = threading.Thread(target=wd.iniciar, daemon=True)
    t.start()

@router.get("/estado")
def estado():
    """Estado actual de Umbra Pulse. FIX: sin datos → SIN_DATOS, no VERDE."""
    if PULSE_FILE.exists():
        try:
            return json.loads(PULSE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {
        "nivel_umbra": "SIN_DATOS",
        "score": 0.0,
        "version": "9.1",
        "gateways_configurados": len(cargar_gateways()),
        "nota": "aún no hay mediciones — agrega gateways con POST /api/umbra-pulse/gateways",
    }

@router.get("/latido")
def latido():
    """Último latido + latidos totales. FIX: sin datos → SIN_DATOS, no VERDE."""
    try:
        lineas = HISTORY_FILE.read_text().strip().splitlines()
        if lineas:
            nivel = "VERDE"
            if PULSE_FILE.exists():
                try:
                    nivel = json.loads(PULSE_FILE.read_text()).get("nivel_umbra", "SIN_DATOS")
                except (json.JSONDecodeError, ValueError):
                    nivel = "SIN_DATOS"
            return {
                **json.loads(lineas[-1]),
                "latidos_total": len(lineas),
                "nivel_umbra": nivel,
            }
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"nivel_umbra": "SIN_DATOS", "score": 0.0, "latidos_total": 0}

@router.get("/gateways")
def listar_gateways():
    gws = cargar_gateways()
    return {"gateways": gws, "total": len(gws)}

@router.post("/gateways")
def agregar_gateway(payload: dict):
    """Agrega o reemplaza un gateway EXPLÍCITAMENTE.
    Formato: {"host": "...", "nombre": "...", "peso": 1}"""
    gws = cargar_gateways()
    host = str(payload.get("host", "")).strip()
    if not host or "/" in host or len(host) > 253:
        return {"error": "host inválido o faltante"}, 400

    # Reemplazar o agregar
    existente = next((i for i, g in enumerate(gws) if g["host"] == host), None)
    nuevo = {"host": host, "nombre": payload.get("nombre", host), "peso": payload.get("peso", 1)}
    if existente is not None:
        gws[existente] = nuevo
    else:
        gws.append(nuevo)
    guardar_gateways(gws)
    return {"ok": True, "gateways": gws}

@router.delete("/gateways/{host}")
def eliminar_gateway(host: str):
    gws = cargar_gateways()
    gws = [g for g in gws if g["host"] != host]
    guardar_gateways(gws)
    return {"ok": True, "gateways": gws}

@router.get("/historial")
def historial(gw: str = None, min_: int = 60):
    """Historial de latencias. ?gw=192.168.1.1&min=120 para filtrar."""
    try:
        lineas = HISTORY_FILE.read_text().strip().splitlines()
    except (FileNotFoundError, OSError):
        return {"datos": []}

    cutoff = datetime.now() - timedelta(minutes=min_)
    datos = []
    for linea in lineas:
        try:
            reg = json.loads(linea)
            if gw and reg.get("host") != gw:
                continue
            ts = datetime.fromisoformat(reg["ts"])
            if ts > cutoff:
                datos.append(reg)
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    return {"datos": datos[-500:], "gw": gw, "min": min_}

@router.get("/anomalias")
def anomalias():
    """Anomalías recientes en el historial."""
    try:
        lineas = ANOMALY_FILE.read_text().strip().splitlines()
    except (FileNotFoundError, OSError):
        return {"anomalias": []}

    recientes = []
    cutoff = datetime.now() - timedelta(hours=1)
    for linea in reversed(lineas[-50:]):
        try:
            reg = json.loads(linea)
            if datetime.fromisoformat(reg["ts"]) > cutoff:
                recientes.append(reg)
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    return {"anomalias": recientes}

@router.post("/cola/recovery")
def recovery():
    """Fuerza el drenado de la cola de sync."""
    n, items = drenar()
    return {"recuperados": n, "items_preview": items[:10]}

@router.post("/test-gateway")
def test_gateway(payload: dict):
    """Prueba un gateway específico sin agregarlo.
    FIX: sin destino predeterminado — el host es OBLIGATORIO."""
    host = str(payload.get("host", "")).strip()
    if not host:
        return {"error": "host requerido (nada de destinos predeterminados)"}, 400
    lat, perdida = ping_gateway(host, count=3)
    return {"host": host, "latencia": lat, "perdida_pct": perdida}
