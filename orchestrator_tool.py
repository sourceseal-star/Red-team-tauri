#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Orchestration & System Monitoring Tool v1.1
Author: Harold Paredes / SourceSeal
Description: API de orquestación de repositorios Git y monitoreo de sistema.
SIN bot de Telegram propio: Sol (@sol_amg_bot) es la ÚNICA voz en Telegram.
Esta API corre en background y Sol la consulta por HTTP cuando el usuario
le pide /repos, /reposync o /top — mismo patrón que ya usa con C2 UNIFIED
PRO (:8005) y Nexus (:8004) en sol_telegram_bridge.py.

v1.1 (2026-10-02, Lyra, Regla #73 — CORRECCIÓN de Regla #71): Harold pidió
explícitamente "el bot de Telegram que hay de Sol déjalo, no incluyas más
bots, todo debe manejarlo Sol". La v1.0 que entregué antes traía un bot de
Telegram propio (variables ORCH_TELEGRAM_*) — exactamente lo que NO había
que hacer. Se eliminó por completo: la clase TelegramBot, el polling, el
SystemMonitor con alertas push (Sol ya monitorea proactivamente vía
sol_daemon.py — duplicarlo sería otro sistema paralelo, lo que Harold
tampoco quiere). Lo que queda es puro backend: RepoManager + estado de
sistema + exec, todo expuesto por HTTP con Bearer auth, para que Sol lo
llame bajo demanda igual que hace con los otros servicios internos.
"""

import os
import sys
import json
import subprocess
import socket
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
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
    "api": {
        # Blindaje: 127.0.0.1 por defecto. Para exponer a la LAN:
        # ORCH_BIND_ALL=1 + ORCH_API_SECRET_KEY fuerte en .env.
        "host": "0.0.0.0" if os.environ.get("ORCH_BIND_ALL", "") == "1" else "127.0.0.1",
        "port": int(os.environ.get("ORCH_PORT", "8080")),
        "secret": os.environ.get("ORCH_API_SECRET_KEY", ""),
    },
    "paths": {
        "log_file": os.path.expanduser("~/.orchestrator.log"),
    },
}

# Fail-closed: exponer a toda la LAN sin clave es un agujero (el API tiene
# /api/exec). Nos negamos a arrancar así.
if CONFIG["api"]["host"] == "0.0.0.0" and not CONFIG["api"]["secret"]:
    sys.exit("[ORCH] FATAL: ORCH_BIND_ALL=1 requiere ORCH_API_SECRET_KEY en .env")

# Sin clave y en localhost: se genera una por arranque (solo útil localmente,
# y de todas formas Sol necesita conocer la real vía ORCH_API_SECRET_KEY
# en el .env compartido para poder llamar a /api/repos, /api/exec, etc).
if not CONFIG["api"]["secret"]:
    import secrets as _secrets
    CONFIG["api"]["secret"] = _secrets.token_urlsafe(24)
    print(f"[ORCH] ORCH_API_SECRET_KEY no configurada — clave efímera "
          f"generada para esta sesión (localhost only): {CONFIG['api']['secret'][:8]}... "
          f"Define ORCH_API_SECRET_KEY en .env para que Sol pueda autenticarse.")

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
        return {
            "branch": branch.get("stdout", "unknown"),
            "has_changes": bool(status.get("stdout", "")),
            "changes": status.get("stdout", ""),
            "error": status.get("error") or branch.get("error")
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
        return {name: self.get_status(name) for name in self.repos if self.repos[name].get("enabled", True)}

    def sync_all(self) -> Dict:
        return {name: self.sync(name) for name in self.repos if self.repos[name].get("enabled", True)}

repo_manager = RepoManager()

# ============================================================
# API REST (Bearer auth) — Sol es el único cliente de Telegram.
# ============================================================
app = FastAPI(title="Orchestrator Tool", version="1.1.0")
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
        "version": "1.1.0",
        "psutil": PSUTIL_OK,
        "bind": CONFIG["api"]["host"],
        "repos": list(CONFIG["repos"].keys()),
    }

@app.get("/api/repos/status")
async def repos_status(user: str = Depends(require_auth)):
    return repo_manager.get_all_status()

@app.post("/api/repos/{repo_name}/sync")
async def repos_sync(repo_name: str, user: str = Depends(require_auth)):
    if repo_name not in repo_manager.repos:
        raise HTTPException(status_code=404, detail=f"Repo desconocido: {repo_name}")
    return repo_manager.sync(repo_name)

@app.post("/api/repos/sync-all")
async def repos_sync_all(user: str = Depends(require_auth)):
    return repo_manager.sync_all()

@app.get("/api/system/status")
async def system_status(user: str = Depends(require_auth)):
    """Estado puntual bajo demanda. El monitoreo PROACTIVO/push de alertas
    es responsabilidad de sol_daemon.py — este endpoint no duplica eso."""
    if not PSUTIL_OK:
        return {"error": "psutil no instalado"}
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / 1e9, 2),
        "ram_total_gb": round(vm.total / 1e9, 2),
        "swap_percent": sw.percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "processes": len(psutil.pids()),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
    }

@app.get("/api/system/top")
async def system_top(user: str = Depends(require_auth)):
    """Top 10 procesos por CPU y por RAM."""
    if not PSUTIL_OK:
        return {"error": "psutil no instalado"}
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except Exception:
            continue
    by_cpu = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:10]
    by_mem = sorted(procs, key=lambda x: x.get("memory_percent") or 0, reverse=True)[:10]
    return {"by_cpu": by_cpu, "by_mem": by_mem}

@app.post("/api/exec")
async def api_exec(request: Request, user: str = Depends(require_auth)):
    """Equivalente HTTP del /exec_command original del diseño de Harold."""
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

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h3>Orchestrator Tool v1.1 — SourceSeal</h3><p>API interna. Habla con Sol en Telegram: /repos /reposync /top</p>"

# ============================================================
# MAIN
# ============================================================
def main():
    logger.info("=" * 50)
    logger.info("ORCHESTRATOR TOOL v1.1 — SourceSeal (API-only, sin bot propio)")
    logger.info(f"Bind: {CONFIG['api']['host']}:{CONFIG['api']['port']}")
    logger.info("Consultado por Sol (@sol_amg_bot) vía HTTP — sin Telegram propio")
    logger.info("=" * 50)
    uvicorn.run(app, host=CONFIG["api"]["host"], port=CONFIG["api"]["port"], log_level="warning")

if __name__ == "__main__":
    main()
