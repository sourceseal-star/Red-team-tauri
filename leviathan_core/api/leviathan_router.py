"""
LEVIATHAN API Router — Expone todos los módulos vía FastAPI
============================================================
Endpoints:
  GET  /api/leviathan/status        — Estado del sistema
  GET  /api/leviathan/modules        — Lista todos los módulos disponibles
  POST /api/leviathan/scan           — Ejecuta uno o más scanners
  POST /api/leviathan/exploit        — Ejecuta un exploiter
  POST /api/leviathan/analyze         — Ejecuta un AI analyzer
  POST /api/leviathan/report          — Genera un informe
  GET  /api/leviathan/cameras         — Cámaras detectadas (persiste en SQLite)
  GET  /api/leviathan/scans           — Historial de escaneos
  GET  /api/leviathan/alerts          — Alertas activas
"""
import asyncio
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/leviathan", tags=["leviathan"])

# ── DB path (comparte con dashboard_server si está en el mismo host) ──
DB_PATH = Path(__file__).resolve().parent.parent.parent / "redteam.db"
if not DB_PATH.exists():
    DB_PATH = Path("redteam.db")

def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_tables():
    conn = _get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS leviathan_cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            port INTEGER DEFAULT 0,
            vendor TEXT,
            model TEXT,
            is_accessible INTEGER DEFAULT 0,
            is_vulnerable INTEGER DEFAULT 0,
            rtsp_url TEXT,
            firmware TEXT,
            first_seen TEXT,
            last_seen TEXT,
            scan_id TEXT
        );
        CREATE TABLE IF NOT EXISTS leviathan_scans (
            id TEXT PRIMARY KEY,
            target TEXT NOT NULL,
            modules TEXT,
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            finished_at TEXT,
            results TEXT,
            statistics TEXT
        );
        CREATE TABLE IF NOT EXISTS leviathan_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT DEFAULT 'medium',
            title TEXT,
            description TEXT,
            source TEXT,
            camera_ip TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            acknowledged INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()

_ensure_tables()

# ── Cargar módulos bajo demanda (lazy) ──
_scanners = None
_exploiters = None
_analyzers = None
_reporters = None

def _load_modules():
    global _scanners, _exploiters, _analyzers, _reporters
    if _scanners is None:
        try:
            from leviathan_core.modules.scanners import register_all as reg_s
            _scanners = reg_s()
        except Exception as e:
            _scanners = []
    if _exploiters is None:
        try:
            from leviathan_core.modules.exploiters import register_all as reg_e
            _exploiters = reg_e()
        except Exception:
            _exploiters = []
    if _analyzers is None:
        try:
            from leviathan_core.modules.ai_analyzers import register_all as reg_a
            _analyzers = reg_a()
        except Exception:
            _analyzers = []
    if _reporters is None:
        try:
            from leviathan_core.modules.reporters import register_all as reg_r
            _reporters = reg_r()
        except Exception:
            _reporters = []

# ── Modelos ──
class ScanRequest(BaseModel):
    target: str
    modules: Optional[List[str]] = None
    context: Optional[Dict] = None

class ExploitRequest(BaseModel):
    target: str
    module: str
    context: Optional[Dict] = None

class AnalyzeRequest(BaseModel):
    target: str
    module: str
    data: Optional[Dict] = None

class ReportRequest(BaseModel):
    target: str
    format: str = "json"
    scan_id: Optional[str] = None
    context: Optional[Dict] = None

# ── Endpoints ──

