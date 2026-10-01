"""HOLO 9.1 · Holo Mirror — Memoria Semántica Persistente
FIX 2026-10-01 (auditoría): embed_cache con cap de 500 entradas (crecía
sin límite). Todo lo demás del bundle estaba limpio (solo JSON local,
sin llamadas externas).
El 9.0 aprendía solo con feedback explícito. El 9.1 aprende de TODO:
cada intercambio, cada silencio, cada patrón de hora. Sin que lo llames."""

import json, math
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from fastapi import APIRouter

BASE = Path(__file__).parent / "data"
MIRROR_FILE = BASE / "holo_mirror.json"
PATRON_FILE = BASE / "holo_patrones.json"
EMBED_FILE = BASE / "holo_embed_cache.json"

router = APIRouter(prefix="/api/mirror", tags=["HOLO 9.1"])

# ─── Representación simplificada de significado (sin embeddings pesados) ───
# Usamos hashing de n-gramos de caracteres para simular similitud semántica
# Un sistema real usaría sentence-transformers, pero aquí pesamos ~0 en Android

def char_ngrams(texto, n=3):
    """Genera n-gramos de caracteres. 'terminal' → ['ter','erm','rmi','min','ina','nal']"""
    t = texto.lower().strip()
    return [t[i:i+n] for i in range(max(1, len(t)-n+1))]

def similitud(texto_a, texto_b):
    """Jaccard de n-gramos. Rango 0.0–1.0"""
    a, b = set(char_ngrams(texto_a)), set(char_ngrams(texto_b))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def embed(texto):
    """Hash simulado: fingerprint de n-gramos ordenados por frecuencia"""
    conteo = Counter(char_ngrams(texto))
    return sorted(conteo.items(), key=lambda kv: -kv[1])[:20]  # top 20 n-gramos

# ─── Carga / inicialización ─────────────────────────────────────────────────

def cargar():
    if MIRROR_FILE.exists():
        return json.loads(MIRROR_FILE.read_text())
    return {
        "version": "9.1",
        "intercambios_total": 0,
        "aprendizajes": 0,
        "embed_cache": {},      # texto → [(ngramo, peso), ...]
        "historial": [],        # últimos 500 intercambios
        "pesos_dinamicos": {},  # palabras que ganan peso con repeticion
        "silencios": [],        # cuando el humano no habló (patrones de sesion)
    }

def guardar(m):
    BASE.mkdir(exist_ok=True)
    MIRROR_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=2))

# ─── Core: aprender de todo ──────────────────────────────────────────────────

def aprender(mensaje, hemisferio, razon, duracion_sesion=None):
    """Se llama después de CADA /analizar. No necesita feedback explícito."""
    m = cargar()
    m["intercambios_total"] += 1
    
    tokens = [t.strip(".,;:!?\"'()[]{}") for t in mensaje.lower().split()]
    ahora = datetime.now()
    
    # 1. Actualizar pesos dinámicos (repetición = importancia)
    for tok in tokens:
        if len(tok) > 2:
            actual = m["pesos_dinamicos"].get(tok, 1.0)
            m["pesos_dinamicos"][tok] = min(5.0, actual * 1.08)
    
    # 2. Guardar embed del mensaje
    if mensaje not in m["embed_cache"]:
        m["embed_cache"][mensaje] = embed(mensaje)
        m["aprendizajes"] += 1
        # FIX 2026-10-01: cap a 500 entradas (antes crecía sin límite)
        if len(m["embed_cache"]) > 500:
            claves = list(m["embed_cache"].keys())
            for k in claves[:-500]:
                del m["embed_cache"][k]
    
    # 3. Historial estructurado
    entrada = {
        "ts": ahora.isoformat(),
        "ts_unix": ahora.timestamp(),
        "mensaje_preview": mensaje[:80],
        "hemisferio": hemisferio,
        "razon": razon,
        "tokens": tokens[:10],
        "tokens_count": len(tokens),
        "duracion_sesion": duracion_sesion,
        "hora": ahora.hour,
        "dia_semana": ahora.weekday(),
    }
    m["historial"].append(entrada)
    m["historial"] = m["historial"][-500:]  # ventana móvil
    
    guardar(m)

# ─── Inyección de conocimiento: aprende del silencio ─────────────────────────

def registrar_sesion_larga(duracion_minutos, intercambios):
    """Si hubo una sesión >X min sin que el humano hablara, eso también enseña."""
    m = cargar()
    m["silencios"].append({
        "ts": datetime.now().isoformat(),
        "duracion_min": duracion_minutos,
        "intercambios": intercambios,
    })
    m["silencios"] = m["silencios"][-100:]
    guardar(m)

