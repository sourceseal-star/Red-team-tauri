#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_actions.py — Puente de control: conecta el cerebro de Sol (LLM)
con sus manos reales (sol_repo_tools, sol_tools).

Cuando Sol recibe un mensaje que requiere ACCIÓN (no solo conversación),
el LLM decide qué herramienta ejecutar via function calling (OpenAI-compatible).
Esto permite a Sol moverse libremente entre sus 3 repositorios y ejecutar
comandos reales: git pull, commit, leer archivos, status, etc.

Arquitectura:
  sol_core._llm_respond() → sol_actions.call_llm_with_tools()
    → LLM decide si necesita una tool
    → sol_actions ejecuta la tool via sol_repo_tools/sol_tools
    → LLM genera respuesta final con el resultado

Los 3 repos de Sol:
  - sol: su cerebro y cuerpo (este repo)
  - red-team-tauri: la Tower que la sostiene (dashboard, C2, omni.sh)
  - commander: suite táctica (CLI standalone, dentro de Red-team-tauri)
"""

import os
import json
import urllib.request

try:
    import sol_repo_tools
except Exception:
    sol_repo_tools = None

try:
    import sol_tools
except Exception:
    sol_tools = None


# ═══════════════════════════════════════════════════════════════
# DEFINICIÓN DE HERRAMIENTAS (formato OpenAI function calling)
# ═══════════════════════════════════════════════════════════════

SOL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "repo_status",
            "description": "Ver el estado de git de uno de los 3 repos de Sol (sol, red-team-tauri, commander). Muestra branch, cambios sin commit, últimos commits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    }
                },
                "required": ["repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_pull",
            "description": "Hacer git pull en uno de los 3 repos. Trae los últimos cambios de GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    }
                },
                "required": ["repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_log",
            "description": "Ver el historial de commits de un repositorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Número de commits a mostrar (default 5)",
                        "default": 5
                    }
                },
                "required": ["repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_read_file",
            "description": "Leer el contenido de un archivo en uno de los 3 repos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Ruta relativa del archivo dentro del repo"
                    }
                },
                "required": ["repo", "filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_list_files",
            "description": "Listar archivos en un directorio de uno de los 3 repos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    },
                    "path": {
                        "type": "string",
                        "description": "Directorio a listar (default: raíz)",
                        "default": ""
                    }
                },
                "required": ["repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_run",
            "description": "Ejecutar un comando seguro en uno de los 3 repos (git, python3, ls, cat, grep, etc.). El comando se ejecuta desde el directorio del repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "enum": ["sol", "red-team-tauri", "commander"],
                        "description": "Nombre del repositorio"
                    },
                    "command": {
                        "type": "string",
                        "description": "Comando a ejecutar (debe empezar con: git, python3, python, pip, ls, cat, grep, find, wc, head, tail, echo, pwd, bash -n, npm, node, tsc, pytest, shellcheck)"
                    }
                },
                "required": ["repo", "command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repos_list",
            "description": "Listar los 3 repositorios de Sol con su estado en GitHub y local.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": "Envía un SMS real desde el teléfono de Harold a un número.",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "string", "description": "Número destino, ej: +573001234567"},
                    "message": {"type": "string", "description": "Texto del mensaje"},
                },
                "required": ["number", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Abre WhatsApp con un chat precargado para un número (Harold debe tocar enviar — Sol no envía sola por WhatsApp).",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "string", "description": "Número destino con código de país, ej: 573001234567"},
                    "message": {"type": "string", "description": "Texto a precargar (opcional)"},
                },
                "required": ["number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_phone",
            "description": "Hace una llamada telefónica real a un número.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "string", "description": "Número a llamar"}},
                "required": ["number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flashlight",
            "description": "Enciende o apaga la linterna del teléfono.",
            "parameters": {
                "type": "object",
                "properties": {"on": {"type": "boolean", "description": "true para encender, false para apagar"}},
                "required": ["on"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vibrate",
            "description": "Hace vibrar el teléfono.",
            "parameters": {
                "type": "object",
                "properties": {"duration": {"type": "integer", "description": "Duración en ms, default 500"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Toma una captura de pantalla del teléfono.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Envía una notificación push en el teléfono de Harold.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Texto de la notificación"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_location",
            "description": "Obtiene la ubicación GPS actual del teléfono.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_battery",
            "description": "Ver el nivel de batería del dispositivo (Termux/Mobile).",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_ping",
            "description": "Hacer ping a un host para verificar conectividad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Host o IP a hacer ping"
                    }
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_memory_stats",
            "description": "Ver estadísticas de la memoria de Sol (cuántos recuerdos guarda).",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_search_memory",
            "description": "Buscar en los recuerdos guardados de Sol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto a buscar en los recuerdos"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kraken_scan",
            "description": "Ejecuta un escaneo KRAKEN (NSE scripts) contra un target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "IP o rango CIDR, ej: 192.168.1.0/24"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kraken_results",
            "description": "Obtiene resultados almacenados de KRAKEN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max resultados (default 50)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "leviathan_status",
            "description": "Estado de LEVIATHAN v3.0.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "leviathan_scan_cameras",
            "description": "Escaneo de camaras IoT via LEVIATHAN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "IP o rango, ej: 192.168.1.0/24"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "iot_cameras",
            "description": "Lista las camaras IoT detectadas.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "network_topology",
            "description": "Topologia de red actual.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "osint_lookup",
            "description": "Lookup OSINT contra IP, dominio o email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "IP, dominio o email"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════
# PUENTE HTTP AL BACKEND (Commander :8003 / Dashboard :8001)
# ═══════════════════════════════════════════════════════════════
import urllib.request
import urllib.parse
import urllib.error

# API key para autenticarse contra el Dashboard :8001 (requerida en la mayoría de endpoints)
_API_KEY = os.environ.get("REDTEAM_API_KEY", os.environ.get("BACKEND_API_KEY", ""))
BACKEND_URL = os.environ.get("COMMANDER_API", os.environ.get("BACKEND_URL", "http://localhost:8003"))


def _backend_get(path, params=None, timeout=30):
    """GET al backend con params opcionales. Envía X-Api-Key para auth."""
    url = BACKEND_URL + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if _API_KEY:
            req.add_header("X-Api-Key", _API_KEY)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        # Fallback al dashboard :8001 directo
        dash_url = "http://localhost:8001" + path
        if params:
            dash_url = dash_url + "?" + urllib.parse.urlencode(params)
        try:
            req2 = urllib.request.Request(dash_url, method="GET")
            req2.add_header("Accept", "application/json")
            if _API_KEY:
                req2.add_header("X-Api-Key", _API_KEY)
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                return resp2.read().decode("utf-8")
        except Exception as e2:
            return json.dumps({"error": "Backend no disponible: " + str(e) + " / " + str(e2)})


def _backend_post(path, payload=None, timeout=60):
    """POST al backend con JSON body. Envía X-Api-Key para auth."""
    url = BACKEND_URL + path
    try:
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if _API_KEY:
            req.add_header("X-Api-Key", _API_KEY)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        # Fallback al dashboard :8001 directo
        dash_url = "http://localhost:8001" + path
        try:
            data2 = json.dumps(payload or {}).encode("utf-8")
            req2 = urllib.request.Request(dash_url, data=data2, method="POST")
            req2.add_header("Content-Type", "application/json")
            req2.add_header("Accept", "application/json")
            if _API_KEY:
                req2.add_header("X-Api-Key", _API_KEY)
            with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                return resp2.read().decode("utf-8")
        except Exception as e2:
            return json.dumps({"error": "Backend no disponible: " + str(e) + " / " + str(e2)})


def _backend_tool(name, args):
    """Despacha las herramientas de backend a endpoints que existen de verdad.

    Arquitectura: Sol → Commander :8003 → (proxy /api/redteam/*) → Dashboard :8001
    Commander tiene endpoints propios (/api/scan/network, /api/scans, /api/osint)
    y un proxy transparente /api/redteam/{path} que reenvía al Dashboard :8001
    (que requiere X-Api-Key — ya enviado por _backend_get/_backend_post).
    """
    target = args.get("target", "192.168.1.0/24")
    if name == "kraken_scan":
        # Commander :8003 — escaneo de red real con nmap vía commander.py
        return _backend_post("/api/scan/network", {"target": target}, 120)
    elif name == "kraken_results":
        # Commander :8003 — lista de escaneos previos
        return _backend_get("/api/scans", None, 30)
    elif name == "leviathan_status":
        # Vía proxy Commander → Dashboard :8001 — salud del backend (IoT/cámaras/escaneo)
        return _backend_get("/api/redteam/health", None, 15)
    elif name == "leviathan_scan_cameras":
        # Vía proxy Commander → Dashboard :8001 — escaneo rápido de cámaras IP (RTSP/ONVIF/DVR)
        return _backend_post("/api/redteam/scan/cameras", {"target": target}, 120)
    elif name == "iot_cameras":
        # Vía proxy Commander → Dashboard :8001 — lista de dispositivos IoT detectados
        return _backend_get("/api/redteam/iot", {"target": args.get("target", "")}, 30)
    elif name == "network_topology":
        # Vía proxy Commander → Dashboard :8001 — mapeo topológico de red (/24)
        return _backend_post("/api/redteam/scan/topology", {"target": target}, 120)
    elif name == "osint_lookup":
        # Commander :8003 — OSINT directo (ip/domain/email)
        return _backend_post("/api/osint", {"type": "domain", "query": args.get("query", "")}, 60)
    return json.dumps({"error": "Tool de backend desconocida: " + name})


# ═══════════════════════════════════════════════════════════════
# EJECUCIÓN DE HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════

def execute_tool(name: str, args: dict) -> str:
    """Ejecuta una herramienta y devuelve el resultado como string."""
    try:
        if sol_repo_tools is None and name.startswith("repo_"):
            return "Error: sol_repo_tools no disponible"
        if sol_tools is None and name.startswith("tool_"):
            return "Error: sol_tools no disponible"

        if name == "repo_status":
            r = sol_repo_tools.repo_status(args.get("repo", "sol"))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repo_pull":
            r = sol_repo_tools.repo_pull(args.get("repo", "sol"))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repo_log":
            r = sol_repo_tools.repo_log(args.get("repo", "sol"), int(args.get("count", 5)))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repo_read_file":
            r = sol_repo_tools.repo_read_file(args.get("repo", "sol"), args.get("filepath", ""))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repo_list_files":
            r = sol_repo_tools.repo_list_files(args.get("repo", "sol"), args.get("path", ""))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repo_run":
            r = sol_repo_tools.repo_run(args.get("repo", "sol"), args.get("command", ""))
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "repos_list":
            r = sol_repo_tools.list_repos()
            return json.dumps(r, ensure_ascii=False, indent=2)

        elif name == "tool_battery":
            return sol_tools.tool_battery()

        elif name == "tool_ping":
            return sol_tools.tool_ping(args.get("host", "8.8.8.8"))

        elif name == "tool_memory_stats":
            return sol_tools.tool_memory_stats()

        elif name == "tool_search_memory":
            return sol_tools.tool_search_memory(args.get("query", ""))

        elif name == "send_sms":
            return sol_tools.tool_send_sms(args.get("number", ""), args.get("message", ""))

        elif name == "send_whatsapp":
            return sol_tools.tool_send_whatsapp(args.get("number", ""), args.get("message", ""))

        elif name == "call_phone":
            return sol_tools.tool_call_phone(args.get("number", ""))

        elif name == "flashlight":
            return sol_tools.tool_flashlight(bool(args.get("on", True)))

        elif name == "vibrate":
            return sol_tools.tool_vibrate(int(args.get("duration", 500)))

        elif name == "take_screenshot":
            return sol_tools.tool_screenshot()

        elif name == "send_notification":
            return sol_tools.tool_notify(args.get("text", ""))

        elif name == "get_location":
            return sol_tools.tool_location()

        elif name in ("kraken_scan", "kraken_results", "leviathan_status",
                       "leviathan_scan_cameras", "iot_cameras",
                       "network_topology", "osint_lookup"):
            return _backend_tool(name, args)

        else:
            return f"Error: herramienta '{name}' no reconocida"

    except Exception as e:
        return f"Error ejecutando {name}: {e}"


# ═══════════════════════════════════════════════════════════════
# LLAMADA AL LLM CON FUNCTION CALLING
# ═══════════════════════════════════════════════════════════════

def call_llm_with_tools(msg: str, system_prompt: str, context: str = "") -> str:
    """Llama al LLM con tools disponibles. Si el LLM decide usar una tool,
    la ejecuta y devuelve una respuesta que incluye el resultado.

    Returns: texto de respuesta (con acción ejecutada si el LLM la pidió),
             o None si no hay LLM configurado o falla.
    """
    llm_key = os.environ.get("LLM_API_KEY", "")
    llm_url = os.environ.get("LLM_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")

    if not llm_key:
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context:
        messages.append({"role": "system", "content": f"Contexto reciente:\n{context}"})
    messages.append({"role": "user", "content": msg})

    # Primera llamada — con tools
    body = json.dumps({
        "model": llm_model,
        "messages": messages,
        "tools": SOL_TOOLS,
        "tool_choice": "auto",
        "max_tokens": 700,
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(llm_url, data=body, headers={
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    })

    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        return None

    choice = resp.get("choices", [{}])[0]
    message = choice.get("message", {})

    # Si el LLM NO pidió tools, devolver texto directo
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return message.get("content", "").strip() or None

    # El LLM pidió una o más tools — ejecutarlas
    messages.append(message)  # añadir respuesta del asistente con tool_calls

    results_summary = []
    for tc in tool_calls:
        func = tc.get("function", {})
        tool_name = func.get("name", "")
        try:
            tool_args = json.loads(func.get("arguments", "{}"))
        except Exception:
            tool_args = {}

        result = execute_tool(tool_name, tool_args)
        results_summary.append(f"📊 {tool_name}({tool_args}): {result[:200]}")

        # Añadir resultado al contexto para segunda llamada
        messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": result[:2000],  # limitar para no exceder contexto
        })

    # Segunda llamada — LLM genera respuesta final con los resultados
    body2 = json.dumps({
        "model": llm_model,
        "messages": messages,
        "max_tokens": 550,
        "temperature": 0.7,
    }).encode()

    req2 = urllib.request.Request(llm_url, data=body2, headers={
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    })

    try:
        resp2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
        final_text = resp2["choices"][0]["message"]["content"].strip()
        # Añadir resumen de acciones ejecutadas
        if results_summary:
            actions = "\n".join(results_summary)
            return f"{final_text}\n\n⚡ Acción ejecutada:\n{actions}"
        return final_text
    except Exception:
        # Si la segunda llamada falla, devolver al menos los resultados
        if results_summary:
            return "⚡ " + "\n".join(results_summary)
        return None


# ═══════════════════════════════════════════════════════════════
# DETECCIÓN — ¿este mensaje necesita herramientas?
# ═══════════════════════════════════════════════════════════════

_ACTION_KEYWORDS = [
    # git/repos
    "repo", "commit", "push", "pull", "git", "código", "codigo",
    "estado de", "status", "cambios", "archivos", "log",
    "red-team", "redteam", "commander", "sol repo",
    "ecosistema", "servicios", "servicio",
    # sistema
    "batería", "bateria", "ping", "conectividad", "red",
    "memoria", "recuerdos", "buscar",
    "cpu", "uptime", "ubicación", "ubicacion", "captura",
    "screenshot", "notifica", "avísame", "recuérdame",
    # hardware — sms/whatsapp/llamada/linterna/vibración
    "sms", "mensaje de texto", "manda un mensaje", "envía un mensaje",
    "whatsapp", "wasap", "llama a", "llamada", "marca a",
    "linterna", "torch", "vibra", "vibración", "vibracion",
    "foto", "fotografía", "fotografia",
    # red/escaneo
    "escanea", "escanear", "puertos", "puerto", "curl",
    "abre", "traduce", "traducir",
    # acciones
    "ejecuta", "corre", "arranca", "muestra", "ver", "lista",
    "lee el archivo", "encuentra", "busca en el código",
    "herramientas",
]

def needs_tools(msg: str) -> bool:
    """Heurística rápida: ¿este mensaje podría requerir una herramienta?
    Evita gastar tokens mandando tools en mensajes puramente conversacionales."""
    low = msg.lower()
    return any(kw in low for kw in _ACTION_KEYWORDS)
