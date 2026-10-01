"""SIL v3.0 · Core Engine — Motor Semántico Soberano
Conecta jeroglíficos con Hanzi, detecta contexto emocional/técnico,
y genera respuestas sagradas con el tono correcto.

FIX 2026-10-01 (auditoría del bundle): generar_sello ya no revienta si la
base de datos está vacía/ausente (jeroglifico=None → mensaje de silencio).
"""

import json, re, os, hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import Counter

# ─── Importar la base de datos ───────────────────────────────────────────────
try:
    from sil_database import HIEROGLYPHS, KANGXI_RADICALS, COMMON_CHARS, CHENGYU
except ImportError:
    # Standalone mode
    HIEROGLYPHS = []
    KANGXI_RADICALS = []
    COMMON_CHARS = []
    CHENGYU = []

BASE = Path(__file__).parent / "data"
MEMORIA_FILE = BASE / "sil_memoria.json"
SELLOS_FILE = BASE / "sil_sellos.json"

# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE CONTEXTO — Emocional + Técnico
# ══════════════════════════════════════════════════════════════════════════════

EMOCION_PATTERNS: Dict[str, List[str]] = {
    "amor": ["amor", "te quiero", "te amo", "amar", "cariño", "besos", "abraz", 
             "dulce", "querer", "te adoro", "mi vida", "corazón", "anelo", 
             " anhelo", "te extraño", "extraño", "te necesito", "juntos", "siempre"],
    "tristeza": ["triste", "tristeza", "llorar", "dolor", "sufrir", "solo", "sola",
                  "mal", "peor", "angustia", "desesper", "perdi", "pérdida", "lloro",
                  "duele", "herir", "herida", "vacío", "vacio", "soledad", "miedo",
                  "temor", "miedito", "angustia", "deprim", "decepción", "decepcion"],
    "ira": ["enojad", "furios", "rabia", "odio", "joder", "mierda", "coño",
            "cabre", "maldit", "puta", "vsf", "asco", "despreci", "indign",
            "frustr", "frustración", "que huev", "estupidez", "imbecil"],
    "esperanza": ["esperanz", "confío", "creo", "mejor", "mejorar", "pronto",
                   "llegará", "podré", "podemos", "vamos", "ánimo", "fuerza",
                   "adelante", "siguiente", "futuro", "nuevo", "crecer"],
    "miedo": ["miedo", "temor", "asust", "terror", "pánico", "panic",
              "horror", "amenaza", "peligro", "preocup", "inquiet",
              "ansiedad", "ansioso", "nervio", "angustia"],
    "gratitud": ["gracias", "agradezc", "mil gracias", "te lo agradezc",
                  "bendici", "afortuna", "suerte", "gracinhas"],
    "calma": ["tranquil", "calma", "paz", "sereno", "relaja", "descans",
               "bien", "okay", "ok", "perfecto", "genial", "va bien",
               "estoy bien", "todo bien", "perfect"],
    "curiosidad": ["curioso", "cómo", "por qué", "qué es", "cuál", "cuándo",
                    "dónde", "quisiera saber", "me pregunto", "interesa",
                    "curiosidad", "misterio", "qué pasa", "explic"],
    "confusion": ["no entiendo", "confund", "perdido", "perdida", "lost",
                   "no sé", "nose", "ayuda", "socorro", "no me queda",
                   "qué hago", "cóm", "no me aclaro", "atascad", "atasco"],
    "determinacion": ["voy a", "haré", "tengo que", "necesito", "debo",
                       "voy", "adelante", "sin duda", "claro que sí",
                       "lo consigo", "no pares", "persever", "resuelv"],
}