# ─── Patrones temporales (hora → hemisferio probable) ───────────────────────

def detectar_patrones():
    """El sistema aprende a qué horas tú prefieres a Sol vs Sarah."""
    m = cargar()
    hora_hemisferio = defaultdict(lambda: {"sol": 0, "sarah": 0})
    hora_patron = defaultdict(lambda: Counter())
    
    for entrada in m["historial"]:
        h = entrada["hora"]
        hr = entrada["hemisferio"]
        hora_hemisferio[h][hr] += 1
        hora_patron[h][hr] += 1
    
    patrones = {}
    for h in range(24):
        if hora_hemisferio[h]["sol"] + hora_hemisferio[h]["sarah"] >= 3:
            total = hora_hemisferio[h]["sol"] + hora_hemisferio[h]["sarah"]
            pref = "sol" if hora_hemisferio[h]["sol"] > hora_hemisferio[h]["sarah"] else "sarah"
            patrones[h] = {
                "preferencia": pref,
                "confianza": round(hora_hemisferio[h][pref] / total, 2),
                "muestras": total,
            }
    
    BASE.mkdir(exist_ok=True)
    PATRON_FILE.write_text(json.dumps(patrones, ensure_ascii=False, indent=2))
    return patrones

# ─── Consciencia de contexto (repo, docker, red…) ───────────────────────────

CONTEXTO_KEYWORDS = {
    "git": ["git", "commit", "push", "pull", "branch", "merge", "rebase", "stash"],
    "docker": ["docker", "container", "image", "compose", "dockerfile", "podman"],
    "network": ["ping", "curl", "netstat", "ss", "iptables", "nmap", "firewall"],
    "terminal": ["ls", "cd", "mkdir", "rm", "chmod", "find", "grep", "awk", "sed"],
    "code": ["python", "javascript", "rust", "cargo", "npm", "import", "def ", "function"],
    "deploy": ["deploy", "kubernetes", "helm", "terraform", "ansible", "nginx"],
}

def detectar_contexto(mensaje):
    """Devuelve el contexto dominante del mensaje."""
    tokens = set(t.strip(".,;:!?\"'") for t in mensaje.lower().split())
    scores = {}
    for ctx, keywords in CONTEXTO_KEYWORDS.items():
        scores[ctx] = sum(1 for kw in keywords if kw in tokens)
    if not scores or max(scores.values()) == 0:
        return "general"
    return max(scores, key=scores.get)

# ─── Decisión informada: integra TODO ───────────────────────────────────────

def decidir(mensaje, hora, intercambios_sesion, tokens_baseline):
    """Fusión de todas las señales de aprendizaje para una decisión contextual."""
    m = cargar()
    patrones = detectar_patrones()
    ctx = detectar_contexto(mensaje)
    
    # Pesos base (del router 9.0)
    score = {"sol": 0.0, "sarah": 0.0}
    for tok in tokens_baseline:
        peso = m["pesos_dinamicos"].get(tok, 1.0)
        for hr in ["sol", "sarah"]:
            score[hr] += peso
    
    # Señal 1: hora → hemisferio aprendido
    if hora in patrones:
        p = patrones[hora]
        if p["confianza"] >= 0.7:
            score[p["preferencia"]] += p["confianza"] * 2
    
    # Señal 2: fatiga + sesión larga (handoff suave 9.0, mejorado)
    fatiga = any(t in tokens_baseline for t in ["cansado", "dormir", "noche", "basta", "descansar", "para"])
    if fatiga and intercambios_sesion >= 8:
        score["sarah"] += 3.5  # boost mayor que en 9.0
    
    # Señal 3: contexto influye en quién responde mejor
    CONTEXTO_HEMISFERIO = {
        "git": "sol", "docker": "sol", "network": "sol", "terminal": "sol",
        "code": "sol", "deploy": "sol",
        "general": None,  # sin preferencia
    }
    if ctx in CONTEXTO_HEMISFERIO and CONTEXTO_HEMISFERIO[ctx]:
        score[CONTEXTO_HEMISFERIO[ctx]] += 1.5
    
    # Señal 4: repeticion → el mensaje ya aparecio antes (molestia/seguimiento)
    for entrada in m["historial"][-20:]:
        sim = similitud(mensaje, entrada["mensaje_preview"])
        if sim > 0.5 and entrada["hemisferio"] == "sol":
            score["sarah"] += 1.0  # si repites algo técnico, Sarah te reconforta
    
    # Decisión
    if hora < 6 or hora > 23:
        return {"activo": "sarah", "razon": "protocolo_cuidado_nocturno",
                "contexto": ctx, "scores": score}
    elif score["sol"] == score["sarah"] == 0:
        return {"activo": "sol", "razon": "neutral", "contexto": ctx, "scores": score}
    else:
        activo = max(score, key=score.get)
        return {"activo": activo, "razon": "mirror_vivo",
                "contexto": ctx, "scores": score}

