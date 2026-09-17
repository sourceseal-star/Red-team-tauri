#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN ORCHESTRATOR — Orquestador Asíncrono Multi-Subred
============================================================
Autor: Harold Paredes / SourceSeal Red Team
Fecha: 2026-09-17

Cierra los 3 huecos de la auditoría del 2026-09-17:

  HUECO 1 — Endpoint asíncrono (/api/leviathan/command + /status/{job_id}):
    Los scans de leviathan_router.py son síncronos: Replit u otro frontend
    se queda colgado esperando y muere por HTTP timeout. Aquí el endpoint
    responde EN MILISEGUNDOS con un job_id y el trabajo pesado corre en
    BackgroundTasks. El frontend hace polling del estado.

  HUECO 2 — Escaneo en bloques (chunk_size) + pausa (sleep_between):
    _scan_active_ips() del network_scanner lanzaba los 254 pings de golpe
    con Semaphore(100). En Android/Termux eso dispara el OOM killer.
    Aquí escaneamos bloques de N IPs (default 10) con una pausa configurable
    (default 0.5s) entre bloques para dejar respirar al recolector de RAM.

  HUECO 3 — Multi-subred (targets: List[str]):
    Cada endpoint del router aceptaba UN solo target. La física de la red de
    Harold tiene varias subredes (Ethernet 192.168.1.x, WiFi 192.168.0.x,
    DVRs 10.0.0.x). Aquí un solo job recorre todas y combina resultados.