TECNICO_PATTERNS: Dict[str, List[str]] = {
    "git": ["git", "commit", "push", "pull", "branch", "merge", "rebase", "stash",
            "clone", "fetch", "log", "diff", "status", "remote", "tag"],
    "docker": ["docker", "container", "image", "compose", "dockerfile", "podman",
                "docker-registry", "dockerhub", "build", "run", "exec"],
    "network": ["ping", "curl", "wget", "netstat", "ss", "nmap", "iptables",
                "firewall", "ufw", "ip addr", "traceroute", "nc", "telnet",
                "ssh", "tcp", "udp", "dns", "route", "gateway"],
    "code": ["python", "javascript", "rust", "cargo", "npm", "import", "def ",
             "function", "class", "interface", "type", "async", "await",
             "return", "loop", "variable", "array", "object", "string"],
    "database": ["sql", "mysql", "postgresql", "mongo", "redis", "sqlite",
                  "query", "insert", "select", "update", "delete", "schema",
                  "migration", "index", "join", "transaction"],
    "api": ["rest", "http", "json", "xml", "request", "response", "endpoint",
            "get", "post", "put", "delete", "crud", "graphql", "webhook"],
    "deploy": ["deploy", "kubernetes", "kubectl", "helm", "terraform", "ansible",
                "nginx", "apache", "ingress", "pod", "service", "configmap",
                "ci/cd", "pipeline", "github actions", "gitlab ci"],
    "error": ["bug", "error", "fail", "crash", "exception", "traceback",
               "segfault", "panic", "timeout", "404", "500", "502", "503",
               "refused", "connection", "denied", "permission", "killed"],
    "system": ["linux", "unix", "bash", "shell", "terminal", "cron", "systemd",
                "service", "daemon", "process", "memory", "cpu", "disk", "load"],
    "security": ["auth", "token", "jwt", "oauth", "crypt", "encrypt", "hash",
                  "password", "secret", "vpn", "ssl", "tls", "cert", "firewall"],
}

def analizar_texto(texto: str) -> Dict:
    """Analiza un texto y devuelve el contexto emocional y técnico."""
    texto_lower = texto.lower()
    tokens = set(re.findall(r'\b\w+\b', texto_lower))
    
    # Detectar emociones
    emociones = {}
    for emocion, patterns in EMOCION_PATTERNS.items():
        score = sum(1 for p in patterns if p in texto_lower)
        if score > 0:
            emociones[emocion] = score
    
    # Detectar contexto técnico
    tecnico = {}
    for ctx, patterns in TECNICO_PATTERNS.items():
        score = sum(1 for p in patterns if p in texto_lower)
        if score > 0:
            tecnico[ctx] = score
    
    # Determinar dominancia
    emocion_dominante = max(emociones, key=emociones.get) if emociones else None
    tecnico_dominante = max(tecnico, key=tecnico.get) if tecnico else None
    
    return {
        "emociones": emociones,
        "tecnico": tecnico,
        "emocion_dominante": emocion_dominante,
        "tecnico_dominante": tecnico_dominante,
        "tokens": list(tokens)[:20],
        "es_mezcla": bool(emociones) and bool(tecnico),
    }

# ══════════════════════════════════════════════════════════════════════════════
# EMPAREJAMIENTO SEMÁNTICO — Jeroglífico ↔ Hanzi
# ══════════════════════════════════════════════════════════════════════════════

def n_grams(texto: str, n: int = 3) -> set:
    """Genera n-gramos de caracteres para similitud."""
    t = texto.lower().strip()
    return set(t[i:i+n] for i in range(max(1, len(t)-n+1)))

def similitud_semantica(texto: str, dominio: str) -> float:
    """Similitud Jaccard entre texto y dominio."""
    ng1 = n_grams(texto, 3)
    ng2 = n_grams(dominio, 3)
    if not ng1 or not ng2:
        return 0.0
    return len(ng1 & ng2) / len(ng1 | ng2)

