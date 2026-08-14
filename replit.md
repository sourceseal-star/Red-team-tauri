# SOURCESEAL RedTeam — Centro de Control

Dashboard de auditoría y monitoreo de seguridad con tres módulos integrados.

## Cómo ejecutar

```bash
bash replit_start.sh
```

El workflow **Start application** ya está configurado y arranca automáticamente.  
Servidor disponible en el puerto **5000**.

## Módulos

| Módulo | Descripción |
|---|---|
| 🛡 Red Team Agent | Ejecuta escenarios de auditoría contra APK/backend y genera reportes JSON |
| 🛰 Site Monitor | Vigila URLs en tiempo real: latencia, TLS, headers, diff de HTML |
| ✏ Editor Frontend | Descarga y edita el frontend de un Repl; genera patches `.bundle.txt` |

## Estructura principal

```
redteam/
├── scripts/dashboard_server.py   # Servidor principal (HTTP + API)
├── dashboard/                    # PWA frontend (HTML/CSS/JS)
├── reports/                      # Reportes JSON generados
├── runner/orchestrator.py        # Orquestador de escenarios
├── scenarios/                    # 13 escenarios de pentest
├── xdr/                          # Correlación + Kill Chain + Attack Surface
├── rasp/                         # RASP Android/iOS + Attestation server
├── soar/                         # Motor SOAR + playbooks
├── tip/                          # STIX 2.1 + TAXII 2.1
└── ...
```

## Variables de entorno (opcionales)

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `5000` | Puerto HTTP del dashboard |
| `SOURCESEAL_API` | `https://api.sourcesealcorp.local` | Backend auditado |
| `SOURCESEAL_KEY` | — | HMAC key para escenarios |
| `RECOVERY_PAGE` | — | URL de página de recuperación |
| `SITE_MONITOR_URL` | — | Auto-inicia el monitor al arrancar |
| `SITE_MONITOR_INTERVAL` | `15` | Segundos entre probes |
| `REPLIT_TOKEN` | — | Habilita publicación directa en Replit |

## Estado del proyecto

Ver `CONTINUAR_AQUI.md` para el estado detallado de cada módulo y los próximos pasos pendientes.

## Tauri Frontend (web preview)

El frontend de Tauri corre como app web con Vite:
```bash
cd tauri-frontend && npm run dev   # puerto 5000
```
Workflow: **Start application** — ya configurado.

## Flujo móvil — APK automático para Android

### Cómo obtener el APK en tu Moto Edge 50 Fusion

1. Haz push del código a GitHub (desde Replit, celular, o cualquier cliente git)
2. GitHub Actions compila el APK automáticamente (`.github/workflows/build-android.yml`)
3. Ve a **GitHub → tu repo → Releases** — aparece el APK listo
4. Descárgalo en el celular e instálalo (activa "fuentes desconocidas" si lo pide)

### Para lanzar el build manualmente desde el celular
GitHub → tu repo → **Actions** → "Build Android APK" → **Run workflow**

### Estructura Tauri
```
src-tauri/
├── Cargo.toml              # dependencias Rust (Tauri 2.0)
├── build.rs                # script de build requerido
├── tauri.conf.json         # config principal de Tauri
├── capabilities/default.json  # permisos Tauri 2.0
├── icons/                  # íconos de la app
└── src/
    ├── main.rs             # entry point Rust
    ├── commands.rs         # comandos invocables desde el frontend
    └── state.rs            # estado compartido (servicios activos)

tauri-frontend/             # Frontend React/Vite
├── src/
│   ├── mocks/tauri.ts      # mock del API Tauri para preview web
│   ├── routes/             # Dashboard, Reports, SOAR, TIP, RASP, Terminal...
│   └── components/         # TopBar, Sidebar, ServiceCard, UI primitives
└── vite.config.ts
```

## User preferences

- Idioma de comunicación: español
