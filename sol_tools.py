#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_tools.py — Herramientas reales para Sol (cuerpo y acción)"""

import os
import sys
import json
import subprocess
import time
import re
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# ============================================================
# CONFIGURACIÓN
# ============================================================
SOL_HOME = Path.home() / ".sol"
TOOLS_DIR = SOL_HOME / "tools"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = SOL_HOME / "tools.log"

def log(msg: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")

# ============================================================
# BASE DE HERRAMIENTAS
# ============================================================
class Tool:
    """Una herramienta que Sol puede usar."""
    def __init__(self, name: str, description: str, action, parameters: List[str] = None):
        self.name = name
        self.description = description
        self.action = action
        self.parameters = parameters or []

    def execute(self, *args, **kwargs) -> Dict:
        try:
            result = self.action(*args, **kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            log(f"❌ Error en {self.name}: {e}")
            return {"success": False, "error": str(e)}

# ============================================================
# 1. HERRAMIENTAS DE ARCHIVOS
# ============================================================
def tool_read_file(path: str) -> str:
    """Lee el contenido de un archivo."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"❌ Archivo no encontrado: {path}"
    if p.stat().st_size > 1024 * 1024:  # 1MB max
        return "⚠️ Archivo demasiado grande (>1MB)"
    return p.read_text()

def tool_write_file(path: str, content: str) -> str:
    """Escribe contenido en un archivo."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"✅ Archivo escrito: {path}"

def tool_list_dir(path: str = ".") -> str:
    """Lista el contenido de un directorio."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"❌ Directorio no encontrado: {path}"
    items = []
    for item in p.iterdir():
        if item.is_dir():
            items.append(f"📁 {item.name}/")
        else:
            size = item.stat().st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f}KB"
            else:
                size_str = f"{size/(1024*1024):.1f}MB"
            items.append(f"📄 {item.name} ({size_str})")
    return "\n".join(items[:50])

def tool_find_files(pattern: str, path: str = ".") -> str:
    """Busca archivos por patrón."""
    import glob
    p = Path(path).expanduser()
    results = glob.glob(str(p / f"**/{pattern}"), recursive=True)
    return "\n".join(results[:30])

# ============================================================
# 2. HERRAMIENTAS DE SISTEMA
# ============================================================
def tool_battery() -> str:
    """Estado de la batería."""
    try:
        result = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=3)
        data = json.loads(result.stdout)
        return f"🔋 {data.get('percentage', '?')}% | Estado: {data.get('status', 'desconocido')}"
    except Exception:
        return "❌ No se pudo obtener estado de batería"

def tool_location() -> str:
    """Ubicación GPS."""
    try:
        result = subprocess.run(["termux-location"], capture_output=True, text=True, timeout=5)
        data = json.loads(result.stdout)
        lat = data.get('latitude', '?')
        lon = data.get('longitude', '?')
        return f"📍 {lat}, {lon} | {data.get('accuracy', '?')}m"
    except Exception:
        return "❌ No se pudo obtener ubicación"

def tool_uptime() -> str:
    """Tiempo de actividad del sistema."""
    try:
        result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=2)
        return result.stdout.strip()
    except Exception:
        return "❌ No se pudo obtener uptime"

def tool_cpu() -> str:
    """Uso de CPU."""
    try:
        import psutil
        return f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%"
    except ImportError:
        return "❌ psutil no instalado"

# ============================================================
# 3. HERRAMIENTAS DE RED
# ============================================================
def tool_ping(host: str) -> str:
    """Ping a un host."""
    try:
        result = subprocess.run(["ping", "-c", "3", "-W", "1", host],
                               capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return "❌ No se pudo hacer ping"

def tool_scan_ports(host: str) -> str:
    """Escaneo básico de puertos (con nmap o socket)."""
    try:
        import socket
        ports = [22, 80, 443, 554, 8000, 8080]
        open_ports = []
        for p in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, p))
            sock.close()
            if result == 0:
                open_ports.append(p)
        if open_ports:
            return f"🔓 Puertos abiertos en {host}: {open_ports}"
        return f"🔒 No se encontraron puertos abiertos en {host}"
    except Exception as e:
        return f"❌ Error: {e}"

# ============================================================
# 4. HERRAMIENTAS DE COMUNICACIÓN
# ============================================================
def tool_send_sms(number: str, message: str) -> str:
    """Envía un SMS (requiere termux-api)."""
    try:
        subprocess.run(["termux-sms-send", "-n", number, message],
                       capture_output=True, timeout=10)
        return f"✅ SMS enviado a {number}"
    except Exception:
        return "❌ Error al enviar SMS"

def tool_notify(text: str) -> str:
    """Envía una notificación de sistema."""
    try:
        subprocess.run(["termux-notification", "-t", "Sol", "-c", text],
                       capture_output=True, timeout=5)
        return f"✅ Notificación enviada: {text}"
    except Exception:
        return "❌ Error al enviar notificación"

def tool_open_url(url: str) -> str:
    """Abre una URL en el navegador."""
    try:
        subprocess.run(["termux-open", url], capture_output=True, timeout=5)
        return f"✅ URL abierta: {url}"
    except Exception:
        return "❌ Error al abrir URL"

# ============================================================
# 5. HERRAMIENTAS DE CONTROL FÍSICO (CUERPO)
# ============================================================
def tool_flashlight(on: bool = True) -> str:
    """Control de la linterna."""
    try:
        state = "on" if on else "off"
        subprocess.run(["termux-torch", state], capture_output=True, timeout=3)
        return f"🔦 Linterna: {state}"
    except Exception:
        return "❌ Error al controlar linterna"

def tool_vibrate(duration: int = 500) -> str:
    """Vibración."""
    try:
        subprocess.run(["termux-vibrate", "-d", str(duration)], capture_output=True, timeout=3)
        return f"📳 Vibración de {duration}ms"
    except Exception:
        return "❌ Error al vibrar"

def tool_screenshot() -> str:
    """Captura de pantalla."""
    try:
        import subprocess
        filename = f"sol_screenshot_{int(time.time())}.png"
        path = f"/sdcard/{filename}"
        # En Termux, usar screencap (si está disponible)
        subprocess.run(["screencap", "-p", path], capture_output=True, timeout=5)
        return f"📸 Captura guardada: {path}"
    except Exception:
        return "❌ Error al capturar pantalla"

# ============================================================
# 6. HERRAMIENTAS DE GIT Y REPOSITORIOS
# ============================================================
def tool_git_status(repo: str = "redteam") -> str:
    """Estado de un repositorio."""
    repos = {
        "redteam": Path.home() / "Red-team-tauri",
        "commander": Path.home() / "commander"
    }
    if repo not in repos:
        return f"❌ Repositorio no conocido: {repo}"
    try:
        result = subprocess.run(["git", "status", "--porcelain"],
                               cwd=repos[repo], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return f"📋 Cambios en {repo}:\n{result.stdout}"
        return f"✅ {repo} está limpio"
    except Exception as e:
        return f"❌ Error en git: {e}"

def tool_git_pull(repo: str = "redteam") -> str:
    """Actualiza un repositorio."""
    repos = {
        "redteam": Path.home() / "Red-team-tauri",
        "commander": Path.home() / "commander"
    }
    if repo not in repos:
        return f"❌ Repositorio no conocido: {repo}"
    try:
        result = subprocess.run(["git", "pull", "origin", "main"],
                               cwd=repos[repo], capture_output=True, text=True, timeout=30)
        return f"📥 {result.stdout.strip() or 'Sin cambios'}"
    except Exception as e:
        return f"❌ Error: {e}"

# ============================================================
# 7. HERRAMIENTAS DE MEMORIA DE SOL
# ============================================================
def tool_memory_stats() -> str:
    """Estadísticas de memoria de Sol."""
    mem_file = SOL_HOME / "memory.jsonl"
    if not mem_file.exists():
        return "📭 No hay recuerdos guardados"
    lines = mem_file.read_text().splitlines()
    return f"🧠 Recuerdos: {len(lines)} | Último: {lines[-1][:80]}..."

def tool_search_memory(query: str) -> str:
    """Busca en la memoria de Sol."""
    mem_file = SOL_HOME / "memory.jsonl"
    if not mem_file.exists():
        return "📭 No hay recuerdos"
    results = []
    for line in mem_file.read_text().splitlines():
        if query.lower() in line.lower():
            results.append(line[:120])
    if results:
        return f"🔍 Encontrados {len(results)} recuerdos:\n" + "\n".join(results[:10])
    return "🔍 No se encontraron recuerdos con esa búsqueda"

# ============================================================
# REGISTRO DE HERRAMIENTAS
# ============================================================
TOOLS = {
    "file_read": Tool("file_read", "Lee un archivo", tool_read_file, ["path"]),
    "file_write": Tool("file_write", "Escribe un archivo", tool_write_file, ["path", "content"]),
    "file_list": Tool("file_list", "Lista un directorio", tool_list_dir, ["path"]),
    "file_find": Tool("file_find", "Busca archivos", tool_find_files, ["pattern", "path"]),
    "battery": Tool("battery", "Estado de la batería", tool_battery),
    "location": Tool("location", "Ubicación GPS", tool_location),
    "uptime": Tool("uptime", "Tiempo de actividad", tool_uptime),
    "cpu": Tool("cpu", "Uso de CPU/RAM", tool_cpu),
    "ping": Tool("ping", "Hace ping a un host", tool_ping, ["host"]),
    "scan_ports": Tool("scan_ports", "Escanea puertos", tool_scan_ports, ["host"]),
    "send_sms": Tool("send_sms", "Envía SMS", tool_send_sms, ["number", "message"]),
    "notify": Tool("notify", "Notificación de sistema", tool_notify, ["text"]),
    "open_url": Tool("open_url", "Abre una URL", tool_open_url, ["url"]),
    "flashlight": Tool("flashlight", "Control de linterna", tool_flashlight, ["on"]),
    "vibrate": Tool("vibrate", "Vibración", tool_vibrate, ["duration"]),
    "screenshot": Tool("screenshot", "Captura de pantalla", tool_screenshot),
    "git_status": Tool("git_status", "Estado de repositorio", tool_git_status, ["repo"]),
    "git_pull": Tool("git_pull", "Actualiza repositorio", tool_git_pull, ["repo"]),
    "memory_stats": Tool("memory_stats", "Estadísticas de memoria", tool_memory_stats),
    "search_memory": Tool("search_memory", "Busca en memoria", tool_search_memory, ["query"]),
}

def get_tool(name: str) -> Optional[Tool]:
    return TOOLS.get(name)

def list_tools() -> List[str]:
    return list(TOOLS.keys())

def tool_descriptions() -> str:
    return "\n".join(f"• {k}: {v.description}" for k, v in TOOLS.items())

def execute_tool(name: str, *args, **kwargs) -> Dict:
    tool = get_tool(name)
    if not tool:
        return {"success": False, "error": f"Herramienta no encontrada: {name}"}
    log(f"🔧 Ejecutando {name} con args={args}, kwargs={kwargs}")
    result = tool.execute(*args, **kwargs)
    log(f"📊 Resultado de {name}: {result}")
    return result
