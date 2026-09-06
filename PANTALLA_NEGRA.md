# 🛰️ PANTALLA NEGRA EN localhost:8001 — Guía de 1 minuto

**La causa más común (le pasó a Harold, 2026-09-06):** el navegador queda
con un `index.html` viejo cacheado que apunta a assets con hash que ya no
existen tras un `git pull` — la página queda en negro aunque el servidor
está perfecto.

## Paso 1 — Diagnóstico (30 segundos)

```bash
cd ~/Red-team-tauri && git pull && bash warroom.sh
```

Lee la salida: cada ❌ trae su solución exacta en la línea `└─`.

## Paso 2 — Si TODO salió ✅

Entonces el servidor está bien y el culpable es el navegador:

1. Abre una **pestaña de incógnito** y ve a `localhost:8001`
2. ¿Cargó la War Room? → cierra incógnito, borra la caché:
   **Chrome → ⋮ → Historial → Borrar datos de navegación → "Última hora" → Borrar datos**
3. Abre `localhost:8001` normal — ya queda.

## Cuándo usar cada script

| Script | Para qué |
|---|---|
| `curar.sh` | Cura TODO el sistema (repos, llaves, procesos, encendido) |
| `warroom.sh` | Solo diagnostica la pantalla de localhost:8001 |

Ambos viven en `~/Red-team-tauri` (NO en `~/sol`).
