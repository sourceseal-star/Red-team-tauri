# Termux Orchestrator — Nodo Maestro

Arquitectura: 3 apps Replit + Tunnel permanente + Termux Maestro

```
INTERNET
|
+--------------+  +--------------+  +--------------+
|  Replit A    |  |  Replit B    |  |  Replit C    |
|  Motor de    |  |  Frontend    |  |  Threat      |
|  Cierre      |<>|  Dashboard   |<>|  Intel Proxy |
|  (Stripe)    |  |  (React)     |  |  (AbuseIPDB) |
+------+-------+  +------+-------+  +------+-------+
       +-----------------+-----------------+
                         |
           +-------------v-------------+
           |  Tunnel permanente         |
           |  tu-subdomain.trycloudflare.com
           +-------------+-------------+
                         |
           +-------------v-------------+
           |       TERMUX (Maestro)     |
           |  +-----------------+      |
           |  |  Orchestrator   |      |
           |  |  - Descubre nodos|     |
           |  |  - Enruta APIs  |      |
           |  |  - Sincroniza DB|      |
           |  +-----------------+      |
           |  +-----------------+      |
           |  |  Core Services  |      |
           |  |  nmap, aircrack |      |
           |  |  ffmpeg, tcpdump|      |
           |  +-----------------+      |
           |  +-----------------+      |
           |  |  SQLite Master  |      |
           |  +-----------------+      |
           +---------------------------+
```

## Estructura

```
gateway/
+-- orchestrator.py            # Nodo Maestro (FastAPI :8080)
+-- start_orchestrator.sh      # Arranque del maestro
+-- node_client.py             # Cliente para nodos secundarios
+-- README.md
```

## Setup — Termux (Nodo Maestro)

```bash
cd gateway
pip install fastapi uvicorn

# Configurar URLs de Replits
export REPLIT_MOTOR_URL="https://tu-replit-motor.repl.co"
export REPLIT_FRONTEND_URL="https://tu-replit-frontend.repl.co"
export REPLIT_THREAT_URL="https://tu-replit-threat.repl.co"

bash start_orchestrator.sh
```

## Endpoints del Orchestrator

### Node Discovery
- `GET /nodes` — Listar nodos Replit + status
- `GET /nodes/{id}` — Info de nodo especifico

### API Proxy
- `ANY /proxy/{node_id}/{path}` — Proxy a cualquier Replit

### DB Sync
- `POST /sync/{node_id}` — Sincronizar DB del nodo
- `GET /sync/log` — Log de sincronizaciones

### Core Services
- `POST /core/exec` — Ejecutar herramienta en Termux

### Health
- `GET /health` — Status del maestro + nodos + tunnel