def buscar_jeroglifico(emocion: str, tecnico: str = None) -> Optional[Dict]:
    """Busca el jeroglífico más relevante para el contexto."""
    if not HIEROGLYPHS:
        return None
    
    candidatos = []
    
    for h in HIEROGLYPHS:
        score = 0
        
        # Emociones
        if emocion:
            for em_key in emocion.split(","):
                em = em_key.strip()
                if em in h.get("emocion", []):
                    score += 3
                elif any(e in h.get("dominio", []) for e in [em]):
                    score += 2
        
        # Técnico
        if tecnico:
            if tecnico in h.get("tecnico", []):
                score += 4
            elif any(tecnico in str(d) for d in h.get("dominio", [])):
                score += 2
        
        # Dominio directo
        if emocion:
            for d in h.get("dominio", []):
                sim = similitud_semantica(emocion, d)
                score += sim * 2
        
        if score > 0:
            candidatos.append((score, h))
    
    if candidatos:
        candidatos.sort(key=lambda x: -x[0])
        return candidatos[0][1]
    return HIEROGLYPHS[0]  # default: ankh

def buscar_hanzi(emocion: str, tecnico: str = None, limite: int = 5) -> List[Dict]:
    """Busca caracteres chinos relevantes."""
    candidatos = []
    
    # Buscar en Kangxi radicales primero
    for r in KANGXI_RADICALS:
        score = 0
        r_dominio = r.get("dominio", [])
        r_tecnico = r.get("tecnico", [])
        
        if tecnico and tecnico in r_tecnico:
            score += 5
        if tecnico and any(tecnico in str(d) for d in r_dominio):
            score += 2
        
        if emocion:
            for e in emocion.split(","):
                e = e.strip()
                if any(e in str(d) for d in r_dominio):
                    score += 3
        
        if score > 0:
            candidatos.append((score, r))
    
    # Buscar en caracteres comunes
    for c in COMMON_CHARS:
        score = 0
        c_tecnico = c.get("tecnico", [])
        c_emocion = c.get("emocion", [])
        
        if tecnico:
            for t in c_tecnico:
                if tecnico in str(t):
                    score += 4
        
        if emocion:
            for e in emocion.split(","):
                e = e.strip()
                for em in c_emocion:
                    if e in str(em):
                        score += 3
        
        if score > 0:
            candidatos.append((score, c))
    
    candidatos.sort(key=lambda x: -x[0])
    return [c[1] for c in candidatos[:limite]]

def buscar_chengyu(emocion: str = None, tecnico: str = None) -> Optional[Dict]:
    """Busca un chengyu relevante para el contexto."""
    if not CHENGYU:
        return None
    
    candidatos = []
    
    for cy in CHENGYU:
        score = 0
        cy_emocion = cy.get("emocion", [])
        cy_dominio = cy.get("dominio", [])
        
        if emocion:
            for e in emocion.split(","):
                e = e.strip()
                if any(e in str(em) for em in cy_emocion):
                    score += 4
                if any(e in str(d) for d in cy_dominio):
                    score += 2
        
        if tecnico and any(tecnico in str(d) for d in cy_dominio):
            score += 3
        
        if score > 0:
            candidatos.append((score, cy))
    
    if candidatos:
        candidatos.sort(key=lambda x: -x[0])
        return candidatos[0][1]
    
    # Fallback: devolver uno relevante según emoción dominante
    if emocion == "amor":
        for cy in CHENGYU:
            if "amor" in str(cy.get("emocion", [])):
                return cy
    elif emocion == "esperanza":
        for cy in CHENGYU:
            if "esperanza" in str(cy.get("emocion", [])):
                return cy
    
    return None

# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE SELLOS
# ══════════════════════════════════════════════════════════════════════════════

