#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_repo_tools.py — Herramientas de gestión de repositorios para Sol.

Permite a Sol gestionar los 3 repositorios de Harold:
  1. sourceseal-star/sol (este repo — el cerebro y cuerpo de Sol)
  2. sourceseal-star/Red-team-tauri (dashboard, COM-LINK, War Room, frontend)
  3. sourceseal-star/commander (COMMANDER v3.4.1 — suite táctica standalone,
     NO es el subdirectorio commander/ dentro de Red-team-tauri, es un repo
     separado con su propio historial y codigo)

Funciones disponibles:
  - repo_status: estado de git (branch, cambios, últimos commits)
  - repo_pull: git pull en un repo
  - repo_log: historial de commits
  - repo_list_files: listar archivos
  - repo_read_file: leer un archivo del repo
  - repo_commit: commit + push de cambios locales
  - repo_run: ejecutar un comando en el directorio del repo

Usa GITHUB_ACCESS_TOKEN para operaciones via API GitHub
y también soporta git local si el repo está clonado.
"""

import os
import json
import subprocess
import urllib.request
from pathlib import Path

GITHUB_TOKEN = os.environ.get("GITHUB_ACCESS_TOKEN", "")
GITHUB_API = "https://api.github.com"

# Directorio real donde vive ESTE script. En Replit, el repo puede estar
# desplegado en su propia raíz (no clonado en ~/sol). Si este proceso tiene
# un .git válido en su directorio, usamos esa ruta como fallback.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths donde pueden estar los repos localmente (Replit/Termux)
REPO_PATHS = {
    "sol": os.path.expanduser("~/sol"),
    "red-team-tauri": os.path.expanduser("~/Red-team-tauri"),
    "redteam": os.path.expanduser("~/Red-team-tauri"),  # alias
    "commander": os.path.expanduser("~/commander"),  # repo standalone, NO subdirectorio
}


def _self_repo_path():
    """Si este script vive dentro de un repo git válido, devuelve su
    directorio. En Replit Red-team-tauri, sol_api.py corre desde la raíz
    del repo, no desde ~/sol — antes no se encontraba a si mismo."""
    if os.path.isdir(os.path.join(SCRIPT_DIR, ".git")):
        return SCRIPT_DIR
    return None

# Mapping de nombres locales a nombres en GitHub
GITHUB_REPOS = {
    "sol": "sourceseal-star/sol",
    "red-team-tauri": "sourceseal-star/Red-team-tauri",
    "redteam": "sourceseal-star/Red-team-tauri",
    "commander": "sourceseal-star/commander",  # repo standalone (COMMANDER v3.4.1)
}


def _get_repo_path(name):
    """Encuentra el path local del repo o None."""
    name = name.lower().strip()
    for key, path in REPO_PATHS.items():
        if key == name:
            if os.path.isdir(path):
                return path
    # Auto-detección: si preguntan por 'sol' y ESTE script corre dentro
    # de un repo git válido (ej. Red-team-tauri en Replit), úsalo.
    if name == "sol":
        self_path = _self_repo_path()
        if self_path:
            return self_path
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, name),
        os.path.join(home, name.replace("-", "_")),
        os.path.join(home, "sourceseal-star", name),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def _api_get(path):
    if not GITHUB_TOKEN:
        return None, "GITHUB_ACCESS_TOKEN no configurado"
    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return resp, None
    except Exception as e:
        return None, str(e)


def _api_post(path, method="POST", body=None):
    if not GITHUB_TOKEN:
        return None, "GITHUB_ACCESS_TOKEN no configurado"
    url = f"{GITHUB_API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    })
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return resp, None
    except Exception as e:
        return None, str(e)


def _git(repo_path, *args):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + list(args),
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1


def repo_status(name="sol"):
    """Estado de un repo."""
    path = _get_repo_path(name)
    if path:
        branch, _, _ = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
        status_out, _, _ = _git(path, "status", "--porcelain")
        dirty = len(status_out.splitlines()) if status_out else 0
        log, _, _ = _git(path, "log", "--oneline", "-5")
        return {
            "repo": name,
            "path": path,
            "branch": branch or "unknown",
            "dirty_files": dirty,
            "recent_commits": log.splitlines()[:5] if log else [],
            "source": "local",
        }

    gh_repo = GITHUB_REPOS.get(name.lower())
    if not gh_repo:
        return {"error": f"Repo '{name}' no reconocido. Disponibles: {list(GITHUB_REPOS.keys())}"}

    data, err = _api_get(f"/repos/{gh_repo}")
    if err:
        return {"error": err}

    commits_data, _ = _api_get(f"/repos/{gh_repo}/commits?per_page=5")
    recent = []
    if commits_data:
        for c in commits_data[:5]:
            recent.append(f"{c['sha'][:10]} {c['commit']['message'].split(chr(10))[0][:60]}")

    return {
        "repo": name,
        "github": gh_repo,
        "branch": data.get("default_branch", "main"),
        "pushed_at": data.get("pushed_at", "?"),
        "recent_commits": recent,
        "source": "github-api",
    }


def repo_pull(name="sol"):
    """Git pull en un repo local."""
    path = _get_repo_path(name)
    if not path:
        return {"error": f"Repo '{name}' no encontrado localmente."}
    out, err, rc = _git(path, "pull", "--rebase", "origin", "main")
    return {
        "repo": name, "path": path,
        "success": rc == 0,
        "output": out,
        "error": err if rc != 0 else None,
    }


def repo_log(name="sol", count=10):
    """Historial de commits."""
    path = _get_repo_path(name)
    if path:
        out, _, _ = _git(path, "log", "--oneline", f"-{count}", "--format=%h %ai %s")
        commits = []
        for line in out.splitlines():
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                commits.append({"hash": parts[0], "date": parts[1], "message": parts[2][:80]})
            elif len(parts) == 2:
                commits.append({"hash": parts[0], "message": parts[1][:80]})
        return {"repo": name, "commits": commits, "source": "local"}

    gh_repo = GITHUB_REPOS.get(name.lower())
    if not gh_repo:
        return {"error": f"Repo '{name}' no reconocido"}
    data, err = _api_get(f"/repos/{gh_repo}/commits?per_page={count}")
    if err:
        return {"error": err}
    commits = []
    for c in data[:count]:
        commits.append({
            "hash": c["sha"][:10],
            "date": c["commit"]["author"]["date"],
            "author": c["commit"]["author"]["name"],
            "message": c["commit"]["message"].split("\n")[0][:80],
        })
    return {"repo": name, "commits": commits, "source": "github-api"}


def repo_list_files(name="sol", path=""):
    """Lista archivos de un repo via GitHub API."""
    gh_repo = GITHUB_REPOS.get(name.lower())
    if not gh_repo:
        return {"error": f"Repo '{name}' no reconocido"}
    api_path = f"/repos/{gh_repo}/contents/{path}" if path else f"/repos/{gh_repo}/contents"
    data, err = _api_get(api_path)
    if err:
        return {"error": err}
    files = []
    for item in data:
        files.append({
            "name": item["name"],
            "type": item["type"],
            "size": item.get("size", 0),
            "path": item["path"],
        })
    return {"repo": name, "path": path, "files": files}


def repo_read_file(name="sol", filepath=""):
    """Lee un archivo de un repo."""
    local_path = _get_repo_path(name)
    if local_path:
        full = os.path.join(local_path, filepath)
        if os.path.isfile(full):
            with open(full) as f:
                content = f.read()
            return {"repo": name, "file": filepath, "content": content, "source": "local"}

    gh_repo = GITHUB_REPOS.get(name.lower())
    if not gh_repo:
        return {"error": f"Repo '{name}' no reconocido"}
    data, err = _api_get(f"/repos/{gh_repo}/contents/{filepath}")
    if err:
        return {"error": err}
    if data.get("encoding") == "base64":
        import base64
        content = base64.b64decode(data["content"]).decode()
    else:
        content = data.get("content", "")
    return {
        "repo": name, "file": filepath,
        "content": content,
        "size": data.get("size", len(content)),
        "source": "github-api",
    }


def repo_commit(name="sol", message="", filepath=None, content=None):
    """Crea o actualiza un archivo en un repo."""
    gh_repo = GITHUB_REPOS.get(name.lower())
    if not gh_repo:
        return {"error": f"Repo '{name}' no reconocido"}

    local_path = _get_repo_path(name)
    if local_path and filepath:
        full = os.path.join(local_path, filepath)
        d = os.path.dirname(full)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(full, 'w') as f:
            f.write(content)
        _git(local_path, "add", filepath)
        _git(local_path, "commit", "-m", message)
        out, err, rc = _git(local_path, "push", "origin", "main")
        return {"repo": name, "file": filepath, "success": rc == 0, "output": out, "error": err if rc else None}

    if not filepath or content is None:
        return {"error": "filepath y content son requeridos"}

    existing, _ = _api_get(f"/repos/{gh_repo}/contents/{filepath}")
    sha = existing.get("sha") if existing and isinstance(existing, dict) else None

    import base64 as b64mod
    payload = {
        "message": message,
        "content": b64mod.b64encode(content.encode()).decode(),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    result, err = _api_post(f"/repos/{gh_repo}/contents/{filepath}", method="PUT", body=payload)
    if err:
        return {"error": err}
    return {
        "repo": name, "file": filepath, "success": True,
        "commit": result.get("commit", {}).get("sha", "")[:10],
    }


def repo_run(name="sol", command=""):
    """Ejecuta un comando en el directorio del repo (solo local)."""
    path = _get_repo_path(name)
    if not path:
        return {"error": f"Repo '{name}' no encontrado localmente."}

    allowed = [
        "git ", "python3 ", "python ", "pip ", "ls ", "cat ", "grep ",
        "find ", "wc ", "head ", "tail ", "echo ", "pwd", "bash -n ",
        "npm ", "node ", "tsc ", "pytest", "shellcheck ",
    ]
    safe = any(command.startswith(p) for p in allowed)
    if not safe:
        return {"error": "Comando no permitido por seguridad"}

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=path
        )
        return {
            "repo": name, "command": command,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500] if result.stderr else "",
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Comando tardó más de 30s. Cancelado."}
    except Exception as e:
        return {"error": str(e)}


def list_repos():
    """Lista los repos disponibles."""
    repos = []
    for name in ["sol", "red-team-tauri", "commander"]:
        info = {"name": name, "github": GITHUB_REPOS.get(name)}
        path = _get_repo_path(name)
        info["local"] = bool(path)
        info["path"] = path
        if GITHUB_TOKEN:
            data, _ = _api_get(f"/repos/{GITHUB_REPOS.get(name)}")
            if data:
                info["branch"] = data.get("default_branch", "main")
                info["pushed_at"] = data.get("pushed_at", "?")
                info["private"] = data.get("private", True)
        repos.append(info)
    return repos


def status():
    return {
        "github_token": bool(GITHUB_TOKEN),
        "repos": list_repos(),
    }
