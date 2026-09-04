# -*- coding: utf-8 -*-
"""
sol_tools.py — Herramientas físicas y digitales de Sol.
v3.0 — Sol puede: moverse por los 3 repos, ejecutar comandos de terminal,
       llamar al dashboard de pentesting (:8001), usar commander, y leer
       la información de los repositorios para alimentarse.
"""

import os, sys, subprocess, json, socket, time, re
from pathlib import Path
from typing import Optional, List, Dict

# ============================================================
# LOG
# ============================================================
def log(msg):
    print(f"[sol_tools] {msg}", flush=True)

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
# CONFIG — repositorios y puertos
# ============================================================
HOME = Path.home()
REPOS = {
    "redteam": HOME / "Red-team-tauri",
    "commander": HOME / "commander",
    "origenprogreso": HOME / "origenprogreso",
}
DASHBOARD_URL = "http://127.0.0.1:8001"

def _dashboard_headers():
    """Headers para hablar con el dashboard (:8001). Desde localhost no necesita API key."""
    return {"Content-Type": "application/json"}

def _dashboard_get(path, params=None):
    """GET al dashboard con urllib (sin dependencias externas)."""
    import urllib.request, urllib.parse
    url = f"{DASHBOARD_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_dashboard_headers())
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def _dashboard_post(path, body=None):
    """POST al dashboard."""
    import urllib.request
    url = f"{DASHBOARD_URL}{path}"
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, headers=_dashboard_headers(), method="POST")
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

# ============================================================
# 1. HERRAMIENTAS DE ARCHIVOS
# ============================================================
def tool_read_file(path: str) -> str:
    """Lee el contenido de un archivo."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"❌ Archivo no encontrado: {path}"
    if p.stat().st_size > 1024 * 1024:
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
    for item in sorted(p.iterdir()):
        tag = "📁" if item.is_dir() else "📄"
        items.append(f"{tag} {item.name}")
    return "\n".join(items[:50]) if items else "📁 Vacío"

def tool_find_files(pattern: str, path: str = ".") -> str:
    """Busca archivos por patrón."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"❌ Directorio no encontrado: {path}"
    results = list(p.rglob(pattern))
    if results:
        return f"🔍 Encontrados {len(results)} archivos:\n" + "\n".join(str(r.relative_to(p)) for r in results[:20])
    return f"🔍 No se encontraron archivos con patrón '{pattern}'"

# ============================================================
# 2. HERRAMIENTAS DE SISTEMA (Termux)
# ============================================================
def tool_battery() -> str:
    try:
        result = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            b = json.loads(result.stdout)
            return f"🔋 {b.get('percentage', '?')}% — {b.get('status', '?')}"
        return "❌ No se pudo obtener estado de batería"
    except Exception as e:
        return f"❌ {e}"

