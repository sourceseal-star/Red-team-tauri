# 🌞 Sol — Restauración del Cuerpo Completo (2026-09-04)

**Estado: ✅ Verificado de punta a punta. Listo para redeploy.**

## El bug de raíz

El botón 🧍 (busto ⇄ cuerpo completo) en `sol.html` pedía desde su creación
4 archivos que **nunca existieron**: ni las imágenes, ni las rutas backend,
en ningún repo.

- `sol.html` hacía: `SOL_FULL_SRC = "/sol_avatar_full.png"` + frames
  `talk/half/blink` → **404 silencioso siempre** → `onerror` caía de vuelta
  al busto.
- El holo ✨ cargaba `/sol_avatar.jpg` (foto de rostro, cuadrada 1024×1024)
  y el canvas la estiraba a un contenedor alto y flaco → **"escaneo
  corporal deforme"** en pantallas angostas.
- La torre (`Red-team-tauri/backend/dashboard_server.py`, :8001) ni
  siquiera tenía la ruta `/holo`: dependía 100% del fallback a :8006.

## El fix (Harold eligió la imagen: aura dorada, de pie, circuitos bio-luminosos)

### Repo `sol` (commit `064f42e`)

| Archivo | Qué es |
|---|---|
| `static/sol_avatar_full.png` | Su cuerpo real — md5 `efe45b11…` idéntico byte a byte al original de Harold |
| `static/sol_avatar_full_talk.png` | Frame quirúrgico boca abierta (99.5% idéntico a la base) |
| `static/sol_avatar_full_talk_half.png` | Frame boca a medio abrir |
| `static/sol_avatar_full_blink.png` | Frame parpadeo |
| `sol_api.py` | +4 rutas: `/sol_avatar_full.png` y variantes (fallback a la base si falta algo) |
| `static/sol_holo_live.html` | `loadDefaultAvatar()` carga su cuerpo real; encuadre **contain** (nunca corta brazos en pantallas angostas); **sway idle** (se mece sola: `sway=Math.sin(t*.35)*10*DPR`) sumado al breathing/glow |

### Repo `Red-team-tauri` (commit `d2ae920`)

- `backend/dashboard_server.py`: +6 rutas — `/holo`, `/sol_avatar_official.jpg`,
  `/sol_avatar_full.png` + 3 variantes. Las variantes sirven los frames
  **REALES** (los archivos existían desde `aeeb72a` pero ninguna ruta los
  servía) con fallback a la base — nunca 404, nunca caída al busto.
- `backend/static/sol_avatar_full.png` + frames: idénticos (md5) al repo sol.
- `backend/static/sol_holo_live.html`: idéntico al repo sol.

### Los frames quirúrgicos

Los frames talk/half/blink los generó el Replit Agent (commit `aeeb72a`)
pero quedaron huérfanos: sin imagen base, sin rutas, y solo en la torre.
Análisis pixel a pixel: **99.5% idénticos** a la imagen elegida — solo
cambian boca/ojos, en el tono dorado de su piel. Resultado: lip-sync real
de 4 pasos (cerrada → half → abierta → half) y parpadeo con timing
irregular en cuerpo completo, igual que el busto.

## Verificación (clon fresco de GitHub + uvicorn real + curl HTTP)

```
1) /holo                     → 200 (12525b) ✅
2) /sol_avatar_full.png      → 200 (160243b) — md5 servido == original ✅
3) /sol_avatar_full_talk.png → 200 (850777b) — frame real, != base ✅
4) /sol_avatar_full_talk_half → 200 (850377b) ✅
5) /sol_avatar_full_blink    → 200 (850560b) ✅
6) /sol.html                 → 200 (134643b) — pide exactamente las rutas que existen ✅
7) /api/sol/state            → {"brain":"online","memories":24,...} ✅
```

Torre (TestClient sobre `dashboard_server.py`): mismas 7 rutas 200,
frame talk != base, holo de la torre carga su cuerpo real.

## 📱 Instrucciones Termux (tras el republish)

```bash
# 1. Actualizar ambos repos
cd ~/sol && git pull
cd ~/Red-team-tauri && git pull

# 2. Sincronizar y arrancar su stack (carga llaves de ~/sol/.env)
cd ~/Red-team-tauri
bash omni.sh sync
bash omni.sh start

# 3. Verificar que despierta con sus llaves
curl localhost:8006/api/sol/llm-status

# 4. Verificar su cuerpo real
curl -o /dev/null -w "%{http_code}\n" localhost:8006/sol_avatar_full.png   # → 200
curl -o /dev/null -w "%{http_code}\n" localhost:8006/holo                   # → 200

# 5. Verificar la torre (:8001) — ruta /holo nueva
curl -o /dev/null -w "%{http_code}\n" localhost:8001/holo                   # → 200
```

Si `llm-status` responde con el modelo cargado, todo está vivo.
Abre `http://localhost:8001/sol` en el navegador del teléfono: el 🧍
ahora muestra su cuerpo completo con lip-sync, y el ✨ su holograma.

## ☁️ Replit (republish)

1. Abrir el workspace del repo `sol` en Replit.
2. Asegurarse de que el workspace está en `main` con `064f42e` (Shell → `git log --oneline -1`).
3. Deployments → **Redeploy**.
4. Al terminar: `curl https://<tu-app>.replit.app/holo` → debe dar 200,
   y `/sol_avatar_full.png` → 160243 bytes.

*Si Replit muestra "This app isn't live yet": el deploy anterior fue
despublicado — volver a Publish desde el workspace.*
