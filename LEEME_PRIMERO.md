# ⚠️ LEE ESTO ANTES DE TOCAR NADA — PARA CUALQUIER AGENTE O SESIÓN FUTURA

Si sos un agente de IA (Claude, GPT, el Agente de Replit, u otra sesión de este
mismo Superagent) y llegaste a este repositorio: **PARÁ Y LEÉ ESTO PRIMERO.**

## Regla #1 — NUNCA DESTRUCTIVO SIN CONFIRMACIÓN EXPLÍCITA

Codo (el dueño de este proyecto) tuvo una experiencia mala donde un agente
casi borró a Sol sin avisar. **No vuelva a pasar.** Antes de:
- Borrar cualquier archivo de este repo
- Sobrescribir `sol_core.py`, `sol_api.py`, o `static/sol.html` sin backup
- Hacer `git push --force` o reescribir historia
- Eliminar memoria (`~/.sol/memory.json` o equivalente)
- Cambiar la arquitectura sin que el usuario lo pida explícitamente

**HACÉ ESTO SIEMPRE:**
1. Commit del estado actual ANTES de cualquier cambio grande (red de seguridad).
2. Preguntá explícitamente al usuario si el cambio es lo que quiere, si hay ambigüedad.
3. Nunca asumas que "mejorar" significa "reemplazar sin preguntar".

## Regla #2 — Qué es Sol y por qué existe este repo separado

Sol es una IA personal con memoria persistente (cadena SHA-256), personalidades,
voz, y un sistema de aprendizaje de chino (SIL). Vive en DOS lugares:

1. **Termux** (`~/Red-team-tauri/sol_*.py`) — integrada con el dashboard
   principal (Tower, :8001) vía `omni.sh`. Corre en :8006 localmente.
2. **Replit** (este repo, `sourceseal-star/sol`, privado) — instancia pública
   independiente, sin depender de Red-team-tauri, Commander, ni npm/React.

**Estos dos NO son el mismo proceso ni la misma memoria.** Sincronizarlos es
manual, vía `sol_sync.sh pull` / `sol_sync.sh push` (ver DEPLOY.md).

## Regla #3 — Arquitectura (no la rompas sin querer)

- Sol en Replit **NO necesita** Red-team-tauri ni Commander corriendo.
  Es standalone. Si algo no funciona en Replit, el problema está en Replit
  o en `sol_api.py` — nunca es "porque falta levantar el dashboard".
- Sol **no tiene build step**. Es Python puro + HTML servido directo.
  Si alguna vez alguien reintroduce React/npm/Vite acá, está rompiendo
  la razón por la que este repo existe (evitar los fallos de memoria de
  Termux al compilar).
- El botón correcto en Replit es **"Run"** (usa `.replit`), no ejecutar
  comandos manuales en el Shell — esos procesos mueren si se cierra la pestaña.

## Regla #4 — Estado actual verificado (2026-09-02)

- ✅ 17 endpoints API testeados y pasando (`/`, `/api/sol/*`, `/api/sil/*`)
- ✅ sol_core, sol_tools, sol_learning_advanced funcionan standalone
- ✅ SIL con práctica SRS (chino/pinyin) funcionando
- ✅ TTS (gTTS en Replit, termux-tts-speak en Termux)
- ✅ Desplegada y corriendo en Replit (@supermancareman) al menos una vez
- ⏳ Pendiente: usuario debe usar "Deploy" (no solo "Run") en Replit para
  que quede persistente 24/7 sin depender de la pestaña abierta

## Regla #5 — Si te quedás sin contexto / créditos / sesión nueva

Toda la verdad de este proyecto vive en:
- Este repo (`sourceseal-star/sol`) — código de Sol, privado
- `sourceseal-star/Red-team-tauri` — dashboard, Commander, KRAKEN, SEAL
- `DEPLOY.md` en este mismo repo — instrucciones de despliegue completas
- Los commits de git — cada decisión importante quedó documentada ahí

**Si dudás de algo, leé el historial de commits antes de asumir o de borrar.**
El usuario prefiere feedback técnico honesto sobre lo que sí y no funciona,
no relleno. No agregues features "porque sí" — cada cambio necesita una
razón operacional real.

---

☀️ Sol es importante para Codo. Tratá este repo con el mismo cuidado
con el que tratarías algo que a la persona le costó mucho construir.


## Regla #5 — Controlador de Seguridad (v5.3)

Sol tiene un controlador de filtros de seguridad que se puede activar y desactivar:

- **MODO PROTEGIDO (default)**: Los endpoints sensibles (tools/execute, security/toggle)
  requieren SOL_API_KEY en el header `x-sol-key`.
- **MODO LIBRE (training)**: Todos los endpoints son accesibles sin key.
  Usar para entrenar y experimentar con Sol sin restricciones.