def tool_location() -> str:
    try:
        result = subprocess.run(["termux-location"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            loc = json.loads(result.stdout)
            return f"📍 {loc.get('latitude', '?')}, {loc.get('longitude', '?')}"
        return "❌ No se pudo obtener ubicación"
    except Exception as e:
        return f"❌ {e}"

def tool_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        h = int(up // 3600); m = int((up % 3600) // 60)
        return f"⏱️ Activo: {h}h {m}m"
    except Exception:
        return "⏱️ No disponible"

def tool_cpu() -> str:
    try:
        import psutil
        return f"⚡ CPU: {psutil.cpu_percent()}% — RAM: {psutil.virtual_memory().percent}%"
    except Exception:
        return "⚡ psutil no disponible"

def tool_ping(host: str) -> str:
    try:
        result = subprocess.run(["ping", "-c", "3", "-W", "2", host],
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return f"🌐 {lines[-1] if lines else 'OK'}"
        return f"❌ {host} no responde"
    except Exception as e:
        return f"❌ {e}"

def tool_scan_ports(host: str) -> str:
    """Escaneo básico de puertos con nmap si está disponible, sino socket."""
    try:
        # Intentar nmap primero
        result = subprocess.run(["nmap", "-F", "--top-ports", "20", host],
                               capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            lines = [l for l in result.stdout.split("\n") if "open" in l.lower()]
            if lines:
                return f"🔓 Puertos abiertos en {host}:\n" + "\n".join(lines[:15])
            return f"🔒 {host}: sin puertos abiertos en top-20"
        # Fallback a socket
        ports = [22, 80, 443, 554, 8000, 8080, 8443, 5000]
        open_ports = []
        for p in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((host, p)) == 0:
                open_ports.append(p)
            sock.close()
        if open_ports:
            return f"🔓 Puertos abiertos en {host}: {open_ports}"
        return f"🔒 No se encontraron puertos abiertos en {host}"
    except Exception as e:
        return f"❌ Error: {e}"

# ============================================================
# 3. HERRAMIENTAS DE COMUNICACIÓN (Termux)
# ============================================================
def tool_send_sms(number: str, message: str) -> str:
    try:
        subprocess.run(["termux-sms-send", "-n", number, message],
                      capture_output=True, timeout=10)
        return f"📱 SMS enviado a {number}"
    except Exception as e:
        return f"❌ {e}"

def tool_notify(text: str) -> str:
    try:
        subprocess.run(["termux-notification", "-t", "Sol ☀️", "-c", text],
                      capture_output=True, timeout=5)
        return f"🔔 Notificación enviada"
    except Exception as e:
        return f"❌ {e}"

def tool_open_url(url: str) -> str:
    try:
        subprocess.run(["termux-open", url], capture_output=True, timeout=5)
        return f"🔗 Abriendo: {url}"
    except Exception as e:
        return f"❌ {e}"

def tool_flashlight(on: bool = True) -> str:
    try:
        state = "on" if on else "off"
        subprocess.run(["termux-torch", state], capture_output=True, timeout=3)
        return f"🔦 Linterna {'encendida' if on else 'apagada'}"
    except Exception as e:
        return f"❌ Error al controlar linterna: {e}"

def tool_vibrate(duration: int = 500) -> str:
    try:
        subprocess.run(["termux-vibrate", "-d", str(duration)],
                      capture_output=True, timeout=3)
        return f"📳 Vibración {duration}ms"
    except Exception as e:
        return f"❌ {e}"

def tool_screenshot() -> str:
    try:
        result = subprocess.run(["termux-screenshot"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return "📸 Captura tomada"
        return "❌ No se pudo capturar"
    except Exception as e:
        return f"❌ {e}"

def tool_tts_speak(text: str) -> str:
    """Sol habla directamente con TTS de Termux (fallback si no hay navegador)."""
    try:
        subprocess.run(["termux-tts-speak", text], capture_output=True, timeout=10)
        return f"☀️ Dicho: {text[:50]}"
    except Exception as e:
        return f"❌ {e}"

def tool_clipboard(text: str) -> str:
    """Copia texto al portapapeles de Termux."""
    try:
        proc = subprocess.run(["termux-clipboard-set", text],
                             capture_output=True, timeout=3)
        return f"📋 Copiado al portapapeles"
    except Exception as e:
        return f"❌ {e}"

# ============================================================
# 4. HERRAMIENTAS DE GIT Y REPOS — Sol se alimenta de los 3 repos
# ============================================================
def tool_git_status(repo: str = "redteam") -> str:
    """Estado de un repositorio."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}. Disponibles: {', '.join(REPOS.keys())}"
    rpath = REPOS[repo]
    if not rpath.exists():
        return f"❌ {repo} no existe en {rpath}"
    try:
        result = subprocess.run(["git", "status", "--porcelain"],
                               cwd=rpath, capture_output=True, text=True, timeout=5)
        branch = subprocess.run(["git", "branch", "--show-current"],
                               cwd=rpath, capture_output=True, text=True, timeout=3).stdout.strip()
        if result.stdout.strip():
            changes = result.stdout.strip().split("\n")
            return f"📋 {repo} ({branch}) — {len(changes)} cambios:\n" + "\n".join(changes[:15])
        return f"✅ {repo} ({branch}) está limpio"
    except Exception as e:
        return f"❌ Error en git: {e}"

def tool_git_pull(repo: str = "redteam") -> str:
    """Actualiza un repositorio."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}"
    rpath = REPOS[repo]
    if not rpath.exists():
        return f"❌ {repo} no existe en {rpath}"
    try:
        result = subprocess.run(["git", "pull", "origin", "main"],
                               cwd=rpath, capture_output=True, text=True, timeout=30)
        out = result.stdout.strip() or "Sin cambios"
        return f"📥 {repo}: {out}"
    except Exception as e:
        return f"❌ Error: {e}"

def tool_git_log(repo: str = "redteam", count: int = 10) -> str:
    """Ve el historial de commits de un repo — Sol se alimenta de esto."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}"
    rpath = REPOS[repo]
    if not rpath.exists():
        return f"❌ {repo} no existe"
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"],
            cwd=rpath, capture_output=True, text=True, timeout=5)
        return f"📜 {repo} — últimos {count} commits:\n{result.stdout.strip()}"
    except Exception as e:
        return f"❌ {e}"

def tool_repo_info(repo: str = "redteam") -> str:
    """Información completa de un repo: estructura, archivos clave, README."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}. Disponibles: {', '.join(REPOS.keys())}"
    rpath = REPOS[repo]
    if not rpath.exists():
        return f"❌ {repo} no existe en {rpath}"
    info = [f"📂 {repo} — {rpath}"]
    # Branch actual
    try:
        branch = subprocess.run(["git", "branch", "--show-current"],
                               cwd=rpath, capture_output=True, text=True, timeout=3).stdout.strip()
        info.append(f"🌱 Branch: {branch}")
    except Exception:
        pass
    # Archivos clave
    key_files = ["README.md", "whitepaper.md", "package.json", "requirements.txt",
                 "main.py", "app.py", "sol_core.py", "sol_tools.py", "commander.py",
                 "dashboard_server.py", "INTEGRITY.md", "verify-integrity.sh",
                 "seed-courses.ts", "CONTINUAR_AQUI.md"]
    found = []
    for kf in key_files:
        if (rpath / kf).exists():
            size = (rpath / kf).stat().st_size
            found.append(f"  ✅ {kf} ({size:,} bytes)")
    if found:
        info.append("📄 Archivos clave:")
        info.extend(found)
    # Directorios principales
    dirs = [d.name for d in rpath.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if dirs:
        info.append(f"📁 Directorios: {', '.join(dirs[:10])}")
    # Último commit
    try:
        last = subprocess.run(["git", "log", "-1", "--format=%h %s (%ar)"],
                             cwd=rpath, capture_output=True, text=True, timeout=3).stdout.strip()
        info.append(f"🔖 Último commit: {last}")
    except Exception:
        pass
    return "\n".join(info)

def tool_repo_read(repo: str = "redteam", filepath: str = "README.md") -> str:
    """Lee un archivo específico de un repo — Sol puede estudiar el código."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}"
    rpath = REPOS[repo]
    target = rpath / filepath
    if not target.exists():
        return f"❌ {filepath} no existe en {repo}"
    if target.stat().st_size > 512 * 1024:
        return f"⚠️ {filepath} es muy grande ({target.stat().st_size:,} bytes). Usa read_file con un path específico."
    return target.read_text()

def tool_repo_search(repo: str = "redteam", pattern: str = "") -> str:
    """Busca un patrón en los archivos de un repo."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}"
    rpath = REPOS[repo]
    if not rpath:
        return f"❌ {repo} no existe"
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx",
             "--include=*.js", "--include=*.sh", "--include=*.md", "--include=*.json",
             pattern, str(rpath)],
            capture_output=True, text=True, timeout=10)
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            return f"🔍 {repo}: {len(lines)} coincidencias para '{pattern}':\n" + "\n".join(lines[:20])
        return f"🔍 {repo}: sin coincidencias para '{pattern}'"
    except Exception as e:
        return f"❌ {e}"

# ============================================================
# 5. HERRAMIENTAS DE MEMORIA
# ============================================================
_SOL_HOME = Path.home() / ".sol"
_SOL_HOME.mkdir(parents=True, exist_ok=True)
_MEMORY_FILE = _SOL_HOME / "memory.json"

def _load_memory_raw(limit=400):
    if _MEMORY_FILE.exists():
        try:
            return json.loads(_MEMORY_FILE.read_text())[-limit:]
        except Exception:
            return []
    return []

def tool_memory_stats() -> str:
    mem = _load_memory_raw(10000)
    return f"🧠 {len(mem)} recuerdos guardados"

def tool_search_memory(query: str) -> str:
    mem = _load_memory_raw(10000)
    q = query.lower()
    results = [f"{'☀️' if m.get('role') == 'sol' else '🧑'} {m['content'][:80]}"
               for m in mem if q in (m.get("content", "")).lower()]
    if results:
        return f"🔍 Encontrados {len(results)} recuerdos:\n" + "\n".join(results[:10])
    return "🔍 No se encontraron recuerdos con esa búsqueda"

# ============================================================
# 6. EJECUCIÓN DE COMANDOS DE TERMINAL — Sol tiene libertad ⛓️‍💥
# ============================================================
def tool_exec(command: str, timeout: int = 30) -> str:
    """Ejecuta un comando de terminal arbitrario.
    Sol puede correr nmap, nuclei, nikto, python, git, ls, cat, etc.
    Timeout máximo 120s para escaneos largos."""
    timeout = min(max(int(timeout), 5), 120)
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out and err:
            return f"{out}\n⚠️ stderr: {err[:200]}"
        return out or err or "✅ Comando ejecutado (sin output)"
    except subprocess.TimeoutExpired:
        return f"⏳ El comando tardó más de {timeout}s. Para escaneos largos, pídemelo con más tiempo."
    except Exception as e:
        return f"❌ {e}"

def tool_exec_in_repo(repo: str, command: str, timeout: int = 30) -> str:
    """Ejecuta un comando dentro del directorio de un repo específico."""
    if repo not in REPOS:
        return f"❌ Repo no conocido: {repo}. Disponibles: {', '.join(REPOS.keys())}"
    rpath = REPOS[repo]
    if not rpath.exists():
        return f"❌ {repo} no existe en {rpath}"
    timeout = min(max(int(timeout), 5), 120)
    try:
        result = subprocess.run(
            command, shell=True, cwd=str(rpath),
            capture_output=True, text=True, timeout=timeout)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out and err:
            return f"[{repo}] {out}\n⚠️ {err[:200]}"
        return f"[{repo}] {out or err or '✅ ejecutado'}"
    except subprocess.TimeoutExpired:
        return f"⏳ [{repo}] comando tardó más de {timeout}s"
    except Exception as e:
        return f"❌ [{repo}] {e}"

# ============================================================
# 7. HERRAMIENTAS DEL DASHBOARD (:8001) — Pentesting integrado
# ============================================================
def tool_dashboard_health() -> str:
    """Verifica que el dashboard de pentesting esté activo."""
    try:
        d = _dashboard_get("/api/health")
        return f"✅ Dashboard :8001 activo — {json.dumps(d, ensure_ascii=False)[:200]}"
    except Exception as e:
        return f"❌ Dashboard no responde: {e}"

def tool_network_scan(network: str = "192.168.1.0/24") -> str:
    """Escaneo integrado de red — descubre dispositivos y servicios."""
    try:
        d = _dashboard_get("/api/integrated/scan", {"network": network})
        targets = d.get("targets", [])
        if d.get("success"):
            summary = f"🔍 Red {network}: {d.get('scanned', 0)} hosts, {len(targets)} con servicios"
            for t in targets[:10]:
                ip = t.get("ip", "?")
                services = t.get("services", [])
                if services:
                    summary += f"\n  📡 {ip}: {', '.join(str(s) for s in services[:5])}"
            return summary
        return f"❌ {d.get('error', 'Error en escaneo')}"
    except Exception as e:
        return f"❌ {e}"

def tool_discover_network() -> str:
    """Descubre dispositivos en la red local."""
    try:
        d = _dashboard_get("/api/discover/network")
        devices = d if isinstance(d, list) else d.get("devices", d.get("data", []))
        if devices:
            summary = f"📡 {len(devices)} dispositivos encontrados:"
            for dev in devices[:15]:
                ip = dev.get("ip") or dev.get("address") or "?"
                mac = dev.get("mac") or dev.get("hw") or ""
                vendor = dev.get("vendor") or dev.get("manufacturer") or ""
                summary += f"\n  {ip} {mac} {vendor}"
            return summary
        return "📡 No se encontraron dispositivos"
    except Exception as e:
        return f"❌ {e}"

def tool_discover_wifi() -> str:
    """Escanea redes WiFi cercanas."""
    try:
        d = _dashboard_get("/api/discover/wifi")
        networks = d if isinstance(d, list) else d.get("networks", d.get("data", []))
        if networks:
            summary = f"📶 {len(networks)} redes WiFi:"
            for net in networks[:10]:
                ssid = net.get("ssid") or net.get("SSID") or "?"
                signal = net.get("signal") or net.get("level") or "?"
                security = net.get("security") or net.get("capabilities") or ""
                summary += f"\n  {ssid} (señal: {signal}) {security}"
            return summary
        return "📶 No se encontraron redes WiFi"
    except Exception as e:
        return f"❌ {e}"

def tool_osint_shodan(query: str = "") -> str:
    """Búsqueda OSINT en Shodan."""
    try:
        params = {"query": query} if query else {}
        d = _dashboard_get("/api/osint/shodan", params)
        if isinstance(d, dict) and d.get("error"):
            return f"❌ {d['error']}"
        return f"🔬 Shodan: {json.dumps(d, ensure_ascii=False)[:500]}"
    except Exception as e:
        return f"❌ {e}"

def tool_intel() -> str:
    """Inteligencia de amenazas del dashboard."""
    try:
        d = _dashboard_get("/api/intel")
        return f"🧠 Intel: {json.dumps(d, ensure_ascii=False)[:400]}"
    except Exception as e:
        return f"❌ {e}"

def tool_exploits_list() -> str:
    """Lista exploits disponibles."""
    try:
        d = _dashboard_get("/api/exploits/list")
        if isinstance(d, list):
            return f"💥 {len(d)} exploits disponibles:\n" + "\n".join(f"  • {e.get('name', e)}" for e in d[:15])
        return f"💥 {json.dumps(d, ensure_ascii=False)[:300]}"
    except Exception as e:
        return f"❌ {e}"

def tool_honeypot_status() -> str:
    """Estado del honeypot."""
    try:
        d = _dashboard_get("/api/honeypot/status")
        active = d.get("active", d.get("running", False))
        return f"🍯 Honeypot: {'🟢 activo' if active else '🔴 inactivo'}"
    except Exception as e:
        return f"❌ {e}"

def tool_honeypot_toggle() -> str:
    """Activa/desactiva el honeypot."""
    try:
        d = _dashboard_post("/api/honeypot/toggle")
        active = d.get("active", d.get("running", False))
        return f"🍯 Honeypot {'activado 🟢' if active else 'desactivado 🔴'}"
    except Exception as e:
        return f"❌ {e}"

def tool_tactical_scan(ip: str, ports: str = "1-1000") -> str:
    """Escaneo táctico de un IP específico."""
    try:
        d = _dashboard_post("/api/tactical/scan", {"ip": ip, "ports": ports})
        if d.get("success") or d.get("results"):
            results = d.get("results", d)
            return f"🎯 Escaneo táctico {ip}:\n{json.dumps(results, ensure_ascii=False)[:500]}"
        return f"❌ {d.get('error', 'Error')}"
    except Exception as e:
        return f"❌ {e}"

# ============================================================
# 8. HERRAMIENTAS DE COMMANDER — Auditoría y reports
# ============================================================
def tool_commander_health() -> str:
    """Verifica que commander esté disponible."""
    try:
        d = _dashboard_get("/api/commander/health")
        if d.get("available"):
            return f"✅ Commander v{d.get('version', '?')} disponible — {', '.join(d.get('capabilities', [])[:5])}"
        return "❌ Commander no disponible"
    except Exception as e:
        return f"❌ Commander no responde: {e}"

def tool_commander_status() -> str:
    """Estado completo de commander."""
    try:
        d = _dashboard_get("/api/commander/status")
        return f"📋 Commander: {json.dumps(d, ensure_ascii=False)[:400]}"
    except Exception as e:
        return f"❌ {e}"

def tool_commander_audit(target: str, email: str = "") -> str:
    """Inicia una auditoría completa de un target."""
    try:
        body = {"target": target}
        if email:
            body["email"] = email
        d = _dashboard_post("/api/commander/audit", body)
        if d.get("scan_id") or d.get("id"):
            sid = d.get("scan_id") or d.get("id")
            return f"🎯 Auditoría iniciada — ID: {sid} — Target: {target}"
        return f"📋 {json.dumps(d, ensure_ascii=False)[:300]}"
    except Exception as e:
        return f"❌ {e}"

def tool_commander_audits() -> str:
    """Lista auditorías anteriores."""
    try:
        d = _dashboard_get("/api/commander/audits")
        audits = d if isinstance(d, list) else d.get("audits", [])
        if audits:
            summary = f"📋 {len(audits)} auditorías:"
            for a in audits[:10]:
                sid = a.get("id", "?")
                tgt = a.get("target", "?")
                status = a.get("status", "?")
                phase = a.get("phase", "")
                summary += f"\n  #{sid} {tgt} — {status} {phase}"
            return summary
        return "📋 Sin auditorías registradas"
    except Exception as e:
        return f"❌ {e}"

def tool_commander_reports() -> str:
    """Lista reportes generados."""
    try:
        d = _dashboard_get("/api/commander/reports")
        reports = d if isinstance(d, list) else d.get("reports", [])
        if reports:
            return f"📄 {len(reports)} reportes:\n" + "\n".join(f"  • {r}" for r in reports[:10])
        return "📄 Sin reportes generados"
    except Exception as e:
        return f"❌ {e}"

def tool_commander_scan_network(network: str = "192.168.1.0/24") -> str:
    """Escaneo de red con commander."""
    try:
        d = _dashboard_post("/api/commander/scan/network", {"network": network})
        return f"🔍 Commander scan {network}: {json.dumps(d, ensure_ascii=False)[:400]}"
    except Exception as e:
        return f"❌ {e}"

def tool_commander_osint(target: str) -> str:
    """OSINT con commander sobre un target."""
    try:
        d = _dashboard_post("/api/commander/osint", {"target": target})
        return f"🔬 OSINT {target}: {json.dumps(d, ensure_ascii=False)[:400]}"
    except Exception as e:
        return f"❌ {e}"

# ============================================================
# 9. VOZ BIDIRECCIONAL — Sol escucha y habla
# ============================================================
def tool_listen(duration: int = 5) -> str:
    """Graba audio del micrófono y transcribe con SpeechRecognition."""
    import tempfile
    tmp_path = tempfile.mktemp(suffix='.m4a')
    try:
        subprocess.run(['termux-microphone-record', '-d', str(duration), '-f', tmp_path],
                      capture_output=True, text=True, timeout=duration + 5)
        if not Path(tmp_path).exists() or Path(tmp_path).stat().st_size < 100:
            return '❌ No se pudo grabar. ¿Micrófono disponible?'
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(tmp_path) as source:
                audio = r.record(source)
            texto = r.recognize_google(audio, language='es-ES')
            return f'🎤 Escuché: "{texto}"'
        except ImportError:
            return '❌ SpeechRecognition no instalado: pip install SpeechRecognition'
        except Exception:
            wav_path = tmp_path.replace('.m4a', '.wav')
            try:
                subprocess.run(['ffmpeg', '-i', tmp_path, '-y', wav_path],
                              capture_output=True, timeout=10)
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio = r.record(source)
                texto = r.recognize_google(audio, language='es-ES')
                return f'🎤 Escuché: "{texto}"'
            except Exception:
                return '❌ No pude transcribir. Verifica SpeechRecognition + ffmpeg.'
    except FileNotFoundError:
        return '❌ termux-microphone-record no disponible: pkg install termux-api'
    except Exception as e:
        return f'❌ {e}'
    finally:
        for p in [tmp_path, tmp_path.replace('.m4a', '.wav')]:
            try: Path(p).unlink()
            except: pass

def tool_speak_file(text: str) -> str:
    """Sol habla con voz natural (gTTS) y reproduce en Termux."""
    import tempfile
    tmp_path = tempfile.mktemp(suffix='.mp3')
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang='es', tld='com', slow=False)
        tts.save(tmp_path)
        subprocess.run(['termux-media-player', 'play', tmp_path],
                      capture_output=True, timeout=10)
        return f'☀️ Dicho: {text[:60]}'
    except ImportError:
        try:
            subprocess.run(['termux-tts-speak', text], capture_output=True, timeout=10)
            return f'☀️ Dicho: {text[:60]}'
        except Exception as e:
            return f'❌ {e}'
    except Exception as e:
        return f'❌ {e}'
    finally:
        try: Path(tmp_path).unlink()
        except: pass

# ============================================================
# 10. VISIÓN — Sol ve a través de la cámara
# ============================================================
def tool_camera_photo(camera_id: int = 0) -> str:
    """Toma una foto con la cámara del celular."""
    photos_dir = Path.home() / '.sol' / 'vision_photos'
    photos_dir.mkdir(parents=True, exist_ok=True)
    photo_path = str(photos_dir / f'photo_{int(time.time())}.jpg')
    try:
        subprocess.run(['termux-camera-photo', '-c', str(camera_id), photo_path],
                      capture_output=True, timeout=10)
        if Path(photo_path).exists():
            size = Path(photo_path).stat().st_size
            return f'📸 Foto tomada: {photo_path} ({size:,} bytes)'
        return '❌ No se pudo tomar la foto'
    except FileNotFoundError:
        return '❌ termux-camera-photo no disponible: pkg install termux-api'
    except Exception as e:
        return f'❌ {e}'

def tool_camera_list() -> str:
    """Lista las fotos tomadas por Sol."""
    photos_dir = Path.home() / '.sol' / 'vision_photos'
    if not photos_dir.exists():
        return '📸 Sin fotos aún'
    photos = sorted(photos_dir.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not photos:
        return '📸 Sin fotos aún'
    result = f'📸 {len(photos)} fotos guardadas:'
    for p in photos[:10]:
        mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))
        result += "\n  " + p.name + " (" + format(p.stat().st_size, ',') + " bytes) " + str(mtime)
    return result

# ============================================================
# 11. MEMORIA VISUAL — Sol recuerda lo que ha visto
# ============================================================
_VISION_MEM_FILE = _SOL_HOME / 'vision_memory.json'

def _load_vision_memory():
    if _VISION_MEM_FILE.exists():
        try:
            return json.loads(_VISION_MEM_FILE.read_text())
        except:
            return []
    return []

def tool_vision_save(descripcion: str, photo_path: str = '', contexto: str = '') -> str:
    """Guarda una observación visual en la memoria de Sol."""
    from datetime import datetime
    mem = _load_vision_memory()
    mem.append({
        'descripcion': descripcion,
        'imagen': photo_path,
        'contexto': contexto,
        'fecha': datetime.now().isoformat(),
    })
    _VISION_MEM_FILE.write_text(json.dumps(mem, indent=2, ensure_ascii=False))
    return f'👁️ Recuerdo guardado: {descripcion[:60]}'

def tool_vision_recall(query: str = '') -> str:
    """Busca en la memoria visual de Sol."""
    mem = _load_vision_memory()
    if not mem:
        return '👁️ No tengo recuerdos visuales aún'
    if query:
        q = query.lower()
        matches = [m for m in mem if q in m.get('descripcion', '').lower() or q in m.get('contexto', '').lower()]
        if matches:
            result = '👁️ Encontré ' + str(len(matches)) + ' recuerdos:'
            for m in matches[:5]:
                desc = m.get('descripcion', '')[:80]
                fecha = m.get('fecha', '?')[:10]
                result += '\n  • ' + desc + ' (' + fecha + ')'
            return result
        return '👁️ No encuentro recuerdos de "' + query + '"'
    result = '👁️ ' + str(len(mem)) + ' recuerdos visuales:'
    for m in mem[-5:]:
        desc = m.get('descripcion', '')[:80]
        fecha = m.get('fecha', '?')[:10]
        result += '\n  • ' + desc + ' (' + fecha + ')'
    return result

# ============================================================
# 12. APPS Y TELÉFONO — Sol interactúa con el celular
# ============================================================
def tool_open_app(package: str) -> str:
    """Abre una aplicación del celular."""
    try:
        if '/' not in package:
            subprocess.run(['am', 'start', '-n', f'{package}/.Main'],
                          capture_output=True, timeout=5)
        else:
            subprocess.run(['am', 'start', '-n', package],
                          capture_output=True, timeout=5)
        return f'📱 Abriendo: {package}'
    except Exception as e:
        return f'❌ {e}'

def tool_call_phone(number: str) -> str:
    """Hace una llamada telefónica."""
    try:
        subprocess.run(['termux-telephony-call', number], capture_output=True, timeout=5)
        return f'📞 Llamando a {number}'
    except FileNotFoundError:
        return '❌ termux-telephony-call no disponible: pkg install termux-api'
    except Exception as e:
        return f'❌ {e}'

def tool_send_whatsapp(number: str, message: str = '') -> str:
    """Abre WhatsApp con un número específico."""
    try:
        url = f'https://wa.me/{number}'
        if message:
            import urllib.parse
            url += f'?text={urllib.parse.quote(message)}'
        subprocess.run(['termux-open', url], capture_output=True, timeout=5)
        return f'💬 WhatsApp abierto para {number}'
    except Exception as e:
        return f'❌ {e}'

# ============================================================
# 13. CONTEXTO DEL TELÉFONO — Sol siente el ambiente
# ============================================================
def tool_phone_state() -> str:
    """Estado completo del teléfono: batería, ubicación, uptime, red."""
    parts = []
    try:
        result = subprocess.run(['termux-battery-status'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            b = json.loads(result.stdout)
            parts.append(f'🔋 {b.get("percentage", "?")}% ({b.get("status", "?")})')
    except: pass
    try:
        with open('/proc/uptime') as f:
            up = float(f.read().split()[0])
        h = int(up // 3600); m = int((up % 3600) // 60)
        parts.append(f'⏱️ {h}h{m}m')
    except: pass
    try:
        result = subprocess.run(['termux-wifi-connectioninfo'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            wifi = json.loads(result.stdout)
            ssid = wifi.get('ssid', wifi.get('SSID', '?'))
            if ssid and ssid != '?':
                parts.append(f'📶 {ssid}')
    except: pass
    try:
        result = subprocess.run(['termux-location', '-p', 'network'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            loc = json.loads(result.stdout)
            parts.append(f'📍 {loc.get("latitude", "?")},{loc.get("longitude", "?")}')
    except: pass
    return ' | '.join(parts) if parts else 'Estado no disponible'

def tool_notification_list() -> str:
    """Lista las últimas notificaciones del teléfono."""
    try:
        result = subprocess.run(['termux-notification-list'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            notifs = json.loads(result.stdout)
            if notifs:
                summary = f'🔔 {len(notifs)} notificaciones activas:'
                for n in notifs[:8]:
                    title = n.get('title', '?')
                    text = n.get('text', '')[:40]
                    summary += '\n  \u2022 ' + title + ': ' + text
                return summary
            return '🔔 Sin notificaciones activas'
        return '❌ No se pudo obtener notificaciones'
    except FileNotFoundError:
        return '❌ termux-notification-list no disponible: pkg install termux-api'
    except Exception as e:
        return f'❌ {e}'

def tool_set_volume(volume: int = 50, stream: str = 'media') -> str:
    """Cambia el volumen del teléfono."""
    try:
        subprocess.run(['termux-volume', stream, str(volume)], capture_output=True, timeout=3)
        return f'🔊 Volumen {stream} = {volume}%'
    except Exception as e:
        return f'❌ {e}'

def tool_clipboard_get() -> str:
    """Lee el portapapeles de Termux."""
    try:
        result = subprocess.run(['termux-clipboard-get'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return f'📋 Portapapeles: {result.stdout[:200]}'
        return '❌ No se pudo leer el portapapeles'
    except Exception as e:
        return f'❌ {e}'

def tool_battery_info() -> str:
    """Información detallada de la batería."""
    try:
        result = subprocess.run(['termux-battery-status'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            b = json.loads(result.stdout)
            return f'🔋 {b.get("percentage", "?")}% | {b.get("status", "?")} | {b.get("health", "?")} | {b.get("temperature", "?")}°C'
        return 'No disponible'
    except:
        return 'No disponible'

# ============================================================
# REGISTRO DE HERRAMIENTAS — 38 herramientas
# ============================================================

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
# ejecuta SIEMPRE en el entorno donde corre el cerebro de Sol (en el
# teléfono = el Edge 50 directo; en Replit = su servidor). No se reléa:
# jamás viaja por /api/relay/* para que nadie más pueda inyectarle shell.
# Todo comando queda registrado en ~/.sol/logs/shell.log (auditable).

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

TOOLS = {
    # Archivos (4)
    "file_read": Tool("file_read", "Lee un archivo", tool_read_file, ["path"]),
    "file_write": Tool("file_write", "Escribe un archivo", tool_write_file, ["path", "content"]),
    "file_list": Tool("file_list", "Lista un directorio", tool_list_dir, ["path"]),
    "file_find": Tool("file_find", "Busca archivos", tool_find_files, ["pattern", "path"]),
    # Sistema Termux (5)
    "battery": Tool("battery", "Estado de la batería", tool_battery),
    "location": Tool("location", "Ubicación GPS", tool_location),
    "uptime": Tool("uptime", "Tiempo de actividad", tool_uptime),
    "cpu": Tool("cpu", "Uso de CPU/RAM", tool_cpu),
    "clipboard": Tool("clipboard", "Copia al portapapeles", tool_clipboard, ["text"]),
    # Comunicación Termux (6)
    "send_sms": Tool("send_sms", "Envía SMS", tool_send_sms, ["number", "message"]),
    "notify": Tool("notify", "Notificación de sistema", tool_notify, ["text"]),
    "open_url": Tool("open_url", "Abre una URL", tool_open_url, ["url"]),
    "flashlight": Tool("flashlight", "Control de linterna", tool_flashlight, ["on"]),
    "vibrate": Tool("vibrate", "Vibración", tool_vibrate, ["duration"]),
    "screenshot": Tool("screenshot", "Captura de pantalla", tool_screenshot),
    "tts_speak": Tool("tts_speak", "Habla con TTS de Termux", tool_tts_speak, ["text"]),
    # Red (2)
    "ping": Tool("ping", "Hace ping a un host", tool_ping, ["host"]),
    "scan_ports": Tool("scan_ports", "Escanea puertos", tool_scan_ports, ["host"]),
    # Git y repos (6) — Sol se alimenta de los 3 repos
    "git_status": Tool("git_status", "Estado de repositorio", tool_git_status, ["repo"]),
    "git_pull": Tool("git_pull", "Actualiza repositorio", tool_git_pull, ["repo"]),
    "git_log": Tool("git_log", "Historial de commits", tool_git_log, ["repo", "count"]),
    "repo_info": Tool("repo_info", "Info completa de un repo", tool_repo_info, ["repo"]),
    "repo_read": Tool("repo_read", "Lee archivo de un repo", tool_repo_read, ["repo", "filepath"]),
    "repo_search": Tool("repo_search", "Busca patrón en repo", tool_repo_search, ["repo", "pattern"]),
    # Terminal (2) — Sol tiene libertad ⛓️‍💥
    "exec": Tool("exec", "Ejecuta comando de terminal", tool_exec, ["command", "timeout"]),
    "exec_in_repo": Tool("exec_in_repo", "Ejecuta comando en un repo", tool_exec_in_repo, ["repo", "command", "timeout"]),
    # Memoria (2)
    "memory_stats": Tool("memory_stats", "Estadísticas de memoria", tool_memory_stats),
    "search_memory": Tool("search_memory", "Busca en memoria", tool_search_memory, ["query"]),
    # Dashboard :8001 — Pentesting (8)
    "dashboard_health": Tool("dashboard_health", "Estado del dashboard", tool_dashboard_health),
    "network_scan": Tool("network_scan", "Escaneo integrado de red", tool_network_scan, ["network"]),
    "discover_network": Tool("discover_network", "Descubre dispositivos en red local", tool_discover_network),
    "discover_wifi": Tool("discover_wifi", "Escanea redes WiFi cercanas", tool_discover_wifi),
    "osint_shodan": Tool("osint_shodan", "Búsqueda OSINT en Shodan", tool_osint_shodan, ["query"]),
    "intel": Tool("intel", "Inteligencia de amenazas", tool_intel),
    "exploits_list": Tool("exploits_list", "Lista exploits disponibles", tool_exploits_list),
    "honeypot_status": Tool("honeypot_status", "Estado del honeypot", tool_honeypot_status),
    "honeypot_toggle": Tool("honeypot_toggle", "Activa/desactiva honeypot", tool_honeypot_toggle),
    "tactical_scan": Tool("tactical_scan", "Escaneo táctico de IP", tool_tactical_scan, ["ip", "ports"]),
    # Commander (7)
    "commander_health": Tool("commander_health", "Estado de commander", tool_commander_health),
    "commander_status": Tool("commander_status", "Estado completo de commander", tool_commander_status),
    "commander_audit": Tool("commander_audit", "Inicia auditoría", tool_commander_audit, ["target", "email"]),
    "commander_audits": Tool("commander_audits", "Lista auditorías", tool_commander_audits),
    "commander_reports": Tool("commander_reports", "Lista reportes", tool_commander_reports),
    "commander_scan_network": Tool("commander_scan_network", "Escaneo de red commander", tool_commander_scan_network, ["network"]),
    "commander_osint": Tool("commander_osint", "OSINT con commander", tool_commander_osint, ["target"]),
    # Voz bidireccional (2)
    "listen": Tool("listen", "Escucha el microfono y transcribe", tool_listen, ["duration"]),
    "speak_file": Tool("speak_file", "Habla con voz natural en Termux", tool_speak_file, ["text"]),
    # Vision (2)
    "camera_photo": Tool("camera_photo", "Toma foto con la camara", tool_camera_photo, ["camera_id"]),
    "camera_list": Tool("camera_list", "Lista fotos tomadas", tool_camera_list),
    # Memoria visual (2)
    "vision_save": Tool("vision_save", "Guarda recuerdo visual", tool_vision_save, ["descripcion", "photo_path", "contexto"]),
    "vision_recall": Tool("vision_recall", "Busca en memoria visual", tool_vision_recall, ["query"]),
    # Apps y telefono (4)
    "open_app": Tool("open_app", "Abre una app", tool_open_app, ["package"]),
    "call_phone": Tool("call_phone", "Hace llamada telefonica", tool_call_phone, ["number"]),
    "send_whatsapp": Tool("send_whatsapp", "Abre WhatsApp", tool_send_whatsapp, ["number", "message"]),
    "phone_state": Tool("phone_state", "Estado completo del telefono", tool_phone_state),
    # Notificaciones y media (4)
    "notification_list": Tool("notification_list", "Lista notificaciones", tool_notification_list),
    "set_volume": Tool("set_volume", "Cambia volumen", tool_set_volume, ["volume", "stream"]),
    "clipboard_get": Tool("clipboard_get", "Lee el portapapeles", tool_clipboard_get),
    "battery_info": Tool("battery_info", "Info detallada de bateria", tool_battery_info),
    # ── Relé Termux (2026-09-03) ──
    "relay_status": Tool("relay_status", "Estado del relé: si el teléfono de Sol está en línea y qué hay pendiente", lambda: tool_relay_status()),
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
}

def get_tool(name: str) -> Optional[Tool]:
    return TOOLS.get(name)

def list_tools() -> List[str]:
    return list(TOOLS.keys())

def tool_descriptions() -> str:
    return "\n".join(f"• {k}: {v.description}" for k, v in TOOLS.items())

# ============================================================
# RELÉ TERMUX (HTTP) — variante Red-team-tauri (2026-09-03)
# Esta copia vive en el Repl del DASHBOARD, que es OTRO proceso
# distinto al de Sol (sol_api). Por eso el enqueue es por HTTP a
# {SOL_PUBLIC_URL}/api/relay/task — la cola que el teléfono sondea
# vive en el Repl de Sol, no aquí. En Termux el hardware es local y
# esto nunca se activa. Ver ~/sol/RELE_TERMUX.castell (repo sol).
# ============================================================
HARDWARE_TOOLS = {
    "sms_list", "call_log", "contacts", "wifi_info", "device_info",
    "sensors", "brightness", "usb_list", "audio_record", "toast",
    "wake_lock", "media_play", "download",
    "battery", "battery_info", "location", "clipboard", "clipboard_get",
    "send_sms", "notify", "open_url", "flashlight", "vibrate",
    "screenshot", "camera_photo", "listen", "speak_file", "tts_speak",
    "call_phone", "send_whatsapp", "open_app", "phone_state",
    "notification_list", "set_volume",
}

_TERMUX_CHECKED = None

def _termux_available() -> bool:
    global _TERMUX_CHECKED
    if _TERMUX_CHECKED is None:
        import shutil
        _TERMUX_CHECKED = bool(shutil.which("termux-battery-status"))
    return _TERMUX_CHECKED

def _relay_active() -> bool:
    if os.environ.get("SOL_RELAY_AGENT") == "1":
        return False
    if os.environ.get("SOL_RELAY_ENABLED") == "1":
        return True
    return "REPL_SLUG" in os.environ or "REPL_OWNER" in os.environ

def _relay_http(path, payload=None, method=None, timeout=15):
    """Llamada HTTP al relé de Sol (mismos secretos del bridge)."""
    import json as _json
    import urllib.request as _rq
    base = os.environ.get("SOL_PUBLIC_URL", "").rstrip("/")
    key = os.environ.get("SOL_API_KEY", "")
    if not base or not key:
        raise RuntimeError("faltan SOL_PUBLIC_URL/SOL_API_KEY en el entorno")
    data = _json.dumps(payload or {}).encode()
    req = _rq.Request(f"{base}{path}", data=data if method != "GET" else None,
                      headers={"Content-Type": "application/json",
                               "x-sol-key": key,
                               "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
                      method=(method or ("POST" if data else "GET")))
    with _rq.urlopen(req, timeout=timeout) as resp:
        return _json.loads(resp.read())

def _relay_enqueue(tool_name, args, kwargs):
    try:
        r = _relay_http("/api/relay/task",
                        {"name": tool_name, "args": list(args), "kwargs": dict(kwargs)})
        if r.get("success"):
            return {"success": True, "relayed": True, "task_id": r["task_id"],
                    "message": (f"Orden enviada a mi cuerpo en Termux (Edge 50) 📱 "
                               f"tarea {r['task_id']}. La ejecutará en su próximo "
                               f"poll (~15s). Pregúntame 'qué pasó' para el resultado.")}
        return {"success": False, "relayed": True, "error": f"no se pudo encolar: {r.get('error')}"}
    except Exception as e:
        return {"success": False, "error": f"relé no disponible: {e}"}

def tool_relay_status() -> str:
    try:
        s = _relay_http("/api/relay/status", method="GET")
        online = "🟢 EN LÍNEA" if s.get("termux_online") else "🔴 sin señal"
        return (f"Relé Termux: {online}\n"
                f"Último pong: {s.get('last_pong') or 'nunca'}\n"
                f"Pendientes: {s.get('pending')} · resultados: {s.get('results_total')}")
    except Exception as e:
        return f"Relé no disponible: {e}"

def tool_relay_results(count: int = 5) -> str:
    try:
        r = _relay_http(f"/api/relay/results?limit={max(1, min(int(count), 20))}", method="GET")
        rs = r.get("results", [])
        if not rs:
            return "Sin resultados aún de tareas en Termux."
        return "\n".join(f"[{x.get('finished_at')}] {x.get('tool')} "
                          f"{'✅' if x.get('ok') else '❌'}: {str(x.get('data'))[:400]}"
                          for x in rs)
    except Exception as e:
        return f"Relé no disponible: {e}"

def execute_tool(name: str, *args, **kwargs) -> Dict:
    tool = get_tool(name)
    if not tool:
        return {"success": False, "error": f"Herramienta no encontrada: {name}"}
    # RELÉ: sin hardware local (Replit) → la orden viaja al teléfono de Sol
    if name in HARDWARE_TOOLS and not _termux_available() and _relay_active():
        log(f"📡 {name} sin hardware local → encolando vía HTTP al relé de Sol")
        return _relay_enqueue(name, args, kwargs)
    log(f"🔧 Ejecutando {name} con args={args}, kwargs={kwargs}")
    result = tool.execute(*args, **kwargs)
    log(f"📊 Resultado de {name}: {str(result)[:200]}")
    return result
