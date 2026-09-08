"""Reflexion profunda con LLM (SOL 2.0). Usa la MISMA configuracion que Sol:
GROQ_API_KEY del entorno + endpoint Groq (sol_groq.py, regla #8/#56).
Sin llave, sin red o con cualquier error → devuelve None y el sistema
sigue exactamente igual con el insight local (nunca bloquea nada)."""
import json, os, urllib.request
from typing import Optional

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def _api_key() -> str:
    return os.environ.get("GROQ_API_KEY", "")

def deep_insight(task_name: str, success: bool, outcome: str, lesson: str) -> Optional[str]:
    key = _api_key()
    if not key:
        return None
    model = os.environ.get("GROQ_MODEL", "") or "openai/gpt-oss-120b"
    prompt = (
        "Eres el nucleo de reflexion de Sol, una IA que aprende de su trabajo operativo "
        "(escaneos de red, camaras, GPS, tutoria). En UNA sola frase concreta y accionable, "
        "profundiza esta leccion recien aprendida:\n"
        f"Tarea: {task_name}\nResultado: {'exito' if success else 'fallo'}\n"
        f"Detalle: {outcome[:300]}\nLeccion local: {lesson[:200]}\n"
        "Responde SOLO la frase, sin preambulos."
    )
    try:
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                           "max_tokens": 80, "temperature": 0.4}).encode()
        req = urllib.request.Request(GROQ_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": "sol-autonomy"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return text.strip() or None
    except Exception:
        return None