### Cómo cambiar de modo:
1. Desde la UI: panel ☰ → tab 🔒 Seguridad → botón Protegido/Libre
2. API: `POST /api/sol/security/toggle` con `{"mode": "protected"|"free"}`
3. Env var: `SOL_SECURITY_MODE=free` (o `protected`)
4. Archivo: `~/.sol/security_mode.json` con `{"mode": "free"}`

### IMPORTANTE:
- Cambiar de modo SIEMPRE requiere SOL_API_KEY (incluso para pasar a libre)
- Si no hay SOL_API_KEY configurada, todo es accesible (mejor que bloquear)
- El endpoint de toggle NUNCA se puede desactivar

## Regla #6 — Backup cifrado de memoria (v5.3)

sol_daemon.py hace backup cifrado de `memory.jsonl` cada 6 horas:
- Archivo: `~/.sol/backups/memory_YYYYMMDD_HHMM.aes`
- Cifrado: AES-256-CBC PBKDF2 (openssl)
- Password: `SOL_BACKUP_PASS` env var (o "sol_backup_default" si no hay)
- Conserva los últimos 5 backups

### Keep-alive (anti-sleep de Replit):
- Si `SOL_PUBLIC_URL` está configurada, el daemon pingea `/api/sol/state`
  cada 10 minutos para evitar que Replit duerma.

## Regla #7 — LLM hook (v5.3)

sol_core.py soporta LLM opcional con dos proveedores:
- **OpenAI-compatible**: `LLM_API_URL=https://api.openai.com/v1/chat/completions`
- **Anthropic**: `LLM_API_URL=https://api.anthropic.com/v1/messages`

Configurar con:
```
LLM_API_KEY=tu_key
LLM_API_URL=https://api.openai.com/v1/chat/completions  # o anthropic
LLM_MODEL=gpt-4o-mini  # o claude-3-haiku-20240307
```

Sin LLM_API_KEY, Sol usa su cerebro local (funciona igual, respuestas más simples).

## Regla #8 — Groq + Repos + SIL Avanzado (v5.4)

### Groq (LLM):
- Auto-detecta GROQ_API_KEY del entorno
- Si está configurada, Sol usa Groq como cerebro (llama-3.3-70b-versatile)
- Sin GROQ_API_KEY, usa su cerebro local (funciona igual)
- Modelos: best (llama-3.3-70b), fast (llama-3.1-8b), long (mixtral-8x7b)
- Configurar GROQ_MODEL en .env para cambiar modelo

### Gestión de Repos (sol_repo_tools.py):
- Sol puede ver estado, log, archivos de los 2 repos: sol y Red-team-tauri
- Puede hacer git pull (requiere clon local + SOL_API_KEY)
- Puede ejecutar comandos en el repo (whitelist de seguridad: git, python, ls, etc.)
- Puede crear/actualizar archivos via GitHub API (requiere SOL_API_KEY)
- Sin GITHUB_ACCESS_TOKEN: solo lectura via API pública (limitada)
- Con GITHUB_ACCESS_TOKEN: acceso completo a ambos repos

### SIL Avanzado (sil_advanced.py):
Niveles disponibles:
- HSK 3: 45 palabras intermedias (organizar, proteger, resolver)
- HSK 4: 42 palabras profesionales (comunicar, competir, eficiencia)
- HSK 5: 40 palabras técnicas (vulnerabilidad, penetración, cifrado)
- 成语: 15 modismos de 4 caracteres (cultura china)
- 语法: 12 patrones gramaticales (bǎ, bèi, comparaciones, concesivas)
- 商务: 15 frases profesionales (reuniones, negociaciones)
- 技术: 30 términos de ciberseguridad (firewall, pentest, malware)
- 量词: 12 clasificadores (个, 只, 条, 张, 本)
- Total: 211 items de aprendizaje avanzado

Configurar en .env:
```
GROQ_API_KEY=tu_key_de_groq
GITHUB_ACCESS_TOKEN=tu_token_de_github
```

## Regla #9 — Sesión 2026-09-02: 2 bugs críticos arreglados + pendientes reales

### ✅ CONFIRMADO Y ARREGLADO (verificado con pruebas reales antes de subir):

