#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICADOR DE MÓDULOS LEVIATHAN — Para Termux
================================================
Verifica que todos los módulos de LEVIATHAN carguen correctamente.

Uso: python3 verify_modules.py
"""
import sys
import os
import importlib

# Añadir rutas
repo = os.path.expanduser("~/Red-team-tauri")
sys.path.insert(0, repo)
sys.path.insert(0, os.path.join(repo, "redteam"))
sys.path.insert(0, os.path.join(repo, "leviathan_core"))

def check_import(name, desc=""):
    """Verifica si un módulo se puede importar."""
    try:
        importlib.import_module(name)
        print(f"  ✅ {name:40s} {desc}")
        return True
    except ImportError as e:
        print(f"  ❌ {name:40s} {desc} — {e}")
        return False
    except Exception as e:
        print(f"  ⚠️  {name:40s} {desc} — {e}")
        return False

def check_dep(mod, desc=""):
    """Verifica una dependencia de sistema."""
    try:
        __import__(mod)
        print(f"  ✅ {mod:20s} {desc}")
        return True
    except ImportError:
        print(f"  ❌ {mod:20s} {desc}")
        return False

print("=" * 60)
print("  LEVIATHAN — VERIFICADOR DE MÓDULOS")
print("=" * 60)

# ── Dependencias base ──
print("\n[1] DEPENDENCIAS BASE")
deps = [
    ("fastapi", "Web framework"),
    ("uvicorn", "ASGI server"),
    ("aiohttp", "HTTP async client"),
    ("requests", "HTTP client"),
    ("pydantic", "Data validation"),
    ("onnxruntime", "ONNX inference (YOLOv8)"),
    ("numpy", "NumPy (pkg install python-numpy)"),
    ("PIL", "Pillow (imágenes)"),
    ("cv2", "OpenCV (opcional)"),
    ("cryptography", "Fernet encryption"),
]
dep_ok = 0
for mod, desc in deps:
    if check_dep(mod, desc):
        dep_ok += 1
print(f"  → {dep_ok}/{len(deps)} dependencias OK")

# ── Módulos LEVIATHAN Core ──
print("\n[2] LEVIATHAN CORE")
core = [
    ("leviathan_core", "Paquete principal"),
    ("leviathan_core.core.engine", "Motor de ejecución"),
    ("leviathan_core.api.leviathan_router", "Router básico"),
    ("leviathan_core.api.integration_router", "Router unificado /api/v1"),
    ("leviathan_core.banner", "Banner ASCII"),
]
core_ok = 0
for name, desc in core:
    if check_import(name, desc):
        core_ok += 1
print(f"  → {core_ok}/{len(core)} módulos core OK")

# ── Scanners ──
print("\n[3] SCANNERS")
scanners = [
    "leviathan_core.modules.scanners.rtsp_scanner",
    "leviathan_core.modules.scanners.onvif_scanner",
    "leviathan_core.modules.scanners.http_fingerprint",
    "leviathan_core.modules.scanners.network_scanner",
    "leviathan_core.modules.scanners.camera_detector",
    "leviathan_core.modules.scanners.service_scanner",
]
scan_ok = 0
for name in scanners:
    short = name.split(".")[-1]
    if check_import(name, short):
        scan_ok += 1
print(f"  → {scan_ok}/{len(scanners)} scanners OK")

# ── Exploiters ──
print("\n[4] EXPLOITERS")
exploiters = [
    "leviathan_core.modules.exploiters.hikvision_rce",
    "leviathan_core.modules.exploiters.dahua_backdoor",
    "leviathan_core.modules.exploiters.generic_brute",
    "leviathan_core.modules.exploiters.kraken_integration",
    "leviathan_core.modules.exploiters.exploit_chain",
]
expl_ok = 0
for name in exploiters:
    short = name.split(".")[-1]
    if check_import(name, short):
        expl_ok += 1
print(f"  → {expl_ok}/{len(exploiters)} exploiters OK")

# ── AI Analyzers ──
print("\n[5] AI ANALYZERS")
ai = [
    "leviathan_core.modules.ai_analyzers.object_detection",
    "leviathan_core.modules.ai_analyzers.anomaly_detector",
    "leviathan_core.modules.ai_analyzers.behavior_analyzer",
    "leviathan_core.modules.ai_analyzers.threat_scoring",
]
ai_ok = 0
for name in ai:
    short = name.split(".")[-1]
    if check_import(name, short):
        ai_ok += 1
print(f"  → {ai_ok}/{len(ai)} analyzers OK")

# ── Reporters ──
print("\n[6] REPORTERS")
reporters = [
    "leviathan_core.modules.reporters.json_reporter",
    "leviathan_core.modules.reporters.html_reporter",
    "leviathan_core.modules.reporters.pdf_reporter",
]
rep_ok = 0
for name in reporters:
    short = name.split(".")[-1]
    if check_import(name, short):
        rep_ok += 1
print(f"  → {rep_ok}/{len(reporters)} reporters OK")

# ── Resumen ──
total = dep_ok + core_ok + scan_ok + expl_ok + ai_ok + rep_ok
max_total = len(deps) + len(core) + len(scanners) + len(exploiters) + len(ai) + len(reporters)
print(f"\n{'='*60}")
print(f"  TOTAL: {total}/{max_total} módulos OK")
if total == max_total:
    print("  ✅ SISTEMA COMPLETO — LISTO PARA OPERAR")
elif total >= max_total * 0.8:
    print("  ⚠️  MAYORÍA OK — algunos módulos opcionales faltan")
else:
    print("  ❌ MÓDULOS CRÍTICOS FALTAN — revisar dependencias")
print(f"{'='*60}")
