#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Orchestration & System Monitoring Tool v1.0
Author: Harold Paredes / SourceSeal
Description: Herramienta de orquestación de repositorios Git, monitoreo de sistema,
y control remoto vía Telegram para administradores autorizados.
Diseñada para entornos de desarrollo y administración de proyectos.

COMPLETADO 2026-10-02 (Lyra, Regla #71): el diseño original de Harold llegó
truncado (cortaba en /help). Se completaron los 5 comandos que faltaban
(/snapshot, /network_info, /top_processes, /monitor_status, /sync_repo),
el SystemMonitor, la API FastAPI con Bearer auth, el loop de polling de
Telegram y el main. Blindaje añadido (sin cambiar el diseño):
  1. Variables ORCH_* — NUNCA TELEGRAM_BOT_TOKEN: el bot de Sol
     (@sol_amg_bot) y este tool competirían por los mismos mensajes
     (bug histórico del LEEME, línea 595). Token propio vía @BotFather.
  2. Bind 127.0.0.1 por defecto. 0.0.0.0 solo con ORCH_BIND_ALL=1 Y
     ORCH_API_SECRET_KEY configurada (fail-closed, nunca expuesto a la
     LAN sin clave).
  3. Allowlist de Telegram deny-by-default: sin ORCH_TELEGRAM_ALLOWED_USERS
     el bot rechaza todo comando (el diseño original permitía a cualquiera
     si la lista estaba vacía — corregido).
  4. /exec_command mantiene el bloqueo de comandos peligrosos + timeout 30s.
"""

import os
import sys
import json
import subprocess
import time
import threading
import asyncio
import shutil
import socket
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests
from fastapi import FastAPI, WebSocket, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

# ============================================================
# CONFIGURACIÓN CENTRALIZADA
# ============================================================
CONFIG = {
    "repos": {
        "dashboard": {
            "path": os.path.expanduser("~/Red-team-tauri"),
            "remote": "origin",
            "branch": "main",
            "enabled": True
        },
        "commander": {
            "path": os.path.expanduser("~/commander"),
            "remote": "origin",
            "branch": "main",
            "enabled": True
        }
    },
    # Variables ORCH_* — deliberadamente distintas a las de Sol para que
    # los dos bots NUNCA compitan por el mismo token de Telegram.
    "telegram": {
        "bot_token": os.environ.get("ORCH_TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("ORCH_TELEGRAM_CHAT_ID", ""),
        "allowed_users": os.environ.get("ORCH_TELEGRAM_ALLOWED_USERS", "").replace(" ", "").split(","),
    },
    "api": {
        # Blindaje: 127.0.0.1 por defecto. Para exponer a la LAN:
        # ORCH_BIND_ALL=1 + ORCH_API_SECRET_KEY fuerte en .env.
        "host": "0.0.0.0" if os.environ.get("ORCH_BIND_ALL", "") == "1" else "127.0.0.1",
        "port": int(os.environ.get("ORCH_PORT", "8080")),
        "secret": os.environ.get("ORCH_API_SECRET_KEY", ""),
    },
    "monitor": {
        "enabled": True,
        "interval": 30,
        "cpu_threshold": 85.0,
        "ram_threshold": 90.0,
    },
    "paths": {
        "log_file": os.path.expanduser("~/.orchestrator.log"),
        "scripts_dir": os.path.expanduser("~/.orchestrator/scripts"),
    },
}

# Fail-closed: exponer a toda la LAN sin clave es un agujero (el API tiene
# /api/exec). Nos negamos a arrancar así.
if CONFIG["api"]["host"] == "0.0.0.0" and not CONFIG["api"]["secret"]:
    sys.exit("[ORCH] FATAL: ORCH_BIND_ALL=1 requiere ORCH_API_SECRET_KEY en .env")

# Sin clave y en localhost: se genera una por arranque (solo útil localmente).
if not CONFIG["api"]["secret"]:
    import secrets as _secrets
    CONFIG["api"]["secret"] = _secrets.token_urlsafe(24)
    print(f"[ORCH] ORCH_API_SECRET_KEY no configurada — clave efímera "
          f"generada para esta sesión (localhost only): {CONFIG['api']['secret'][:8]}...")

# ============================================================
# LOGGING
# ============================================================
def setup_logging():
    Path(CONFIG["paths"]["log_file"]).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(CONFIG["paths"]["log_file"]),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("Orchestrator")

logger = setup_logging()

# ============================================================
# GESTOR DE REPOSITORIOS
# ============================================================
class RepoManager:
    """Gestiona repositorios Git para proyectos."""
    def __init__(self):
        self.repos = CONFIG["repos"]
        self.status_cache = {}

    def _git(self, repo_name: str, *args) -> Dict:
        repo_path = self.repos[repo_name]["path"]
        if not os.path.exists(repo_path):
            return {"error": f"Repositorio {repo_name} no encontrado en {repo_path}"}
        cmd = ["git", "-C", repo_path] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Timeout ejecutando git"}
        except Exception as e:
            return {"error": str(e)}

    def get_status(self, repo_name: str) -> Dict:
        status = self._git(repo_name, "status", "--porcelain")
        branch = self._git(repo_name, "branch", "--show-current")
        remote = self._git(repo_name, "remote", "-v")
        return {
            "branch": branch.get("stdout", "unknown"),
            "has_changes": bool(status.get("stdout", "")),
            "changes": status.get("stdout", ""),
            "remote": remote.get("stdout", ""),
            "error": status.get("error") or branch.get("error") or remote.get("error")
        }

    def pull(self, repo_name: str) -> Dict:
        return self._git(repo_name, "pull", self.repos[repo_name]["remote"], self.repos[repo_name]["branch"])

    def push(self, repo_name: str) -> Dict:
        return self._git(repo_name, "push", self.repos[repo_name]["remote"], self.repos[repo_name]["branch"])

    def sync(self, repo_name: str) -> Dict:
        pull_res = self.pull(repo_name)
        if "error" in pull_res:
            return {"pull": pull_res, "push": {"error": "Pull fallido, no se ejecuta push"}}
        push_res = self.push(repo_name)
        return {"pull": pull_res, "push": push_res}

    def get_all_status(self) -> Dict:
        status = {}
        for name in self.repos:
            if self.repos[name].get("enabled", True):
                status[name] = self.get_status(name)
        return status

repo_manager = RepoManager()

# ============================================================
# TELEGRAM BOT (Control Remoto para Administradores)
# ============================================================
class TelegramBot:
    """Bot de Telegram para control remoto de la herramienta de orquestación."""
    def __init__(self):
        self.token = CONFIG["telegram"]["bot_token"]
        self.chat_id = CONFIG["telegram"]["chat_id"]
        self.allowed_users = set(u for u in CONFIG["telegram"]["allowed_users"] if u)
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.commands = {
            "/status": self.cmd_status,
            "/scan_repo": self.cmd_scan_repo,
            "/stop_process": self.cmd_stop_process,
            "/emergency": self.cmd_emergency,
            "/update_repos": self.cmd_update_repos,
            "/deploy_scripts": self.cmd_deploy_scripts,
            "/exec_command": self.cmd_exec_command,
            "/help": self.cmd_help,
            "/snapshot": self.cmd_snapshot,
            "/network_info": self.cmd_network_info,
            "/top_processes": self.cmd_top_processes,
            "/monitor_status": self.cmd_monitor_status,
            "/sync_repo": self.cmd_sync_repo
        }
        self.alert_cpu = False
        self.alert_ram = False
        logger.info("🤖 Telegram Bot inicializado")

    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram no configurado")
            return False
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return False

    def handle_message(self, message: Dict) -> Optional[str]:
        text = message.get("text", "")
        if not text:
            return None
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        user_id = str(message.get("from", {}).get("id", ""))
        # DENY-BY-DEFAULT (completado 2026-10-02): sin allowlist configurada
        # nadie puede ejecutar comandos — incluido /exec_command. Mejor
        # configurar de más que dejar el teléfono abierto a cualquiera.
        if not self.allowed_users or user_id not in self.allowed_users:
            logger.warning(f"Usuario no autorizado id={user_id} intentó: {cmd}")
            return "⛔ Usuario no autorizado. Contacta al administrador."
        if cmd in self.commands:
            return self.commands[cmd](args)
        return f"❌ Comando desconocido. Usa /help para ver los disponibles."

    # --- COMANDOS DE ADMINISTRACIÓN ---
    def cmd_status(self, args):
        status = repo_manager.get_all_status()
        msg = "📊 **ESTADO DE PROYECTOS**\n\n"
        for repo, data in status.items():
            changes = "✅" if not data.get("has_changes", False) else "📝"
            branch = data.get("branch", "N/A")
            msg += f"• **{repo}**: {changes} `{branch}`\n"
            if data.get("has_changes"):
                msg += f" Cambios:\n```\n{data['changes'][:200]}\n```\n"
        # Estado del sistema
        if PSUTIL_OK:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            msg += f"\n🖥️ **CPU**: {cpu}%"
            msg += f"\n🧠 **RAM**: {mem}%"
            msg += f"\n💾 **DISCO**: {disk}%"
        else:
            msg += "\n⚠️ psutil no instalado (pip install psutil)"
        return msg

    def cmd_scan_repo(self, args):
        target = args[0] if args else "192.168.1.0/24"
        msg = f"🔍 **Iniciando análisis en {target}...**\n"
        # Aquí se podría llamar a un script de análisis de red (ej. nmap)
        # Pero lo dejamos como un placeholder para no activar alertas de seguridad
        msg += "⚠️ Función de análisis de red deshabilitada en esta versión.\n"
        msg += "Para análisis de red, usa herramientas externas como `nmap`."
        return msg

    def cmd_stop_process(self, args):
        if not args:
            return "❌ Uso: /stop_process <PID>"
        pid = args[0]
        try:
            p = psutil.Process(int(pid))
            p.terminate()
            return f"✅ Proceso {pid} ({p.name()}) finalizado correctamente."
        except psutil.NoSuchProcess:
            return f"❌ Proceso {pid} no encontrado."
        except Exception as e:
            return f"❌ Error: {e}"

    def cmd_emergency(self, args):
        msg = " ".join(args) if args else "🚨 ALERTA DE EMERGENCIA ACTIVADA 🚨"
        # Aquí se ejecutaría un script de respaldo, pero solo mostramos mensaje
        return f"🚨 **EMERGENCIA**\nMensaje: {msg}\nSe han notificado a los administradores."

    def cmd_update_repos(self, args):
        results = {}
        for repo in repo_manager.repos:
            if repo_manager.repos[repo].get("enabled", True):
                res = repo_manager.sync(repo)
                results[repo] = res
        msg = "📦 **ACTUALIZACIÓN DE REPOSITORIOS**\n\n"
        for repo, res in results.items():
            if "error" in str(res):
                msg += f"❌ **{repo}**: Error durante la sincronización\n"
            else:
                msg += f"✅ **{repo}**: Actualizado correctamente\n"
        return msg

    def cmd_deploy_scripts(self, args):
        source = args[0] if args else "~/commander/scripts"
        target = args[1] if len(args) > 1 else "~/.orchestrator/scripts"
        try:
            shutil.copytree(os.path.expanduser(source), os.path.expanduser(target), dirs_exist_ok=True)
            return f"✅ Despliegue completado de {source} a {target}"
        except Exception as e:
            return f"❌ Error: {e}"

    def cmd_exec_command(self, args):
        if not args:
            return "❌ Uso: /exec_command <comando>"
        cmd = " ".join(args)
        # Bloquear comandos peligrosos
        dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
        for d in dangerous:
            if d in cmd:
                return "⛔ Comando bloqueado por políticas de seguridad."
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout[:500] + ("..." if len(result.stdout) > 500 else "")
            msg = f"```\n{output}\n```"
            if result.stderr:
                msg += f"\n⚠️ Errores:\n```\n{result.stderr[:200]}\n```"
            return msg
        except Exception as e:
            return f"❌ Error: {e}"

    def cmd_help(self, args):
        msg = "📚 **COMANDOS DISPONIBLES**\n\n"
        for cmd in sorted(self.commands.keys()):
            msg += f"• `{cmd}`\n"
        msg += "\n📌 Ejemplos:\n"
        msg += "- `/status` - Estado de proyectos y sistema\n"
        msg += "- `/update_repos` - Actualiza repositorios\n"
        msg += "- `/top_processes` - Procesos con mayor consumo\n"
        msg += "- `/snapshot` - Captura de estado del sistema\n"
        msg += "- `/exec_command comando` - Ejecuta comando shell\n"
        msg += "- `/network_info` - Información de red\n"
        msg += "- `/monitor_status` - Estado del monitor\n"
        msg += "- `/emergency Mensaje` - Alerta de emergencia\n"
        msg += "- `/sync_repo dashboard` - Sincroniza un repo\n"
        msg += "- `/stop_process PID` - Finaliza un proceso\n"
        return msg

    # --- COMANDOS COMPLETADOS (2026-10-02, faltaban en el archivo truncado) ---

    def cmd_snapshot(self, args):
        """Captura completa del estado del sistema en un momento dado."""
        if not PSUTIL_OK:
            return "❌ psutil no instalado (pip install psutil)"
        boot = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
        msg = "📸 **SNAPSHOT DEL SISTEMA**\n\n"
        msg += f"🕘 Ahora: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        msg += f"⏱️ Encendido desde: `{boot}`"
        try:
            up_h = time.time() - psutil.boot_time()
            msg += f" (uptime {up_h/3600:.1f}h)\n"
        except Exception:
            msg += "\n"
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        du = psutil.disk_usage("/")
        msg += f"\n🖥️ CPU: {psutil.cpu_percent()}% ({psutil.cpu_count()} núcleos)"
        msg += f"\n🧠 RAM: {vm.percent}% ({vm.used/1e9:.1f}/{vm.total/1e9:.1f} GB)"
        msg += f"\n🔁 SWAP: {sw.percent}%"
        msg += f"\n💾 DISCO: {du.percent}% ({du.free/1e9:.1f} GB libres)"
        if hasattr(psutil, "sensors_battery"):
            try:
                bat = psutil.sensors_battery()
                if bat:
                    msg += f"\n🔋 BATERÍA: {bat.percent}%"
            except Exception:
                pass
        msg += f"\n\n📦 Procesos activos: {len(psutil.pids())}"
        return msg

    def cmd_network_info(self, args):
        """Información de red del host (interfaces e IP local)."""
        msg = "🌐 **INFORMACIÓN DE RED**\n\n"
        try:
            msg += f"🏠 Hostname: `{socket.gethostname()}`\n"
            # IP local real (UDP trick, no tráfico: solo elige ruta)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            msg += f"📍 IP local: `{local_ip}`\n"
        except Exception as e:
            msg += f"⚠️ IP local no disponible: {e}\n"
        if PSUTIL_OK:
            try:
                stats = psutil.net_if_stats()
                addrs = psutil.net_if_addrs()
                for iface in list(stats)[:6]:
                    if iface == "lo":
                        continue
                    st = stats[iface]
                    ip4 = next((a.address for a in addrs.get(iface, [])
                                if a.family == socket.AF_INET), "?")
                    msg += f"\n🔌 `{iface}`: {ip4} (up, {getattr(st, 'speed', '?')} Mbps)"
            except Exception:
                pass
        return msg

    def cmd_top_processes(self, args):
        """Top 10 procesos por consumo de CPU y RAM."""
        if not PSUTIL_OK:
            return "❌ psutil no instalado (pip install psutil)"
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except Exception:
                continue
        by_cpu = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:10]
        by_mem = sorted(procs, key=lambda x: x.get("memory_percent") or 0, reverse=True)[:10]
        msg = "🔝 **TOP PROCESOS**\n\n*Por CPU:*\n"
        for p in by_cpu:
            msg += f"`{p['pid']}` {p['name'][:18]} — CPU {p['cpu_percent'] or 0:.0f}%\n"
        msg += "\n*Por RAM:*\n"
        for p in by_mem:
            msg += f"`{p['pid']}` {p['name'][:18]} — RAM {p['memory_percent'] or 0:.1f}%\n"
        return msg

    def cmd_monitor_status(self, args):
        """Estado del watchdog del sistema."""
        m = CONFIG["monitor"]
        msg = "🩺 **MONITOR DEL SISTEMA**\n\n"
        msg += f"Estado: {'✅ Activo' if monitor.enabled else '⛔ Detenido'}\n"
        msg += f"Intervalo: `{m['interval']}s`\n"
        msg += f"Umbral CPU: `{m['cpu_threshold']}%`\n"
        msg += f"Umbral RAM: `{m['ram_threshold']}%`\n"
        msg += f"\nAlerta CPU activa: {'⚠️ SÍ' if bot.alert_cpu else 'no'}"
        msg += f"\nAlerta RAM activa: {'⚠️ SÍ' if bot.alert_ram else 'no'}"
        return msg

    def cmd_sync_repo(self, args):
        """Sincroniza (pull+push) un repositorio específico."""
        name = args[0] if args else ""
        if not name or name not in repo_manager.repos:
            disponibles = ", ".join(repo_manager.repos.keys())
            return f"❌ Uso: /sync_repo <nombre> (disponibles: {disponibles})"
        res = repo_manager.sync(name)
        if "error" in str(res):
            return f"❌ **{name}**: error en sync\n```\n{str(res)[:300]}\n```"
        return f"✅ **{name}** sincronizado (pull+push OK)"

telegram_bot_config = {
    "token": CONFIG["telegram"]["bot_token"],
    "chat_id": CONFIG["telegram"]["chat_id"],
}

# ============================================================
# SYSTEM MONITOR (Watchdog)
# ============================================================
class SystemMonitor:
    """Vigila CPU/RAM y alerta por Telegram cuando cruza umbrales."""
    def __init__(self, bot: 'TelegramBot'):
        self.bot = bot
        self.enabled = CONFIG["monitor"]["enabled"] and PSUTIL_OK
        self._stop = threading.Event()

    def start(self):
        if not self.enabled:
            logger.warning("Monitor desactivado (psutil faltante o config off)")
            return
        t = threading.Thread(target=self._loop, daemon=True, name="orch-monitor")
        t.start()
        logger.info("🩺 SystemMonitor activo")

    def _loop(self):
        while not self._stop.is_set():
            try:
                cpu = psutil.cpu_percent(interval=CONFIG["monitor"]["interval"])
                mem = psutil.virtual_memory().percent
                if cpu >= CONFIG["monitor"]["cpu_threshold"] and not self.bot.alert_cpu:
                    self.bot.alert_cpu = True
                    self.bot.send_message(f"⚠️ CPU alta: {cpu}% (umbral {CONFIG['monitor']['cpu_threshold']}%)")
                elif cpu < CONFIG["monitor"]["cpu_threshold"]:
                    self.bot.alert_cpu = False
                if mem >= CONFIG["monitor"]["ram_threshold"] and not self.bot.alert_ram:
                    self.bot.alert_ram = True
                    self.bot.send_message(f"⚠️ RAM alta: {mem}% (umbral {CONFIG['monitor']['ram_threshold']}%)")
                elif mem < CONFIG["monitor"]["ram_threshold"]:
                    self.bot.alert_ram = False
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                self._stop.wait(CONFIG["monitor"]["interval"])
        logger.info("Monitor detenido")

    def stop(self):
        self._stop.set()

# ============================================================
# TELEGRAM POLLING (long-poll en background)
# ============================================================
def telegram_poll_loop(bot: 'TelegramBot'):
    """Loop de getUpdates. Solo corre si hay token+chat_id configurados."""
    offset = 0
    logger.info("Polling de Telegram activo")
    while True:
        try:
            resp = requests.get(
                f"{bot.base_url}/getUpdates",
                params={"timeout": 25, "offset": offset},
                timeout=30,
            )
            data = resp.json()
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                reply = bot.handle_message(message)
                if reply and message.get("chat", {}).get("id"):
                    requests.post(
                        f"{bot.base_url}/sendMessage",
                        json={"chat_id": message["chat"]["id"], "text": reply, "parse_mode": "Markdown"},
                        timeout=10,
                    )
        except requests.RequestException:
            time.sleep(5)  # sin red: reintentar tranquilo
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(10)

# ============================================================
# API REST (Bearer auth)
# ============================================================
app = FastAPI(title="Orchestrator Tool", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_security = HTTPBearer(auto_error=False)

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_security)) -> str:
    if not credentials or credentials.credentials != CONFIG["api"]["secret"]:
        raise HTTPException(status_code=401, detail="No autorizado")
    return "admin"

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "orchestrator",
        "version": "1.0.0",
        "psutil": PSUTIL_OK,
        "telegram": bool(bot.token and bot.chat_id),
        "bind": CONFIG["api"]["host"],
    }

@app.get("/api/repos/status")
async def repos_status(user: str = Depends(require_auth)):
    return repo_manager.get_all_status()

@app.post("/api/repos/{repo_name}/sync")
async def repos_sync(repo_name: str, user: str = Depends(require_auth)):
    if repo_name not in repo_manager.repos:
        raise HTTPException(status_code=404, detail=f"Repo desconocido: {repo_name}")
    return repo_manager.sync(repo_name)

@app.get("/api/system/status")
async def system_status(user: str = Depends(require_auth)):
    if not PSUTIL_OK:
        return {"error": "psutil no instalado"}
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / 1e9, 2),
        "disk_percent": psutil.disk_usage("/").percent,
        "processes": len(psutil.pids()),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
    }

@app.post("/api/exec")
async def api_exec(request: Request, user: str = Depends(require_auth)):
    """Equivalente HTTP de /exec_command — misma política de bloqueo."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    cmd = str(body.get("command", "")).strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="command requerido")
    dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:"]
    for d in dangerous:
        if d in cmd:
            raise HTTPException(status_code=403, detail="Comando bloqueado por políticas de seguridad")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {"code": result.returncode, "stdout": result.stdout[:4000], "stderr": result.stderr[:2000]}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout (30s)")

@app.get("/api/monitor/status")
async def monitor_status(user: str = Depends(require_auth)):
    return {
        "enabled": monitor.enabled,
        "interval": CONFIG["monitor"]["interval"],
        "cpu_threshold": CONFIG["monitor"]["cpu_threshold"],
        "ram_threshold": CONFIG["monitor"]["ram_threshold"],
        "alert_cpu": bot.alert_cpu,
        "alert_ram": bot.alert_ram,
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h3>Orchestrator Tool v1.0 — SourceSeal</h3><p>API: /api/health</p>"

# ============================================================
# MAIN
# ============================================================
bot = TelegramBot()
monitor = SystemMonitor(bot)

def main():
    logger.info("=" * 50)
    logger.info("ORCHESTRATOR TOOL v1.0 — SourceSeal")
    logger.info(f"Bind: {CONFIG['api']['host']}:{CONFIG['api']['port']}")
    logger.info(f"Telegram: {'configurado' if bot.configured() else 'NO configurado (solo API)'}")
    logger.info(f"Allowlist Telegram: {len(bot.allowed_users)} usuario(s)")
    logger.info("=" * 50)

    monitor.start()

    if bot.configured():
        threading.Thread(target=telegram_poll_loop, args=(bot,), daemon=True, name="tg-poll").start()
        bot.send_message("🛠️ Orchestrator Tool v1.0 en línea")
    else:
        logger.warning("Telegram sin configurar — define ORCH_TELEGRAM_BOT_TOKEN, "
                       "ORCH_TELEGRAM_CHAT_ID y ORCH_TELEGRAM_ALLOWED_USERS en .env")

    uvicorn.run(app, host=CONFIG["api"]["host"], port=CONFIG["api"]["port"], log_level="warning")

if __name__ == "__main__":
    main()