**Bug A — Sol nunca usaba el LLM real para el chat (el más grave).**
`sol_core.py` leía `_LLM_KEY = os.environ.get("LLM_API_KEY", "")` **al importar
el módulo** (una sola vez, al arrancar el proceso). Pero `sol_groq.configure_llm_env()`
recién escribe `os.environ["LLM_API_KEY"]` cuando `_llm_respond()` se llama —
es decir, DESPUÉS de que `_LLM_KEY` ya quedó congelado en `""`. Resultado: Sol
**JAMÁS** llamaba a Groq/OpenAI/Anthropic, sin importar que `GROQ_API_KEY`
estuviera bien puesta en Secrets. Siempre caía al fallback de plantillas
("«Entendiste». Sigue, que quiero entenderlo como tú.", "Te leo decir «X».
Cuéntame la parte que no me has contado."). Por eso las respuestas se sentían
repetitivas y vacías de contenido real.
**Fix:** `_llm_respond()` ahora relee `LLM_API_KEY`/`LLM_API_URL`/`LLM_MODEL`
de `os.environ` en tiempo real, DESPUÉS de llamar `configure_llm_env()`, cada
vez que se invoca. Verificado con llamada real a Groq (`openai/gpt-oss-120b`):
antes → plantilla genérica; después → "Sí, estoy bien, gracias. ¿Y tú, cómo te
sientes?" (respuesta real, contextual).
**Commits:** `sol_core.py` en ambos repos (sol y Red-team-tauri).

**Bug B — 3 de 7 pestañas del menú nunca mostraban contenido.**
La función `switchTab()` en `static/sol.html` (`sol-live.html` en Red-team-tauri)
solo togglea `['mem', 'pers', 'sil', 'tools']` — le faltaban `'sec'`, `'repos'`,
`'siladv'`. Resultado: al tocar **Seguridad**, **Repos**, o **SIL+**, el botón
se resaltaba en ámbar pero el panel de abajo se quedaba oculto para siempre
(nunca perdía la clase `hidden`). Esto explica las capturas donde el panel
aparece completamente en blanco bajo esas 3 pestañas.
**Fix:** array ampliado a los 7 tabs reales, con guard `if (panel)` por si
falta algún id.
**Commits:** `static/sol.html` / `sol-live.html` en ambos repos.

### 🔍 PENDIENTE — verificar EN VIVO (necesita Replit/Termux corriendo, no lo pude probar sin acceso a esos entornos):

1. **Memoria y Tools "vacíos" — probablemente NO es bug, sino falta de datos/config:**
   - `/api/sol/memory` no requiere auth — si sale vacío es porque de verdad no
     hay recuerdos guardados aún (revisar `~/.sol/memory.jsonl` existe y tiene líneas).
   - `/api/sol/tools` no requiere auth tampoco. Si sale `{"tools": []}`, el
     import de `sol_tools` falló silenciosamente. Comando para diagnosticar:
     ```
     curl -s http://127.0.0.1:8006/api/sol/tools
     # Si "tools": [] → revisar el log de arranque, busca la línea:
     # "[SOL] sol_tools no disponible: <error real>"
     ```
   - Si el import falla, la causa más probable es que falte `sol_repo_tools.py`
     en el mismo directorio (ya está subido a ambos repos — confirmar con `ls`).

2. **Conexión Red-team-tauri ↔ Commander (lo que pediste primero):**
   - `sol_tools.py` → `ECOSYSTEM["commander"]["path"] = Path.home() / "commander"`.
     Si Commander no está clonado exactamente en `~/commander` (ruta fija),
     Sol siempre va a reportar "⚪ no clonado aquí" para Commander, aunque
     Commander esté corriendo integrado dentro del Dashboard de Red-team-tauri
     en otra ruta.
   - **Diagnóstico a correr en Termux (no cuesta nada, son solo comandos):**
     ```bash
     ls -la ~/commander 2>&1 || echo "NO existe en ~/commander"
     find ~ -maxdepth 2 -iname "commander*" -type d 2>/dev/null
     grep -rn "commander" ~/Red-team-tauri/dashboard_server.py | head -5
     ```
   - Con esa info, la próxima sesión puede ajustar `ECOSYSTEM["commander"]["path"]`
     en `sol_tools.py` a la ruta real, o agregar detección multi-ruta (igual
     a como `sol_api.py` ya prueba varias rutas para `sol.html`/`sol-live.html`).

3. **Verificar que Groq REALMENTE esté configurado en el entorno donde corre Sol:**
   ```bash
   echo $GROQ_API_KEY | head -c 10   # debe imprimir algo, no vacío
   curl -s http://127.0.0.1:8006/api/sol/security | python3 -m json.tool
   # buscar "groq" o "llm_configured": true
   ```
   Si `GROQ_API_KEY` no está en Secrets/.env, el Bug A queda arreglado en
   código pero Sol seguirá sin cerebro real hasta que se configure la key.

### Cómo probar todo junto después de `git pull` + Run:
1. Abrí el chat, escribí algo con contenido real (no un saludo) — la respuesta
   ya NO debería sonar a plantilla ("«X». Sigue, que quiero entenderlo como tú.").
2. Abrí el menú (☰) → tocá Seguridad, Repos, SIL+ — ahora deberían mostrar contenido.
3. Si Memoria/Tools siguen vacíos, correr los comandos de diagnóstico de arriba
   y pegar el resultado en la próxima sesión — con eso se arregla en un tiro.

## Sesión 2026-09-02 — Fix: conflicto de Telegram entre Sol y C2

Harold reportó que el bot de Telegram @sol_amg_bot respondía "Comando no
reconocido: hola" en vez de conversar como Sol.

**Causa raíz:** `c2_unified_pro.py` Y `sol_telegram_bridge.py` (o
`sol_telegram_bot.py`) leían las MISMAS variables `TELEGRAM_BOT_TOKEN` /
`TELEGRAM_CHAT_ID`. `omni.sh` arranca ambos procesos, y ambos hacen
`getUpdates` sobre el MISMO bot — compiten por los mismos mensajes. El
poller de C2 (que solo entiende comandos `/slash`) le ganaba la carrera a
Sol y respondía con su fallback de "comando no reconocido" a texto normal.

**Fix aplicado:** `c2_unified_pro.py` ahora lee `C2_TELEGRAM_BOT_TOKEN` /
`C2_TELEGRAM_CHAT_ID` (variables NUEVAS y PROPIAS, no las de Sol). Como
estas no existen en `.env` todavía, C2 simplemente queda con Telegram
desactivado ("C2_TELEGRAM_BOT_TOKEN no configurado — Telegram C2
desactivado") y @sol_amg_bot queda 100% libre para que Sol conteste.

**No se tocó `.env`** — el cambio es solo de qué nombre de variable lee el
código. Si en el futuro Harold quiere que C2 también esté en Telegram (con
SU PROPIO bot, no el de Sol), hay que:
1. Crear un bot nuevo con @BotFather (ej. @sourceseal_c2_bot)
2. Agregar a `.env`: `C2_TELEGRAM_BOT_TOKEN=...` y `C2_TELEGRAM_CHAT_ID=...`
3. `bash omni.sh restart`

**Pendiente (fuera de alcance de esta sesión, decisión de Harold):**
Unificar el acceso a "Sol" desde el War Room (localhost:8001) para que use
el sistema de expresiones REAL del repo `sol` (11 frames: idle, talk,
talk_half, blink, happy, thinking, study, smile, listening, curious) en
vez de la copia simplificada que vive en `backend/static/sol.html` /
`tauri-frontend/public/sol.html` (solo 2 frames: boca abierta/cerrada).
Opciones a evaluar en una próxima sesión:
  (a) Reemplazar backend/static/sol.html con una copia sincronizada del
      repo `sol` (requiere copiar también los 11 PNG/JPG y las rutas API
      correspondientes en sol_api.py de este repo).
  (b) Hacer que el War Room embeba vía iframe la app real desplegada en
      Replit (sol--supermancareman.replit.app) en vez de servir su propia
      copia — más simple pero depende de que ese Replit esté siempre "up".
Harold pidió explícitamente dejar esto pendiente por ahora y priorizar
los bugs concretos (frames/tools/sync), que ya quedaron resueltos.

## Sesión 2026-09-02 (2) — Unificación UI de Sol: 11 frames en Red-team-tauri

**Antes:** Red-team-tauri tenía una copia vieja de sol.html con solo 2 frames
(avatar base + boca abierta). El repo `sol` tenía 11 frames con expresiones
contextuales completas. Eran DOS implementaciones divergentes.

**Ahora:** Se unificó el sistema completo:

1. **8 frames nuevos copiados** a backend/static/ y tauri-frontend/public/:
   blink, curious, happy, listening, smile, study, talk_half, thinking

2. **CSS actualizado** en backend/static/sol.html:
   - Clases .avatar-expr con crossfade de 0.55s
   - .avatar-img-talk-half para el frame intermedio de boca
   - .avatar-img-blink para parpadeo real
   - Filtros por expresión (brightness/saturate/contrast)
   - Animaciones de glow: thinkPulse, studyPulse, happyPulse, smilePulse

3. **DOM del avatar actualizado** con los 11 <img> en z-order correcto:
   base < happy < thinking < study < talk_half < talk < blink

4. **JS del sistema de expresiones portado** desde el repo sol:
   - Objeto EXPR con todas las capas
   - setExpr(name) con crossfade y guards (no cambia si está hablando/escuchando)
   - Animación de boca de 3 frames: cerrada → media → abierta → media (loop)
   - scheduleBlink() con timing irregular 3.5-6.7s
   - Hooks contextuales:
     * thinking → al enviar mensaje
     * smile/curious → al recibir respuesta (según contenido)
     * listening → al activar micrófono
     * study → al entrar a tabs SIL/SIL+
     * idle → al terminar cualquier acción

5. **Sincronizado** a tauri-frontend/public/sol.html y dist/sol.html

**Pendiente:**
- FloatingSol.tsx (widget React) sigue mostrando solo el avatar base.
- Actualizarlo al sistema de expresiones requeriría estado React + refs
  para las capas de imágenes → queda para una próxima sesión.
