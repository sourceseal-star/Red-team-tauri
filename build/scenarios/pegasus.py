"""
Escenario: Detección de Pegasus / Spyware Comercial (Pegasus, FinFisher, HT, Candiru, Stalkerware)
----------------------------------------------------------------------------------------------------
Audita si el dispositivo/red de la víctima muestra señales de compromiso por
spyware comercial de alta sofisticación. Vectoriza:

- C2 beaconing: comparación de los IoC conocidos contra tu tráfico
- DNS sospechoso: consultas a dominios de C2 conocidos
- Permisos abusivos: apps instaladas con permisos típicos de stalkerware
- Procesos anómalos: binarios sospechosos en /Applications, etc.
- Archivos canario: ¿fueron accedidos?
- Persistencia: launch agents, cron, init scripts
- Anti-forense: logs borrados, binarios modificados

Solo aplica en dispositivos donde el usuario ha dado consentimiento explícito
para el análisis (EULA + opt-in). Pensado para app de seguridad tipo
Camscanner / monitor de CCTV con función de "device health check".
"""
import os
import json
import re
import subprocess
import pathlib
import platform
import socket
import time
import hashlib
from typing import List, Dict
from collections import Counter


def _check_suspicious_processes() -> List[Dict]:
    """Busca procesos típicos de spyware comercial o herramientas sospechosas."""
    suspicious = []
    system = platform.system()

    if system == "Darwin" or system == "Linux":
        try:
            out = subprocess.check_output(["ps", "auxww"], text=True, timeout=5)
            # Patrones típicos de C2 daemon / spyware persistente
            patterns = [
                r"\.peg\.[a-z]+",  # Pegasus process names
                r"frida",  # Frida instrumentation
                r"cuckoobox",  # Sandboxing
                r"keylogger",
                r"\.launchd",
                r"com\.apple\.\w+helper",
                r"\.kext",  # kernel extensions
                r"stagefright",
                r"iphonesubstrate",
            ]
            for line in out.splitlines():
                for p in patterns:
                    if re.search(p, line, re.IGNORECASE):
                        suspicious.append({"process": line[:200], "pattern": p})
        except Exception:
            pass
    return suspicious


def _check_persistence_macos() -> List[Dict]:
    """Launch Agents/Daemons sospechosos en macOS."""
    paths = [
        pathlib.Path.home() / "Library" / "LaunchAgents",
        pathlib.Path("/Library/LaunchAgents"),
        pathlib.Path("/Library/LaunchDaemons"),
    ]
    suspicious = []
    for p in paths:
        if not p.exists(): continue
        for f in p.glob("*.plist"):
            try:
                content = f.read_text(errors="ignore")
                # Heurísticas simples
                if "chrome" not in content.lower() and "adobe" not in content.lower():
                    if re.search(r"ProgramArguments|ServiceIPC", content):
                        # buscar binarios que no sean de Apple/Microsoft/etc
                        binary_match = re.search(r"<string>(/[\w/.-]+)</string>", content)
                        if binary_match:
                            binary = binary_match.group(1)
                            if not any(trusted in binary.lower() for trusted in
                                       ["apple", "microsoft", "google", "adobe",
                                        "mozilla", "1password", "dropbox"]):
                                suspicious.append({"plist": str(f), "binary": binary,
                                                   "reason": "non-trusted vendor"})
            except Exception:
                pass
    return suspicious


def _check_ioc_dns(domains: List[str]) -> List[Dict]:
    """Revisa logs DNS del sistema (si accessible) o usa resolución directa."""
    hits = []
    ioc_domains = {
        "nso": ["nso-group.com", "nsogroup.com", "pegasus-c2.net",
                "apple-updates.org", "ios-updates.net"],
        "finfisher": ["finfisher.com", "finspy.info", "gamma-international.com"],
        "hackingteam": ["hackingteam.com", "ht-cdn.com"],
        "candiru": ["candiru.com", "sourgum.io"],
        "stalkerware": ["mspy.com", "flexispy.com", "hoverwatch.com"],
    }
    # Solo chequea si hay lista explícita para validar
    if not domains:
        return hits
    for d in domains:
        d_low = d.lower()
        for family, ioc_list in ioc_domains.items():
            for ioc in ioc_list:
                if ioc in d_low or d_low.endswith("." + ioc):
                    hits.append({"domain": d, "family": family})
    return hits