@router.get("/status")
async def status():
    _load_modules()
    return {
        "system": "LEVIATHAN",
        "version": "3.0.0",
        "status": "operational",
        "modules": {
            "scanners": len(_scanners),
            "exploiters": len(_exploiters),
            "ai_analyzers": len(_analyzers),
            "reporters": len(_reporters),
        },
        "db_path": str(DB_PATH),
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/modules")
async def list_modules():
    _load_modules()
    result = {"scanners": [], "exploiters": [], "ai_analyzers": [], "reporters": []}
    for s in _scanners:
        result["scanners"].append(s.to_dict())
    for e in _exploiters:
        result["exploiters"].append(e.to_dict())
    for a in _analyzers:
        result["ai_analyzers"].append(a.to_dict())
    for r in _reporters:
        result["reporters"].append(r.to_dict())
    return result

@router.post("/scan")
async def run_scan(req: ScanRequest):
    _load_modules()
    scan_id = f"scan_{int(time.time())}"
    conn = _get_db()
    conn.execute(
        "INSERT INTO leviathan_scans (id, target, modules, status, started_at) VALUES (?,?,?,?,?)",
        (scan_id, req.target, json.dumps(req.modules or []), "running", datetime.now().isoformat())
    )
    conn.commit()

    results = {}
    applicable = [s for s in _scanners if (not req.modules or s.name in req.modules)]
    if not applicable:
        applicable = _scanners

    for scanner in applicable:
        try:
            if scanner.is_applicable(req.target):
                if asyncio.iscoroutinefunction(scanner.scan):
                    res = await scanner.scan(req.target, req.context)
                else:
                    res = await asyncio.to_thread(scanner.scan, req.target, req.context)
                results[scanner.name] = res
                # Persistir cámaras detectadas
                if scanner.name == "camera_detector" and isinstance(res, dict):
                    for cam in res.get("cameras", []):
                        conn.execute(
                            "INSERT INTO leviathan_cameras (ip, port, vendor, model, is_accessible, is_vulnerable, rtsp_url, first_seen, last_seen, scan_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (cam.get("ip"), cam.get("port", 0), cam.get("vendor"), cam.get("model"),
                             int(cam.get("is_accessible", False)), int(cam.get("is_vulnerable", False)),
                             cam.get("rtsp_url"), datetime.now().isoformat(), datetime.now().isoformat(), scan_id)
                        )
                        # Alert si vulnerable
                        if cam.get("is_vulnerable"):
                            conn.execute(
                                "INSERT INTO leviathan_alerts (severity, title, description, source, camera_ip) VALUES (?,?,?,?,?)",
                                ("high", f"Cámara vulnerable: {cam.get('ip')}", f"{cam.get('vendor','')} {cam.get('model','')} en {cam.get('ip')}:{cam.get('port')}", "camera_detector", cam.get("ip"))
                            )
            else:
                results[scanner.name] = {"skipped": True, "reason": "Not applicable to target"}
        except Exception as e:
            results[scanner.name] = {"error": str(e)[:200]}

    stats = {
        "modules_run": len(results),
        "modules_success": sum(1 for v in results.values() if not v.get("error")),
        "cameras_found": sum(len(v.get("cameras", [])) for v in results.values() if isinstance(v, dict)),
    }
    conn.execute(
        "UPDATE leviathan_scans SET status=?, finished_at=?, results=?, statistics=? WHERE id=?",
        ("completed", datetime.now().isoformat(), json.dumps(results, default=str), json.dumps(stats), scan_id)
    )
    conn.commit()
    conn.close()
    return {"scan_id": scan_id, "target": req.target, "results": results, "statistics": stats}

@router.post("/exploit")
async def run_exploit(req: ExploitRequest):
    _load_modules()
    exploiter = next((e for e in _exploiters if e.name == req.module), None)
    if not exploiter:
        raise HTTPException(404, f"Exploiter '{req.module}' no encontrado. Disponibles: {[e.name for e in _exploiters]}")
    try:
        if exploiter.is_applicable(req.target):
            if asyncio.iscoroutinefunction(exploiter.exploit):
                result = await exploiter.exploit(req.target, req.context)
            else:
                result = await asyncio.to_thread(exploiter.exploit, req.target, req.context)
        else:
            result = {"skipped": True, "reason": "Not applicable"}
        return {"module": req.module, "target": req.target, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:200])

@router.post("/analyze")
async def run_analyze(req: AnalyzeRequest):
    _load_modules()
    analyzer = next((a for a in _analyzers if a.name == req.module), None)
    if not analyzer:
        raise HTTPException(404, f"Analyzer '{req.module}' no encontrado. Disponibles: {[a.name for a in _analyzers]}")
    try:
        if asyncio.iscoroutinefunction(analyzer.analyze):
            result = await analyzer.analyze(req.target, req.data)
        else:
            result = await asyncio.to_thread(analyzer.analyze, req.target, req.data)
        return {"module": req.module, "target": req.target, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:200])

@router.post("/report")
async def generate_report(req: ReportRequest):
    _load_modules()
    reporter = next((r for r in _reporters if f"{req.format}" in r.name.lower()), None)
    if not reporter:
        raise HTTPException(404, f"Reporter '{req.format}' no encontrado. Disponibles: {[r.name for r in _reporters]}")
    try:
        if asyncio.iscoroutinefunction(reporter.generate):
            result = await reporter.generate(req.target, req.context or {})
        else:
            result = await asyncio.to_thread(reporter.generate, req.target, req.context or {})
        return {"format": req.format, "target": req.target, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e)[:200])

