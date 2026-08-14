# API Gateway Mesh

Arquitectura distribuida para conectar nodos Termux/Replit.

## Estructura

```
gateway/
├── mesh_server.py           # Servidor central (FastAPI + WebSocket)
├── node_client.py            # Cliente que corre en cada nodo
├── node_config.example.json  # Template de configuración
└── README.md
```

## Arquitectura

```
Control Tower (React)
       │
   Gateway Mesh (mesh_server.py :8080)
       │
   ┌───┼───┐
   │   │   │
Nodo A  Nodo B  Nodo C
Termux  Termux  Replit
```

## Setup — Gateway (central)

```bash
pip install fastapi uvicorn websockets
python mesh_server.py
# Corre en :8080
```

## Setup — Nodo Termux

```bash
pip install websockets
cp node_config.example.json node_config.json
# Editar node_config.json con tu node_id y capabilities
python node_client.py
```

## Endpoints HTTP

- `POST /nodes/register` — Registrar nodo
- `POST /nodes/{id}/heartbeat` — Heartbeat manual
- `GET /nodes` — Listar nodos
- `GET /nodes/{id}` — Info de nodo específico
- `DELETE /nodes/{id}` — Desconectar nodo
- `GET /health` — Health del gateway

## WebSocket

- `ws://host:8080/ws/{node_id}` — Conexión bidireccional
- Tipos de mensaje:
  - `heartbeat` — Keepalive + telemetría
  - `command` — Enviar comando a nodo específico
  - `broadcast` — Broadcast a todos los nodos
  - `telemetry` — Stats del nodo (CPU, RAM, disk)

## Comandos soportados

- `run_scan` — nmap scan (requiere nmap)
- `capture_camera` — Captura de cámara
- `network_monitor` — tcpdump capture
- `ping` — Health check del nodo