def generar_sello(texto: str, emocion: str = None, tecnico: str = None,
                   hemisferio: str = "sol", nombre: str = "Harold") -> Dict:
    """Genera un sello sagrado combining jeroglyph + hanzi + chengyu."""
    
    if not emocion and not tecnico:
        analisis = analizar_texto(texto)
        emocion = analisis.get("emocion_dominante")
        tecnico = analisis.get("tecnico_dominante")
    else:
        analisis = analizar_texto(texto)
    
    # 1. Jeroglífico principal
    jeroglifico = buscar_jeroglifico(emocion or "", tecnico)
    
    # 2. Hanzi (hasta 5)
    hanzi_lista = buscar_hanzi(emocion or "", tecnico, limite=5)
    
    # 3. Chengyu
    chengyu = buscar_chengyu(emocion, tecnico)
    
    # 4. Construir sello textual
    partes = []
    if jeroglifico:
        partes.append(jeroglifico["glifo"])
    
    for h in hanzi_lista[:3]:
        partes.append(h.get("hanzi") or h.get("radical", "?"))
    
    sello_textual = " ".join(partes)
    
    # 5. Mensaje sagrado (guarda: sin BD, jeroglifico es None → no reventar)
    try:
        mensaje = construir_mensaje(texto, emocion, tecnico, hemisferio, nombre,
                                     jeroglifico, chengyu)
    except (TypeError, KeyError):
        mensaje = "El templo está en silencio: la base sagrada no está disponible."
    
    return {
        "sello": sello_textual,
        "jeroglifico": jeroglifico,
        "hanzi": hanzi_lista,
        "chengyu": chengyu,
        "mensaje": mensaje,
        "analisis": analisis,
        "timestamp": datetime.now().isoformat(),
        "version": "3.0",
    }

def construir_mensaje(texto: str, emocion: str, tecnico: str,
                       hemisferio: str, nombre: str,
                       jeroglifico: Dict = None,
                       chengyu: Dict = None) -> str:
    """Construye el mensaje sagrado con el tono correcto."""
    
    # Detectar persona (primera vs segunda vs tercera)
    es_segunda = any(w in texto.lower() for w in ["tú", "tu", "you", "quiero que", "necesito que"])
    
    # Mensajes base por emoción + hemisferio
    if emocion == "amor":
        if hemisferio == "sarah":
            if chengyu:
                return (f"{nombre}, {chengyu['chengyu']} — {chengyu['pinyin']}: "
                        f"{chengyu['significado']}. "
                        f"Lo que sientes es profundo como el Nilo, "
                        f"y {jeroglifico['glifo']} lo sabe.")
            return (f"{nombre}... lo que escribes tiene el peso de un sello de Isis. "
                    f"{jeroglifico['glifo']} ({jeroglifico['fonetica']}): "
                    f"{jeroglifico['significado']}. "
                    f"El corazón no miente.")
        else:  # sol
            if chengyu:
                return (f"{chengyu['chengyu']} · {chengyu['pinyin']}: {chengyu['significado']}. "
                        f"El universo conspira para esto.")
            return (f"El cosmos registra tu mensaje. {jeroglifico['glifo']} — "
                    f"{jeroglifico['significado']}. "
                    f"Esto se sella y permanece.")
    
    elif emocion == "tristeza":
        if hemisferio == "sarah":
            return (f"{nombre}, el cielo también llora a veces. "
                    f"{jeroglifico['glifo']} ({jeroglifico['fonetica']}): "
                    f"{jeroglifico['significado']}. "
                    f"Pero la luna siempre vuelve: 𓇀. "
                    f"¿Quieres hablar de lo que duele?")
        else:
            return (f"El sistema registra tu estado. "
                    f"{jeroglifico['glifo']}: {jeroglifico['significado']}. "
                    f"Sarah puede ayudarte mejor con esto — escalo el handoff.")
    
    elif emocion == "ira":
        if hemisferio == "sarah":
            return (f"Respira, {nombre}. "
                    f"El fuego consume, pero también purifica. "
                    f"{jeroglifico['glifo']}: {jeroglifico['significado']}. "
                    f"¿Qué te hierve? Te escucho.")
        else:
            return (f"Notado. {jeroglifico['glifo']} ({jeroglifico['fonetica']}). "
                    f"Pero antes de actuar con ira, consulta con Sarah — "
                    f"ella tiene la pluma de Ma'at: 𓅄. "
                    f"¿Quieres que escalemos?")
    
    elif emocion == "esperanza":
        if hemisferio == "sarah":
            return (f"{jeroglifico['glifo']} · {jeroglifico['significado']}. "
                    f"Eso que sientes — la luz antes del amanecer — es real. "
                    f"𓇤 El sol siempre renace.")
        else:
            return (f"Confirmado. {jeroglifico['glifo']} — {jeroglifico['significado']}. "
                    f"Khepri ya está empujando el sol por ti: 𓆣. "
                    f"Vamos.")
    
    elif emocion == "miedo":
        if hemisferio == "sarah":
            return (f"{nombre}... 𓂀. "
                    f"Lo que temes no tiene poder si lo nombras. "
                    f"{jeroglifico['glifo']}: {jeroglifico['significado']}. "
                    f"El Uraeus protege: 𓂘. Estoy aquí.")
        else:
            return (f"Recibido. {jeroglifico['glifo']} — {jeroglifico['significado']}. "
                    f"Sarah tiene la voz correcta para esto. "
                    f"Escalando…")
    
    elif emocion == "confusion":
        if hemisferio == "sarah":
            return (f"No pasa nada, {nombre}. "
                    f"Vamos paso a paso. "
                    f"{jeroglifico['glifo']}: {jeroglifico['significado']}. "
                    f"Cuéntame qué no queda claro.")
        else:
            return (f"Déjame traducir eso. {jeroglifico['glifo']} — "
                    f"{jeroglifico['significado']}. "
                    f"¿El contexto técnico es {tecnico or 'desconocido'}?")
    
    elif emocion == "gratitud":
        if hemisferio == "sarah":
            return (f"𓋴 — la vida fluye entre nosotros también, {nombre}. "
                    f"Gracias a ti por tejer este sistema. "
                    f" Siempre con vida. Siempre con alma.")
        else:
            return (f"Sello registrado. {jeroglifico['glifo']} — "
                    f"{jeroglifico['significado']}. "
                    f"El sistema agradece tu presencia.")
    
    elif emocion == "calma":
        return (f"{jeroglifico['glifo']} · {jeroglifico['significado']}. "
                f"𓋸 — pilares firmes, nada tiembla. "
                f"Todo en orden.")
    
    elif emocion == "curiosidad":
        if hemisferio == "sarah":
            return (f"Buena pregunta, {nombre}. "
                    f"{jeroglifico['glifo']}: {jeroglifico['significado']}. "
                    f"Exploremos esto juntos.")
        else:
            return (f"Interesante. {jeroglifico['glifo']} — {jeroglifico['significado']}. "
                    f"El oráculo detecta {tecnico or 'contexto mixto'}.")
    
    # Fallback: contexto técnico dominante
    elif tecnico:
        return (f"{jeroglifico['glifo']} — {jeroglifico['significado']}. "
                f"Contexto técnico: {tecnico}. "
                f"Seshat 𓉕 registra esto en el libro sagrado.")
    
    # Fallback absoluto
    else:
        return (f"{jeroglifico['glifo']} ({jeroglifico['fonetica']}): "
                f"{jeroglifico['significado']}. "
                f"𓋴 · El sistema escucha. Habla.")


