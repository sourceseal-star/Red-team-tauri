"""Authenticated PULL endpoints shared by Sol and Commander Termux workers."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import sol_relay_queue as relay
import sol_tools

router = APIRouter(tags=["Termux Relay"])


def _device_info(value):
    if not isinstance(value, dict):
        return {}
    allowed = ("host", "device", "android")
    return {
        key: str(value[key])[:120]
        for key in allowed
        if value.get(key) is not None
    }


async def _read_json(request: Request):
    try:
        value = await request.json()
    except Exception:
        return None
    return value if isinstance(value, dict) else None


@router.get("/api/relay/status")
async def relay_status():
    return relay.status()


@router.post("/api/relay/task")
async def relay_task(request: Request):
    body = await _read_json(request)
    if body is None:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    name = body.get("name") or body.get("tool")
    if not isinstance(name, str) or not sol_tools.get_tool(name):
        return JSONResponse({"error": "Herramienta Sol no permitida"}, status_code=400)
    args = body.get("args", [])
    kwargs = body.get("kwargs", {})
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        return JSONResponse({"error": "args debe ser lista y kwargs objeto"}, status_code=400)
    return relay.enqueue(name, args, kwargs, origin="api")


@router.post("/api/relay/poll")
async def relay_poll(request: Request):
    body = await _read_json(request)
    if body is None:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    device = _device_info(body.get("device"))
    tasks = relay.fetch_batch(max_tasks=5, claim=True, device=device)
    return {"tasks": tasks, "pong": relay.status()["last_pong"]}


@router.get("/api/relay/poll")
async def relay_poll_get():
    # Compatibility for old clients; this path also claims tasks.
    tasks = relay.fetch_batch(max_tasks=5, claim=True)
    return {"tasks": tasks, "pong": relay.status()["last_pong"]}


@router.post("/api/relay/announce")
async def relay_announce(request: Request):
    body = await _read_json(request)
    if body is None:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    relay.fetch_batch(max_tasks=0, claim=False, device=_device_info(body.get("device")))
    return {"ok": True}


@router.post("/api/relay/result")
async def relay_result(request: Request):
    body = await _read_json(request)
    if body is None:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    task_id = body.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return JSONResponse({"error": "Falta task_id"}, status_code=400)
    entry = relay.push_result(
        task_id,
        body.get("ok", False),
        body.get("data"),
        device=_device_info(body.get("device")),
    )
    if entry is None:
        return JSONResponse({"error": "Tarea inexistente o ya finalizada"}, status_code=404)
    return {"ok": True, "entry": entry}


@router.get("/api/relay/results")
async def relay_results(limit: int = 10):
    return {"results": relay.results(limit=max(1, min(limit, 50)))}


@router.get("/api/relay/tasks/{task_id}")
async def relay_task_status(task_id: str):
    status = relay.task_status(task_id)
    if status is None:
        return JSONResponse({"error": "Tarea no encontrada"}, status_code=404)
    return status