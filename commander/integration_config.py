#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integration_config.py — Configuración centralizada del sistema SourceSeal Commander.

TODOS los módulos (commander.py, sourceseal_tactical.py, OSIRIS connectors)
deben importar su configuración desde aquí.

Uso:
    from integration_config import get_config, CONFIG
    config = get_config()
    port = config["port"]  # 8001
"""

import os
from pathlib import Path
from datetime import datetime

# ============================================================
# RUTAS BASE
# ============================================================
ROOT_DIR = Path(__file__).parent.absolute()
COMLINK_DIR = ROOT_DIR / "comlink"
OSIRIS_DIR = ROOT_DIR / "sourceseal-osiris"

# ============================================================
# CONFIGURACIÓN UNIFICADA
# ============================================================
CONFIG = {
    # ── General ──
    "version": "4.0.0",
    "debug": True,
    "reload": True,
    "host": "0.0.0.0",
    "port": 8001,  # Puerto unificado (standing instruction)

    # ── Base de datos ──
    "commander_db": os.path.expanduser("~/commander.db"),
    "tactical_db": os.path.expanduser("~/seal_tactical.db"),
    "osiris_cache_db": os.path.expanduser("~/connector_cache.db"),

    # ── Commander (auditoría) ──
    "commander": {
        "report_dir": os.path.expanduser("~/storage/downloads/commander_reports"),
        "temp_dir": os.path.expanduser("~/.commander_tmp"),
        "log_path": os.path.expanduser("~/commander.log"),
        "sourceseal_api": "https://source.coal/api/v1/anchor",
        "yara_rules_dir": os.path.expanduser("~/yara_rules"),
        "max_concurrent": 5,
        "encryption_key": os.environ.get("SEAL_ENCRYPTION_KEY", ""),
    },

    # ── TACTICAL (operaciones distribuidas) ──
    "tactical": {
        "mode": "master",
        "master_url": "http://localhost:8001",
        "worker_id": os.urandom(4).hex(),
        "max_workers": 10,
        "scan_timeout": 120,
        "default_ports": "21,22,23,25,53,80,110,135,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017",
        "logs_dir": str(ROOT_DIR / "logs"),
    },

    # ── COM-LINK v3.0 ──
    "comlink": {
        "enabled": True,
        "dir": str(COMLINK_DIR),
        "main_script": str(COMLINK_DIR / "comlink.sh"),
        "encryption_key": os.environ.get("SEAL_MASTER_KEY", ""),
        "channels": ["telegram", "sms", "voip", "mesh_wifi", "mesh_bluetooth", "radio", "satellite"],
    },

    # ── OSIRIS (conectores) ──
    "osiris": {
        "enabled": True,
        "dir": str(OSIRIS_DIR),
        "osiris_url": "http://localhost:3000/api",
        "seal_ws": "ws://localhost:8001/ws/alerts",
        "log_file": os.path.expanduser("~/connector.log"),
        "log_level": "INFO",
        "max_retries": 5,
        "retry_delay": 1.0,
        "enable_camera": False,
        "enable_playbook": True,
    },

    # ── ARTO (Automated Red Team Operations) ──
    "arto": {
        "enabled": True,
        "autostart": True,  # Arranque automático en startup FastAPI (standing instruction)
        "db_path": os.path.expanduser("~/seal_tactical.db"),
        "decision_threshold": 0.75,
        "max_actions_per_minute": 10,
    },

    # ── SEAL (SourceSeal anchoring) ──
    "seal": {
        "enabled": True,
        "autostart": True,  # Arranque automático en startup FastAPI (standing instruction)
        "api_url": "https://source.coal/api/v1/anchor",
        "schnorr_bits": 2048,
    },

    # ── LEVIATHAN (estructura base de UI) ──

    # === IoT & Cámaras (v6.0 — nuevos endpoints Red-team-tauri) ===
    "iot": {
        "base_url": "http://localhost:8001/api/iot",
        "endpoints": {
            "vulns": "/api/iot/vulns",           # GET ?ip=X&port=Y → vendor + CVEs + creds
            "auto_access": "/api/iot/auto-access", # GET ?ip=X&port=Y → orquestación completa
            "batch": "/api/iot/auto-access-batch", # POST {cidr} → escanea red entera
            "snapshot": "/api/iot/snapshot",       # GET ?ip=X&port=Y&user=U&pwd=P → imagen
            "stream": "/api/iot/stream",          # GET ?ip=X&port=Y&path=P → proxy MJPEG
            "scan_network": "/api/iot/scan-network", # POST {cidr} → descubre dispositivos
        },
        "vendors_detected": ["Hikvision", "Dahua", "Xiongmai", "D-Link", "Netgear", "GoAhead", "Ubiquiti"],
        "cve_db": {
            "Hikvision": ["CVE-2021-36260", "CVE-2021-33044", "CVE-2017-7921"],
            "Dahua": ["CVE-2021-33045", "CVE-2020-25078", "CVE-2022-30560"],
            "Xiongmai": ["CVE-2017-17215", "CVE-2017-8225"],
            "D-Link": ["CVE-2019-16920", "CVE-2020-25078"],
            "Netgear": ["CVE-2016-6277"],
            "GoAhead": ["CVE-2017-8225"],
            "Ubiquiti": ["CVE-2021-35064"],
        },
        "default_creds_count": 23,
        "batch_max_concurrency": 8,
        "scan_ports": [554, 80, 443, 8080, 8000, 37777, 8554],
    },
    "leviathan": {
        "enabled": True,
        "flow": ["Detección", "Análisis", "Explotación", "Reportes"],
        "phases": {
            "Detección": {
                "description": "Descubrimiento de objetivos, escaneo de red y fingerprinting",
                "modules": ["scan_network", "scan_cameras", "osint_ip", "osint_domain"],
                "tactical_endpoints": ["/api/scan"],
            },
            "Análisis": {
                "description": "Análisis de vulnerabilidades, OSINT profundo y evaluación de amenazas",
                "modules": ["osint_email", "osint_domain", "anchor_to_sourceseal"],
                "tactical_endpoints": ["/api/playbook/execute", "/api/playbook/list"],
                "playbooks": ["osint_deep_dive"],
            },
            "Explotación": {
                "description": "Ejecución de exploits, playbooks de ataque y registro SEAL",
                "modules": ["scan_cameras", "anchor_to_sourceseal"],
                "tactical_endpoints": ["/api/playbook/execute", "/api/distributed/dispatch"],
                "playbooks": ["hikvision_full_assault"],
            },
            "Reportes": {
                "description": "Generación de informes, alertas y certificados",
                "modules": ["save_report", "anchor_to_sourceseal"],
                "tactical_endpoints": ["/api/alerts", "/api/status"],
                "comlink": True,
            },
        },
    },
}


def get_config(key: str = None):
    """
    Obtener configuración completa o una sección específica.

    Args:
        key: Sección ('commander', 'tactical', 'comlink', 'osiris', 'arto', 'seal', 'leviathan')
             Si es None, retorna el CONFIG completo.

    Returns:
        dict con la configuración solicitada.
    """
    if key is None:
        return CONFIG
    return CONFIG.get(key, {})


def get_port() -> int:
    """Retorna el puerto unificado (8001)."""
    return CONFIG["port"]


def is_debug() -> bool:
    """Retorna si el modo debug está activo."""
    return CONFIG["debug"]


def is_reload() -> bool:
    """Retorna si el reload (hot-reload) está activo."""
    return CONFIG["reload"]


def get_leviathan_flow() -> list:
    """Retorna el flujo LEVIATHAN: ['Detección', 'Análisis', 'Explotación', 'Reportes']."""
    return CONFIG["leviathan"]["flow"]


def get_db_path(module: str = "commander") -> str:
    """
    Obtener la ruta de DB para un módulo específico.

    Args:
        module: 'commander', 'tactical', 'arto', 'osiris'
    """
    mapping = {
        "commander": CONFIG["commander_db"],
        "tactical": CONFIG["tactical_db"],
        "arto": CONFIG["arto"]["db_path"],
        "osiris": CONFIG["osiris_cache_db"],
    }
    return mapping.get(module, CONFIG["commander_db"])


# ============================================================
# VALIDACIÓN AL IMPORTAR
# ============================================================
def _validate():
    """Verifica que las rutas críticas existan o sean creables."""
    issues = []

    # COM-LINK
    if not os.path.exists(CONFIG["comlink"]["main_script"]):
        issues.append(f"COM-LINK no encontrado: {CONFIG['comlink']['main_script']}")

    # commander.py
    if not os.path.exists(ROOT_DIR / "commander.py"):
        issues.append("commander.py no encontrado en ROOT_DIR")

    # Directorios de DB
    for name, path in [("commander_db", CONFIG["commander_db"]),
                      ("tactical_db", CONFIG["tactical_db"])]:
        try:
            db_dir = os.path.dirname(path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            issues.append(f"No se puede crear directorio para {name}: {e}")

    return issues


if __name__ == "__main__":
    print(f"SourceSeal Commander — integration_config.py v{CONFIG['version']}")
    print(f"Puerto: {CONFIG['port']}")
    print(f"Debug: {CONFIG['debug']} | Reload: {CONFIG['reload']}")
    print(f"COM-LINK: {'✅' if os.path.exists(CONFIG['comlink']['main_script']) else '❌'}")
    print(f"OSIRIS dir: {'✅' if os.path.exists(CONFIG['osiris']['dir']) else '❌'}")
    print(f"LEVIATHAN: {' → '.join(CONFIG['leviathan']['flow'])}")
    print(f"ARTO autostart: {CONFIG['arto']['autostart']}")
    print(f"SEAL autostart: {CONFIG['seal']['autostart']}")

    issues = _validate()
    if issues:
        print(f"\n⚠️ Advertencias:")
        for i in issues:
            print(f"  - {i}")
    else:
        print(f"\n✅ Configuración válida")