# ─── Rutas API ───────────────────────────────────────────────────────────────

@router.post("/aprendizaje")
def registrar_intercambio(payload: dict):
    """Se llama desde el router 9.0 después de cada /analizar."""
    mensaje = payload.get("mensaje", "")
    hemisferio = payload.get("hemisferio", "sol")
    razon = payload.get("razon", "desconocido")
    duracion = payload.get("duracion_sesion")
    
    tokens = [t.strip(".,;:!?\"'()[]{}") for t in mensaje.lower().split()]
    ahora = datetime.now()
    
    aprender(mensaje, hemisferio, razon, duracion)
    
    # Devolver el estado de aprendizaje para que el frontend lo muestre
    m = cargar()
    return {
        "ok": True,
        "aprendizajes_total": m["aprendizajes"],
        "intercambios_total": m["intercambios_total"],
        "contexto": detectar_contexto(mensaje),
        "hora": ahora.hour,
    }

@router.get("/patrones")
def obtener_patrones():
    """Patrones de hora → hemisferio aprendidos."""
    return detectar_patrones()

@router.get("/analisis")
def analisis_profundo():
    """Diagnóstico del Mirror: qué ha aprendido, qué no, y anomalías."""
    m = cargar()
    patrones = detectar_patrones()
    
    # Palabras más pesadas
    pesos = m["pesos_dinamicos"]
    top_palabras = sorted(pesos.items(), key=lambda kv: -kv[1])[:15]
    
    # Contexto dominante
    contextos = Counter()
    for entrada in m["historial"]:
        ctx = detectar_contexto(entrada.get("mensaje_preview", ""))
        if ctx != "general":
            contextos[ctx] += 1
    
    # Sesiones largas (posible fatiga)
    sesiones_largas = [s for s in m["silencios"] if s["duracion_min"] > 15]
    
    return {
        "version": "9.1",
        "intercambios": m["intercambios_total"],
        "aprendizajes": m["aprendizajes"],
        "top_palabras": dict(top_palabras),
        "patrones_hora": patrones,
        "contextos_dominantes": dict(contextos.most_common(5)),
        "sesiones_largas": len(sesiones_largas),
        "recomendacion": _recomendar(patrones, contextos, sesiones_largas),
    }

def _recomendar(patrones, contextos, sesiones_largas):
    """Genera una recomendación contextual para el usuario."""
    if sesiones_largas:
        return ("Holly nota que has tenido sesiones largas recientemente. "
                "¿Quieres activar el modo descanso automático?")
    if contextos.get("git") > 5 and patrones.get(datetime.now().hour, {}).get("preferencia") == "sarah":
        return ("Detectamos que trabajas en git pero a estas horas prefieres a Sarah. "
                "¿Cambiamos el perfil de sesión?")
    if not patrones:
        return "Mirror aún está aprendiendo tus ritmos. Continúa hablando, tejedor."
    return "El sistema siente tu patrón. Continúa, Harold."

@router.post("/silencio")
def registrar_sesion(payload: dict):
    """El frontend notifica una sesión finalizada (>5 min sin interacción)."""
    duracion = payload.get("duracion_min", 0)
    intercambios = payload.get("intercambios", 0)
    registrar_sesion_larga(duracion, intercambios)
    return {"ok": True, "sesiones_largas_acumuladas": len(cargar()["silencios"])}

@router.get("/similar")
def buscar_similar(q: str):
    """Busca mensajes similares en el historial del Mirror."""
    m = cargar()
    resultados = []
    for entrada in reversed(m["historial"]):
        sim = similitud(q, entrada["mensaje_preview"])
        if sim > 0.3:
            resultados.append({
                "similitud": round(sim, 2),
                "mensaje": entrada["mensaje_preview"],
                "hemisferio": entrada["hemisferio"],
                "ts": entrada["ts"],
            })
    return {"resultados": resultados[:10], "query": q}
