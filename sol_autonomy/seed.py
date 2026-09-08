"""Siembra inicial del cerebro — lo que Sol YA sabe de verdad.
Fuente honesta: el LEEME_PRIMERO (habilidades construidas y lecciones pagadas).
Idempotente: solo siembra si el cerebro esta vacio; nunca pisa nada."""
from datetime import datetime
from typing import List, Tuple
from .memory import SolMemory, Experience, ExperienceType

_INITIAL_SKILLS: List[Tuple[str, str, float, float]] = [
    ("network_scan", "Escaneo de redes: nmap -sn + fallback TCP sin root (Termux)", 75, 70),
    ("camera_scan", "Deteccion de camaras por puertos/RTSP", 60, 65),
    ("gps_termux", "GPS via termux-location con reintentos", 55, 60),
    ("voice_tts", "Voz: gTTS (Replit) / termux-tts-speak (Termux)", 80, 85),
    ("sil_chinese", "Chino/pinyin con repeticion espaciada (SIL)", 65, 75),
    ("tutoria", "Tutoria pedagogica de Harold (sol_tutor + sol_pedagogy)", 70, 80),
    ("repo_management", "Gestion de repos GitHub (sol_repo_tools)", 65, 70),
    ("memory_distillation", "Destilacion del Libro de Vida (regla #56)", 60, 70),
]

_INITIAL_LESSONS: List[Tuple[str, float, str]] = [
    ("El fallback TCP connect() encuentra hosts vivos en Termux sin CAP_NET_RAW — nmap -sn se queda en silencio con 0 hosts sin esa capacidad", 8.0, "discovery"),
    ("El dist del frontend DEBE quedar completo en git tras cada rebuild — los publishes de Replit lo rompen (Regla #41)", 9.0, "mistake"),
    ("Validar deploys con navegador real (0 pageerror), nunca solo con curl — curl sin -f da falsos positivos", 8.0, "learning"),
    ("El token del dashboard ES la REDTEAM_API_KEY: si cambia el .env hay que re-login (leccion del temblor)", 7.0, "learning"),
]

def seed_initial_knowledge(memory: SolMemory) -> bool:
    try:
        if memory.count_experiences() > 0 or len(memory.get_top_skills(limit=100)) > 0:
            return False  # cerebro ya poblado — respetar lo que hay
        now = datetime.now().isoformat()
        for name, desc, prof, rate in _INITIAL_SKILLS:
            with memory._conn() as conn:
                conn.execute("""INSERT OR IGNORE INTO skills
                    (name, description, proficiency, last_used, times_used, success_rate)
                    VALUES (?,?,?,?,?,?)""", (name, desc, prof, now, 1, rate))
        for lesson, imp, typ in _INITIAL_LESSONS:
            memory.remember_experience(Experience(
                id=None, timestamp=now, type=ExperienceType(typ),
                context="historia heredada (LEEME_PRIMERO)", action="siembra inicial",
                outcome=lesson, lesson=lesson, importance=imp, tags=["seed"]))
        return True
    except Exception as e:
        print(f"[SOL-SEED] fallo la siembra (no bloquea): {e}")
        return False