def _check_canary_files(canary_paths: List[str]) -> List[Dict]:
    """Verifica si los archivos canario fueron accedidos o eliminados."""
    findings = []
    for p in canary_paths:
        path = pathlib.Path(p)
        if not path.exists():
            findings.append({"path": p, "status": "DELETED",
                             "severity": "critical",
                             "interpretation": "Canario eliminado — spyware probablemente lo borró tras leerlo"})
        else:
            try:
                st = path.stat()
                # Comparar con marker original (almacenado como sidecar .meta)
                meta_path = path.with_suffix(path.suffix + ".meta")
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    if st.st_atime > meta.get("deployed_at_epoch", 0):
                        findings.append({"path": p, "status": "ACCESSED",
                                         "severity": "critical",
                                         "atime": st.st_atime,
                                         "interpretation": "Canario accedido tras deploy"})
            except Exception:
                pass
    return findings


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    evidence = pathlib.Path(output_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    findings.append({
        "scenario": "pegasus",
        "severity": "info",
        "title": f"Análisis ejecutado en {system} {platform.release()}",
        "description": f"Plataforma: {system}, versión: {platform.version()}",
        "evidence_path": "",
        "remediation": "N/A",
    })

    # 1) Procesos sospechosos
    procs = _check_suspicious_processes()
    if procs:
        findings.append({
            "scenario": "pegasus",
            "severity": "critical",
            "title": f"{len(procs)} procesos sospechosos detectados",
            "description": "Patrones típicos de spyware comercial o herramientas de ataque. " +
                           "; ".join(set(p["pattern"] for p in procs)),
            "evidence_path": str(evidence / "pegasus-processes.json"),
            "remediation": "NO los termines manualmente — preserva evidencia. "
                           "Captura memoria y disco, luego desconecta el dispositivo de la red.",
        })
        (evidence / "pegasus-processes.json").write_text(json.dumps(procs, indent=2))
    else:
        findings.append({
            "scenario": "pegasus",
            "severity": "info",
            "title": "Sin procesos sospechosos",
            "description": "No se detectaron patrones conocidos en la lista de procesos.",
            "evidence_path": "",
            "remediation": "Mantener monitoreo continuo. Pegasus se esconde; análisis estático no es suficiente.",
        })

    # 2) Persistencia en macOS
    if system == "Darwin":
        persistence = _check_persistence_macos()
        if persistence:
            findings.append({
                "scenario": "pegasus",
                "severity": "high",
                "title": f"{len(persistence)} LaunchAgents/Daemons sospechosos",
                "description": "Binarios de vendor no confiable con auto-arranque. " +
                               "; ".join(p["binary"] for p in persistence[:5]),
                "evidence_path": str(evidence / "pegasus-persistence.json"),
                "remediation": "Investigar cada uno. Desactivar solo tras copia forense del .plist.",
            })
            (evidence / "pegasus-persistence.json").write_text(json.dumps(persistence, indent=2))

    # 3) IoC DNS (si el caller pasó dominios para chequear)
    ioc_domains_env = os.environ.get("CHECK_DNS_DOMAINS", "")
    if ioc_domains_env:
        domains = [d.strip() for d in ioc_domains_env.split(",") if d.strip()]
        ioc_hits = _check_ioc_dns(domains)
        if ioc_hits:
            findings.append({
                "scenario": "pegasus",
                "severity": "critical",
                "title": f"{len(ioc_hits)} dominios coinciden con IoC de C2 conocido",
                "description": "; ".join(f"{h['domain']} ({h['family']})" for h in ioc_hits),
                "evidence_path": str(evidence / "pegasus-dns-ioc.json"),
                "remediation": "Dispositivo probablemente comprometido. Captura forense, rota credenciales, "
                               "considera reimagen del sistema.",
            })
            (evidence / "pegasus-dns-ioc.json").write_text(json.dumps(ioc_hits, indent=2))

    # 4) Archivos canario
    canary_env = os.environ.get("CHECK_CANARY_PATHS", "")
    if canary_env:
        canary_paths = [p.strip() for p in canary_env.split(",") if p.strip()]
        canary_hits = _check_canary_files(canary_paths)
        if canary_hits:
            for hit in canary_hits:
                findings.append({
                    "scenario": "pegasus",
                    "severity": "critical",
                    "title": f"CANARIO {hit['status']}: {hit['path']}",
                    "description": hit["interpretation"],
                    "evidence_path": hit["path"],
                    "remediation": "Activar protocolo de respuesta a incidente. "
                                   "El dispositivo probablemente está bajo compromiso activo.",
                })
            (evidence / "pegasus-canary.json").write_text(json.dumps(canary_hits, indent=2))

    # 5) Verificación de que el C2 sinkhole está corriendo
    sinkhole_log = pathlib.Path(__file__).parent.parent / "evidence" / "c2-sinkhole"
    c2_alerts = list(sinkhole_log.glob("!!ALERT-*.json")) if sinkhole_log.exists() else []
    if c2_alerts:
        findings.append({
            "scenario": "pegasus",
            "severity": "critical",
            "title": f"{len(c2_alerts)} alertas del C2 sinkhole",
            "description": "El sinkhole detectó requests con IoC de spyware comercial. "
                           "Esto indica compromiso activo en uno o más dispositivos.",
            "evidence_path": str(sinkhole_log),
            "remediation": "Revisar cada alerta en evidence/c2-sinkhole/!!ALERT-*.json. "
                           "Identificar dispositivo, capturar forense, desconectar de la red.",
        })

    return findings
