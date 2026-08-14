import os
from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="SourceSeal Satellite Node")

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "")
ORCHESTRATOR_KEY = os.getenv("ORCHESTRATOR_KEY", "")
NODE_ID = os.getenv("NODE_ID", "satellite_01")

class EventPayload(BaseModel):
    event_type: str
    payload: dict

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "node_id": NODE_ID,
        "version": "1.0.0",
        "type": "satellite",
        "orchestrator": ORCHESTRATOR_URL or "not_configured"
    }

@app.post("/webhook/event")
async def receive_event(event: EventPayload, x_signature: str = Header(None)):
    """Recibe eventos del orchestrator."""
    print(f"[EVENT] {event.event_type}: {event.payload}")
    # Aqui procesas el evento segun el tipo
    if event.event_type == "scan_complete":
        # Notificar al frontend
        pass
    elif event.event_type == "payment_received":
        # Actualizar metricas
        pass
    return {"received": True, "node": NODE_ID}

@app.post("/register")
async def register_with_orchestrator():
    """Se registra automaticamente con el orchestrator."""
    if not ORCHESTRATOR_URL:
        raise HTTPException(status_code=503, detail="Orchestrator no configurado")
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{ORCHESTRATOR_URL}/nodes/register",
            headers={"Authorization": f"Bearer {ORCHESTRATOR_KEY}"},
            json={"node_id": NODE_ID, "url": os.getenv("REPLIT_URL", ""), "services": ["stripe", "openai"]}
        ) as resp:
            return await resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
