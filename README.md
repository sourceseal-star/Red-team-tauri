# SourceSeal Console Pro v2.0.0

Red Team & Pentesting Toolkit — Flutter + Python Backend

## Features

### Scanning
- **Port Scanner** — TCP SYN/Connect, UDP, banner grabbing, service detection
- **WiFi Scanner** — Network discovery, security analysis, signal strength, WPS detection
- **Camera Scanner** — IP camera detection (Hikvision, Dahua, Axis, Foscam, Avigilon)
- **Radio Scanner** — FM/AM/Digital frequency scanning
- **IoT Scanner** — MQTT, CoAP, ZigBEE, BLE, WiFi device discovery

### Network Analysis
- **Topology Mapper** — Network graph visualization, host discovery, OS fingerprinting
- **Recon** — Hostname resolution, MAC vendor lookup, service enumeration

### Operations
- **C2 Manager** — Session management, implant control, command execution
- **Exploit Framework** — CVE database (EternalBlue, Log4Shell, Hikvision RCE, etc.)
- **OSINT** — Shodan lookup, WHOIS queries

### Reporting
- **Executive Reports** — PDF/Excel/Markdown export with severity scoring
- **Scan History** — Persistent scan results with audit trail

## Architecture

```
┌─────────────────────────────────────┐
│  Flutter App (lib/)                  │
│  ┌─────┬──────┬──────┬──────┬─────┐ │
│  │Dash │ WiFi │ Topo │ Scan │ C2  │ │
│  └─────┴──────┴──────┴──────┴─────┘ │
│         Dio HTTP + WebSocket         │
└──────────────┬──────────────────────┘
               │ HTTP/WS :8000
┌──────────────┴──────────────────────┐
│  Python Backend (backend/main.py)    │
│  FastAPI + ThreadPoolExecutor        │
│  ┌─────┬──────┬──────┬──────┬─────┐ │
│  │Scan │Camera│Radio │ IoT  │Explo│ │
│  └─────┴──────┴──────┴──────┴─────┘ │
└─────────────────────────────────────┘
```

## Quick Start

### Backend (Python)

```bash
cd backend
pip install -r requirements.txt
python main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Flutter App

```bash
flutter pub get
flutter run
```

### Replit

```bash
bash scripts/install_replit.sh
```

### Termux (Android)

```bash
bash scripts/install_termux.sh
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/scan/port` | Port scan |
| POST | `/api/scan/wifi` | WiFi scan |
| POST | `/api/scan/cameras` | Camera scan |
| POST | `/api/scan/radio` | Radio scan |
| POST | `/api/scan/iot` | IoT scan |
| POST | `/api/scan/topology` | Network topology |
| GET | `/api/scan/results/{id}` | Get scan result |
| GET | `/api/scan/history` | Scan history |
| GET | `/api/c2/sessions` | List C2 sessions |
| POST | `/api/c2/sessions/{id}/command` | Send C2 command |
| WS | `/ws` | WebSocket real-time |
| GET | `/api/exploits/list` | List exploits |
| POST | `/api/exploits/run` | Run exploit |
| GET | `/api/osint/shodan/lookup` | Shodan lookup |
| GET | `/api/osint/whois` | WHOIS lookup |
| POST | `/api/report/generate` | Generate report |

## Tech Stack

- **Frontend**: Flutter 3.24+, Dart 3.5+, go_router, flutter_bloc, dio, fl_chart
- **Backend**: FastAPI 0.115, uvicorn, python-nmap, python-whois
- **Real-time**: WebSocket for live scan updates
- **Security**: flutter_secure_storage, local_auth, crypto

## Version

2.0.0+20 — Pro Release (August 2026)
