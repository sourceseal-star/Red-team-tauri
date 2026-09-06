# Post-mortem — Pantalla negra del War Room + bugs relacionados (2026-09-06)

## Resumen para Harold

La pantalla negra **no era una Sol borrada**. Era un bug de arranque de React
que crasheaba en TODO navegador real (Termux, Replit, Chrome, Brave) desde
antes de que empezáramos a "reconectar" nada. `curl` nunca lo detectó porque
`curl` solo mira si el servidor responde 200 — no ejecuta el JavaScript.
Se necesitó un navegador real (Playwright headless) para ver el error exacto.

## 1. CAUSA RAÍZ confirmada y arreglada — crash de React (`useLanguage`)

**Síntoma:** pantalla completamente negra al abrir `localhost:8001` o la app
pública de Replit. El bundle servía HTTP 200 perfecto, pero nada se pintaba.

**Causa:** `tauri-frontend/src/App.tsx` nunca envolvía la app en
`<LanguageProvider>`, pero varios componentes (`OSINTAdvancedPanel`,
`InterceptorAdvancedPanel`, `LanguageSwitcher` del menú) llaman al hook
`useLanguage()`. React lanza un error fatal apenas monta el árbol:

```
Error: useLanguage must be used within a LanguageProvider
```

Ese error es un `pageerror` de JS — invisible para cualquier chequeo con
`curl`/`wget`, por eso 15 intentos de "sincronizar" no arreglaban nada: el
problema nunca estuvo en la sincronización de repos, sino en un `import`
faltante en el código React.

**Fix aplicado** (commits `646be69` + `cc1006d` en `Red-team-tauri`):
```tsx
// src/App.tsx
import { LanguageProvider } from './i18n/LanguageContext'
...
function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </LanguageProvider>
  )
}
```

**Verificación:** clon fresco del repo + Playwright headless contra el
bundle real → 0 errores JS, War Room renderiza completo (Topología,
Cámaras, Ultrasonidos, Guardar Layout, todos los módulos).

**Nota operativa importante:** `tauri-frontend/dist/` está en `.gitignore`.
El primer intento de arreglo (`646be69`) commiteó el `index.html` nuevo
pero el `.gitignore` bloqueó silenciosamente los `.js` nuevos — el
`index.html` quedó pidiendo un archivo que no existía en git. Hubo que
forzar con `git add -f tauri-frontend/dist` (commit `cc1006d`). **Regla
para el futuro: cualquier rebuild del frontend SIEMPRE debe forzarse con
`git add -f tauri-frontend/dist` antes de commitear**, o el `dist/` que
viaja al repo puede quedar incompleto sin que nadie lo note (git no avisa
con error, solo con un `hint` fácil de pasar por alto).

## 2. Botón de corazón (💗 modo libre/romántico/dormir/safe) → HTTP 404

**Síntoma:** al tocar el botón de corazón en `/sol`, sale
`No se pudo cambiar el modo: HTTP 404`.

**Causa confirmada:** el frontend (`backend/static/sol.html`, función
`toggleSolMode()`) llama a `POST /api/sol/mode`. **Ese endpoint no existe
en ningún backend del proyecto** — ni en `sol_rescate/sol_api.py`, ni en
`~/sol/sol_api.py`, ni en `sol_router.py` (el router in-process de
`dashboard_server.py`). Es una función de frontend que quedó sin su
contraparte en el servidor — nunca se implementó, no es una regresión de
esta sesión.

**Pendiente:** implementar `GET/POST /api/sol/mode` en el backend (guardar
el modo en el estado de Sol, análogo a como ya funciona
`/api/sol/security/toggle`, que SÍ existe y SÍ funciona).

## 3. Chat de Sol responde genérico ("Lo siento, no puedo ayudar con eso")

**Causa probable (por confirmar con `.env` real):** en el log de arranque
de `omni.sh` de esa misma madrugada aparecen como **faltantes**:
`SOL_API_KEY`, `LLM_API_KEY` (o `GROQ_API_KEY`), `SOL_PUBLIC_URL`,
`TELEGRAM_BOT_TOKEN` en `~/sol/.env`. Sin `LLM_API_KEY`/`GROQ_API_KEY`, Sol
cae a plantillas locales genéricas en vez de usar el modelo real — eso
explica la respuesta plana y la voz que "no suena bien" (sin LLM real,
también puede estar usando fallback de TTS en vez de `edge-tts`).

**Pendiente:** completar esas 4 variables en `~/sol/.env` (Termux) y
verificar con `bash omni.sh restart && bash diagnostico.sh`.

## 4. Cámaras, frames y video "desaparecidos"

**Causa muy probable:** el propio log de `omni.sh` reporta
`Puente Termux:API COLGADO — CLI y app desincronizadas`. Sin ese puente,
el escaneo de cámaras/frames no tiene de dónde traer datos — no es que se
haya borrado código, es que la fuente (Termux:API) está colgada.

**Remedio ya documentado** en `docs/TERMUX_API_SALUD.md`:
1. `pkg update` (actualizar CLI)
2. Actualizar la app Termux:API desde F-Droid
3. Ajustes del sistema → Batería → Sin restricciones (para Termux y Termux:API)
4. `bash omni.sh restart` y `bash diagnostico.sh`

## 5. Ruta `/ultra` (Ultrasonidos) en blanco

**Síntoma:** `/ultra` muestra solo el título "Ultrasonidos" y el subtítulo,
sin contenido — a diferencia del panel de Ultrasonidos que SÍ aparece
completo dentro del War Room (`/`).

**Estado:** pendiente de investigar — probablemente `dashboardUltrasonicPanel`
depende de props/contexto que solo existen cuando se renderiza embebido en
`WarRoom`, y como ruta independiente le faltan.

## Checklist para que esto no vuelva a pasar

- [ ] Cualquier rebuild de `tauri-frontend` → `git add -f dist/` SIEMPRE,
      nunca `git add dist/` a secas.
- [ ] Antes de dar por bueno un deploy, no basta con `curl` — correr un
      smoke test con navegador real (Playwright headless) que confirme
      `0 pageerror` y que aparezca texto esperado (ej. "War Room").
- [ ] Mantener `~/sol/.env` completo: `SOL_API_KEY`, `GROQ_API_KEY` o
      `LLM_API_KEY`, `SOL_PUBLIC_URL`, `TELEGRAM_BOT_TOKEN`.
- [ ] Si las cámaras/frames fallan, lo primero es revisar
      `docs/TERMUX_API_SALUD.md`, no el código React.
- [ ] Implementar `/api/sol/mode` en el backend (ver punto 2) para que el
      botón de corazón deje de dar 404.
