# SourceSeal Federation Gateway

Arquitectura: 3 apps Replit + conexion permanente + Termux Maestro

## Estructura

```
gateway/
+-- orchestrator.py            # Nodo Maestro (FastAPI :9000)
+-- satellite.py               # Nodo Satelite (para cada Replit)
+-- start_federation.sh       # Launcher completo
+-- start_orchestrator.sh     # Launcher solo orchestrator
+-- node_client.py            # Cliente legacy
+-- README.md
```

## Setup Termux (Nodo Maestro)

```bash
cd gateway
pip install fastapi uvicorn aiohttp
bash start_federation.sh
```

## Setup Replit (cada nodo)

1. Copia `satellite.py` a tu Replit
2. Crea `.env`:
```
ORCHESTRATOR_URL=https://tu-tunnel.trycloudflare.com
ORCHESTRATOR_KEY=tu-clave-maestra-federada
NODE_ID=motor_01
REPLIT_URL=https://tu-replit.replit.app
```
3. Run: `python satellite.py`

## Comunicacion entre nodos

### Proxy a un Replit especifico

```bash
curl -X POST http://localhost:9000/proxy \
  -H "Content-Type: application/json" \
  -d '{
    "target_node": "replit_motor",
    "endpoint": "/webhook/email-reply",
    "method": "POST",
    "payload": {
      "lead_email": "test@test.com",
      "subject": "Hola",
      "body_text": "Quiero comprar"
    }
  }'
```

### Broadcast a todos los nodos

```bash
curl -X POST http://localhost:9000/broadcast \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "scan_complete",
    "payload": {"hosts_found": 12, "vulns": 3},
    "target_nodes": ["replit_frontend", "replit_motor"]
  }'
```

## Endpoints

| Endpoint | Metodo | Descripcion |
|---|---|---|
| /health | GET | Status del maestro |
| /nodes | GET | Lista de nodos con status y latencia |
| /proxy | POST | Enruta peticion a un Replit |
| /broadcast | POST | Envia evento a nodos suscritos |
| /events | GET | Log de eventos |

## Problemas conocidos

| Problema | Solucion |
|---|---|
| Replit se duerme | UptimeRobot o cron-job.org ping cada 5 min a /health |
| URL del tunel cambia | cloudflared tunnel create con cuenta fija |
| Termux mata procesos | termux-wake-lock y nohup |
| Latencia entre nodos | Orchestrator cachea resultados 60s |
