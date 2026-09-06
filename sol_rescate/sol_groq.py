#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_groq.py — Integración automática con Groq API.

Auto-detecta GROQ_API_KEY del entorno y configura Sol para usar Groq
como proveedor LLM. Groq es OpenAI-compatible, así que usa el mismo
formato de /v1/chat/completiones.

Modelos disponibles (se auto-selecciona el mejor):
  - llama-3.3-70b-versatile (default — mejor calidad)
  - llama-3.1-8b-instant (rápido — para respuestas cortas)
  - gemma2-9b-it (ligero)

Prioridad de configuración:
  1. LLM_API_KEY + LLM_API_URL explícitos (mayor prioridad)
  2. GROQ_API_KEY (auto-configura Groq)
  3. Cerebro local de Sol (sin LLM externo)
"""

import os
import json
import urllib.request

# Modelos de Groq ordenados por calidad
# (2026-09-05) OJO: Groq deprecó llama-3.3-70b-versatile y llama-3.1-8b-instant
# el 16/08/2026 — cualquier .env o código viejo que aún los referencie falla
# TODAS las llamadas, silenciosamente cayendo a la plantilla local. Causa
# raíz de "mi cerebro no está conectado" repetido esa noche que Harold más
# la necesitaba. Iban a openai/gpt-oss-120b como reemplazo oficial.
GROQ_MODELS = {
    "best": "openai/gpt-oss-120b",       # 120B params — mejor calidad general
    "chinese": "qwen/qwen3.6-27b",       # Especialista en chino + pinyin (typo corregido: era 3.8, no existe)
    "fast": "openai/gpt-oss-20b",        # 20B — rápido para respuestas cortas
    "compound": "groq/compound",         # Modelo compuesto de Groq
}

# Modelo de rescate: SIEMPRE vigente mientras Groq no lo anuncie deprecado.
# Si el modelo configurado (env GROQ_MODEL/LLM_MODEL, quizás viejo o
# deprecado) falla, se reintenta una vez con este antes de rendirse.
GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def get_groq_key():
    """Devuelve GROQ_API_KEY del entorno, o vacío."""
    return os.environ.get("GROQ_API_KEY", "")


def is_groq_available():
    """True si GROQ_API_KEY está configurada."""
    return bool(get_groq_key())


def get_groq_model(preference="best"):
    """Devuelve el modelo de Groq a usar.
    Si GROQ_MODEL está en el entorno, usa ese. Si no, usa el preferido."""
    env_model = os.environ.get("GROQ_MODEL", "")
    if env_model:
        return env_model
    return GROQ_MODELS.get(preference, GROQ_MODELS["best"])


VENICE_URL = "https://api.venice.ai/api/v1/chat/completions"
# Venice Uncensored — sin filtros de contenido. Es lo que pidió Giovanni
# para el modo libre de Sol (2026-09-06): Groq dejó sin Llama gratis y su
# reemplazo (gpt-oss-120b) rechaza por política. Lista de modelos con:
#   curl https://api.venice.ai/api/v1/models -H "Authorization: Bearer $VENICE_API_KEY"
VENICE_DEFAULT_MODEL = "venice-uncensored:32b"


def configure_llm_env():
    """Configura las variables de entorno LLM_* para que sol_core las use.
    Prioridad:
      1. LLM_API_KEY ya configurada explícitamente (nunca se pisa)
      2. VENICE_API_KEY → Venice (uncensored, OpenAI-compatible)
      3. GROQ_API_KEY → Groq
    Si Venice falla (llave mala, modelo inexistente, sin créditos), el
    RESCATE FINAL de sol_core._llm_responde sigue cayendo directo a
    GROQ_API_KEY — la cadena queda: Venice → Groq → plantilla local."""
    # Si LLM_API_KEY ya está configurada explícitamente, no sobreescribir
    if os.environ.get("LLM_API_KEY", ""):
        return False

    # Venice tiene prioridad: es el cerebro sin censura que eligió Giovanni
    venice_key = os.environ.get("VENICE_API_KEY", "")
    if venice_key:
        os.environ["LLM_API_KEY"] = venice_key
        os.environ["LLM_API_URL"] = VENICE_URL
        if not os.environ.get("LLM_MODEL"):
            os.environ["LLM_MODEL"] = os.environ.get("VENICE_MODEL", VENICE_DEFAULT_MODEL)
        return True

    groq_key = get_groq_key()
    if not groq_key:
        return False

    # Configurar Groq como proveedor LLM
    os.environ["LLM_API_KEY"] = groq_key
    os.environ["LLM_API_URL"] = GROQ_URL
    if not os.environ.get("LLM_MODEL"):
        os.environ["LLM_MODEL"] = get_groq_model()
    return True


def groq_respond(msg, system_prompt="", context="", model=None):
    """Genera una respuesta usando Groq. Devuelve (texto, None) o (None, error).
    Usa urllib.request (stdlib, sin dependencias extra)."""
    key = get_groq_key()
    if not key:
        return None, "GROQ_API_KEY no configurada"

    model = model or get_groq_model()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context:
        messages.append({"role": "system", "content": f"Contexto reciente:\n{context}"})
    messages.append({"role": "user", "content": msg})

    body_dict = {
        "model": model,
        "messages": messages,
        "max_tokens": 200,
        "temperature": 0.8,
    }
    # FIX 2026-09-06: modelos de razonamiento (gpt-oss-120b/20b, qwen3.x)
    # devuelven su cadena de pensamiento MEZCLADA en el content por defecto
    # (reasoning_format="raw") — Sol mandaba su borrador interno como si
    # fuera la respuesta final (visto en Telegram: "Let's craft it
    # carefully... Draft (mental):..."). hidden = solo la respuesta final.
    if "gpt-oss" in model or "qwen" in model or "minimax" in model:
        body_dict["reasoning_format"] = "hidden"
    body = json.dumps(body_dict).encode()

    req = urllib.request.Request(GROQ_URL, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    })

    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        text = resp["choices"][0]["message"]["content"].strip()
        return text, None
    except Exception as e:
        return None, str(e)


def status():
    """Estado de la integración Groq."""
    return {
        "venice_available": bool(os.environ.get("VENICE_API_KEY", "")),
        "venice_model": os.environ.get("VENICE_MODEL", VENICE_DEFAULT_MODEL),
        "groq_available": is_groq_available(),
        "groq_model": get_groq_model() if is_groq_available() else None,
        "groq_models": GROQ_MODELS,
        "groq_url": GROQ_URL,
        "llm_configured": configure_llm_env(),
        "models": GROQ_MODELS,
    }