@router.get("/cameras")
async def get_cameras(limit: int = 100):
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM leviathan_cameras ORDER BY last_seen DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {"cameras": [dict(r) for r in rows], "total": len(rows)}

@router.get("/scans")
async def get_scans(limit: int = 50):
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM leviathan_scans ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {"scans": [dict(r) for r in rows], "total": len(rows)}

@router.get("/alerts")
async def get_alerts(acknowledged: Optional[bool] = None):
    conn = _get_db()
    if acknowledged is not None:
        rows = conn.execute(
            "SELECT * FROM leviathan_alerts WHERE acknowledged=? ORDER BY created_at DESC",
            (int(acknowledged),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM leviathan_alerts ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return {"alerts": [dict(r) for r in rows], "total": len(rows)}

# ──────────────────────────────────────────────────────────────────────
# ENDPOINTS ADICIONALES —compatibilidad con el frontend LEVIATHAN v3.0
# ──────────────────────────────────────────────────────────────────────

# ── Modelos extra ──
class NetworkScanRequest(BaseModel):
    target: str = ""
    network: Optional[str] = None
    modules: Optional[List[str]] = None

class CameraScanRequest(BaseModel):
    network: str

class QuickScanRequest(BaseModel):
    target: str

class CameraExploitRequest(BaseModel):
    target: str
    method: Optional[str] = "default"
    context: Optional[Dict] = None

class ChainExploitRequest(BaseModel):
    target: str
    context: Optional[Dict] = None

class KrakenExploitRequest(BaseModel):
    target: str
    context: Optional[Dict] = None

class AIAnalyzeRequest(BaseModel):
    target: str
    data: Optional[Dict] = None
    module: Optional[str] = "behavior"

class AIDetectRequest(BaseModel):
    target: str
    data: Optional[Dict] = None

class ReportGenRequest(BaseModel):
    target: str
    format: str = "json"
    scan_id: Optional[str] = None

# ── Scan wrappers ──

@router.post("/scan/network")
async def scan_network(req: NetworkScanRequest):
    """Ejecuta escaneo de red completo con todos los scanners aplicables."""
    target = req.target or req.network or ""
    if not target:
        raise HTTPException(400, "Se requiere 'target' o 'network'")
    return await run_scan(ScanRequest(target=target, modules=req.modules))

@router.post("/scan/cameras")
async def scan_cameras(req: CameraScanRequest):
    """Escaneo específico de cámaras IP en una red."""
    target = req.network or ""
    if not target:
        raise HTTPException(400, "Se requiere 'network'")
    return await run_scan(ScanRequest(target=target, modules=["camera_detector"]))

@router.post("/scan/quick")
async def scan_quick(req: QuickScanRequest):
    """Escaneo rápido — solo los scanners más ligeros."""
    if not req.target:
        raise HTTPException(400, "Se requiere 'target'")
    return await run_scan(ScanRequest(target=req.target))

# ── Exploit wrappers ──

@router.post("/exploit/camera")
async def exploit_camera(req: CameraExploitRequest):
    """Explotación específica de cámaras IP."""
    return await run_exploit(ExploitRequest(
        target=req.target,
        module="camera_exploiter",
        context={**(req.context or {}), "method": req.method}
    ))

@router.post("/exploit/chain")
async def exploit_chain(req: ChainExploitRequest):
    """Explotación en cadena — intenta múltiples exploiters secuencialmente."""
    _load_modules()
    results = {}
    for exploiter in _exploiters:
        try:
            if exploiter.is_applicable(req.target):
                if asyncio.iscoroutinefunction(exploiter.exploit):
                    result = await exploiter.exploit(req.target, req.context)
                else:
                    result = await asyncio.to_thread(exploiter.exploit, req.target, req.context)
                results[exploiter.name] = result
        except Exception as e:
            results[exploiter.name] = {"error": str(e)[:200]}
    return {"target": req.target, "results": results, "modules_tried": len(results)}

@router.post("/exploit/kraken")
async def exploit_kraken(req: KrakenExploitRequest):
    """Explotación con KRAKEN — el motor de fuerza bruta/credenciales."""
    return await run_exploit(ExploitRequest(
        target=req.target,
        module="kraken",
        context=req.context
    ))

# ── AI wrappers ──

@router.post("/ai/analyze")
async def ai_analyze(req: AIAnalyzeRequest):
    """Análisis con IA — comportamiento, anomalías, scoring de amenazas."""
    return await run_analyze(AnalyzeRequest(
        target=req.target,
        module=req.module or "behavior",
        data=req.data
    ))

@router.post("/ai/detect")
async def ai_detect(req: AIDetectRequest):
    """Detección con IA — objetos, anomalías visuales, detección de intrusión."""
    return await run_analyze(AnalyzeRequest(
        target=req.target,
        module="object_detector",
        data=req.data
    ))

# ── Report wrapper ──

@router.post("/report/generate")
async def report_generate(req: ReportGenRequest):
    """Genera un informe del escaneo/explotación."""
    return await generate_report(ReportRequest(
        target=req.target,
        format=req.format,
        scan_id=req.scan_id
    ))

# ── Stats / Threat-map / Services / History ──

@router.get("/stats")
async def get_stats():
    """Estadísticas agregadas del sistema LEVIATHAN."""
    _load_modules()
    conn = _get_db()
    total_cameras = conn.execute("SELECT COUNT(*) FROM leviathan_cameras").fetchone()[0]
    vuln_cameras = conn.execute("SELECT COUNT(*) FROM leviathan_cameras WHERE is_vulnerable=1").fetchone()[0]
    total_scans = conn.execute("SELECT COUNT(*) FROM leviathan_scans").fetchone()[0]
    total_alerts = conn.execute("SELECT COUNT(*) FROM leviathan_alerts").fetchone()[0]
    crit_alerts = conn.execute("SELECT COUNT(*) FROM leviathan_alerts WHERE severity='critical'").fetchone()[0]
    high_alerts = conn.execute("SELECT COUNT(*) FROM leviathan_alerts WHERE severity='high'").fetchone()[0]
    conn.close()
    return {
        "cameras": {"total": total_cameras, "vulnerable": vuln_cameras, "accessible": total_cameras - vuln_cameras},
        "scans": {"total": total_scans},
        "alerts": {"total": total_alerts, "critical": crit_alerts, "high": high_alerts},
        "modules": {
            "scanners": len(_scanners),
            "exploiters": len(_exploiters),
            "ai_analyzers": len(_analyzers),
            "reporters": len(_reporters),
        },
        "timestamp": datetime.now().isoformat(),
    }

@router.get("/threat-map")
async def get_threat_map():
    """Datos para el mapa de amenazas — cameras y alerts con ubicación/IP."""
    conn = _get_db()
    cameras = conn.execute(
        "SELECT ip, port, vendor, model, is_vulnerable, is_accessible FROM leviathan_cameras"
    ).fetchall()
    alerts = conn.execute(
        "SELECT severity, title, camera_ip, created_at FROM leviathan_alerts ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()

    markers = []
    for cam in cameras:
        severity = "critical" if cam["is_vulnerable"] else ("medium" if cam["is_accessible"] else "low")
        markers.append({
            "ip": cam["ip"],
            "port": cam["port"],
            "label": f"{cam['vendor'] or ''} {cam['model'] or ''}".strip(),
            "severity": severity,
            "type": "camera",
        })
    for alert in alerts:
        markers.append({
            "ip": alert["camera_ip"] or "unknown",
            "label": alert["title"],
            "severity": alert["severity"],
            "type": "alert",
            "created_at": alert["created_at"],
        })
    return {"markers": markers, "total": len(markers)}

@router.get("/services")
async def get_services():
    """Lista servicios/modules disponibles agrupados por categoría."""
    _load_modules()
    services = []
    for s in _scanners:
        services.append({"name": s.name, "type": "scanner", "status": "available"})
    for e in _exploiters:
        services.append({"name": e.name, "type": "exploiter", "status": "available"})
    for a in _analyzers:
        services.append({"name": a.name, "type": "ai_analyzer", "status": "available"})
    for r in _reporters:
        services.append({"name": r.name, "type": "reporter", "status": "available"})
    return {"services": services, "total": len(services)}

@router.get("/history")
async def get_history(limit: int = 50):
    """Historial completo de operaciones — alias de /scans con más detalle."""
    conn = _get_db()
    scans = conn.execute(
        "SELECT * FROM leviathan_scans ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    cameras = conn.execute(
        "SELECT * FROM leviathan_cameras ORDER BY last_seen DESC LIMIT ?", (limit,)
    ).fetchall()
    alerts = conn.execute(
        "SELECT * FROM leviathan_alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {
        "scans": [dict(r) for r in scans],
        "cameras": [dict(r) for r in cameras],
        "alerts": [dict(r) for r in alerts],
        "total": len(scans) + len(cameras) + len(alerts),
    }