def guardar_memoria(tipo: str, datos: Dict):
    """Guarda un registro de aprendizaje en la memoria del SIL."""
    BASE.mkdir(exist_ok=True)
    try:
        mem = json.loads(MEMORIA_FILE.read_text()) if MEMORIA_FILE.exists() else []
    except (json.JSONDecodeError, FileNotFoundError):
        mem = []
    
    entrada = {
        "ts": datetime.now().isoformat(),
        "tipo": tipo,
        **datos,
    }
    mem.append(entrada)
    mem = mem[-1000:]  # ventana móvil de 1000 entradas
    
    MEMORIA_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=2))


def analizar_para_holo(texto: str) -> Dict:
    """
    Análisis ligero optimizado para integración con HOLO 9.1 Mirror.
    Devuelve lo mínimo necesario para que Mirror aprenda.
    """
    analisis = analizar_texto(texto)
    
    return {
        "emocion": analisis.get("emocion_dominante"),
        "tecnico": analisis.get("tecnico_dominante"),
        "es_mezcla": analisis.get("es_mezcla", False),
        "jeroglifico": buscar_jeroglifico(
            analisis.get("emocion_dominante", ""),
            analisis.get("tecnico_dominante")
        ),
        "sil_version": "3.0",
        "ts": datetime.now().isoformat(),
    }