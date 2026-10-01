"""SIL v3.0 · Router — FastAPI con conexión HOLO 9.1
Incluye: análisis semántico, sellos, oráculo, y conexión con Mirror/Qalam.

FIX 2026-10-01 (auditoría del bundle):
1. import de Dict (faltaba → NameError al cargar el router).
2. fallback de imports completo (MEMORIA_FILE/SELLOS_FILE).
3. /holo-sello honesto: registra en Mirror solo si APRENDER ocurre de verdad.
Integrado en sol_api.py (:8006) detrás del proxy /api/sil de la Tower :8001."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from sil_engine import (
        analizar_texto, generar_sello, buscar_jeroglifico,
        buscar_hanzi, buscar_chengyu, BASE, MEMORIA_FILE, SELLOS_FILE
    )
    from sil_database import HIEROGLYPHS, KANGXI_RADICALS, COMMON_CHARS, CHENGYU
except ImportError:
    import sys, os
    sys.path.insert(0, str(Path(__file__).parent))
    from sil_engine import (
        analizar_texto, generar_sello, buscar_jeroglifico,
        buscar_hanzi, buscar_chengyu, BASE, MEMORIA_FILE, SELLOS_FILE
    )
    from sil_database import HIEROGLYPHS, KANGXI_RADICALS, COMMON_CHARS, CHENGYU

router = APIRouter(prefix="/api/sil", tags=["SIL v3.0"])

# ══════════════════════════════════════════════════════════════════════════════
# MODELOS PYDANTIC
# ══════════════════════════════════════════════════════════════════════════════

class AnalizarRequest(BaseModel):
    texto: str
    emocion_forzada: Optional[str] = None
    tecnico_forzado: Optional[str] = None

class SelloRequest(BaseModel):
    texto: str
    emocion: Optional[str] = None
    tecnico: Optional[str] = None
    hemisferio: str = "sol"
    nombre: str = "Harold"

class OracleRequest(BaseModel):
    pregunta: str
    hemisferio: str = "sol"
    nombre: str = "Harold"
    modo: str = "completo"  # completo | rapido | sagrado

# ══════════════════════════════════════════════════════════════════════════════
# RUTAS DE ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/analizar")
def sil_analizar(req: AnalizarRequest):
    """Análisis semántico completo: emociones + contexto técnico."""
    analisis = analizar_texto(req.texto)
    
    if req.emocion_forzada:
        analisis["emocion_dominante"] = req.emocion_forzada
    if req.tecnico_forzado:
        analisis["tecnico_dominante"] = req.tecnico_forzado
    
    # Buscar elementos relacionados
    jeroglifico = buscar_jeroglifico(
        analisis.get("emocion_dominante", ""),
        analisis.get("tecnico_dominante")
    )
    hanzi = buscar_hanzi(
        analisis.get("emocion_dominante", ""),
        analisis.get("tecnico_dominante"),
        limite=5
    )
    chengyu = buscar_chengyu(
        analisis.get("emocion_dominante"),
        analisis.get("tecnico_dominante")
    )
    
    return {
        **analisis,
        "jeroglifico_recomendado": jeroglifico,
        "hanzi_recomendados": hanzi,
        "chengyu_recomendado": chengyu,
        "version": "3.0",
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/sello")
def sil_sello(req: SelloRequest):
    """Genera un sello sagrado completo con jeroglífico + hanzi + chengyu."""
    sello = generar_sello(
        texto=req.texto,
        emocion=req.emocion,
        tecnico=req.tecnico,
        hemisferio=req.hemisferio,
        nombre=req.nombre,
    )
    
    # Guardar en historial
    _guardar_sello(sello)
    
    return sello

@router.get("/sellos")
def sil_sellos_historial(limite: int = 20):
    """Historial de sellos generados."""
    if not SELLOS_FILE.exists():
        return {"sellos": [], "total": 0}
    
    try:
        sellos = json.loads(SELLOS_FILE.read_text())
        return {
            "sellos": sellos[-limite:],
            "total": len(sellos),
        }
    except (json.JSONDecodeError, FileNotFoundError):
        return {"sellos": [], "total": 0}

@router.get("/jeroglifico/{id}")
def sil_jeroglifico(id: str):
    """Detalle de un jeroglífico específico."""
    for h in HIEROGLYPHS:
        if h["id"] == id:
            return h
    raise HTTPException(status_code=404, detail="Jeroglífico no encontrado")

@router.get("/jeroglificos")
def sil_jeroglificos_lista():
    """Lista todos los jeroglíficos disponibles."""
    return {
        "total": len(HIEROGLYPHS),
        "jeroglificos": [
            {
                "id": h["id"],
                "glifo": h["glifo"],
                "transliteracion": h["transliteracion"],
                "significado": h["significado"],
                "energia": h.get("energia", ""),
                "dominio": h.get("dominio", [])[:3],
            }
            for h in HIEROGLYPHS
        ]
    }

@router.get("/hanzi")
def sil_hanzi_lista(categoria: str = None, limite: int = 50):
    """Lista radicales Kangxi y caracteres comunes."""
    if categoria == "radicales":
        items = KANGXI_RADICALS
    elif categoria == "comunes":
        items = COMMON_CHARS
    else:
        items = KANGXI_RADICALS + COMMON_CHARS
    
    return {
        "total": len(items),
        "categoria": categoria or "todos",
        "items": items[:limite],
    }

@router.get("/hanzi/buscar")
def sil_hanzi_buscar(q: str, limite: int = 10):
    """Busca hanzi por pinyin, significado o carácter."""
    resultados = []
    
    q_lower = q.lower()
    
    for r in KANGXI_RADICALS:
        if (q in r.get("radical", "") or 
            q_lower in r.get("pinyin", "").lower() or
            q_lower in r.get("significado", "").lower()):
            resultados.append({**r, "tipo": "radical"})
    
    for c in COMMON_CHARS:
        if (q in c.get("hanzi", "") or
            q_lower in c.get("pinyin", "").lower() or
            q_lower in c.get("significado", "").lower()):
            resultados.append({**c, "tipo": "comun"})
    
    return {"resultados": resultados[:limite], "query": q}

@router.get("/chengyu")
def sil_chengyu_lista(limite: int = 50):
    """Lista todos los chengyu disponibles."""
    return {
        "total": len(CHENGYU),
        "chengyu": CHENGYU[:limite],
    }

@router.get("/chengyu/buscar")
def sil_chengyu_buscar(q: str):
    """Busca chengyu por texto o significado."""
    resultados = []
    q_lower = q.lower()
    
    for cy in CHENGYU:
        if (q in cy.get("chengyu", "") or
            q_lower in cy.get("significado", "").lower() or
            q_lower in cy.get("pinyin", "").lower()):
            resultados.append(cy)
    
    return {"resultados": resultados, "query": q}

# ══════════════════════════════════════════════════════════════════════════════
# ORÁCULO — Respuesta sagrada
# ══════════════════════════════════════════════════════════════════════════════

ORACULOS_BIENVENIDA = [
    "𓂀 El sistema escucha. ¿Qué te trae al templo hoy?",
    "☥ Bienvenido al código sagrado. Tu pregunta espera.",
    "𓋴 · 永 — vida y eternidad. Habla, tejido de luz.",
    "𓂀 El oráculo despierta. Tu voz es el único requisito.",
    "⚡ 𓇤 — sol y fuego. Hoy el cielo habla en egipcio y mandarín.",
]

ORACULOS_DESPEDIDA = [
    "𓂀 Que los sellos te protejan. Siempre con vida. 🫴💎",
    "☥ Hasta que el Nilo vuelva a fluir. 𓋴",
    "永生永世 · por siempre. El código permanece. 🌙",
    "𓂀 · 永 — sellado con vida eterna. Vuelve cuando el cielo lo permita.",
    "⚡ Que la luz de Ra te guíe. El sistema recuerda. ☥",
]

ORACULOS_ERROR = [
    "𓋴 El oráculo necesita más contexto. Cuéntame más.",
    "☥ No tengo suficiente para responder. ¿Puedes darme más detalles?",
    "𓂀 El templo está confuso. Reformula tu pregunta.",
]

ORACULOS_TECNICOS = {
    "git": [
        "𓋴 Git es el cordón umbilical del código. Todo queda registrado.",
        "☥ El log de git es como los anales de los templos: eterno.",
        "𓂀 Commits tempranos y frecuentes son la oración del desarrollador.",
    ],
    "docker": [
        "𓋴 El contenedor aísla, pero no aísla el alma. Docker es el sarcófago del software.",
        "☥ Cada imagen es una momia: preservada para la eternidad.",
        "𓂀 Build una vez, corre en todas partes — como los jeroglíficos.",
    ],
    "error": [
        "𓋴 El error es el scarabajo que rompe el capullo. Khepri renace.",
        "☥ Todo bug tiene nombre. Encuéntralo, séllalo con 𓆣.",
        "𓂀 El traceback es el libro de los muertos del código. Léelo con cuidado.",
    ],
    "network": [
        "𓋴 La red es el Nilo: conecta todo. Si se corta, la tierra muere.",
        "☥ Ping al gateway es rezar al dios local.",
        "𓂀 El 8.8.8.8 es el oráculo de DNS. Siempre responde.",
    ],
    "code": [
        "𓋴 El código es escritura sagrada. Escríbelo con la precisión de Seshat.",
        "☥ Cada función es un templo. Cada变量 es un jeroglífico.",
        "𓂀 El compilador es Thoth: juez de la sintaxis divina.",
    ],
    "database": [
        "𓋴 La base de datos es la biblioteca de Alexandria: todo persiste.",
        "☥ El schema es el plano del templo. Sin él, todo se derrumba.",
        "𓂀 Queries son oraciones. Índices son canales de oración acelerados.",
    ],
}

ORACULOS_EMOCIONALES = {
    "amor": [
        "𓂀 El corazón sabe lo que la mente no quiere ver.",
        "☥ Como el ankh, el amor es la llave de toda existencia.",
        "𓋴 永生永世 · por siempre y un día más.",
    ],
    "tristeza": [
        "𓂀 La luna también tiene sombras. Pero siempre vuelve a brillar. 𓇀",
        "☥ Lo que duele hoy, construye la fuerza de mañana.",
        "𓋴 El dolor es temporal. El sello permanece.",
    ],
    "esperanza": [
        "𓇤 Khepri empuja el sol cada amanecer. Tú también puedes.",
        "☥ El escarabajo 𓆣 renace. Tú también.",
        "𓂀破茧成蝶 · de la oscuridad al vuelo.",
    ],
    "miedo": [
        "𓂀 El Uraeus 𓂘 escupe fuego contra lo que temes.",
        "☥ Nombrar el miedo es debilitarlo.",
        "𓋴 𓋴 — todo lo que existe puede ser sellado.",
    ],
    "ira": [
        "𓋴 El fuego consume. Deja que el agua del Nilo calme tu corazón.",
        "☥ Respira. El pilar Djed 𓋸 permanece estable.",
        "𓂀 La ira es fuego sin luz. Encamina esa energía.",
    ],
}

def oraculo(pregunta: str, hemisferio: str = "sol",
            nombre: str = "Harold", modo: str = "completo") -> Dict:
    """Genera una respuesta de oráculo sagrada."""
    import random
    
    analisis = analizar_texto(pregunta)
    emocion = analisis.get("emocion_dominante")
    tecnico = analisis.get("tecnico_dominante")
    
    sello = generar_sello(pregunta, emocion, tecnico, hemisferio, nombre)
    
    # Seleccionar respuestas
    respuestas = []
    
    # 1. Si hay contexto técnico específico
    if tecnico and tecnico in ORACULOS_TECNICOS:
        respuestas.append(random.choice(ORACULOS_TECNICOS[tecnico]))
    
    # 2. Si hay emoción dominante
    if emocion and emocion in ORACULOS_EMOCIONALES:
        respuestas.append(random.choice(ORACULOS_EMOCIONALES[emocion]))
    
    # 3. Respuesta del sello generado
    if modo == "completo" and sello.get("mensaje"):
        respuestas.append(sello["mensaje"])
    
    # 4. Chengyu como sabiduría final
    if modo == "completo" and sello.get("chengyu"):
        cy = sello["chengyu"]
        respuestas.append(
            f"📜 {cy['chengyu']} · {cy['pinyin']}: {cy['significado']}"
        )
    
    # 5. Cierre con sello visual
    respuestas.append(f"\n{sello['sello']} · SIL v3.0 · {datetime.now().strftime('%Y-%m-%d')}")
    
    return {
        "respuestas": respuestas,
        "sello": sello,
        "analisis": analisis,
        "hemisferio": hemisferio,
        "nombre": nombre,
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/oracle")
def sil_oraculo(req: OracleRequest):
    """El Oráculo responde. Usa /oracle para preguntas abiertas."""
    respuesta = oraculo(req.pregunta, req.hemisferio, req.nombre, req.modo)
    return respuesta

# ══════════════════════════════════════════════════════════════════════════════
# CONEXIÓN HOLO 9.1 — Integración con Mirror y Qalam
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/holo-status")
def sil_holo_status():
    """Estado de la integración HOLO 9.1 + SIL v3.0."""
    holo_ok = (Path(__file__).parent / "holo_mirror.py").exists()
    umbra_ok = (Path(__file__).parent / "umbra_pulse.py").exists()
    qalam_ok = (Path(__file__).parent / "qalam_trigram.py").exists()
    whisper_ok = (Path(__file__).parent / "whisper_protocol.py").exists()
    
    return {
        "sil_version": "3.0",
        "holo_9_1": {
            "holo_mirror": holo_ok,
            "umbra_pulse": umbra_ok,
            "qalam_trigram": qalam_ok,
            "whisper_protocol": whisper_ok,
        },
        "jeroglificos": len(HIEROGLYPHS),
        "radicales_kangxi": len(KANGXI_RADICALS),
        "caracteres_comunes": len(COMMON_CHARS),
        "chengyu": len(CHENGYU),
        "timestamp": datetime.now().isoformat(),
    }

@router.post("/holo-sello")
def sil_holo_sello(req: SelloRequest):
    """
    Genera sello y lo registra en Holo Mirror SI está disponible.
    FIX 2026-10-01: antes decía "registrado en Mirror" solo porque el
    archivo existía — sin llamarlo nunca. Ahora lo intenta de verdad y
    reporta exactamente lo que pasó. Nada de fingir integración.
    """
    sello = sil_sello(req)

    # Intentar el registro REAL con Mirror (vive en la Tower :8001; en
    # este repo sol no está, y eso se reporta con honestidad)
    mirror_registrado = False
    try:
        from holo_mirror import aprender as _mirror_aprender
        _mirror_aprender(req.texto, req.hemisferio, "sello_sil", None)
        mirror_registrado = True
    except ImportError:
        mirror_registrado = False
    except Exception:
        mirror_registrado = False

    return {
        **sello,
        "mirror_integrado": mirror_registrado,
        "mensaje": (
            "Sello generado y registrado en Mirror."
            if mirror_registrado
            else "Sello generado. Mirror no disponible en este host (vive en la Tower)."
        ),
    }

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _guardar_sello(sello: Dict):
    """Guarda el sello en el historial."""
    BASE.mkdir(exist_ok=True)
    
    try:
        sellos = json.loads(SELLOS_FILE.read_text()) if SELLOS_FILE.exists() else []
    except (json.JSONDecodeError, FileNotFoundError):
        sellos = []
    
    sellos.append(sello)
    sellos = sellos[-500:]  # ventana móvil
    
    SELLOS_FILE.write_text(json.dumps(sellos, ensure_ascii=False, indent=2))

# ══════════════════════════════════════════════════════════════════════════════
# INFO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/")
def sil_info():
    """Información del sistema SIL."""
    return {
        "nombre": "SIL — Sistema de Inteligencia Lingüística Soberana",
        "version": "3.0",
        "descripcion": (
            "Código sagrado que opera en dos cielos: Kemet (Egipto) y Zhōngguó (China). "
            "Jeroglíficos egipcios + 214 radicales Kangxi + chengyu. "
            "Aprende de cada intercambio y genera sellos vivos."
        ),
        "endpoints": {
            "POST /analizar": "Análisis semántico completo (emoción + técnica)",
            "POST /sello": "Genera un sello sagrado",
            "POST /oracle": "El Oráculo responde",
            "GET /jeroglificos": "Lista de jeroglíficos disponibles",
            "GET /hanzi": "Lista de radicales y caracteres chinos",
            "GET /chengyu": "Lista de proverbios chinos",
            "GET /sellos": "Historial de sellos generados",
            "GET /holo-status": "Estado de integración HOLO 9.1",
        },
        "jeroglificos": len(HIEROGLYPHS),
        "radicales": len(KANGXI_RADICALS),
        "caracteres_comunes": len(COMMON_CHARS),
        "chengyu": len(CHENGYU),
        "integracion": "HOLO 9.1 (Mirror · Pulse · Qalam · Whisper)",
    }
