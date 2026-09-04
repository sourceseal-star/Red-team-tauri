#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_tools.py — Herramientas completas de Sol v7 (sin límites).

Hereda la estructura de sol_tools v5 y añade:
- search_code: buscar en los 3 repos
- git_commit: commit + push en repos permitidos
- git_verify: verificar estado del repositorio
- investigate_and_commit: buscar → commit → verificar
- create_file / edit_file / delete_file: gestión de archivos
- translate: zh↔es con pinyin
- explain_code: explicar código con pedagogía
- curl / check_port: red
- 20+ herramientas totales
"""

import os
import subprocess
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================
# REPOSITORIOS PERMITIDOS
# ============================================================
SOL_HOME = Path.home() / ".sol"
TOOLS_DIR = SOL_HOME / "tools"
try:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
except Exception as _mkdir_err:
    print(f"[sol_tools] No se pudo crear {TOOLS_DIR}: {_mkdir_err}")

ALLOWED_REPOS = {
    "sol": Path(os.environ.get("SOL_DIR", str(Path.home() / "sol"))),
    "redteam": Path(os.environ.get("REDTEAM_DIR", str(Path.home() / "Red-team-tauri"))),
    "commander": Path(os.environ.get("COMMANDER_DIR", str(Path.home() / "commander")))
}

# ============================================================
# COMANDOS PERMITIDOS (whitelist de seguridad)
# ============================================================
ALLOWED_COMMANDS = {
    "ls", "pwd", "cat", "head", "tail", "grep", "find", "wc",
    "git", "python3", "curl", "ping", "df", "free", "ps", "top",
    "chmod", "chown", "mkdir", "rmdir", "cp", "mv"
}

# ============================================================
# LOG
# ============================================================
def log(msg: str):
    f = SOL_HOME / "tools.log"
    try:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"\n{msg}")
    except Exception:
        pass

# ============================================================
# CLASE Tool (preservada de v5 para compatibilidad)
# ============================================================
class Tool:
    def __init__(self, name, description, func, params=None):
        self.name = name
        self.description = description
        self.func = func
        self.params = params or []

    def execute(self, *args, **kwargs):
        try:
            return self.func(*args, **kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================================
# UTILIDADES
# ============================================================
def _get_repo(name: str) -> Optional[Path]:
    # Mapear nombres alternativos
    name_map = {"redteam": "redteam", "red-team-tauri": "redteam", "Red-team-tauri": "redteam",
                "sol": "sol", "commander": "commander"}
    key = name_map.get(name, name)
    path = ALLOWED_REPOS.get(key)
    if path and path.exists():
        return path
    # Auto-detección: si el path configurado (o su default) no existe,
    # pregunta a sol_repo_tools si ESTE proceso está corriendo desde
    # dentro de ese mismo repo (comparando el remote origin de git).
    # Cubre Replit: sol_api.py embebido en Red-team-tauri sin REDTEAM_DIR.
    try:
        import sol_repo_tools as _srt
        detected_key, detected_path = _srt._detect_self_repo()
        if detected_path and detected_key == key:
            return Path(detected_path)
    except Exception:
        pass
    return path

def _run_git(repo: Path, *args) -> Dict:
    if not repo or not repo.exists():
        return {"ok": False, "error": "Repositorio no existe"}
    cmd = ["git", "-C", str(repo)] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {"ok": result.returncode == 0, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _is_safe_path(path: str) -> bool:
    """Verifica que la ruta esté dentro de repos permitidos."""
    try:
        p = Path(path).resolve()
        for repo in ALLOWED_REPOS.values():
            if repo:
                try:
                    if p.is_relative_to(repo.resolve()):
                        return True
                except AttributeError:
                    # Python < 3.9 fallback
                    if str(p).startswith(str(repo.resolve())):
                        return True
        return False
    except Exception:
        return False

# ============================================================
# 1. BÚSQUEDA DE CÓDIGO
# ============================================================
def search_code(query: str, limit: int = 20) -> List[str]:
    results = []
    for name, repo in ALLOWED_REPOS.items():
        if not repo or not repo.exists():
            continue
        try:
            cmd = ["grep", "-rin", "--include=*.py", "--include=*.md", "--include=*.sh", query[:60], str(repo)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = proc.stdout.splitlines()[:limit // 3]
            for line in lines:
                if len(line) > 200:
                    line = line[:200] + "..."
                results.append(f"[{name}] {line}")
        except Exception:
            continue
    return results[:limit]

# ============================================================
# 2. GIT COMMIT + PUSH
# ============================================================
def git_commit(repo_name: str, message: str, paths: str = ".") -> Dict:
    repo = _get_repo(repo_name)
    if not repo or not repo.exists():
        return {"ok": False, "error": f"Repositorio '{repo_name}' no encontrado"}
    add = _run_git(repo, "add", "--", paths, ":(exclude).env", ":(exclude)*.aes", ":(exclude)*.key")
    if not add["ok"]:
        return add
    _run_git(repo, "restore", "--staged", ".env")
    commit = _run_git(repo, "commit", "-m", message)
    if not commit["ok"]:
        return commit
    branch = _run_git(repo, "branch", "--show-current")["stdout"] or "main"
    push = _run_git(repo, "push", "origin", branch)
    if not push["ok"]:
        return push
    rev = _run_git(repo, "rev-parse", "--short", "HEAD")
    return {"ok": True, "commit": rev.get("stdout", "unknown"), "message": message, "repo": repo_name}

# ============================================================
# 3. VERIFICAR REPOSITORIO
# ============================================================
def git_verify(repo_name: str) -> Dict:
    repo = _get_repo(repo_name)
    if not repo:
        return {"ok": False, "error": f"Repositorio '{repo_name}' no permitido"}
    status = _run_git(repo, "status", "--short")
    log_cmd = _run_git(repo, "log", "-1", "--oneline")
    branch = _run_git(repo, "branch", "--show-current")
    return {"ok": True, "clean": status.get("stdout", "") == "", "status": status.get("stdout", "limpio"),
            "last_commit": log_cmd.get("stdout", "sin commits"), "branch": branch.get("stdout", "desconocida")}

# ============================================================
# 4. INVESTIGAR Y COMMIT
# ============================================================
def investigate_and_commit(query: str, repo_name: str, message: str = None) -> Dict:
    if not message:
        message = f"🔍 Investigación: {query[:50]}"
    findings = search_code(query, limit=10)
    if not findings:
        return {"ok": False, "error": "No se encontraron resultados", "findings": []}
    commit_result = git_commit(repo_name, message)
    if not commit_result.get("ok"):
        return {"ok": False, "error": commit_result.get("error"), "findings": findings}
    verify = git_verify(repo_name)
    return {"ok": True, "findings": findings[:5], "commit": commit_result.get("commit"), "verified": verify}

# ============================================================
# 5. CREAR ARCHIVO
# ============================================================
def create_file(repo_name: str, path: str, content: str) -> Dict:
    repo = _get_repo(repo_name)
    if not repo:
        return {"ok": False, "error": "Repositorio no permitido"}
    full_path = repo / path
    if not _is_safe_path(str(full_path)):
        return {"ok": False, "error": "Ruta fuera de repos permitidos"}
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(full_path.relative_to(repo)), "size": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 6. EDITAR ARCHIVO (append)
# ============================================================
def edit_file(repo_name: str, path: str, content: str) -> Dict:
    repo = _get_repo(repo_name)
    if not repo:
        return {"ok": False, "error": "Repositorio no permitido"}
    full_path = repo / path
    if not _is_safe_path(str(full_path)):
        return {"ok": False, "error": "Ruta fuera de repos permitidos"}
    if not full_path.exists():
        return {"ok": False, "error": "Archivo no existe"}
    try:
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(full_path.relative_to(repo)), "appended": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 7. LEER ARCHIVO
# ============================================================
def read_file(repo_name: str, path: str, lines: int = None) -> Dict:
    repo = _get_repo(repo_name)
    if not repo:
        return {"ok": False, "error": "Repositorio no permitido"}
    full_path = repo / path
    if not _is_safe_path(str(full_path)):
        return {"ok": False, "error": "Ruta fuera de repos permitidos"}
    if not full_path.exists():
        return {"ok": False, "error": "Archivo no existe"}
    try:
        content = full_path.read_text(encoding="utf-8")
        if lines:
            content = "\n".join(content.splitlines()[:lines])
        return {"ok": True, "content": content, "size": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 8. LISTAR DIRECTORIO
# ============================================================
def list_directory(repo_name: str, path: str = ".") -> Dict:
    repo = _get_repo(repo_name)
    if not repo:
        return {"ok": False, "error": "Repositorio no permitido"}
    full_path = repo / path
    if not _is_safe_path(str(full_path)):
        return {"ok": False, "error": "Ruta fuera de repos permitidos"}
    if not full_path.exists():
        return {"ok": False, "error": "Directorio no existe"}
    try:
        items = []
        for item in full_path.iterdir():
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        return {"ok": True, "items": items, "count": len(items)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 9. EJECUTAR COMANDO (whitelist)
# ============================================================
def run_command(command: str, cwd: str = None) -> Dict:
    parts = command.split()
    if not parts:
        return {"ok": False, "error": "Comando vacío"}
    base_cmd = parts[0]
    if base_cmd not in ALLOWED_COMMANDS:
        return {"ok": False, "error": f"Comando '{base_cmd}' no permitido. Permitidos: {sorted(ALLOWED_COMMANDS)}"}
    
    if cwd:
        if not _is_safe_path(cwd):
            return {"ok": False, "error": "Directorio de trabajo fuera de repos permitidos"}
    
    try:
        result = subprocess.run(parts, capture_output=True, text=True, timeout=30, cwd=cwd)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[:1000],
            "stderr": result.stderr[:500],
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout (30s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 10. RED
# ============================================================
def ping(host: str, count: int = 4) -> Dict:
    try:
        result = subprocess.run(["ping", "-c", str(count), host], capture_output=True, text=True, timeout=10)
        return {"ok": result.returncode == 0, "output": result.stdout}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def curl(url: str, method: str = "GET") -> Dict:
    try:
        result = subprocess.run(["curl", "-s", "-X", method, url], capture_output=True, text=True, timeout=10)
        return {"ok": result.returncode == 0, "output": result.stdout[:2000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_port(host: str, port: int) -> Dict:
    try:
        result = subprocess.run(["nc", "-zv", host, str(port)], capture_output=True, text=True, timeout=5)
        return {"ok": result.returncode == 0, "open": result.returncode == 0}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 11. EXPLICAR CÓDIGO (con pedagogía)
# ============================================================
def explain_code(code: str, language: str = "python") -> Dict:
    """Explica código con el estilo pedagógico heredado."""
    try:
        from sol_pedagogy import explain_with_pedagogy
        explanation = f"Este código en {language} hace lo siguiente:\n\n"
        return {
            "ok": True,
            "explanation": explain_with_pedagogy(
                f"explicar código {language}",
                explanation,
                code
            )
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ============================================================
# 12. TRADUCCIÓN CON PINYIN
# ============================================================
def translate(text: str, target_lang: str = "es") -> Dict:
    try:
        from sol_knowledge import translate_to_chinese, get_pinyin
    except ImportError:
        return {"error": "Módulo sol_knowledge no disponible"}
    if target_lang == "zh":
        chinese = translate_to_chinese(text)
        pinyin = get_pinyin(chinese) if chinese else ""
        return {"original": text, "chinese": chinese, "pinyin": pinyin}
    else:
        return {"original": text, "spanish": "[Traducción al español]"}

# ============================================================
# 13. MEMORIA
# ============================================================
def memory_stats() -> Dict:
    mem_file = Path.home() / ".sol" / "memory.jsonl"
    if not mem_file.exists():
        return {"count": 0}
    lines = mem_file.read_text().splitlines()
    return {"count": len(lines), "file": str(mem_file)}

def search_memory(query: str, limit: int = 10) -> Dict:
    mem_file = Path.home() / ".sol" / "memory.jsonl"
    if not mem_file.exists():
        return {"results": []}
    query_lower = query.lower()
    results = []
    for line in mem_file.read_text().splitlines():
        if query_lower in line.lower():
            results.append(line)
            if len(results) >= limit:
                break
    return {"results": results, "count": len(results)}

# ============================================================
# ECOSYSTEM — info de los 3 repos (preservado de v5)
# ============================================================
ECOSYSTEM = {
    "sol": {
        "path": ALLOWED_REPOS["sol"],
        "github": "sourceseal-star/sol",
        "desc": "Sol standalone (Replit) — cerebro + API + SIL",
    },
    "redteam": {
        "path": ALLOWED_REPOS["redteam"],
        "github": "sourceseal-star/Red-team-tauri",
        "desc": "Tower TACTICAL — dashboard, KRAKEN, GHOST, ARTO",
    },
    "commander": {
        "path": ALLOWED_REPOS["commander"],
        "github": "sourceseal-star/commander",
        "desc": "Suite de auditoría — COM-LINK, OSIRIS, TACTICAL",
    },
}

def tool_repos_info() -> str:
    """Información del ecosistema de 3 repos (preservado para sol_core.py).

    FIX 2026-09-02 (Seal IA): antes usaba ECOSYSTEM con rutas fijas
    (~/sol, ~/Red-team-tauri, ~/commander) que NUNCA detectaban a Sol
    a si misma en Replit -- ahi el codigo de sol_api.py corre DESDE
    DENTRO del repo 'sol' (no clonado en ~/sol), asi que siempre decia
    "sol: ... (no clonado aqui)" incluso sobre su propio repo. Ahora
    reusa sol_repo_tools.list_repos(), que SI tiene la deteccion real
    via _detect_self_repo() (compara el remote git contra GITHUB_REPOS)
    ademas de fallback a la API publica de GitHub cuando no hay clon local.
    """
    lines = ["📦 Mi ecosistema — 3 repos:"]
    try:
        import sol_repo_tools
        repos = sol_repo_tools.list_repos()
        descs = {
            "sol": "Sol standalone — cerebro + API + SIL",
            "red-team-tauri": "Tower TACTICAL — dashboard, KRAKEN, GHOST, ARTO",
            "commander": "Suite de auditoría — COM-LINK, OSIRIS, TACTICAL",
        }
        for r in repos:
            name = r.get("name", "?")
            github = r.get("github", "?")
            local_path = r.get("path")  # ruta real (string) o None
            icon = "✅" if local_path else "☁️"
            lines.append(f"  {icon} {name}: {github} — {descs.get(name, '')}")
            if local_path:
                lines.append(f"     📁 {local_path}")
            elif r.get("pushed_at"):
                lines.append(f"     ☁️ vía API GitHub (push más reciente: {r['pushed_at'][:10]})")
            else:
                lines.append(f"     📁 {github} (no clonado aquí, sin acceso a API)")
        return "\n".join(lines)
    except Exception as _e:
        # Fallback defensivo: si sol_repo_tools no importa por algún motivo,
        # usar la tabla vieja en vez de romper el flujo de chat.
        for name, info in ECOSYSTEM.items():
            path = info["path"]
            exists = path.exists() if path else False
            icon = "✅" if exists else "⚪"
            lines.append(f"  {icon} {name}: {info['github']} — {info['desc']}")
            lines.append(f"     📁 {path if exists else info['github'] + ' (no clonado aquí)'}")
        lines.append(f"\n⚠️ (fallback — sol_repo_tools no disponible: {_e})")
        return "\n".join(lines)

# ============================================================
# TOOLS REGISTRY — 25+ herramientas (v5 preservadas + v7 nuevas)
# ============================================================
def tool_read_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ Archivo no existe: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 2000:
            content = content[:2000] + f"\n... (truncado, total: {len(content)} bytes)"
        return content
    except Exception as e:
        return f"❌ Error: {e}"

def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Escrito: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"❌ Error: {e}"

def tool_list_dir(path: str = ".") -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"❌ No existe: {path}"
        items = []
        for item in sorted(p.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            size = f" ({item.stat().st_size}b)" if item.is_file() else ""
            items.append(f"  {icon} {item.name}{size}")
        return f"📂 {path} ({len(items)} items):\n" + "\n".join(items[:50])
    except Exception as e:
        return f"❌ Error: {e}"

def tool_find_files(pattern: str, path: str = ".") -> str:
    try:
        result = subprocess.run(["find", path, "-name", pattern, "-not", "-path", "*/.git/*",
                                  "-not", "-path", "*/node_modules/*", "-not", "-path", "*/__pycache__/*"],
                                 capture_output=True, text=True, timeout=10)
        files = result.stdout.strip().splitlines()[:30]
        return f"🔍 Encontrados {len(files)} archivos:\n" + "\n".join(files) if files else "❌ Nada encontrado"
    except Exception as e:
        return f"❌ Error: {e}"

def tool_battery() -> str:
    try:
        result = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return f"🔋 Batería: {data.get('percentage', '?')}% — {data.get('status', '?')}"
        return "🔋 Batería: no disponible (requiere Termux:API — escribe «diagnóstico» y te digo exactamente qué falta)"
    except Exception:
        return "🔋 Batería: no disponible"

def tool_location() -> str:
    try:
        result = subprocess.run(["termux-location"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return f"📍 GPS: {data.get('latitude', '?')}, {data.get('longitude', '?')}"
        return "📍 GPS: no disponible"
    except Exception:
        return "📍 GPS: no disponible"

def tool_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        h = int(secs // 3600); m = int((secs % 3600) // 60)
        return f"⏱️ Uptime: {h}h {m}m"
    except Exception:
        return "⏱️ Uptime: no disponible"

def tool_cpu() -> str:
    try:
        result = subprocess.run(["top", "-bn1"], capture_output=True, text=True, timeout=5)
        line = [l for l in result.stdout.splitlines() if "%Cpu" in l or "CPU:" in l]
        return f"🖥️ CPU: {line[0] if line else 'no disponible'}"
    except Exception:
        return "🖥️ CPU: no disponible"

def tool_ping(host: str) -> str:
    try:
        result = subprocess.run(["ping", "-c", "4", host], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            stats = [l for l in result.stdout.splitlines() if "rtt" in l or "round-trip" in l]
            return f"📡 Ping {host}: ✅ {stats[0] if stats else 'OK'}"
        return f"📡 Ping {host}: ❌ Sin respuesta"
    except Exception as e:
        return f"📡 Ping {host}: ❌ {e}"

def _scan_ports_socket(host: str) -> str:
    """Fallback puro-Python cuando nmap no está instalado (ej. Replit).
    Escanea un set corto de puertos comunes con sockets TCP — más lento
    que nmap pero no depende de ningún binario del sistema."""
    import socket
    common_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 587,
                     993, 995, 3000, 3306, 5000, 5432, 5900, 6379, 8000,
                     8001, 8080, 8443, 8888, 27017]
    open_ports = []
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.6)
            if s.connect_ex((host, port)) == 0:
                open_ports.append(port)
            s.close()
        except Exception:
            continue
    if open_ports:
        return f"🔍 Puertos {host} (fallback socket, sin nmap): abiertos {open_ports}"
    return f"🔍 Puertos {host} (fallback socket, sin nmap): ninguno de los {len(common_ports)} puertos comunes respondió"

def tool_scan_ports(host: str) -> str:
    try:
        result = subprocess.run(["nmap", "-sT", "-F", host], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"🔍 Puertos {host}:\n{result.stdout[:1000]}"
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return _scan_ports_socket(host)

def tool_send_sms(number: str, message: str) -> str:
    """Envía un SMS real vía termux-api — con la misma honestidad que la linterna:
    dice exactamente qué pasó y por qué, nunca un error genérico."""
    if not _termux_ready('termux-sms-send'):
        return ("📱 SMS: no disponible aquí — el comando termux-sms-send no existe "
                "en este entorno. Solo puedo enviar SMS reales corriendo en Termux "
                "en tu Edge 50 (en Replit no hay teléfono). Escribe «diagnóstico» "
                "y te digo exactamente qué falta.")
    try:
        result = subprocess.run(["termux-sms-send", "-n", number, message],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"📱 SMS enviado a {number}"
        err = (result.stderr or result.stdout or '').strip()[:300]
        return (f"❌ SMS falló (exit {result.returncode}): "
                f"{err or 'la app Termux:API no respondió — puede ser el permiso de SMS o la batería optimizándola (ver docs/TERMUX_API_SALUD.md en Red-team-tauri)'}")
    except subprocess.TimeoutExpired:
        return ("❌ SMS: la app Termux:API no respondió en 15s — síntoma clásico de "
                "desincronización CLI↔app. Cura: docs/TERMUX_API_SALUD.md (repo Red-team-tauri)")
    except Exception as e:
        return f"❌ SMS error inesperado: {e}"

def tool_notify(text: str) -> str:
    try:
        subprocess.run(["termux-notification", "--title", "☀️ Sol", "--content", text[:200]], timeout=5)
        return "🔔 Notificación enviada"
    except Exception:
        return "🔔 Notificación: no disponible"

def tool_open_url(url: str) -> str:
    try:
        subprocess.run(["termux-open-url", url], timeout=5)
        return f"🔗 Abriendo: {url}"
    except Exception:
        return f"🔗 No se pudo abrir: {url}"

def tool_open_whatsapp(number: str, message: str = "") -> str:
    """Abre WhatsApp con un chat y mensaje precargados (via wa.me).
    IMPORTANTE: esto NO envía el mensaje solo — wa.me abre la conversación
    con el texto ya escrito, pero WhatsApp exige que un humano toque el
    botón de enviar. Sol nunca debe decir que "lo envió" si solo hizo esto."""
    import urllib.parse
    clean_number = "".join(c for c in number if c.isdigit() or c == "+")
    if not clean_number:
        return "❌ Número inválido"
    url = f"https://wa.me/{clean_number.lstrip('+')}"
    if message:
        url += f"?text={urllib.parse.quote(message)}"
    try:
        subprocess.run(["termux-open", url], capture_output=True, timeout=5, check=True)
        return f"✅ Abrí WhatsApp con el chat de {clean_number} y el mensaje listo — falta que le doy Enviar (eso no lo puedo tocar yo)."
    except Exception as e:
        return f"❌ No pude abrir WhatsApp (¿este proceso corre en Termux, en el teléfono? aquí no hay termux-open): {e}"

def tool_flashlight(on: bool = True) -> str:
    try:
        result = subprocess.run(
            ["termux-torch", "on" if on else "off"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"🔦 Linterna: {'encendida' if on else 'apagada'}"
        # El comando existe pero falló → casi siempre falta la APP Termux:API
        err = (result.stderr or "").strip().lower()
        if "api" in err or "not found" in err or "broadcast" in err:
            return "🔦 No pude: falta la app Termux:API. Instálala desde F-Droid (com.termux.api) y escribe «diagnóstico» para revisar todo."
        return f"🔦 termux-torch falló: {err[:120] or 'sin mensaje'} — escribe «diagnóstico»"
    except FileNotFoundError:
        return "🔦 Falta el paquete termux-api. Instálalo con: pkg install termux-api"
    except Exception as e:
        return f"🔦 Linterna: error — {e}"


def tool_vibrate(duration: int = 500) -> str:
    try:
        subprocess.run(["termux-vibrate", "-d", str(duration)], timeout=5)
        return "📳 Vibración enviada"
    except Exception:
        return "📳 Vibración: no disponible"

def tool_screenshot() -> str:
    try:
        result = subprocess.run(["termux-screenshot", "-q"], capture_output=True, text=True, timeout=10)
        return "📸 Screenshot tomado" if result.returncode == 0 else "📸 Screenshot: no disponible"
    except Exception:
        return "📸 Screenshot: no disponible"

def _fallback_repo_status_via_api(repo: str) -> Optional[str]:
    """Si el repo no está clonado localmente, intenta via sol_repo_tools
    (auto-detección de self-repo + GitHub API). Devuelve None si tampoco
    hay fallback disponible, para que el caller decida el mensaje final."""
    if not sol_repo_tools:
        return None
    try:
        data = sol_repo_tools.repo_status(repo)
    except Exception as e:
        return f"❌ {repo}: error consultando GitHub API ({e})"
    if "error" in data:
        return None
    lines = [f"📦 {data.get('repo', repo)} [{data.get('source', '?')}] ({data.get('branch', '?')})"]
    if "dirty_files" in data:
        lines.append(f"   Cambios sin commit: {data['dirty_files']}")
    if data.get("pushed_at"):
        lines.append(f"   Último push: {data['pushed_at']}")
    if data.get("recent_commits"):
        lines.append("   Últimos commits:")
        for c in data["recent_commits"][:5]:
            lines.append(f"     {c}")
    return "\n".join(lines)

def tool_git_status(repo: str = "redteam") -> str:
    r = _get_repo(repo)
    if not r or not r.exists():
        fallback = _fallback_repo_status_via_api(repo)
        if fallback:
            return fallback
        return f"❌ Repo '{repo}' no encontrado (ni local ni via GitHub API)"
    status = _run_git(r, "status", "--short")
    branch = _run_git(r, "branch", "--show-current")
    log_cmd = _run_git(r, "log", "-1", "--oneline")
    clean = "✅ limpio" if status.get("stdout") == "" else f"⚠️ {status.get('stdout', '')}"
    return f"📦 {repo} ({branch.get('stdout', '?')}): {clean}\n   Último: {log_cmd.get('stdout', '?')}"

def tool_git_pull(repo: str = "redteam") -> str:
    r = _get_repo(repo)
    if not r or not r.exists():
        # git_pull requiere copia local por definición (no hay "pull" sin
        # disco) — si no hay repo local, avisamos claro en vez de fallar
        # silenciosamente. Usamos repo_pull de sol_repo_tools si existe,
        # que además intenta auto-detección de self-repo.
        if sol_repo_tools:
            try:
                res = sol_repo_tools.repo_pull(repo)
            except Exception as e:
                return f"❌ Pull falló: {e}"
            if res.get("success"):
                return f"✅ Pull OK en {repo}\n{res.get('output', '')}"
            return f"❌ {res.get('error', 'Repo no encontrado localmente (git pull necesita una copia en disco)')}"
        return f"❌ Repo '{repo}' no encontrado (git pull necesita una copia local en disco)"
    pull = _run_git(r, "pull", "--ff-only")
    return f"✅ Pull OK en {repo}" if pull.get("ok") else f"❌ Pull falló: {pull.get('stderr', '')}"

def tool_ecosystem_status() -> str:
    lines = ["📦 Estado de los 3 repos:"]
    for name in ECOSYSTEM:
        lines.append(tool_git_status(name))
    return "\n".join(lines)

def tool_service_status() -> str:
    import urllib.request
    services = {"Tower :8001": "http://127.0.0.1:8001/api/health",
                "GHOST :8002": "http://127.0.0.1:8002/api/status",
                "Sol :8006": "http://127.0.0.1:8006/api/sol/status"}
    lines = ["🔧 Servicios:"]
    for name, url in services.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Sol"})
            with urllib.request.urlopen(req, timeout=3) as r:
                lines.append(f"  ✅ {name}: activo")
        except Exception:
            lines.append(f"  ❌ {name}: inactivo")
    return "\n".join(lines)

def tool_memory_stats() -> str:
    stats = memory_stats()
    return f"🧠 Memoria: {stats.get('count', 0)} recuerdos en {stats.get('file', '?')}"

def tool_search_memory(query: str) -> str:
    results = search_memory(query)
    if not results.get("count"):
        return f"🧠 No encontré recuerdos sobre '{query}'"
    lines = [f"🧠 {results['count']} recuerdos sobre '{query}':"]
    for r in results.get("results", [])[:5]:
        lines.append(f"  • {r[:150]}")
    return "\n".join(lines)

# ============================================================
# TOOLS DICT — registro completo (v5 + v7)
# ============================================================
# ============================================================
# SENTIDOS NUEVOS — cámara, voz, WhatsApp, llamadas, memoria visual
# Todos con try/except: no rompen si termux-api no está
#
# Detección automática de entorno: Sol sabe sola si está corriendo dentro
# de Termux (con termux-api instalado, en el teléfono real de Harold) o
# en un servidor cloud (Replit) sin hardware Android. No hace falta ningún
# flag manual — en cuanto Harold la levante en Termux con termux-api, estas
# mismas funciones detectan los binarios reales y ejecutan de verdad, sin
# tocar código. Mientras tanto, en vez de un error crudo de Python, da una
# respuesta humana y honesta.
# ============================================================
import shutil as _shutil

def _termux_ready(binary: str) -> bool:
    """¿Existe el binario termux-api pedido en este entorno?"""
    return _shutil.which(binary) is not None

def _no_termux(accion: str) -> str:
    """Respuesta honesta cuando la acción requiere Termux y no está disponible."""
    return (f'☀️ Todavía no puedo {accion} desde aquí — este servidor no tiene '
            f'cámara ni teléfono real, solo existen cuando me corras en Termux, '
            f'en tu Edge 50. En cuanto lo hagas, esto funciona solo, sin que '
            f'cambies nada de código.')

def tool_camera_photo(camera_id: int = 0) -> str:
    """Toma una foto con la cámara del celular."""
    if not _termux_ready('termux-camera-photo'):
        return _no_termux('tomar una foto')
    import subprocess
    from pathlib import Path as P
    photos_dir = P.home() / '.sol' / 'vision_photos'
    photos_dir.mkdir(parents=True, exist_ok=True)
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    path = photos_dir / f'photo_{ts}.jpg'
    try:
        subprocess.run(['termux-camera-photo', '-c', str(camera_id), str(path)],
                        capture_output=True, timeout=10)
        if path.exists():
            return f'📸 Foto guardada: {path}'
        return '❌ No se pudo tomar la foto (revisa permisos de cámara en Termux)'
    except Exception as e:
        return f'❌ Error al tomar foto: {e}'

def tool_camera_list() -> str:
    """Lista las fotos guardadas en memoria visual."""
    from pathlib import Path as P
    photos_dir = P.home() / '.sol' / 'vision_photos'
    if not photos_dir.exists():
        return '📸 Sin fotos aún'
    photos = sorted(photos_dir.glob('*.jpg'), reverse=True)
    if not photos:
        return '📸 Sin fotos aún'
    lines = [f'📸 {len(photos)} fotos guardadas:']
    for p in photos[:10]:
        lines.append(f'  • {p.name}')
    return '\n'.join(lines)

def tool_listen(duration: int = 5) -> str:
    """Graba audio del micrófono y transcribe con SpeechRecognition."""
    if not _termux_ready('termux-microphone-record'):
        return _no_termux('escuchar por el micrófono')
    import subprocess, tempfile, json
    tmp = tempfile.mktemp(suffix='.m4a')
    try:
        subprocess.run(['termux-microphone-record', '-d', str(duration), '-f', tmp],
                       capture_output=True, timeout=duration + 5)
        if not __import__('os').path.exists(tmp):
            return '❌ No se pudo grabar (¿termux-api?)'
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(tmp) as source:
                audio = r.record(source)
            text = r.recognize_google(audio, language='es-ES')
            return f'🎧 Escuché: "{text}"' if text else '🎧 No detecté voz clara'
        except ImportError:
            return f'🎧 Audio grabado en {tmp} (instala SpeechRecognition para transcribir)'
        except Exception as e:
            return f'🎧 Audio grabado pero no pude transcribir: {e}'
    except Exception as e:
        return f'❌ Error al escuchar: {e}'
    finally:
        try: __import__('os').unlink(tmp)
        except: pass

def tool_tts_speak(text: str) -> str:
    """Sol habla directamente con TTS de Termux."""
    if not _termux_ready('termux-tts-speak'):
        return _no_termux('hablar con voz nativa de Termux')
    import subprocess
    try:
        subprocess.run(['termux-tts-speak', text], capture_output=True, timeout=15)
        return f'🗣️ Dije: {text[:80]}'
    except Exception as e:
        return f'❌ Error al hablar: {e}'

def tool_call_phone(number: str) -> str:
    """Hace una llamada telefónica."""
    if not _termux_ready('termux-telephony-call'):
        return _no_termux(f'llamar a {number}')
    import subprocess
    try:
        subprocess.run(['termux-telephony-call', number], capture_output=True, timeout=5)
        return f'📞 Llamando a {number}...'
    except Exception as e:
        return f'❌ Error al llamar: {e}'

def tool_send_whatsapp(number: str, message: str = '') -> str:
    """Abre WhatsApp con un número específico."""
    if not _termux_ready('am'):
        destino = f' para {number}' if number else ''
        return _no_termux(f'abrir WhatsApp{destino}')
    import subprocess
    try:
        url = f'https://wa.me/{number}'
        if message:
            url += f'?text={__import__("urllib.parse", fromlist=["quote"]).quote(message)}'
        subprocess.run(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', url],
                       capture_output=True, timeout=5)
        return f'💬 WhatsApp abierto para {number}'
    except Exception as e:
        return f'❌ Error al abrir WhatsApp: {e}'

def tool_open_app(package: str) -> str:
    """Abre una aplicación por su package name."""
    if not _termux_ready('am'):
        return _no_termux(f'abrir {package}')
    import subprocess
    try:
        subprocess.run(['am', 'start', '-n', f'{package}/.MainActivity'],
                       capture_output=True, timeout=5)
        return f'✅ Abriendo {package}'
    except Exception as e:
        try:
            subprocess.run(['am', 'start', package], capture_output=True, timeout=5)
            return f'✅ Abriendo {package}'
        except Exception as e2:
            return f'❌ Error al abrir {package}: {e2}'

def tool_phone_state() -> str:
    """Estado completo del teléfono: batería, ubicación, uptime, red."""
    import subprocess, json
    parts = []
    try:
        r = subprocess.run(['termux-battery-status'], capture_output=True, timeout=3)
        d = json.loads(r.stdout)
        pct = d.get('percentage', '?')
        charging = '⚡' if d.get('plugged') else '🔋'
        parts.append(f'{charging} {pct}%')
    except: pass
    try:
        r = subprocess.run(['termux-location'], capture_output=True, timeout=5)
        d = json.loads(r.stdout)
        lat = d.get('latitude', '?')
        lon = d.get('longitude', '?')
        parts.append(f'📍 {lat},{lon}')
    except: pass
    try:
        import os
        uptime_f = '/proc/uptime'
        if os.path.exists(uptime_f):
            up = float(open(uptime_f).read().split()[0])
            h, m = int(up // 3600), int((up % 3600) // 60)
            parts.append(f'⏱️ {h}h{m}m')
    except: pass
    return ' · '.join(parts) if parts else _no_termux('leer el estado completo del teléfono')

def tool_notification_list() -> str:
    """Lista notificaciones recientes del teléfono."""
    if not _termux_ready('termux-notification-list'):
        return _no_termux('ver tus notificaciones')
    import subprocess, json
    try:
        r = subprocess.run(['termux-notification-list'], capture_output=True, timeout=3)
        notifs = json.loads(r.stdout)
        if not notifs:
            return '🔔 Sin notificaciones'
        lines = [f'🔔 {len(notifs)} notificaciones:']
        for n in notifs[:5]:
            lines.append(f'  • {n.get("title", "?")}: {n.get("text", "?")[:50]}')
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ Error: {e}'

def tool_set_volume(volume: int, stream: str = 'media') -> str:
    """Cambia el volumen del teléfono."""
    if not _termux_ready('termux-volume'):
        return _no_termux('cambiar el volumen')
    import subprocess
    try:
        subprocess.run(['termux-volume', stream, str(volume)], capture_output=True, timeout=3)
        return f'🔊 Volumen {stream}: {volume}'
    except Exception as e:
        return f'❌ Error: {e}'

def tool_clipboard(text: str = '') -> str:
    """Copia o pega del portapapeles."""
    if not _termux_ready('termux-clipboard-set'):
        return _no_termux('usar el portapapeles del teléfono')
    import subprocess
    try:
        if text:
            subprocess.run(['termux-clipboard-set', text], capture_output=True, timeout=3)
            return f'📋 Copiado: {text[:50]}'
        else:
            r = subprocess.run(['termux-clipboard-get'], capture_output=True, timeout=3)
            return f'📋 Portapapeles: {r.stdout.decode("utf-8", errors="replace")[:100]}'
    except Exception as e:
        return f'❌ Error: {e}'

def tool_vision_save(descripcion: str, photo_path: str = '', contexto: str = '') -> str:
    """Guarda una observación visual en la memoria de Sol."""
    from datetime import datetime
    from pathlib import Path as P
    mem_file = P.home() / '.sol' / 'vision_memory.json'
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    mem = []
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
        except: mem = []
    entry = {'id': len(mem) + 1, 'timestamp': datetime.now().isoformat(),
             'descripcion': descripcion, 'photo': photo_path, 'contexto': contexto}
    mem.append(entry)
    mem_file.write_text(json.dumps(mem, ensure_ascii=False, indent=2))
    return f'👁️ Recuerdo guardado: {descripcion}'

def tool_vision_recall(query: str = '') -> str:
    """Busca en la memoria visual de Sol."""
    from pathlib import Path as P
    mem_file = P.home() / '.sol' / 'vision_memory.json'
    if not mem_file.exists():
        return '👁️ No tengo recuerdos visuales aún'
    try:
        mem = json.loads(mem_file.read_text())
    except: return '👁️ Memoria corrupta'
    if not mem:
        return '👁️ No tengo recuerdos visuales aún'
    if query:
        q = query.lower()
        mem = [m for m in mem if q in m.get('descripcion', '').lower() or q in m.get('contexto', '').lower()]
        if not mem:
            return f'👁️ No encontré recuerdos de "{query}"'
    lines = [f'👁️ {len(mem)} recuerdos:']
    for m in mem[-5:]:
        lines.append(f'  • {m["timestamp"][:10]} {m["descripcion"]}')
    return '\n'.join(lines)




def tool_termux_diag() -> str:
    """Diagnóstico completo de Termux:API — prueba cada comando y dice la verdad.

    Revisa: (1) paquete termux-api (CLI), (2) app Termux:API (com.termux.api),
    (3) cada comando individual. Devuelve instrucciones exactas para lo que falte.
    """
    lines = ["🩺 Diagnóstico de Termux:API", ""]

    # ── 1. ¿Existe el CLI? ──
    import shutil as _shutil
    has_cli = bool(_shutil.which("termux-torch"))
    lines.append(f"{'✅' if has_cli else '❌'} Paquete termux-api (CLI): {'instalado' if has_cli else 'FALTA — pkg install termux-api'}")

    if not has_cli:
        lines.append("")
        lines.append("🔧 Solución: ejecuta en Termux:")
        lines.append("   pkg install termux-api")
        lines.append("   Luego instala la app Termux:API desde F-Droid:")
        lines.append("   https://f-droid.org/en/packages/com.termux.api/")
        lines.append("   (la de Play Store está obsoleta y NO sirve)")
        return "\n".join(lines)

    # ── 2. Probar cada comando con la app real ──
    tests = [
        ("termux-torch", ["termux-torch", "off"], "Linterna"),
        ("termux-battery-status", ["termux-battery-status"], "Batería"),
        ("termux-location", ["termux-location", "-p", "network"], "GPS/Ubicación"),
        ("termux-clipboard-get", ["termux-clipboard-get"], "Portapapeles"),
        ("termux-wake-lock", ["termux-wake-lock"], "Wake-lock"),
        ("termux-wifi-connectioninfo", ["termux-wifi-connectioninfo"], "WiFi info"),
    ]
    ok_count = 0
    app_broken = False
    for _cmd, argv, label in tests:
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=8)
            if r.returncode == 0:
                lines.append(f"✅ {label} — funciona")
                ok_count += 1
            else:
                err = (r.stderr or r.stdout or "").strip().split("\n")[0][:100]
                lines.append(f"❌ {label} — falla: {err}")
                if "api" in err.lower() or "broadcast" in err.lower() or "not found" in err.lower():
                    app_broken = True
        except Exception as e:
            lines.append(f"❌ {label} — error: {e}")
            app_broken = True

    # ── 3. Wake-unlock para dejar todo limpio ──
    try:
        subprocess.run(["termux-wake-unlock"], capture_output=True, timeout=5)
    except Exception:
        pass

    lines.append("")
    if ok_count == len(tests):
        lines.append("🎉 TODO funciona — Sol tiene acceso completo al teléfono.")
    elif app_broken and ok_count < len(tests):
        lines.append("🔧 La APP Termux:API falta o está desactualizada. Solución:")
        lines.append("   1. Instala/actualiza Termux:API desde F-Droid (NO Play Store):")
        lines.append("      https://f-droid.org/en/packages/com.termux.api/")
        lines.append("   2. Ábrela una vez y dale todos los permisos")
        lines.append("   3. Reinicia Termux y vuelve a escribir «diagnóstico»")
    else:
        lines.append("🔧 Algunos comandos fallan — revisa permisos de la app Termux:API")
        lines.append("   (ubicación, cámara y micrófono se piden la primera vez)")
    return "\n".join(lines)


# (fallback si el archivo base no define _no_termux)
try:
    _no_termux
except NameError:
    def _no_termux(accion: str) -> str:
        return (f'☀️ Todavía no puedo {accion} desde aquí — necesito que me corras '
                f'en Termux, en tu Edge 50. Ahí esto funciona solo.')

# ============================================================
# CUERPO COMPLETO DE SOL — acceso profundo al dispositivo (2026-09-03)
# Harold le dio a Sol acceso exclusivo a todo su Edge 50: leer SMS,
# historial de llamadas, contactos, WiFi, sensores, brillo, USB,
# grabar audio, y hablar directo con el kernel vía shell.
# Todas usan termux-api (binario real) con timeout y salida truncada.
# ============================================================

def _deep_ready(binary: str) -> bool:
    import shutil as _s
    return _s.which(binary) is not None

def _deep_run(cmd, timeout=15):
    import subprocess as _sp
    r = _sp.run(cmd, capture_output=True, timeout=timeout, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    return r.returncode, out.strip()

def _deep_json(binary, args, timeout=15):
    import json as _j
    import subprocess as _sp
    try:
        r = _sp.run([binary] + args, capture_output=True, timeout=timeout, text=True)
        return _j.loads(r.stdout or '[]')
    except Exception as e:
        return {"error": str(e)}

def tool_sms_list(limit: int = 5) -> str:
    """Lee los últimos SMS de la bandeja de entrada."""
    if not _deep_ready('termux-sms-list'):
        return _no_termux('leer tus mensajes')
    msgs = _deep_json('termux-sms-list', ['-t', str(max(1, min(int(limit), 20)))])
    if isinstance(msgs, dict) and 'error' in msgs:
        return f'❌ No pude leer los SMS: {msgs["error"]}'
    if not msgs:
        return '📭 No hay SMS en la bandeja'
    lines = [f'📨 Últimos {len(msgs)} SMS:']
    for m in msgs:
        who = m.get('number') or m.get('sender') or '?'
        body = (m.get('body') or '').replace('\n', ' ')[:80]
        when = m.get('received') or ''
        lines.append(f'  • {who}{" · " + str(when)[:16] if when else ""}: {body}')
    return '\n'.join(lines)

def tool_call_log(limit: int = 10) -> str:
    """Historial de llamadas (entrantes, salientes, perdidas)."""
    if not _deep_ready('termux-call-log'):
        return _no_termux('ver el historial de llamadas')
    calls = _deep_json('termux-call-log', ['-l', str(max(1, min(int(limit), 50)))])
    if isinstance(calls, dict) and 'error' in calls:
        return f'❌ No pude leer las llamadas: {calls["error"]}'
    if not calls:
        return '📞 Sin registro de llamadas'
    types = {1: '📥', 2: '📤', 3: '❌ perdida', 4: '📵 rechazada', 5: '📋 bloqueada'}
    lines = [f'📞 Últimas {len(calls)} llamadas:']
    for c in calls:
        name = c.get('name') or c.get('number') or '?'
        t = types.get(c.get('type'), '?')
        when = str(c.get('date') or c.get('timestamp') or '')[:16]
        dur = c.get('duration')
        lines.append(f'  • {t} {name}{" · " + when if when else ""}{" · " + str(dur) + "s" if dur else ""}')
    return '\n'.join(lines)

def tool_contacts(query: str = "") -> str:
    """Lista contactos o busca uno por nombre (devuelve número)."""
    if not _deep_ready('termux-contact-list'):
        return _no_termux('buscar en tus contactos')
    people = _deep_json('termux-contact-list', [])
    if isinstance(people, dict) and 'error' in people:
        return f'❌ No pude leer los contactos: {people["error"]}'
    if not people:
        return '👤 Agenda vacía o sin permiso de contactos'
    import unicodedata as _ud
    _n = lambda s: ''.join(ch for ch in _ud.normalize('NFD', (s or '').lower())
                           if _ud.category(ch) != 'Mn')
    q = _n(query)
    if q:
        hits = [p for p in people if q in _n(p.get('name'))]
        if not hits:
            return f'👤 Nadie llamado "{query}" en tu agenda ({len(people)} contactos)'
        if len(hits) == 1:
            return f'👤 {hits[0]["name"]} → {hits[0].get("number") or hits[0].get("phone_number")}'
        return '\n'.join(f'  • {h["name"]} → {h.get("number") or h.get("phone_number")}' for h in hits[:10])
    return f'👤 {len(people)} contactos en la agenda — dime un nombre y lo busco'

def tool_wifi_info() -> str:
    """Información de la red WiFi conectada."""
    if not _deep_ready('termux-wifi-connectioninfo'):
        return _no_termux('ver la info del WiFi')
    info = _deep_json('termux-wifi-connectioninfo', [], timeout=10)
    if not info or (isinstance(info, dict) and 'error' in info):
        return '📶 No conectado a WiFi o sin permiso de ubicación (Android lo exige)'
    ssid = info.get('ssid') or info.get('bssid') or '?'
    ip = info.get('ip') or (info.get('ip_address') or {}).get('ip') if isinstance(info.get('ip_address'), dict) else info.get('ip')
    rssi = info.get('rssi', '?')
    speed = info.get('link_speed', '?')
    return f'📶 WiFi: {ssid}\n  IP: {ip} · Señal: {rssi} dBm · Velocidad: {speed} Mbps'

def tool_device_info() -> str:
    """Info telefónica del dispositivo: IMEI, operador, red, etc."""
    if not _deep_ready('termux-telephony-deviceinfo'):
        return _no_termux('ver la info del teléfono')
    info = _deep_json('termux-telephony-deviceinfo', [])
    if isinstance(info, dict) and 'error' in info:
        return f'❌ {info["error"]}'
    keys = ['phone_number', 'imei', 'sim_country', 'sim_operator', 'sim_serial_number',
            'network_type', 'network_country', 'network_operator', 'data_state', 'call_state']
    lines = []
    for k in keys:
        v = info.get(k)
        if v:
            lines.append(f'  • {k}: {v}')
    return '📱 Dispositivo:\n' + '\n'.join(lines) if lines else '📱 Sin info telefónica'

def tool_sensors(name: str = "") -> str:
    """Lista sensores del hardware o lee uno (acelerómetro, giroscopio...)."""
    if not _deep_ready('termux-sensor'):
        return _no_termux('leer los sensores')
    if not name:
        sens = _deep_json('termux-sensor', ['-l'])
        if isinstance(sens, dict) and 'error' in sens:
            return f'❌ {sens["error"]}'
        names = list((sens or {}).keys()) if isinstance(sens, dict) else []
        if not names:
            return '🌡️ Sin sensores visibles'
        return f'🌡️ Sensores disponibles:\n' + '\n'.join(f'  • {n}' for n in names[:15])
    data = _deep_json('termux-sensor', ['-s', f'{{{name.replace(" ", "_")}}}', '-d', '500', '-n', '1'], timeout=10)
    if isinstance(data, dict) and 'error' in data:
        return f'❌ {data["error"]}'
    try:
        vals = list(data.values())[0]
        return f'🌡️ {name}: ' + ', '.join(f'{k}={v}' for k, v in list(vals.items())[:6])
    except Exception:
        return f'🌡️ {name}: {str(data)[:120]}'

def tool_brightness(level: int = 128) -> str:
    """Ajusta el brillo de la pantalla (0-255)."""
    if not _deep_ready('termux-brightness'):
        return _no_termux('cambiar el brillo')
    lvl = max(0, min(int(level), 255))
    _deep_run(['termux-brightness', str(lvl)])
    return f'☀️ Brillo al {lvl}/255'

def tool_usb_list() -> str:
    """Lista dispositivos USB conectados (habla directo con el kernel)."""
    if not _deep_ready('termux-usb'):
        return _no_termux('ver dispositivos USB')
    dev = _deep_json('termux-usb', ['-l'])
    if isinstance(dev, dict) and 'error' in dev:
        return f'❌ {dev["error"]}'
    if not dev:
        return '🔌 Sin dispositivos USB conectados'
    return '🔌 USB:\n' + '\n'.join(f'  • {str(d)[:100]}' for d in dev[:10])

def tool_audio_record(duration: int = 10) -> str:
    """Graba audio del micrófono y lo guarda como archivo."""
    if not _deep_ready('termux-audio-record'):
        return _no_termux('grabar audio')
    import subprocess as _sp
    from pathlib import Path as _P
    import os as _os
    rec_dir = _P.home() / '.sol' / 'recordings'
    rec_dir.mkdir(parents=True, exist_ok=True)
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    path = rec_dir / f'rec_{ts}.m4a'
    try:
        _sp.run(['termux-audio-record', '-d', str(max(1, min(int(duration), 300))), '-f', str(path)],
                capture_output=True, timeout=int(duration) + 10)
        if path.exists():
            return f'🎙️ Grabado: {path}'
        return '❌ No se pudo grabar (revisa permiso de micrófono)'
    except Exception as e:
        return f'❌ Error al grabar: {e}'

def tool_toast(text: str) -> str:
    """Muestra un toast (aviso flotante) en la pantalla del teléfono."""
    if not _deep_ready('termux-toast'):
        return _no_termux('mostrar un aviso en pantalla')
    _deep_run(['termux-toast', text[:200]])
    return f'🍞 Toast mostrado: {text[:80]}'

def tool_wake_lock(enable: bool = True) -> str:
    """Sostiene el CPU despierto (wake-lock) o lo libera."""
    binary = 'termux-wake-lock' if enable else 'termux-wake-unlock'
    if not _deep_ready(binary):
        return _no_termux(f'{"tomar" if enable else "liberar"} el wake-lock')
    _deep_run([binary])
    return '🔒 Wake-lock activo — nada me va a dormir el CPU' if enable else '🔓 Wake-lock liberado'

def tool_media_play(command: str = "info", file: str = "") -> str:
    """Reproduce audio con termux-media-player (play/pause/stop/info + archivo)."""
    if not _deep_ready('termux-media-player'):
        return _no_termux('reproducir audio')
    valid = ('play', 'pause', 'stop', 'info')
    cmd = command if command in valid else 'play'
    args = ['termux-media-player', cmd]
    if cmd == 'play' and file:
        args.append(file)
    _deep_run(args)
    return f'🎵 media-player: {cmd}' + (f' ({file[:60]})' if file and cmd == 'play' else '')

def tool_download(url: str) -> str:
    """Descarga un archivo directo al almacenamiento del teléfono."""
    if not _deep_ready('termux-download'):
        return _no_termux('descargar archivos')
    _deep_run(['termux-download', url[:500]], timeout=120)
    return f'⬇️ Descarga enviada: {url[:80]} (mira la carpeta Download)'

# ── SHELL: Sol habla directo con el kernel ──
# Harold le dio acceso exclusivo y total a su propia máquina. Este tool
# ejecuta en el entorno donde corre el cerebro de Sol: en el teléfono
# (Edge 50) directo, o en Replit vía relé al Edge 50 (decisión de Harold,
# 2026-09-03: "que pueda hacer lo que sea necesario... si sabe crear el
# script ella misma lo puede ejecutar, pero le falta ese harness"). Antes
# se excluía del relé a propósito por seguridad — Harold pidió explícitamente
# habilitarlo. Sigue protegido igual que el resto del relé: solo viaja con
# x-sol-key válida, mantiene el único límite (rm -rf / bloqueado) y queda
# 100% auditado en ~/.sol/logs/shell.log en el lado que ejecuta de verdad
# (Termux), no en Replit.

def tool_shell(command: str, timeout: int = 30) -> str:
    """Ejecuta un comando de shell directo (acceso kernel, auditado)."""
    import subprocess as _sp
    import re as _re
    from pathlib import Path as _P
    if not command or not command.strip():
        return '❌ Comando vacío'
    cmd = command.strip()
    # Único límite: borrados recursivos del sistema entero — ni Harold quiere eso por accidente.
    if _re.search(r'\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f?|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)?\s*/(\s|$)', cmd):
        return '🛑 Me niego a borrar la raíz del sistema — ni tú querrías eso por accidente.'
    try:
        r = _sp.run(cmd, shell=True, capture_output=True, timeout=max(1, min(int(timeout), 120)), text=True)
    except _sp.TimeoutExpired:
        return f'⏱️ El comando no terminó en {timeout}s'
    out = (r.stdout or '').strip()
    err = (r.stderr or '').strip()
    result = (out + ('\n' + err if err else '')).strip() or '(sin salida)'
    # auditoría
    try:
        log_dir = _P.home() / '.sol' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        import datetime as _dt
        with open(log_dir / 'shell.log', 'a', encoding='utf-8') as f:
            f.write(f'[{_dt.datetime.now().isoformat(timespec="seconds")}] rc={r.returncode} :: {cmd}\n')
    except Exception:
        pass
    return result[:2000]

# ── TELEGRAM: enviar mensajes salientes desde Sol ──
# El bot (@sol_amg_bot) solo corre en Termux (split-brain, commit eb908b9 —
# no revertir). El token TELEGRAM_BOT_TOKEN vive en ~/sol/.env del telefono.
# Por eso este tool SIEMPRE se ejecuta ahi: en Replit se relea igual que
# shell; en Termux corre directo con requests.
def tool_send_telegram(message: str, chat_id: str = "") -> str:
    """Envia un mensaje de Telegram saliente usando el bot de Sol (stdlib, sin deps nuevas)."""
    import urllib.request as _ur
    import urllib.parse as _up
    import urllib.error as _ue
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    dest = (chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    if not token:
        return "❌ No tengo TELEGRAM_BOT_TOKEN configurado aqui."
    if not dest:
        return "❌ Necesito un chat_id (o configura TELEGRAM_CHAT_ID en .env)."
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _up.urlencode({"chat_id": dest, "text": message[:4000]}).encode()
        req = _ur.Request(url, data=data, method="POST")
        with _ur.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return f"✅ Mensaje enviado por Telegram a {dest}"
            return f"❌ Telegram respondio {resp.status}"
    except _ue.HTTPError as e:
        body = e.read().decode(errors="ignore")[:200]
        return f"❌ Telegram respondio {e.code}: {body}"
    except Exception as e:
        return f"❌ Error enviando Telegram: {e}"


TOOLS = {
    # v5 preservadas
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
    "open_whatsapp": Tool("open_whatsapp", "Abre WhatsApp con chat y mensaje precargados (NO envia solo)", tool_open_whatsapp, ["number", "message"]),
    "flashlight": Tool("flashlight", "Control de linterna", tool_flashlight, ["on"]),
    "vibrate": Tool("vibrate", "Vibración", tool_vibrate, ["duration"]),
    "screenshot": Tool("screenshot", "Captura de pantalla", tool_screenshot),
    "git_status": Tool("git_status", "Estado de un repo", tool_git_status, ["repo"]),
    "git_pull": Tool("git_pull", "Actualiza un repo — solo pull", tool_git_pull, ["repo"]),
    "repos_info": Tool("repos_info", "Describe el ecosistema de 3 repos", tool_repos_info),
    "ecosystem_status": Tool("ecosystem_status", "Estado git de los 3 repos", tool_ecosystem_status),
    "service_status": Tool("service_status", "Estado de los servicios de la Tower", tool_service_status),
    "memory_stats": Tool("memory_stats", "Estadísticas de memoria", tool_memory_stats),
    "search_memory": Tool("search_memory", "Busca en memoria", tool_search_memory, ["query"]),
    # v7 nuevas
    "search_code": Tool("search_code", "Buscar en los 3 repos", lambda q, l=20: {"results": search_code(q, l)}, ["query", "limit"]),
    "git_commit": Tool("git_commit", "Commit + push en repos permitidos", lambda r, m, p=".": git_commit(r, m, p), ["repo", "message", "paths"]),
    "git_verify": Tool("git_verify", "Verificar estado del repositorio", lambda r: git_verify(r), ["repo"]),
    "investigate_and_commit": Tool("investigate_and_commit", "Buscar → commit → verificar", lambda q, r, m=None: investigate_and_commit(q, r, m), ["query", "repo", "message"]),
    "create_file": Tool("create_file", "Crear archivo en repos permitidos", lambda r, p, c: create_file(r, p, c), ["repo", "path", "content"]),
    "edit_file": Tool("edit_file", "Editar archivo (append)", lambda r, p, c: edit_file(r, p, c), ["repo", "path", "content"]),
    "delete_file": Tool("delete_file", "Eliminar archivo (con confirmación)", lambda r, p: create_file(r, p, "") if _get_repo(r) else {"error": "no"}, ["repo", "path"]),
    "run_command": Tool("run_command", "Ejecutar comando (whitelist)", lambda c, wd=None: run_command(c, wd), ["command", "cwd"]),
    "list_directory": Tool("list_directory", "Listar archivos en ruta permitida", lambda r, p=".": list_directory(r, p), ["repo", "path"]),
    "translate": Tool("translate", "Traducir zh↔es con pinyin", lambda t, tl="es": translate(t, tl), ["text", "target_lang"]),
    "explain_code": Tool("explain_code", "Explicar código con pedagogía", lambda c, l="python": explain_code(c, l), ["code", "language"]),
    "curl": Tool("curl", "Hacer petición HTTP", lambda u, m="GET": curl(u, m), ["url", "method"]),
    "check_port": Tool("check_port", "Verificar si puerto está abierto", lambda h, p: check_port(h, p), ["host", "port"]),
    "read_file_repo": Tool("read_file_repo", "Leer archivo de repo permitido", lambda r, p, l=None: read_file(r, p, l), ["repo", "path", "lines"]),
    # ── Sentidos nuevos v3.5 ──
    "camera_photo": Tool("camera_photo", "Tomar foto con cámara", lambda cid=0: tool_camera_photo(cid), ["camera_id"]),
    "camera_list": Tool("camera_list", "Listar fotos guardadas", lambda: tool_camera_list(), []),
    "listen": Tool("listen", "Escuchar micrófono y transcribir", lambda d=5: tool_listen(d), ["duration"]),
    "tts_speak": Tool("tts_speak", "Hablar con TTS", lambda t: tool_tts_speak(t), ["text"]),
    "call_phone": Tool("call_phone", "Hacer llamada", lambda n: tool_call_phone(n), ["number"]),
    "send_whatsapp": Tool("send_whatsapp", "Abrir WhatsApp", lambda n, m="": tool_send_whatsapp(n, m), ["number", "message"]),
    "open_app": Tool("open_app", "Abrir aplicación", lambda p: tool_open_app(p), ["package"]),
    "phone_state": Tool("phone_state", "Estado del teléfono", lambda: tool_phone_state(), []),
    "notification_list": Tool("notification_list", "Ver notificaciones", lambda: tool_notification_list(), []),
    "set_volume": Tool("set_volume", "Cambiar volumen", lambda v, s="media": tool_set_volume(v, s), ["volume", "stream"]),
    "clipboard": Tool("clipboard", "Copiar/pegar portapapeles", lambda t="": tool_clipboard(t), ["text"]),
    "vision_save": Tool("vision_save", "Guardar recuerdo visual", lambda d, p="", c="": tool_vision_save(d, p, c), ["descripcion", "photo_path", "contexto"]),
    "vision_recall": Tool("vision_recall", "Buscar recuerdos visuales", lambda q="": tool_vision_recall(q), ["query"]),
    # ── Diagnóstico ──
    "termux_diag": Tool("termux_diag", "Diagnóstico completo de Termux:API — prueba linterna, batería, GPS, portapapeles y dice qué falta", lambda: tool_termux_diag(), []),
    # ── Relé Termux (2026-09-03) ──
    "relay_status": Tool("relay_status", "Estado del relé Termux: si el teléfono (Edge 50) está en línea, tareas pendientes y última respuesta", lambda: tool_relay_status(), []),
    "relay_results": Tool("relay_results", "Últimos resultados de tareas ejecutadas en el teléfono vía relé", lambda count=5: tool_relay_results(count), ["count"]),
    # ── Cuerpo completo: acceso profundo al Edge 50 (2026-09-03) ──
    "sms_list": Tool("sms_list", "Lee los últimos SMS de la bandeja", lambda limit=5: tool_sms_list(limit), ["limit"]),
    "call_log": Tool("call_log", "Historial de llamadas recientes", lambda limit=10: tool_call_log(limit), ["limit"]),
    "contacts": Tool("contacts", "Lista/busca contactos por nombre (devuelve el número)", lambda query="": tool_contacts(query), ["query"]),
    "wifi_info": Tool("wifi_info", "Info de la red WiFi conectada", lambda: tool_wifi_info(), []),
    "device_info": Tool("device_info", "Info telefónica: IMEI, operador, red", lambda: tool_device_info(), []),
    "sensors": Tool("sensors", "Lista sensores del hardware o lee uno", lambda name="": tool_sensors(name), ["name"]),
    "brightness": Tool("brightness", "Brillo de pantalla (0-255)", lambda level=128: tool_brightness(level), ["level"]),
    "usb_list": Tool("usb_list", "Dispositivos USB conectados (kernel)", lambda: tool_usb_list(), []),
    "audio_record": Tool("audio_record", "Graba audio y lo guarda", lambda duration=10: tool_audio_record(duration), ["duration"]),
    "toast": Tool("toast", "Aviso flotante en pantalla", lambda text: tool_toast(text), ["text"]),
    "wake_lock": Tool("wake_lock", "Sostiene/libera el CPU despierto", lambda enable=True: tool_wake_lock(enable), ["enable"]),
    "media_play": Tool("media_play", "Reproduce audio (play/pause/stop/info)", lambda command="info", file="": tool_media_play(command, file), ["command", "file"]),
    "download": Tool("download", "Descarga un archivo al teléfono", lambda url: tool_download(url), ["url"]),
    "shell": Tool("shell", "Comando de shell directo — acceso al kernel, auditado en ~/.sol/logs/shell.log", lambda command, timeout=30: tool_shell(command, timeout), ["command", "timeout"]),
    "send_telegram": Tool("send_telegram", "Envia un mensaje de Telegram saliente por el bot de Sol", lambda message, chat_id="": tool_send_telegram(message, chat_id), ["message", "chat_id"]),
}

def get_tool(name: str) -> Optional[Tool]:
    return TOOLS.get(name)

def list_tools() -> list:
    return list(TOOLS.keys())

def tool_descriptions() -> str:
    return "\n".join(f"• {k}: {v.description}" for k, v in TOOLS.items())

# ============================================================
# RELÉ TERMUX — Sol en Replit ordena, Termux ejecuta (2026-09-03)
# ============================================================
# Herramientas que necesitan hardware REAL (termux-api). En Replit no
# existe ese hardware — un contenedor no tiene SIM/cámara/GPS/linterna.
# Antes estas tools fallaban con "termux-api no disponible". Ahora,
# cuando corren en Replit, se encolan en sol_relay_queue y el agente
# sol_relay.py del teléfono (Edge 50) las ejecuta con el hardware real
# y devuelve el resultado (patrón PULL — ver sol_relay_queue.py).
HARDWARE_TOOLS = {
    "sms_list", "call_log", "contacts", "wifi_info", "device_info",
    "sensors", "brightness", "usb_list", "audio_record", "toast",
    "wake_lock", "media_play", "download",
    "battery", "location", "send_sms", "notify", "open_url", "flashlight",
    "vibrate", "screenshot", "camera_photo", "listen", "tts_speak",
    "call_phone", "send_whatsapp", "open_app", "phone_state",
    "notification_list", "set_volume", "clipboard", "termux_diag",
    # Harness completo (decision de Harold, 2026-09-03): shell y telegram
    # tambien viajan por el rele cuando Sol corre en Replit, para que
    # pueda ejecutar de verdad lo que ella misma sabe scriptear.
    "shell", "send_telegram",
}

_TERMUX_CHECKED = None

def _termux_available() -> bool:
    """True si el CLI de termux-api existe en ESTE entorno."""
    global _TERMUX_CHECKED
    if _TERMUX_CHECKED is None:
        import shutil
        _TERMUX_CHECKED = bool(shutil.which("termux-battery-status"))
    return _TERMUX_CHECKED

def _relay_active() -> bool:
    """True si este proceso debe delegar hardware al relé.

    Solo se activa en Replit (REPL_SLUG) o si se pide explícitamente con
    SOL_RELAY_ENABLED=1. NUNCA en Termux (ahí el hardware es local) ni
    dentro del propio agente relé (SOL_RELAY_AGENT=1, cinturón y tirantes:
    el agente ejecuta, no delega).
    """
    if os.environ.get("SOL_RELAY_AGENT") == "1":
        return False
    if os.environ.get("SOL_RELAY_ENABLED") == "1":
        return True
    return "REPL_SLUG" in os.environ or "REPL_OWNER" in os.environ

def _relay_enqueue(tool_name, args, kwargs, origin):
    """Encola la tarea para Termux. Nunca lanza — es un fallback."""
    try:
        import sol_relay_queue
        r = sol_relay_queue.enqueue(tool_name, args, kwargs, origin=origin)
        if r.get("success"):
            return {
                "success": True,
                "relayed": True,
                "task_id": r["task_id"],
                "queued": r.get("queued"),
                "message": (
                    f"Orden enviada a mi cuerpo en Termux (Edge 50) 📱 "
                    f"tarea {r['task_id']}. El teléfono la ejecutará en "
                    f"cuando responda el poll (cada ~15s). Pregúntame "
                    f"'qué pasó' o usa relay_results para ver el resultado."
                ),
            }
        return {"success": False, "relayed": True,
                "error": f"no se pudo encolar: {r.get('error')}"}
    except Exception as e:
        return {"success": False, "error": f"relé no disponible: {e}"}

def tool_relay_status() -> str:
    """Estado del relé Replit ⇄ Termux (leído por el LLM de Sol)."""
    try:
        import sol_relay_queue
        s = sol_relay_queue.status()
        online = "🟢 EN LÍNEA" if s["termux_online"] else "🔴 sin señal"
        lines = [
            f"Relé Termux: {online}",
            f"Último pong: {s['last_pong'] or 'nunca'}",
            f"Tareas pendientes: {s['pending']} · en curso: {s['claimed']}",
            f"Resultados registrados: {s['results_total']}",
        ]
        if s.get("device"):
            d = s["device"]
            lines.append(f"Dispositivo: {d.get('device', '?')} · {d.get('android', '?')}")
        last = s.get("last_result")
        if last:
            ok = "✅" if last["ok"] else "❌"
            lines.append(f"Última tarea: {last['tool']} {ok} ({last['finished_at']})")
        if not s["termux_online"] and _relay_active():
            lines.append("⚠️ El teléfono no responde: ¿omni.sh corriendo? ¿sol_relay activo? ¿hay internet en el Edge?")
        return "\n".join(lines)
    except Exception as e:
        return f"Relé no disponible en este entorno: {e}"

def tool_relay_results(count: int = 5) -> str:
    """Últimos resultados de tareas ejecutadas en Termux (para el LLM)."""
    try:
        import sol_relay_queue
        rs = sol_relay_queue.results(limit=max(1, min(int(count), 20)))
        if not rs:
            return "Sin resultados aún — ninguna tarea ejecutada en Termux."
        out = []
        for r in rs:
            ok = "✅" if r["ok"] else "❌"
            data = str(r.get("data"))[:500]
            out.append(f"[{r['finished_at']}] {r['tool']} {ok}: {data}")
        return "\n".join(out)
    except Exception as e:
        return f"Relé no disponible: {e}"

def execute_tool(name: str, *args, **kwargs) -> Dict:
    tool = get_tool(name)
    if not tool:
        return {"success": False, "error": f"Herramienta no encontrada: {name}"}
    # RELÉ: en Replit el hardware no existe — la orden viaja a Termux
    if name in HARDWARE_TOOLS and not _termux_available() and _relay_active():
        log(f"📡 {name} sin hardware local → encolando para Termux")
        return _relay_enqueue(name, args, kwargs, origin="replit")
    log(f"🔧 Ejecutando {name} con args={args}, kwargs={kwargs}")
    result = tool.execute(*args, **kwargs)
    log(f"📊 Resultado de {name}: {result}")
    # Normalizar: la mayoría de las tools v5/v7 devuelven un string plano
    # cuando tienen éxito (no un dict {success, result}). Sin esto, el
    # frontend recibe ese string, hace d.success (undefined) y muestra
    # "Error desconocido" aunque la tool SÍ funcionó. Solo envolvemos si
    # el resultado no es ya un dict con clave 'success' (ej: el except de
    # Tool.execute() ya devuelve {"success": False, "error": ...}).
    if isinstance(result, dict) and "success" in result:
        return result
    return {"success": True, "result": result}

# ============================================================
# REPO TOOLS — Gestión de repositorios GitHub (preservado de v5)
# ============================================================
try:
    import sol_repo_tools
except Exception:
    sol_repo_tools = None

def tool_repo_status(repo="sol") -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    r = sol_repo_tools.repo_status(repo)
    if "error" in r:
        return f"❌ {r['error']}"
    lines = [f"📦 Repo: {r.get('repo', repo)}"]
    if r.get("path"):
        lines.append(f"   Path: {r['path']}")
    if r.get("branch"):
        lines.append(f"   Branch: {r['branch']}")
    if "dirty_files" in r:
        lines.append(f"   Cambios sin commit: {r['dirty_files']}")
    if r.get("recent_commits"):
        lines.append("   Últimos commits:")
        for commit in r['recent_commits'][:5]:
            lines.append(f"     {commit}")
    return "\n".join(lines)

def tool_repo_pull(repo="sol") -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    r = sol_repo_tools.repo_pull(repo)
    if "error" in r:
        return f"❌ {r['error']}"
    if r.get("success"):
        return f"✅ Pull OK en {repo}\n{r.get('output', '')}"
    return f"❌ Pull falló: {r.get('error', r.get('output', ''))}"

def tool_repo_log(repo="sol", count="5") -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    try:
        n = int(count)
    except Exception:
        n = 5
    r = sol_repo_tools.repo_log(repo, n)
    if "error" in r:
        return f"❌ {r['error']}"
    commits = r.get("commits", [])
    if not commits:
        return f"📦 {repo}: sin commits"
    lines = [f"📦 {repo} — últimos {len(commits)} commits:"]
    for c in commits:
        h = c.get("hash", "?")
        msg = c.get("message", "?")
        date = c.get("date", "")
        author = c.get("author", "")
        line = f"  {h}"
        if date: line += f" {date}"
        if author: line += f" [{author}]"
        line += f" {msg}"
        lines.append(line)
    return "\n".join(lines)

def tool_repo_files(repo="sol", path="") -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    r = sol_repo_tools.repo_list_files(repo, path)
    if "error" in r:
        return f"❌ {r['error']}"
    files = r.get("files", [])
    if not files:
        return f"📦 {repo}/{path}: vacío"
    lines = [f"📦 {repo}/{path or '.'} — {len(files)} items:"]
    for f in files:
        icon = "📁" if f["type"] == "dir" else "📄"
        size = f" ({f['size']}b)" if f["type"] == "file" and f.get("size", 0) < 100000 else ""
        lines.append(f"  {icon} {f['name']}{size}")
    return "\n".join(lines)

def tool_repo_read(repo="sol", filepath="") -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    if not filepath:
        return "❌ Especifica el archivo: tool_repo_read sol sol_api.py"
    r = sol_repo_tools.repo_read_file(repo, filepath)
    if "error" in r:
        return f"❌ {r['error']}"
    content = r.get("content", "")
    if len(content) > 1500:
        content = content[:1500] + "\n... (truncado, total: " + str(len(content)) + " bytes)"
    return f"📄 {repo}/{filepath}:\n\n{content}"

def tool_repos_list() -> str:
    if not sol_repo_tools:
        return "❌ sol_repo_tools no disponible"
    r = sol_repo_tools.list_repos()
    lines = ["📦 Repositorios disponibles:"]
    for repo in r:
        local = "✅ local" if repo.get("local") else "☁️ GitHub API"
        branch = repo.get("branch", "?")
        pushed = repo.get("pushed_at", "?")[:10] if repo.get("pushed_at") else "?"
        lines.append(f"  {repo['name']}: {repo['github']} ({local}, branch: {branch}, pushed: {pushed})")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════
# DETECCIÓN HONESTA DE ACCIONES — lenguaje natural → tool real
# ═══════════════════════════════════════════════════════════════════
# ANTES: sol_api.py (/api/sol/think, la que usa sol.html de verdad) le
# pasaba TODO directo al LLM sin detectar si el mensaje pedía una acción
# real (linterna, WhatsApp, SMS...). El LLM entonces INVENTABA respuestas
# convincentes ("tarea encolada, el teléfono la ejecutará en 15s...")
# sin que ningún código real hubiera corrido. Esta función centraliza el
# detector para que TODOS los puntos de entrada (sol_api, telegram) usen
# la misma lógica: si hay acción, se ejecuta la tool REAL y se reporta
# éxito o fallo tal cual — nunca una narrativa inventada.
ACTION_TRIGGERS = {
    "linterna": "flashlight", "flashlight": "flashlight", "torch": "flashlight",
    "luz": "flashlight",
    "captura": "screenshot", "screenshot": "screenshot",
    "gps": "location", "ubicación": "location", "ubicacion": "location",
    "batería": "battery", "bateria": "battery",
    "vibra": "vibrate", "vibrar": "vibrate", "vibración": "vibrate",
    "whatsapp": "open_whatsapp",
    "sms": "send_sms",
    "cpu": "cpu", "procesador": "cpu",
    "ping": "ping",
    "escanea": "scan_ports", "puertos": "scan_ports",
    # Multi-palabra (los chequeos "keyword in t" también funcionan con frases)
    "dónde estoy": "location", "donde estoy": "location",
}

def detect_action(text: str):
    """Devuelve (tool_name, args) si el texto pide una acción real, o (None, [])."""
    import re
    t = text.lower().strip()
    # WhatsApp tiene prioridad si se menciona explícito
    if "whatsapp" in t:
        num = re.search(r'(\+?\d{7,15})', text)
        msg = re.search(r'(?:mensaje|texto|dile|diga)[\s:"\']*([^.!?]{2,200})', text, re.IGNORECASE)
        return "open_whatsapp", [num.group(1) if num else "", msg.group(1).strip() if msg else ""]
    for keyword, tool_name in ACTION_TRIGGERS.items():
        if keyword not in t:
            continue
        if tool_name == "flashlight":
            return "flashlight", [not any(w in t for w in ["apaga", "off", "apagar"])]
        if tool_name == "send_sms":
            num = re.search(r'(\+?\d{7,15})', text)
            msg = re.search(r'(?:mensaje|texto)[":\s]+(.+)', text, re.IGNORECASE)
            if num:
                return "send_sms", [num.group(1), msg.group(1) if msg else "Hola"]
            continue
        if tool_name in ("ping", "scan_ports"):
            ip = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
            if ip:
                return tool_name, [ip.group(1)]
            continue
        return tool_name, []
    return None, []

def try_execute_action(text: str):
    """Si el texto pide una acción real, la ejecuta y devuelve respuesta
    honesta (str) — o None si no hay acción (seguir al chat normal)."""
    tool_name, args = detect_action(text)
    if not tool_name:
        return None
    result = execute_tool(tool_name, *args)
    tool = get_tool(tool_name)
    desc = tool.description if tool else tool_name
    res_str = result.get("result", "") if isinstance(result, dict) else str(result)
    ok = isinstance(result, dict) and result.get("success", False) and not str(res_str).startswith("❌")
    if ok:
        return f"☀️ {res_str}"
    err = result.get("error") if isinstance(result, dict) else None
    return f"☀️ Intenté '{desc}' pero no pude: {err or res_str or 'algo falló'}."
