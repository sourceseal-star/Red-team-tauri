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
# REGISTRO DE HERRAMIENTAS — 38 herramientas
# ============================================================
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
    log(f"📊 Resultado de {name}: {str(result)[:200]}")
    return result
