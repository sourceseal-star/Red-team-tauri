# TODO — Auditoría Táctica asíncrona + multi-subred (pendiente de implementar)

**Anotado el 2026-09-17, después de la verificación táctica.**
**Contexto: el orquestador de LEVIATHAN ya está subido (commit 5143793) y es
la plantilla exacta para esto.**

## Estado actual de la Auditoría Táctica (verificado)

- Motor REAL y sólido: TCP connect sin root, banner grabbing, diccionario de
  credenciales por vendor (hikvision, etc.), informe sellado SHA-256 +
  evidencia, Telegram.
- Cableada al War Room: ruta /tactical en App.tsx, presente en dist.
- Endpoints correctos: /api/tactical/scan, /report/{filename},
  /credentials, /ports. Progreso por websocket (tactical_progress).

## Huecos encontrados (los mismos que tenía LEVIATHAN)

1. `/api/tactical/scan` es SÍNCRONO: corre todo el pipeline
   (descubrimiento → fingerprint → credenciales → informe → Telegram)
   dentro de UNA petición HTTP. Local aguanta; por el túnel desde Replit
   muere por timeout.
2. Una sola subred por scan (no acepta lista multi-red).
3. TACTICAL_PORTS no incluye 8000 y 8899 (HTTP de Hikvision/Dahua).

## Cómo arreglarlo (guía para el próximo agente)

### Paso 1 — Puertos (5 minutos)
En `redteam/modules/tactical_executor.py`, TACTICAL_PORTS:
agregar `8000, 8899` (ya están 37777 y 34567).

### Paso 2 — Asíncrono (copiar el patrón del orquestador)
En `leviathan_core/orchestrator.py` está TODO el patrón funcionando:
- POST acepta job → responde job_id en milisegundos
- `background_tasks.add_task(...)` corre el trabajo pesado
- JOBS dict en memoria + persistencia en SQLite (leviathan_scans)
- GET /status/{job_id} para polling; cae a SQLite si el proceso reinició
- Validación de CIDR antes de aceptar

Para lo táctico:
1. Crear `TACTICAL_JOBS: Dict[str, Dict]` (en dashboard_server.py o un
   módulo propio, como prefieras).
2. Endpoint NUEVO `POST /api/tactical/scan/async`:
   - body: `{"subnets": ["192.168.1.0/24","192.168.0.0/24","10.0.0.0/24"], "ports": null, "notify_telegram": true}`
   - genera job_id, guarda en JOBS, `background_tasks.add_task(_tactical_job, job_id, body)`
   - responde `{"status":"accepted","job_id":...,"poll":"/api/tactical/status/<job_id>"}` inmediato
3. `_tactical_job(job_id, body)`: por cada subnet repite el flujo actual de
   `tactical_scan()` (descubrimiento TCP → fingerprint → run_tactical_scan
   → informe), actualizando `JOBS[job_id]["progress"]` por subnet, con
   pausa `await asyncio.sleep(0.5)` entre subnets (anti-OOM de Android,
   misma regla que el orquestador).
4. Endpoint `GET /api/tactical/status/{job_id}` que devuelva el JOBS dict.
5. El panel TacticalPanel.tsx se actualiza igual que el ejemplo de
   LEVIATHAN: lanza y hace polling cada 3s, barra de progreso con
   `progress.percent`, resultados al completar.

NO reescribir tactical_executor.py — solo envolverlo.

### Paso 3 — Reglas del repo que aplican
- LEEME_PRIMERO Regla #41: si se toca el frontend, rebuild + `git add -f
  tauri-frontend/dist` EN EL MISMO COMMIT.
- Post-mortem: smoke test con navegador real (0 pageerror), no solo curl.
- Todo commit empujado a GitHub antes de cerrar sesión.

## Prueba de aceptación
- POST /api/tactical/scan/async con 2 subredes responde < 1s con job_id.
- Polling muestra progreso por subnet y termina "completed".
- El informe sellado se genera y aparece en /api/tactical/report/{filename}.
- Desde Replit (por el túnel) el flujo completo no da timeout.