NO reemplaza los scanners existentes: los usa como motores
(NetworkScanner._scan_ports / _identify_service son la lógica real de
TCP connect + banner grabbing que ya estaba probada).
"""

import asyncio
import ipaddress
import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from .modules.scanners.network_scanner import NetworkScanner

router = APIRouter(prefix="/api/leviathan")

# ── DB (misma que leviathan_router) ──
DB_PATH = Path(__file__).resolve().parent.parent.parent / "redteam.db"
if not DB_PATH.exists():
    DB_PATH = Path("redteam.db")

# Puerto 8899 (Dahua HTTP) y 34567 (Hikvision-likes) agregados: la lista
# del network_scanner NO los tenía y son de los más comunes en DVRs.
DEFAULT_PORTS: List[int] = [
    80, 443, 554, 8000, 8080, 8899, 37777, 34567,
    22, 445, 3389, 23, 21, 3306, 5432,
]

# Puertos que, si responden, marcan el dispositivo como posible cámara/DVR
CAMERA_HINT_PORTS = {554, 8000, 8899, 37777, 34567, 8080, 8554, 3702}


# ── 1. MODELOS ──────────────────────────────────────────────

class CommandRequest(BaseModel):
    targets: List[str] = Field(
        ..., description='Subredes CIDR: ["192.168.1.0/24", "10.0.0.0/24"]'
    )
    ports: List[int] = Field(default=DEFAULT_PORTS)
    chunk_size: int = Field(default=10, ge=1, le=50)
    sleep_between: float = Field(default=0.5, ge=0.0, le=10.0)
    origin: str = Field(default="local", description="Quién ordenó: replit/local/etc")


# ── 2. GESTOR DE TRABAJOS ────────────────────────────────────
# Memoria = fuente de verdad mientras el proceso vive (polling rápido).
# SQLite (leviathan_scans) = persistencia: si Termux muere o reinicia,
# el estado final sobrevive y /status puede responder desde disco.

JOBS: Dict[str, Dict[str, Any]] = {}


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # La tabla la crea leviathan_router al importar; pero si el orquestador
    # corre solo (o el router aún no la creó), la creamos aquí — idéntica.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS leviathan_scans ("
        " id TEXT PRIMARY KEY, target TEXT, modules TEXT, status TEXT,"
        " started_at TEXT, finished_at TEXT, results TEXT, statistics TEXT)"
    )
    return conn


def _persist_job(job_id: str, status: str, payload: Optional[Dict] = None) -> None:
    """Best-effort: la persistencia nunca debe tumbar el orquestador."""
    try:
        conn = _db()
        conn.execute(
            "INSERT INTO leviathan_scans (id, target, modules, status, started_at, finished_at, results, statistics)"
            " VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
            " finished_at=excluded.finished_at, results=excluded.results,"
            " statistics=excluded.statistics",
            (
                job_id,
                ",".join(JOBS[job_id]["targets"]) if job_id in JOBS else "",
                json.dumps(["orchestrator"]),
                status,
                JOBS[job_id].get("started_iso", datetime.now().isoformat()) if job_id in JOBS else datetime.now().isoformat(),
                datetime.now().isoformat() if status in ("completed", "error") else None,
                json.dumps(payload or {}, default=str)[:1_000_000],
                json.dumps(JOBS[job_id].get("statistics", {})) if job_id in JOBS else "{}",
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # tabla aún no creada, disco lleno, etc.
        print(f"[ORCH] persistencia de {job_id} falló (no fatal): {e}", flush=True)


# ── 3. MOTOR DE ESCANEO EN BLOQUES ──────────────────────────

_scanner = NetworkScanner()  # motor real: TCP connect + banner grabbing


async def _scan_chunk(ips: List[str], ports: List[int]) -> List[Dict]:
    """Escanea UN bloque pequeño de IPs con el motor REAL de LEVIATHAN.

    Usa NetworkScanner._scan_ports (TCP connect puro, funciona sin root
    en Termux) y _identify_service (banner grabbing real: envía b'\\r\\n',
    lee la respuesta, clasifica por banner).
    """
    results: List[Dict] = []
    context = {"ports": ports, "port_timeout": 0.4, "port_concurrency": 15}

    for ip in ips:
        open_ports: List[int] = []
        services: List[Dict] = []
        try:
            open_ports = await _scanner._scan_ports(ip, context)
            if open_ports:
                for port in open_ports:
                    svc = await _scanner._identify_service(ip, port)
                    if svc:
                        services.append(svc)
        except Exception:
            continue  # host muerto a mitad de bloque — no aborta el job

        if not open_ports:
            continue

        banners = {s.get("port"): s.get("banner", "") for s in services}
        is_camera = bool(CAMERA_HINT_PORTS.intersection(open_ports)) or any(
            "RTSP" in (banners.get(p) or "") for p in open_ports
        )

        results.append({
            "ip": ip,
            "ports": [
                {"port": s.get("port"), "service": s.get("service"),
                 "banner": (s.get("banner") or "")[:200]}
                for s in services
            ],
            "open_ports": open_ports,
            "is_camera": is_camera,
            "alive": True,
            "scanned_at": datetime.now().isoformat(),
        })
    return results


async def _run_job(job_id: str, req: CommandRequest) -> None:
    """Orquestador principal — corre como BackgroundTask."""
    JOBS[job_id]["status"] = "running"
    JOBS[job_id]["started_at"] = time.time()
    JOBS[job_id]["started_iso"] = datetime.now().isoformat()
    all_results: List[Dict] = []

    try:
        for target in req.targets:
            JOBS[job_id]["current_target"] = target
            try:
                net = ipaddress.ip_network(target, strict=False)
            except ValueError as ve:
                raise ValueError(f"CIDR inválido '{target}': {ve}")

            ips = [str(ip) for ip in net.hosts()]
            total_ips = len(ips)
            JOBS[job_id]["progress"] = {
                "target": target, "current": 0,
                "total": total_ips, "percent": 0,
            }

            for i in range(0, total_ips, req.chunk_size):
                chunk = ips[i: i + req.chunk_size]

                chunk_results = await _scan_chunk(chunk, req.ports)
                all_results.extend(chunk_results)
                JOBS[job_id]["results"] = all_results

                done = min(i + len(chunk), total_ips)
                JOBS[job_id]["progress"] = {
                    "target": target,
                    "current": done,
                    "total": total_ips,
                    "percent": int((done / total_ips) * 100) if total_ips else 100,
                }

                # La pausa vital: le da al GC de Android tiempo de liberar RAM
                if req.sleep_between > 0 and i + req.chunk_size < total_ips:
                    await asyncio.sleep(req.sleep_between)

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["finished_at"] = time.time()
        JOBS[job_id]["statistics"] = {
            "total_devices": len(all_results),
            "cameras_found": sum(1 for r in all_results if r.get("is_camera")),
            "networks_scanned": len(req.targets),
            "duration_s": round(time.time() - JOBS[job_id]["started_at"], 2),
        }
        # Persistir resultado final (sobrevive reinicios de Termux)
        _persist_job(job_id, "completed", {"devices": all_results})

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)[:500]
        JOBS[job_id]["finished_at"] = time.time()
        _persist_job(job_id, "error", {"devices": all_results, "error": str(e)[:500]})


# ── 4. ENDPOINTS (HUECO 1 y 3) ──────────────────────────────

@router.post("/command")
async def leviathan_command(req: CommandRequest, background_tasks: BackgroundTasks):
    """Hueco 1: asíncrono, responde INMEDIATAMENTE con job_id.
    Hueco 3: acepta lista de subredes (multi-red) en un solo trabajo."""
    if not req.targets:
        raise HTTPException(400, "Se requiere al menos un target CIDR")
    if len(req.targets) > 8:
        raise HTTPException(400, "Máximo 8 subredes por job")

    # Validar todos los CIDR ANTES de aceptar (falla rápido, sin job zombi)
    for t in req.targets:
        try:
            ipaddress.ip_network(t, strict=False)
        except ValueError:
            raise HTTPException(400, f"CIDR inválido: {t}")

    job_id = f"orch_{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {
        "status": "accepted",
        "targets": req.targets,
        "origin": req.origin,
        "results": [],
        "progress": {"percent": 0},
        "created_at": datetime.now().isoformat(),
    }
    _persist_job(job_id, "accepted")

    background_tasks.add_task(_run_job, job_id, req)

    return {
        "status": "accepted",
        "job_id": job_id,
        "message": f"Escaneo multi-subred iniciado: {len(req.targets)} red(es), "
                   f"bloques de {req.chunk_size} IPs, pausa {req.sleep_between}s.",
        "poll": f"/api/leviathan/status/{job_id}",
    }


@router.get("/status/{job_id}")
async def leviathan_status(job_id: str):
    """Hueco 1: polling para Replit/frontend. Lee de memoria; si el
    proceso reinició, cae a SQLite para dar el estado final real."""
    job = JOBS.get(job_id)
    if job:
        return {"job_id": job_id, **job}

    # Proceso reiniciado → intentar recuperar de disco (estado final)
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, target, status, started_at, finished_at, results, statistics"
            " FROM leviathan_scans WHERE id=?", (job_id,)
        ).fetchone()
        conn.close()
        if row:
            results = json.loads(row["results"] or "{}")
            return {
                "job_id": job_id,
                "status": row["status"],
                "targets": (row["target"] or "").split(","),
                "results": results.get("devices", []),
                "statistics": json.loads(row["statistics"] or "{}"),
                "restored_from": "sqlite (el proceso reinició después de aceptar el job)",
            }
    except Exception:
        pass
    raise HTTPException(404, f"Job '{job_id}' no encontrado")


@router.get("/jobs")
async def leviathan_jobs():
    """Lista de jobs activos/recientes en memoria (diagnóstico)."""
    return {
        "jobs": [
            {"job_id": jid, "status": j["status"], "targets": j.get("targets", []),
             "progress": j.get("progress", {})}
            for jid, j in JOBS.items()
        ],
        "total": len(JOBS),
    }
