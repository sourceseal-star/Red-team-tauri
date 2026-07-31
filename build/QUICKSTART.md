# SOURCESEAL Centro de Control — Quickstart

Centro de control **todo-en-uno** con tres módulos que viven en un solo
servidor Python y un solo dashboard web:

| Módulo | Qué hace | Para qué te sirve |
|---|---|---|
| 🛡 **Red Team Agent** | Ejecuta 11 escenarios de auditoría contra tu APK/backend y produce reportes JSON | Detectar vulnerabilidades, ver historial de hallazgos |
| 🛰 **Site Monitor** | Vigila tu Repl (o cualquier URL) en tiempo real, mide latencia, headers, TLS, cambios de HTML | Saber al instante si el sitio cae, deface, o se degrada |
| ✏ **Editor Frontend** | Descarga el HTML/CSS/JS de tu Repl, edita localmente, descarga patches `.bundle.txt` listos para pegar | Modificar el frontend sin pagar la versión premium de Replit |

## Arrancar en 30 segundos

### Local (Linux/Mac)
```bash
pip install -r requirements.txt
PORT=8000 python3 scripts/dashboard_server.py
# abre http://localhost:8000
```

### Replit
1. Sube el ZIP al Repl (o importa desde GitHub)
2. En **Secrets** configura lo que quieras:
   - `SOURCESEAL_API`, `SOURCESEAL_KEY`, `RECOVERY_PAGE` (para el Red Team Agent)
   - `SITE_MONITOR_URL` (la URL de tu Repl, p.ej. `https://mi-app.mi-user.repl.co`)
   - `SITE_MONITOR_INTERVAL` (segundos entre probes, default 15)
   - `REPLIT_TOKEN` (opcional, para que el editor publique directamente)
3. Pulsa **Run** → el dashboard aparece en la URL del Repl

### Docker
```bash
docker build -t sourceseal-cc -f agent/standalone/Dockerfile .
docker run --rm -p 8000:8000 \
  -e SITE_MONITOR_URL=https://mi-app.repl.co \
  -e REPLIT_TOKEN=... \
  sourceseal-cc
```

## Cómo usar cada pestaña

### 🛡 Red Team Agent
- Se carga automáticamente el último reporte de `reports/`
- **Ejecutar escaneo** corre los 11 escenarios (puede tardar minutos)
- Cada reporte se guarda como `reports/report-YYYYMMDD-HHMMSS.json`

### 🛰 Monitor del Sitio
1. Pega la URL de tu Repl (o de cualquier sitio que quieras vigilar)
2. Pulsa **Iniciar monitor**
3. Verás en vivo:
   - Estado (UP/DEGRADED/DOWN)
   - Latencia en ms
   - Código HTTP
   - Días hasta que expire el certificado TLS
   - Headers de seguridad presentes / faltantes
   - Log de eventos en tiempo real (vía Server-Sent Events)
   - **Diff de HTML** entre muestras: si alguien inyecta algo, lo ves

### ✏ Editor Frontend (sin token = modo patches)
1. Pega la URL de tu Repl
2. Pulsa **Descargar sitio**: trae HTML, CSS, JS, imágenes (hasta 60 archivos / 8 MB)
3. Elige un archivo en la lista, modifícalo en el editor
4. Pulsa **Guardar patch**: el cambio se guarda en `localStorage` (no se pierde al refrescar)
5. **Descargar bundle** te da un `.bundle.txt` con todos los patches, listo para pegar de vuelta en Replit

#### Con `REPLIT_TOKEN` (modo publish)
Si configuras la variable de entorno `REPLIT_TOKEN` con un token de la Replit
API, aparece un botón **🚀 Publicar patches a Replit** que escribe los
archivos directamente en tu Repl. Para generar el token:
1. Replit → tu perfil → Account → API tokens → Create token
2. **NO uses tu contraseña de Replit** — el token es lo que va en la env var

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `8000` | Puerto HTTP del dashboard |
| `SITE_MONITOR_URL` | — | Auto-inicia el monitor al arrancar |
| `SITE_MONITOR_INTERVAL` | `15` | Segundos entre probes |
| `SITE_MONITOR_TIMEOUT` | `10` | Timeout por probe en segundos |
| `REPLIT_TOKEN` | — | Habilita publicación directa en Replit |
| `SOURCESEAL_API` | `https://api.sourcesealcorp.local` | URL del backend auditado por el RedTeam Agent |
| `SOURCESEAL_KEY` | — | HMAC key para escenarios SOURCESEALCORP |
| `RECOVERY_PAGE` | — | URL de la página de recuperación auditada |

## Endpoints API

```
GET  /api/latest                  último reporte del RedTeam
GET  /api/history                 historial compacto
POST /api/scan                    dispara un escaneo
GET  /api/site/state              snapshot del monitor
GET  /api/site/events             SSE: stream de eventos en vivo
POST /api/site/configure          {url, interval} configura monitor
GET  /api/site/fetch?url=...      descarga el sitio para edición
POST /api/site/publish            publica patches (requiere REPLIT_TOKEN)
```

## ⚠️ Aviso legal

Solo audita infraestructura sobre la que tengas autorización escrita. No
uses el monitor ni el Red Team contra sistemas de terceros.
