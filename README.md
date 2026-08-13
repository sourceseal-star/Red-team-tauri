# SourceSeal Console Pro v3.0 — Sala de Guerra Unificada

> **Consola de operaciones de seguridad ofensiva y defensiva.**  
> Topología + Cámaras + Ultrasonidos + Threat Intel + Exploits + Captura de tráfico.

**📖 [MANUAL OPERATIVO COMPLETO](./MANUAL_OPERATIVO.md)** — Instalación, comandos, API y troubleshooting.

---

## Inicio rápido

### Termux (Android)
```bash
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
bash termux_setup.sh
bash start-termux.sh
```

### Replit / Local (Linux/Mac)
```bash
bash replit_start.sh
# → http://localhost:8001
```

### Sincronizar cambios
```bash
bash sync.sh
```

---

## Módulos

| Módulo | Descripción | Estado |
|---|---|---|
| 🗺️ **Topología** | Grafo interactivo (vis-network) + traceroute + geolocalización | ✅ |
| 📹 **Cámaras** | Detección IP, snapshots, RTSP→HLS, detección de movimiento | ✅ |
| 🦇 **MURCIÉLAGO** | Comunicación por ultrasonidos 18-20 kHz (Web Audio API + FFT) | ✅ |
| 🌐 **Threat Intel** | AbuseIPDB + cache SQLite + verdict semafórico | ✅ |
| 🎯 **Exploit Matcher** | ExploitDB offline + match HIGH/MEDIUM/LOW | ✅ |
| 📡 **Packet Analyzer** | tcpdump + detección ARP storm / port scan | ✅ |
| 📤 **Evidencia Blindada** | Hash SHA-256 + blockchain + PDF con QR + modo offline | ✅ |
| 🪤 **Honeypot** | Honeypot + canary tokens | ✅ |
| 🔍 **OSINT** | Shodan + WHOIS + geolocalización | ✅ |

---

## Stack

- **Backend**: FastAPI + Uvicorn + httpx + WebSocket (puerto 8001)
- **Frontend**: React 18 + TypeScript + Vite
- **Estado**: Zustand
- **Grafo**: vis-network | **Mapas**: Leaflet | **Iconos**: lucide-react
- **Audio**: Web Audio API (emisor) + numpy FFT (receptor)
- **Cache**: SQLite

## Identidad visual SourceSeal

Cyan `#00e5ff` · Amber `#fbbf24` · Red `#ff3b5c` · Green `#00ff88`

---

*SourceSeal / Red-Team-Tauri v3.0 · 2026*
