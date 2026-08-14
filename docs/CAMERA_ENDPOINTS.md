# Análisis de Endpoints de Cámaras — Red-Team-Tauri v3.0

## 1. Formato de `/api/scan/cameras` (POST)

**No** devuelve un array plano. Devuelve un objeto con `results` y `count`:

```json
{
  "results": [
    {
      "ip": "192.168.1.10",
      "rtsp": "banner_crudo_del_puerto_554_o_string_vacio",
      "ports": {
        "80": "banner_o_null",
        "443": null,
        "8000": "banner_o_null",
        "8080": null,
        "37777": null,
        "8554": null
      },
      "type": "camera",
      "first_seen": "2026-08-13T03:10:00.123456"
    }
  ],
  "count": 1
}
```

### Diferencias con un formato simplificado esperado:
- **No hay `model`** — el backend no detecta modelo en este endpoint
- **No hay `path`** — no detecta la ruta RTSP/MJPEG aquí
- **No hay `auth`** — no verifica autenticación en este endpoint
- `rtsp` es el **banner TCP crudo** del puerto 554 (string vacío si no responde, o `"RTSP/1.0 200 OK"`)
- `ports` es un **dict** (no array) — keys son puertos extra (80, 443, 8000, 8080, 37777, 8554), values son banner o `null`
- El puerto 554 está **implícito** en el campo `rtsp`, no aparece como `port: 554`

### Endpoint separado para modelo y rutas: `GET /api/iot/video-urls`

```bash
GET /api/iot/video-urls?ip=192.168.1.10&port=80
```

```json
{
  "ip": "192.168.1.10",
  "video_sources": [
    {
      "path": "/snapshot.cgi",
      "port": 80,
      "type": "snapshot",
      "vendor": "Hikvision",
      "available": true,
      "stream_url": null,
      "snapshot_url": "/api/iot/snapshot?ip=192.168.1.10&port=80&path=%2Fsnapshot.cgi",
      "rtsp_url": "rtsp://192.168.1.10:554",
      "content_type": "image/jpeg"
    }
  ],
  "total": 1
}
```

Este endpoint SÍ detecta `vendor` (marca), `path`, y genera URLs listas para consumir.

---

## 2. Protocolos: RTSP vs HTTP-MJPEG

El backend detecta **ambos** pero solo sirve uno:

| Tipo | Paths que busca | Endpoint de visor | Estado |
|------|----------------|-------------------|--------|
| `snapshot` | `/snapshot.cgi`, `/cgi-bin/viewer/video.jpg`, `/ISAPI/Streaming/channels/1/picture` | `GET /api/iot/snapshot` → `image/jpeg` | ✅ Funciona — usar con `<img>` |
| `mjpeg` | `/mjpg/video.mjpg`, `/video/mjpg.cgi` | `GET /api/iot/stream` | ❌ Devuelve 501 (no implementado) |
| `onvif` | `/onvif/device_service` | — | Solo detección |
| `html` | `/live/cam.html` | — | Solo detección |

### Limitación de streaming MJPEG:
El endpoint `/api/iot/stream` existe pero devuelve **501 Not Implemented**:
```json
{"error": "MJPEG streaming requires a browser-facing proxy. Use the snapshot endpoint.", "ip": "..."}
```

### Limitación de RTSP:
El backend genera `rtsp_url: "rtsp://ip:554"` pero **no lo sirve** — solo lo detecta como string. No hay proxy RTSP→WebRTC ni jmuxer.

### Conclusión de visor:
- **Hoy funciona:** snapshot estático vía `<img src="/api/iot/snapshot?ip=...&port=...&path=...">`
- **Para MJPEG:** falta implementar el proxy en el backend (o usar un visor que soporte multipart/x-mixed-replace directamente en el navegador)
- **Para RTSP:** necesita un servidor intermedio (WebRTC gateway o jmuxer) — el backend no lo provee

---

## 3. Prueba sin cámara física

El backend usa `nmap` real sobre la subred local (detecta el CIDR con `subnet_from_iface()`). No hay mocks ni simulación.

### Simular una cámara MJPEG con ffmpeg:
```bash
ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=10 \
  -f mjpeg -pix_fmt yuvj420p \
  http://0.0.0.0:8090/mjpg/video.mjpg
```

Esto deja un stream MJPEG en `http://<ip>:8090/mjpg/video.mjpg` que el backend detectará como cámara con snapshot disponible.

---

## Endpoints relacionados (referencia)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/scan/cameras` | POST | Escanea subred, detecta cámaras por puerto 554 + puertos extra |
| `/api/network/cameras` | POST | Alias del anterior |
| `/api/iot/video-urls` | GET | Detecta rutas de video (snapshot/mjpeg/onvif) para una IP específica |
| `/api/iot/snapshot` | GET | Proxy de snapshot JPEG — devuelve `image/jpeg` directo |
| `/api/iot/stream` | GET | Streaming MJPEG — **501 Not Implemented** |
| `/api/iot/scan-local` | POST | Detecta red local + escanea cámaras en el rango |
| `/api/scan/topology` | POST | Escaneo completo de topología (todos los dispositivos) |

---

## Puertos de cámara que escanea el backend

```python
CAM_PORTS = [554, 80, 443, 8000, 8080, 37777, 8554]
```

- `554` — RTSP (siempre se escanea primero)
- `80` — HTTP web interface / snapshot
- `443` — HTTPS
- `8000` — Hikvision web alternativo
- `8080` — HTTP alternativo
- `37777` — Dahua/NVR
- `8554` — RTSP alternativo

## Paths de video que detecta

```python
CAM_VIDEO_PATHS = [
    ("/snapshot.cgi", "snapshot", "image/jpeg"),
    ("/mjpg/video.mjpg", "mjpeg", "multipart/x-mixed-replace"),
    ("/cgi-bin/viewer/video.jpg", "snapshot", "image/jpeg"),
    ("/ISAPI/Streaming/channels/1/picture", "snapshot", "image/jpeg"),  # Hikvision ISAPI
    ("/onvif/device_service", "onvif", "application/soap+xml"),
    ("/live/cam.html", "html", "text/html"),
    ("/video/mjpg.cgi", "mjpeg", "multipart/x-mixed-replace"),
]
```

---

*Documento generado: 2026-08-13 — Análisis del código en `redteam/scripts/dashboard_server.py`*
