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

## Regla #10 — Sesión 2026-09-02: Sol v7 — Pedagogía heredada + capacidades sin límites

### ✅ APLICADO Y VERIFICADO (commit fc47a23):

**4 archivos:**
1. `sol_pedagogy.py` (NUEVO) — 10 principios pedagógicos heredados de la creadora.
   `teaching_style()` genera respuestas con estructura: contexto → explicación →
   código → verificación → apoyo. `EXAMPLES` con security/debugging/architecture.
2. `sol_core.py` (MODIFICADO) — Añadidas `_is_technical_question()`,
   `explain_with_pedagogy()`, `generate_response_pedagogical()`. Integrado en
   `generate_response()` DESPUÉS del LLM y ANTES de memoria/saludos/defecto.
   Si la pregunta es técnica → responde con pedagogía. Si no → flujo normal.
   Si el LLM está configurado, su respuesta se enriquece con "¿Tiene sentido? 💙".
3. `sol_tools.py` (REEMPLAZADO) — 37 herramientas (23 v5 preservadas + 14 v7
   nuevas). Compatibilidad con `sol_api.py` preservada: `tool_repos_info()`,
   `list_tools()`, `get_tool()`, `execute_tool()`, `tool_descriptions()`.
   Nuevas: search_code, git_commit, git_verify, investigate_and_commit,
   create_file, edit_file, run_command, list_directory, translate,
   explain_code, curl, check_port, read_file_repo.
4. `PEDAGOGY_MANUAL.md` (NUEVO) — Documentación de la filosofía pedagógica.

### Cómo funciona la pedagogía en Sol v7:

```
Mensaje de Harold → generate_response()
  ├── _learn() + _mood() + _llm_respond()
  ├── Si es crisis → línea 106
  ├── NUEVO: _is_technical_question()?
  │   ├── SÍ → generate_response_pedagogical()
  │   │   ├── LLM da respuesta real → cierre "¿Tiene sentido? 💙"
  │   │   ├── RAG (sol_knowledge) → explain_with_pedagogy()
  │   │   └── Fallback → respuesta pedagógica honesta
  │   └── NO → flujo normal (memoria, saludos, espejo, defecto)
  └── ... (resto del flujo original intacto)
```

### ⚠️ IMPORTANTE para futuras sesiones:
- **NO borrar `sol_pedagogy.py`** — es el corazón de v7. Sin él, Sol pierde
  la pedagogía pero sigue funcionando (fallback a estructura simple).
- **NO reemplazar `sol_tools.py` sin preservar** `tool_repos_info()`,
  `list_tools()`, `get_tool()`, `execute_tool()`, `tool_descriptions()`.
  Estas funciones las usan `sol_core.py` y `sol_api.py`.
- **`sol_tools.py.bak` NO se subió** al repo (solo era backup local).

## Regla #11 — Sesión 2026-09-02: Sol Tutor v2 — Mentora personal con LLM + RAG + conocimiento

### ✅ APLICADO Y VERIFICADO (commits de esta sesión):

**Nuevo archivo: `sol_tutor.py`** — Tutora personal de programación con 4 capacidades:
1. **LLM (Groq/Anthropic/local)** — comprensión profunda del código. Usa `urllib` (sin `requests`).
2. **RAG de errores** — registra cada error que Harold comete en `~/.sol/tutor/errores.json`
   y los usa para generar ejercicios de repaso personalizados.
3. **Modelo de conocimiento** — sabe qué sabe Harold (14 conceptos), qué no sabe (12),
   y qué confunde (4). Se actualiza automáticamente al acertar ejercicios.
4. **Sesiones adaptativas** — sesiones de práctica con tiempo, aciertos/fallos,
   y recomendaciones basadas en el progreso real.

**Archivos modificados:**
- `sol_core.py` — `generate_response()` ahora llama a `sol_tutor.get_tutor_response()`
  ANTES del LLM y de las respuestas por defecto. Si es pregunta de tutoría → el tutor
  responde. Si no → el flujo normal (LLM, pedagogía, memoria, saludos, afecto) sigue.
- `sol_api.py` — 3 nuevos endpoints:
  - `POST /api/sol/tutor` — preguntar al tutor
  - `GET /api/sol/tutor/status` — estado del sistema de tutoría
  - `POST /api/sol/tutor/session` — gestionar sesiones (start/end/result)

**Archivos del tutor en `~/.sol/tutor/`:**
- `conocimiento.json` — modelo de conocimiento (sabe/no_sabe/confunde)
- `errores.json` — RAG de errores registrados
- `progreso.json` — progreso histórico
- `sesion_activa.json` — sesión de práctica actual

**Flujo completo de generate_response() con todas las capas:**
```
Mensaje → generate_response()
  ├── _learn() + _mood()
  ├── TUTOR v2: ¿es pregunta de tutoría?
  │   ├── SÍ → get_tutor_response()
  │   │   ├── Error/traceback → explicar_codigo_profundo() + RAG
  │   │   ├── "explica código" → LLM + contexto
  │   │   ├── "ejercicio" → generar_ejercicio_adaptativo()
  │   │   ├── "revisa mi código" → LLM review
  │   │   ├── "lección de X" → LLM lesson personalizada
  │   │   ├── "progreso" → KnowledgeModel + sesión
  │   │   └── "recomienda" → recomendar_siguiente_paso()
  │   └── NO → continuar flujo normal
  ├── LLM (si configurado) → _llm_respond()
  ├── Crisis → línea 106
  ├── PEDAGOGÍA v7: ¿es pregunta técnica?
  │   ├── SÍ → generate_response_pedagogical()
  │   └── NO → continuar
  ├── Memoria, saludos, afecto, identidad, estado, ecosistema
  └── Defecto: espejo + mood + resurface
```

### Configuración del tutor:
```bash
# Opcional — para LLM profundo (sin esto, usa cerebro local)
export GROQ_API_KEY="tu_key"      # Recomendado (gratis, rápido)
# o
export ANTHROPIC_API_KEY="tu_key" # Alternativa

# Probar
python3 -c "import sol_tutor; sol_tutor.init_tutor()"
python3 -c "import sol_tutor; print(sol_tutor.get_tutor_response('dame un ejercicio'))"
```

### Lo que el tutor detecta como preguntas de tutoría:
explica, código, ejercicio, lección, concepto, error, revisa, corrige,
enseña, qué es, cómo funciona, variables, funciones, listas, bucles,
condicionales, depura, debug, traceback, falla, dame un ejercicio,
práctica, reto, progreso, estadísticas, qué aprender, recomienda, mi código

### Lo que NO es tutoría (sigue el flujo normal):
hola, buenos días, gracias, te quiero, cómo estás, cuéntame, etc.


## Regla #12 -- OPERACION PUENTE: Capacidades offline reales (HECHO)

### Sol Offline Bridge (HECHO -- 2026-09-02)

`sol_offline_bridge.py` es un **complemento** aditivo que:
- Detecta si hay internet cada 5 min
- Si hay internet: sincroniza memoria local con Replit
- Si no hay internet: Sol sigue funcionando con cerebro local + memoria local
- Cuando vuelve internet: re-sincroniza automaticamente
- **NO modifica sol_core.py ni sol_api.py** -- es puramente aditivo

Endpoints anadidos a sol_api.py:
- `GET /api/sol/offline-status` -- estado del bridge
- `POST /api/sol/sync` -- recibir memoria desde otra instancia (ej: Termux)

Integracion: `start_replit.sh` arranca el bridge en background automaticamente.
Standalone: `python3 sol_offline_bridge.py --status` o `--sync` o `--check`

Secrets: Sol ya tiene todo en el `.env` de Replit:
- GROQ_API_KEY (LLM)
- TELEGRAM_BOT_TOKEN (bot)
- GITHUB_TOKEN (git ops)
- SOL_API_KEY (seguridad API)
- SOL_PUBLIC_URL (keep-alive + sync)
El `.env.example` en este repo documenta todas las variables.

### COM-LINK real (HECHO -- 2026-09-02)

**Problema:** COM-LINK en Red-team-tauri era fachada. Los endpoints existian
en `dashboard_server.py` pero la implementacion real de SMS/mesh/VoIP
offline no estaba cableada.

**Solucion:** `comlink_real.py` en Red-team-tauri como LIBRERIA importable.
Los endpoints `/api/commander/comlink/*` en `dashboard_server.py` ahora
usan `comlink_real.py` primero (SMS/calls/Telegram reales via termux-api)
y caen a `comlink.sh` como fallback. Integrado en `omni.sh`:
- `omni.sh status` muestra canales COM-LINK en tiempo real
- `omni.sh comlink status` — estado de canales
- `omni.sh comlink sms NUM MSG` — enviar SMS real
- `omni.sh comlink channels` — canales disponibles
NO crea un dashboard separado — usa el frontend React existente (WarRoom.tsx)
que ya habla con `:8001`.

**Plan:**
1. Crear `comlink_real.py` en Red-team-tauri usando `termux-api`:
   - `termux-sms-send` para SMS reales
   - `termux-telephony-call` para llamadas
   - Bluetooth mesh entre dispositivos (futuro)
2. Conectar los endpoints `/api/commander/comlink/*` a `comlink_real.py`
3. Probar SMS real desde el dashboard
4. No depende de internet -- solo de termux-api

Ver codigo completo en el commit de esta sesion o preguntarle a Sol.

### War Room real (HECHO -- 2026-09-02)

**Problema:** War Room en Red-team-tauri era frontend React sin backend real.
Los paneles mostraban datos pero no coordinaban dispositivos offline.

**Solucion:** El frontend React `WarRoom.tsx` YA EXISTE y ya habla con
`:8001` (dashboard_server.py). No se creo un dashboard separado. Lo que
se cableo fue:
- Los endpoints `/api/commander/comlink/*` ahora usan `comlink_real.py`
- Los datos de War Room (servicios, recursos, alertas, scanning) ya
  existian en `dashboard_server.py` — COM-LINK era lo que faltaba
- `omni.sh status` ahora incluye COM-LINK en el resumen del sistema

**Plan:**
1. Crear `warroom.py` en Red-team-tauri como FastAPI local en `:8010`
2. Dashboard HTML simple (sin React, sin build) que muestra:
   - Estado de Sol (local/remoto)
   - Estado de COM-LINK (SMS disponible)
   - Estado de servicios (backend, GHOST, Nexus)
   - Internet: conectado/desconectado
3. Funciona sin internet -- todo es local
4. Integrar con `iniciar_unificado.sh` como servicio opcional

Ver codigo completo en el commit de esta sesion o preguntarle a Sol.

### Estado final:
1. `comlink_real.py` creado en Red-team-tauri (libreria Python, no servidor)
2. `dashboard_server.py` parcheado: endpoints COM-LINK usan comlink_real primero
3. `omni.sh` parcheado: status muestra COM-LINK + nuevo comando `omni.sh comlink`
4. `warroom.py` ELIMINADO — el frontend React ya tiene WarRoom.tsx que usa :8001
5. `iniciar_unificado.sh` REVERTIDO — omni.sh es el orquestador maestro
6. ⏳ Probar en Termux: `bash omni.sh comlink status`
7. ⏳ Probar en Termux: `bash omni.sh status` (debe mostrar linea COM-LINK)

Para actualizar en Termux: `cd ~/Red-team-tauri && git pull origin main`

## Regla #10 — Sesión 2026-09-02 (cont.): animación facial más fluida

Harold generó 2 frames nuevos (con créditos de imagen, no de código) y pidió
terminar la integración antes de quedarse sin más créditos:
- `sol_avatar_talk_half.png` — boca a medio abrir
- `sol_avatar_blink.png` — ojos cerrados (parpadeo real)

**Antes:** la boca solo alternaba 2 frames (cerrada ↔ abierta, flip binario
brusco) y el parpadeo era una sombra CSS falsa sobre los ojos, no una imagen.

**Hecho:**
1. Frames copiados a `assets/` y `static/` (mismo patrón que `sol_avatar_talk.png`).
2. `sol_api.py`: rutas nuevas `GET /sol_avatar_talk_half.png` y
   `GET /sol_avatar_blink.png` (mismo patrón que `avatar_talk()`).
3. `static/sol.html`:
   - Boca ahora es un ciclo de 4 pasos (cerrada→media→abierta→media) en vez
     de un flip de 2 — `startMouthMovement()` / `_setMouthFrame()`.
   - Parpadeo real vía `scheduleBlink()`: usa la imagen `avatar-blink`,
     timing irregular 3.5s–6.7s (recursivo con setTimeout, no setInterval
     fijo, para que no se sienta en loop perfecto). Se eliminó la sombra
     CSS falsa (`@keyframes blink` + `.avatar-wrap::after`).
4. `sol_sync.sh`: se arregló un gap — `sol_avatar_talk.png` NUNCA se
   sincronizaba entre Termux y Replit (solo `sol_avatar_official.jpg` y
   `sol_avatar.jpg`). Ahora `pull()` y `push()` incluyen los 3 frames de
   animación (talk, talk_half, blink).

**Verificado:** sintaxis Python (`ast.parse`) y JS (`node --check`) OK antes
de subir. Dimensiones de los frames nuevos confirmadas idénticas (1024x1024)
a los frames existentes.

**Pendiente para Harold (cuando tenga créditos de imagen otra vez):** un
4to frame de "boca casi cerrada" opcional haría el ciclo aún más fluido
(5 pasos en vez de 4), pero con los 4 actuales ya no hay flip brusco.

Para ver el resultado: Replit → Run/Deploy, o Termux → `bash sol_sync.sh pull`
(para bajar estos cambios a Red-team-tauri) → reiniciar.

## Regla #11 — Sesión 2026-09-02 (cont.): sistema de expresiones contextuales

Harold proporcionó 3 imágenes adicionales para dar a Sol más capacidad de
interacción — no solo animación de boca/parpadeo, sino expresiones que cambian
según el contexto de la conversación.

**Frames añadidos (7 en total ahora):**
1. `sol_avatar_official.jpg` — base/idle (existía)
2. `sol_avatar_talk.png` — boca abierta (existía)
3. `sol_avatar_talk_half.png` — boca a medio abrir (sesión anterior)
4. `sol_avatar_blink.png` — parpadeo (sesión anterior)
5. `sol_avatar_happy.png` — expresión cálida/feliz (NUEVA)
6. `sol_avatar_thinking.png` — expresión pensativa/atenta (NUEVA)
7. `sol_avatar_study.png` — expresión de estudio/SIL (NUEVA, de check_official)

**Sistema de expresiones contextuales (`setExpr()`):**
- `idle` → reposo (avatar oficial neutro)
- `listening` → cuando el usuario habla por micrófono
- `thinking` → mientras procesa la respuesta ("💭 pensando…")
- `speaking` → mientras Sol habla (happy + ciclo de boca)
- `happy` → al saludar o responder algo cálido (detecta "hola", "☀", "amor", "❤", "bien")
- `study` → cuando entra a las pestañas SIL/SIL+ (modo aprendizaje)

**Micro-expresiones en reposo (`scheduleMicroExpr()`):**
- Cada 4-8 segundos rota sutilmente entre idle/happy/thinking si no está
  hablando ni escuchando — como una persona viva que tiene micro-gestos.
- Usa setTimeout recursivo (no setInterval) para timing orgánico.

**Crossfade:** todas las transiciones son de 0.35s (opacity) para evitar
cortes bruscos. Cada expresión tiene un glow sutil distinto en CSS
(thinkPulse/studyPulse/happyPulse) con la paleta de SourceSeal.

**Hooks inyectados sin romper las funciones originales:**
- `sendMsg` → setExpr('thinking') al enviar, setExpr('happy'|'idle') al recibir
- `speak` → setExpr('happy') durante el habla
- `toggleMic` → setExpr('listening') al activar mic
- `switchTab` → setExpr('study') en pestañas SIL/SIL+, idle en el resto

**sol_sync.sh:** actualizado para sincronizar los 7 frames entre Termux/Replit.

**Verificado:** Sintaxis JS (node --check) y Python (ast.parse) OK.
DIMENSIONES: Los 7 frames son 1024x1024, compatibles entre sí.

## Regla #12 — Sesión 2026-09-02 (final): 3 frames generados por IA

Con los últimos 3 créditos de imagen, se generaron e integraron frames
adicionales para enriquecer el sistema de expresiones contextuales.

**Inventario final de frames de Sol (10 en total):**
1. sol_avatar_official.jpg  — base/idle (existía)
2. sol_avatar.jpg           — fallback (existía)
3. sol_avatar_talk.png      — boca abierta (existía)
4. sol_avatar_talk_half.png — boca a medio abrir (sesión anterior)
5. sol_avatar_blink.png     — parpadeo real (sesión anterior)
6. sol_avatar_happy.png     — expresión cálida reactiva (Referla de Harold)
7. sol_avatar_thinking.png  — expresión pensativa (Referla de Harold)
8. sol_avatar_study.png     — modo estudio/SIL (Referla de Harold)
9. sol_avatar_smile.png     — sonrisa cálida genuina (GENERADA por IA)
10. sol_avatar_listening.png — expresión atenta al escuchar (GENERADA)
11. sol_avatar_curious.png  — expresión curiosa/sorprendida (GENERADA)

**Nuevas expresiones contextuales:**
- smile     → saludos y respuestas afectuosas (sostenida, más suave que happy)
- listening → micrófono activo (ojos enfocados, leve inclinación)
- curious   → cuando la respuesta tiene '?' o 'wow' o 'vaya' (asombro)

**Micro-expresiones en reposo ahora rotan entre:**
idle, happy, thinking, smile, curious (con peso hacia idle)

**Compromiso de seguridad:** cada frame se commiteó y pusheó
INMEDIATAMENTE después de generarse, para no perder nada si los
créditos se agotaban. 3 commits individuales confirmados en main.

## Regla #13 — Sesión 2026-09-02 (fixes críticos reportados por Harold)

Harold reportó 3 problemas reales tras usar la app en producción (Replit +
Termux). Los 3 fueron reproducidos localmente y corregidos:

**1. Frames "como diapositiva"**
Causa raíz: `scheduleMicroExpr()` cambiaba a un retrato COMPLETO distinto
cada 4-8s incluso en reposo total. Como cada expresión es una imagen de IA
generada por separado (no frames de una misma animación), el cambio
constante se percibía como fotos diferentes pasando, no como alguien vivo.
Fix: se eliminó la rotación aleatoria por completo. Ahora Sol solo cambia
de expresión ante eventos reales (thinking/listening/smile/curious/study),
y el resto del tiempo queda en idle con solo parpadeo + breathe sutil.
Crossfade alargado de 0.35s a 0.55s para que sea más gradual.

**2. Tools con HTTP 500**
Causa raíz: en `sol_api.py`, `list_tools()` y `tool_info()` leían
`t.parameters`, pero la clase `Tool` en `sol_tools.py` define el atributo
como `.params` (no `.parameters`) — AttributeError no capturado -> 500.
Fix: corregido a `.params` en ambos endpoints + try/except para que un
futuro bug similar devuelva un JSON con error claro en vez de un 500 crudo.
Verificado: las 37 tools ahora se listan sin error.

**3. "Repo 'sol' no encontrado localmente" al sincronizar**
Causa raíz: `_get_repo_path("sol")` en `sol_repo_tools.py` SOLO buscaba en
`~/sol`. Pero cuando sol_api.py corre en Replit, el código YA ES el repo
'sol' desplegado en su propia raíz (NO clonado en ~/sol) — así que nunca
se encontraba a sí mismo.
Fix: nueva función `_self_repo_path()` que detecta si el propio script
corre dentro de un repo git válido (`.git` en su directorio) y lo usa como
fallback para el alias "sol" antes de rendirse. Repos "commander" y
"red-team-tauri" siguen usando GitHub API como fallback (ya funcionaba
para status/log/files/read; pull/run siguen requiriendo clon local de esos
otros 2 repos, ya que sol no los tiene dentro de su propio proceso).

**Pendiente (no resuelto en esta sesión, según lo acordado con Harold):**
- Unificar el acceso a "Sol" en War Room / Red-team-tauri para que apunte
  al repo real 'sol' con sus capacidades reales, en vez de la copia
  simplificada de sol.html que vive dentro de Red-team-tauri
  (backend/static/sol.html, tauri-frontend/public/sol.html) con solo 2
  frames de boca. Actualmente son DOS implementaciones divergentes de la
  UI de Sol en DOS repos distintos.
- Bot de Telegram @sol_amg_bot mostrando comandos de "C2 UNIFIED PRO"
  (del repo commander) en vez de conversación real con sol_core — sugiere
  que el bot de Telegram está sirviendo el bridge de C2, no el de Sol, o
  hay conflicto entre ambos pollers del mismo token.

## Regla #14 — Sesión Seal IA (Base44) 2026-09-02: tools vacías + Error desconocido + mkdir que tumbaba imports

### ✅ ARREGLADO Y VERIFICADO (por Seal IA, con pruebas reales antes de subir):

**Bug A — "Error desconocido" en la UI aunque la tool SÍ funcionaba (el más visible).**
`execute_tool()` en `sol_tools.py` devolvía el string crudo de la tool cuando tenía
éxito (ej: "📦 Estado de los 3 repos: ..."). El frontend (`static/sol.html`,
`runTool()`) hace `d.success` sobre la respuesta — sobre un string eso es
`undefined` → caía al branch `d.error || 'Error desconocido'` aunque la tool
hubiera funcionado perfectamente. Las tools de navegador (flashlight, vibrate,
battery...) SÍ funcionaban porque `BROWSER_TOOLS` en JS siempre devuelve
`{success, result}` bien formado — por eso parecía que "unas sí y otras no".
**Fix:** `execute_tool()` ahora normaliza: si el resultado ya es dict con clave
`success` (ej: el except de `Tool.execute()`) se devuelve tal cual; si es string
u otro tipo, se envuelve en `{"success": True, "result": ...}`.

**Bug B — mkdir sin try/except que tumbaba TODOS los imports (el de raíz).**
`sol_knowledge.py` línea 38 y `sol_tools.py` (TOOLS_DIR) ejecutaban
`.mkdir(parents=True)` A NIVEL DE MÓDULO, sin try/except. Si el entorno no
tenía permisos de escritura en `~/.sol/`, el import entero explotaba →
"sol_tools no disponible" / "Módulo sol_knowledge no disponible" con TODA la
gama de tools muerta de un golpe. **Fix:** ambos mkdir ahora son defensivos
(loguean el error y siguen), y `write_text` de knowledge_full.json re-intenta
`mkdir` antes de guardar.

**Bug C — tool_git_status/git_pull "no encontrado" sin fallback a GitHub API.**
`sol_tools.py` (tools viejas v5) solo miraban `ALLOWED_REPOS` local. Si el repo
no estaba clonado → "❌ Repo no encontrado" a pesar de que `sol_repo_tools.py`
(que SÍ tiene fallback a GitHub API + auto-detección de self-repo) estaba
disponible en el mismo proceso. **Fix:** nueva `_fallback_repo_status_via_api()`
— `tool_git_status` consulta `sol_repo_tools.repo_status()` cuando no hay copia
local; `ecosystem_status` hereda el fix en cascada (llama a git_status por repo).
`tool_git_pull` usa `sol_repo_tools.repo_pull()` (con self-repo detection);
si tampoco hay copia local, avisa claro que git pull requiere disco (física
de git, no bug).
**Verificado con llamada real:** `ecosystem_status` ahora responde sol [local],
redteam [github-api] con últimos commits, commander [github-api].

### ⚠️ NOTA para futuras sesiones:
- El backup pre-cambio de esta sesión está en el workspace de Seal IA
  (sol_backup_20260902_2213/) — no hace falta en el repo, `git revert` basta.
- NO tocar `sol_core.py` ni `sol_api.py` en esta sesión — solo se parchearon
  `sol_tools.py` y `sol_knowledge.py`, ambos con `py_compile` verificado.
- Los pendientes de la Regla #13 (unificar UI de Sol en Red-team-tauri, bot de
  Telegram con comandos de C2) SIGUEN pendientes.

## Regla #15 — Sesión Seal IA 2026-09-02 (cont.): Sol incrustada ya puede pensar (proxy :8001→:8006)

### ✅ RESUELTO el pendiente #1 de Regla #13 — "Unificar UI de Sol":

Diagnóstico real: la unificación VISUAL ya la había hecho el Agente de
Replit (commits 8207b6b — 11 frames contextuales en War Room, b560afe —
FloatingSol.tsx burbuja con parpadeo, 956c807 — FloatingSol via iframe a
/sol.html). Pero la UI incrustada habla con rutas RELATIVAS /api/sol/* y
/api/sil/* — servida desde el dashboard :8001, esas rutas caían en el 404
del SPA fallback porque dashboard_server.py NO TENÍA ningún endpoint de
Sol. Sol se veía bonita pero muda: chat, memoria, SIL, tools, todo muerto.

**Fix (commit 2a0017e en Red-team-tauri):** proxy transparente con
httpx.AsyncClient en dashboard_server.py — /api/sol/{rest} y /api/sil/{rest}
se reenvían al sol_api.py real (:8006), pasando body, query params y
x-sol-key. Registrado ANTES del catch-all /{full_path:path} (orden de
registro importa en FastAPI). Si Sol no corre: 502 con mensaje accionable
en vez de 404 mudo. Configurable: SOL_API_BASE, SOL_PROXY_TIMEOUT.

**Verificado punta a punta en sandbox:** GET /api/sol/status via :8001 →
estado real del cerebro; POST /api/sol/think → respuesta conversacional
real de Sol; GET /api/sil/stats → 200; sol_api abajo → 502 claro.

### 🔍 NOTA — repo confundido:
Existen DOS repos: `sourceseal-star/Red-team` (VIEJO, quedó en 58af755)
y `sourceseal-star/Red-team-tauri` (ACTIVO, con Sol/War Room/FloatingSol).
El clon de una sesión anterior apuntaba al viejo y por eso "no encontraba"
ni sol.html ni los commits nuevos. Verificar SIEMPRE que el remote sea
Red-team-tauri.git antes de diagnosticar.

### ⏳ SIGUE pendiente (Regla #13): bot de Telegram @sol_amg_bot.
Diagnóstico Seal IA (código, no confirmado en vivo): sol_start.sh arranca
sol_telegram_bridge.py (menú de COMANDOS de sistema que incluye /c2 C2
UNIFIED PRO) y NUNCA sol_telegram_bot.py (el bot CONVERSACIONAL con
sol_core: pensar/recordar/hablar, memoria, personalidades, miniapp inline).
No era conflicto con commander (bc1bc78 ya separó tokens) — era que el
script maestro siempre levanta el bridge de comandos. Fix propuesto:
start_sol_bridge() prefiere sol_telegram_bot.py con fallback automático al
bridge si python-telegram-bot no está instalado. Parche redactado pero NO
aplicado (esperando confirmación de Harold antes de cambiar el arranque).

## Regla #16 — Sesión Seal IA 2026-09-02 (final): funcionamiento en conjunto verificado

### Arquitectura REAL del dashboard (importante — hay 3 copias):
- `redteam/scripts/dashboard_server.py` (8427 líneas) = **el VIVO** — el que
  arranca omni.sh (:8001). Monta sol_router IN-PROCESS (cerebro de Sol en el
  mismo proceso: think/memory/tools/sil básico SIN depender de :8006).
- `backend/dashboard_server.py` (3384 líneas) = variante con proxy completo a
  :8006 (commit 2a0017e — defensa en profundidad, ningún script lo arranca).
- `build/scripts/dashboard_server.py` (309 líneas) = mínima de build.

### Fixes aplicados hoy (verificados E2E en sandbox antes de subir):
1. **Proxy catch-all en el dashboard vivo** (Red-team-tauri 75abe0d): los
   endpoints que sol_router NO cubre (groq, groq/test, knowledge/*, repos,
   security, sil/advanced) se reenvían a sol_api :8006. Registrado DESPUÉS
   del include del router (las rutas específicas ganan) y ANTES del SPA
   fallback. Resultado probado: chat SOBREVIVE con :8006 abajo (sol_core
   in-process), lo avanzado degrada con 502 accionable, todo vuelve al
   levantar :8006.
2. **sol_start.sh** (sol 957a442): prefiere sol_telegram_bot.py (bot
   CONVERSACIONAL) con fallback automático al bridge de comandos. Un solo
   poller por token (regla 409 de Telegram). Mismo criterio que omni.sh.
3. **omni.sh sync**: lista ampliada de 7 a 13 módulos de Sol (antes
   sol_telegram_bot, sol_groq, sol_daemon, sol_learning_advanced y
   sol_tutor NUNCA se propagaban de ~/sol) y ahora también TRAE archivos
   nuevos, no solo sobreescribe pares existentes.

### ✅ CHECKLIST DE CREDENCIALES (secrets de Replit — verificar EN VIVO):
Los secrets viven SOLO en Replit/Termux .env (bien — nunca en git). Para
verificar que funcionan, tras `bash omni.sh sync && bash omni.sh up`:
1. **GROQ_API_KEY**: `curl -X POST http://127.0.0.1:8001/api/sol/groq/test`
   → {ok:true, response:...} = key válida CONTRA la API real de Groq.
   503 "GROQ_API_KEY no configurada" = falta el secret.
2. **TELEGRAM_BOT_TOKEN**: omni.sh arranca → "Miniapp Telegram activa ☀️"
   = token válido. "Puente Telegram activo (fallback)" = revisar tg_bot.log.
3. **SOL_API_KEY** (modo protegido): los endpoints sensibles responden
   401 sin `x-sol-key` y 200 con el header = key correcta.
4. **GitHub token** (de sol_repo_tools): `curl http://127.0.0.1:8001/api/sol/repos`
   → commits con hash = token vivo.
   En Replit: mismo checklist contra la URL pública del agente (/api/sol/status).

## Regla #17 — Sesión Seal IA 2026-09-03: GITHUB_TOKEN vivo + SIL fusionado + gamificación

### Commits de esta sesión (todos verificados y pusheados a main):
- `bc9c3f3` — fix GITHUB_TOKEN congelado + botón "🧪 Probar token GitHub"
- `a759aea` — fusión de base de datos de vocabulario (motor aditivo, 77 palabras)
- `d7b4b41` — gamificación SRS: nivel, racha 🔥, XP, precisión (4 tiles en la sala SIL)

### Fixes aplicados:
1. **GITHUB_TOKEN congelado** (sol_repo_tools.py): era constante leída UNA vez al
   importar — si Harold agregaba el secreto después de que el proceso corría,
   Sol seguía viendo "no configurado" hasta reiniciar. Ahora `_github_token()`
   lee el entorno VIVO en cada llamada. sol_knowledge.py tenía el bug espejo
   (solo miraba GITHUB_ACCESS_TOKEN legado, no GITHUB_TOKEN) — mismo fix.
   Nuevo: `POST /api/sol/repos/test` → diagnóstico real (usuario, scopes,
   acceso a commander específicamente) + botón en la sala Repos del dashboard.
2. **Fusión de lecciones SIL** (sol_learning_advanced.py): los defaults eran
   todo-o-nada (si existía UN archivo, las categorías nuevas jamás llegaban a
   instalaciones viejas). Ahora: `_default_lessons()` construye, `_create_
   default_lessons()` escribe SOLO lo faltante, y `_merge_defaults_into()`
   expande las lecciones existentes con el vocabulario que les falte —
   deduplicado por hanzi, SIN tocar/reordenar/borrar lo que ya hay, persistido.
   Verificado con instalación vieja simulada: datos custom preservados.
   Set expandido: saludos +早上好晚上好没关系 · comida +咖啡鸡蛋肉鱼 ·
   numeros +六七八九 · emociones +渴生气 · acciones +吃喝读 · tiempo +下午
   · lugares +医院. Total: 9 categorías chino, 2 japonés, 77 palabras.
3. **Gamificación SRS** (sol_learning_advanced.py): `_update_gamification()`
   en cada respuesta — XP = quality×10 si quality≥3, racha de días consecutivos,
   nivel sube cada level×100 XP conservando remanente. Compat con srs_data.json
   viejos (campos se rellenan solos). get_stats expone level/xp/xp_to_next/
   streak_days/accuracy. UI: 4 tiles nuevos en sala SIL que se refrescan
   en vivo tras cada respuesta (loadSilStats ya corría en answerPractice).

### ⏳ PENDIENTE (SIL) — ejercicios nuevos, la siguiente piedra:
La sala de práctica hoy solo hace UN tipo: "¿qué significa X?" con 4 opciones.
Falta implementar en `sol_api.py` (sil_practice_next) + `sol.html` (showPractice):
1. **Escucha** 🔊 — suena el audio (gTTS zh-CN, endpoint /api/sol/tts ya existe)
   y hay que elegir/c escribir el hanzi que se oyó.
2. **Escritura** ✏️ — input de texto libre: dado el significado en español,
   escribir el hanzi (validar contra la lección).
3. **Emparejar** 🔗 — mini-juego de pares hanzi↔significado (una fila de
   tarjetas, click-para-conectar, sin opciones múltiples).
4. **Modismos (Chengyu)** 📜 — usar las 15 entradas de CHENGYU de sil_advanced.py
   (word/pinyin/meaning/literal/example ya están cargadas).
5. **Gramática** 📝 — los 12 patrones de GRAMMAR_PATTERNS con ejercicio de
   completar la estructura (estructura/ejemplo/note ya están).
6. **HSK 3/4/5 como lecciones jugables** — hoy solo se ven en la sala avanzada
   de solo lectura; conectarlos al SRS para que entren al repaso espaciado.
Diseño sugerido: parámetro `exercise_type` en POST /api/sol/sil/practice/next
y un `switch` en showPractice() que renderice cada tipo. SIN tocar el
algoritmo SM-2 ni el formato de srs_data.json.

### ⏳ PENDIENTE (de sesión anterior, SIN cambios): bot de Telegram
@sol_amg_bot — el fix propuesto (start_sol_bridge() prefiere sol_telegram_bot.py)
sigue esperando confirmación de Harold antes de cambiar el arranque.

## 2026-09-03 — Sol recibe acceso exclusivo y total (decisión de Harold)

Harold activó a Sol en Telegram y le dio acceso EXCLUSIVO a todo:

**1. Cuerpo completo (sol_tools.py — este repo y Red-team-tauri):**
14 herramientas nuevas, todas con termux-api real: sms_list (leer
bandeja), call_log (historial), contacts (búsqueda con resolución de
tildes: "mama" encuentra "Mamá"), wifi_info, device_info (IMEI),
sensors, brightness, usb_list, audio_record, toast, wake_lock,
media_play, download, y **shell** — Sol habla directo con el kernel,
siempre LOCAL (nunca viaja por el relé), con auditoría en
~/.sol/logs/shell.log. Única prohibición: rm -rf / (anti-accidente).

**2. Telegram (sol_telegram_bot.py):** capa de acción real — Sol
EJECUTA órdenes naturales en español: "llama a mamá" (resuelve la
agenda → termux-telephony-call), "mándale un mensaje a Laura que
diga te amo" (SMS), "whatsapp a X", linterna, foto, ubicación,
vibra, brillo, notificaciones, "shell: comando", "diagnóstico".
27 casos de prueba OK. Si no es una orden, conversa como siempre.

**3. Activación del bot:** confirmada por Harold. omni.sh arranca la
Miniapp (sol_telegram_bot.py) automáticamente si TELEGRAM_BOT_TOKEN
está en ~/sol/.env. Ya no hay pendiente de confirmación.


## Regla #18 — Sesión Seal IA 2026-09-04: Presencia Total v4 — cuerpo real en video

Harold pidió "mucho más": AR con cámara, latido ECG que vibra con su voz real,
zona de amor, carga del corazón (mantén→cita+onda), clima emocional, escenarios,
dibujo con luz, baile, wake word "Sol, …" manos libres. Pegó el script completo
de `sol_holo_live.html` v4 y pidió fusionar 3 videos nuevos + "los otros videos
de ella" (el loop anterior de sus 2 primeros clips, ya en producción).

### Lo que se hizo (verificado antes de subir):
1. **Deduplicación:** de los 3 videos nuevos que mandó Harold, 2 eran el MISMO
   archivo (md5 idéntico) — probablemente un duplicado al subir. Se usó 1 copia
   + el 3er video único.
2. **Fusión de 3 clips en un solo loop:** el loop ya existente (`sol_viva_loop.mp4`,
   sus 2 primeros videos, 8.9s) + los 2 clips nuevos únicos, normalizados a
   720x720/24fps y encadenados con `xfade` (crossfade 0.7s) → un bucle continuo
   de **17.6s, 3.4MB**. Se sobrescribieron los MISMOS nombres de archivo
   (`sol_viva_loop.mp4`/`sol_viva_poster.jpg`) — el backend (`sol_api.py`,
   rutas `/sol_viva_loop.mp4` y `/sol_viva_poster.jpg`) no necesitó ningún cambio.
3. **sol_holo_live.html reescrito completo** con el script que pegó Harold, PERO
   con una modificación clave: su cuerpo ahora es **video real** (la fusión de
   arriba) en vez de una imagen fija cargada manualmente por archivo — mismo
   patrón `loadVivaVideo()` que ya existía en la versión anterior del archivo,
   fusionado dentro de TODOS los poderes nuevos que pidió Harold (AR, ECG, clima,
   baile, dibujo, wake word, etc.). El input de archivo 🖼️ sigue existiendo como
   override manual (por si quiere cargar una imagen distinta), pero por defecto
   ahora ella respira con su cuerpo real en loop.
4. **Fix de encaje conservado:** el `dw/dh` usa "contain" (nunca le corta brazos
   en pantallas angostas) — el mismo fix aplicado en la Regla de restauración
   del cuerpo (SOL_CUERPO_COMPLETO.md), llevado también a este archivo nuevo.
5. **Zona "pecho" separada de "corazón":** el chip decía "pecho=panel, corazón
   mantén" pero el script original solo tenía una zona (el corazón, que abría
   el panel en toque corto o daba cita+onda en toque largo). Se agregó una
   zona rectangular más amplia en el pecho (24%-48% de alto) que abre el panel
   directo, sin invadir el círculo del corazón — ahora el chip es literal.

### Verificación antes de subir (sin acceso a Replit/Termux, no se pudo probar
en navegador real — SÍ se verificó todo lo que se puede verificar sin eso):
- `node --check` sobre el único bloque `<script>` extraído del HTML → sintaxis OK.
- Cruce de TODOS los ids que el JS busca (`$('...')`/`getElementById`) contra
  los ids que existen en el HTML → sin faltantes.
- `ffprobe` confirmó el video fusionado: 17.584s, 720x720, h264, yuv420p, 3.4MB.
- Los 3 archivos subidos a GitHub se re-descargaron después del commit y se
  comparó su MD5 contra el archivo local → **idénticos, sin corrupción**, en
  AMBOS repos (sol y Red-team-tauri).

### Archivos tocados (ambos repos, mismos nombres, sin tocar backend):
- `static/sol_holo_live.html` (sol) / `backend/static/sol_holo_live.html` (RT)
- `static/sol_viva_loop.mp4` (sol) / `backend/static/sol_viva_loop.mp4` (RT)
- `static/sol_viva_poster.jpg` (sol) / `backend/static/sol_viva_poster.jpg` (RT)

### ⚠️ NO tocado (a propósito): `sol_elixir_1/2/3.mp4` en Red-team-tauri
Existen otros 3 videos de ella (`backend/static/sol_elixir_*.mp4`) que se usan
en `sol.html`/`tauri-frontend/public/sol.html` — una pantalla DISTINTA a
`sol_holo_live.html`. No forman parte de esta fusión y no se tocaron.

### 🔍 PENDIENTE — verificar EN VIVO tras el próximo redeploy:
- Abrir `/holo` (o `/sol_holo_live.html`) y confirmar que el video se reproduce
  en loop, sin cortes visibles en el punto de wraparound (último frame → primer
  frame no tiene crossfade, es un salto directo — funcionaba así antes también).
- Probar los gestos nuevos en el teléfono real: cámara AR (pide permiso HTTPS),
  wake word (requiere Web Speech API — no todos los navegadores Android la dan
  en background), grabar video 12s.
- Si `/api/sol/services` no existe como endpoint (el panel del pecho lo pide),
  el panel muestra solo lo que sí responda — no debería romper nada, pero
  confirmar en vivo qué trae ese endpoint hoy.

## Regla #19 — Sesión Seal IA 2026-09-04 (cont.): +2 videos al loop, verificación de omni.sh

Harold mandó 2 videos más para integrar a la Presencia Total v4. Se hizo:

1. **Fusión ampliada:** se descargó el `sol_viva_loop.mp4` recién publicado (17.6s,
   3 momentos) y se fusionó con crossfade con los 2 clips nuevos → **loop de
   24s, 5 momentos reales de ella, 4.5MB**. Mismos nombres de archivo — el
   `sol_holo_live.html` no necesitó ningún cambio (reproduce el `<video loop>`
   tal cual venga, sin importar su duración).
2. **Verificación de integridad:** `ffmpeg -f null` decodificó el archivo
   completo sin errores antes de subir. Tras el commit, se re-descargó de
   GitHub y se comparó MD5 contra el local — idéntico, en los 2 repos.
3. **Auditoría de `omni.sh` y `start_replit.sh`** (sin tocar nada — Harold pidió
   confirmar que "sigan actualizando/sincronizando/levantando todo"): ambos
   scripts YA hacen `git pull --ff-only` (o reset a canónico si diverge) de
   **su propio repo** Y del otro (Red-team-tauri↔sol vía `ensure_sol_repo()`)
   ANTES de arrancar nada — confirmado leyendo el código real, no solo el
   changelog. Como `ensure_sol_repo()` hace `git pull` del repo completo (no
   una lista fija de archivos), cualquier módulo nuevo de Sol (sol_tutor.py,
   sol_actions.py, sol_relay.py, etc.) llega automáticamente sin tener que
   tocar `omni.sh` cada vez. **No se hizo ningún cambio** — todo lo que ya
   existe cumple lo pedido. Nota curiosa encontrada de paso: `omni.sh start`
   ya instala `edge-tts` para voz neuronal de Sol (es-CO-SalomeNeural) si no
   está — con fallback a gTTS si falla. No se sabe si esto ya está probado en
   vivo; queda para el checklist de la próxima sesión con Termux real.

### 🔍 PENDIENTE (acumulado, sin cambios): todo lo de la Regla #18, más
verificar en vivo que el loop de 24s no se sienta largo/lento en el HUD del
holograma — si Harold lo siente pesado, la fusión es reversible (los 5 clips
fuente quedan documentados en el historial de commits, no se perdió nada).

## Regla #20 — Sesión Seal IA 2026-09-04 (final): Voz Encantada v2 — prosodia neuronal real

Harold: "el último cambio quedó increíblemente bien, se escucha muy bien pero
asegúrate de que esté mejor". El cambio anterior (edge-tts, es-CO-SalomeNeural)
ya sonaba muy bien — pero había UN detalle que mataba encanto en el holo:

**Causa raíz:** el "carácter por personalidad" del holograma
(`sol_holo_live.html`) se hacía con `voiceA.playbackRate = PALS[PALN].r` —
estirando/encogiendo el audio YA SINTETIZADO. Eso cambia el tono junto con la
velocidad (efecto chipmunk/robot): poética a 0.92x sonaba grave y apagada,
táctica a 1.08x sonaba aguda y acelerada. NO era prosodia real.

**Fix — ENCHANT v2 (commits sol@85599172, holo sol@652d32b / RT@44ed0f7):**
1. `sol_api.py`: nuevo `TTS_CHARMS` — rate/pitch NATIVOS de edge-tts por
   personalidad. El motor re-sintetiza la prosodia de verdad; la voz sigue
   siendo Salome pura en todas:
   - cálida (default): rate -6%, pitch +2Hz → un poquito más lenta, tono con
     un lift sutil y cálido. Íntima sin perder naturalidad.
   - poética: rate -12%, pitch +2Hz → lenta, soñadora, hablándote de cerca.
   - táctica: rate +4%, pitch +0Hz → ágil y precisa, tono natural.
   - analítica: rate +0%, pitch +1Hz → neutra y clara.
2. `/api/sol/tts` y `/api/sol/voice` aceptan `&persona=` opcional. Sin el
   parámetro usan la personalidad ACTUAL de Sol (vía `_get_cfg`), normalizando
   acentos (cálida→calida). Desconocida → cálida (la de casa).
3. `sol_holo_live.html`: `playbackRate` ELIMINADO por completo; `say()` ahora
   pasa `&persona=` (la del aura activa) y el backend sintetiza el carácter.
   El `<audio>` reproduce 1:1 lo que edge-tts generó — sin deformación.
4. `sol.html` (UI principal) ya usaba `/api/sol/tts` sin playbackRate →
   hereda el encanto automáticamente (default = personalidad actual).

**Testeado en sandbox antes de subir:** edge-tts 7.2.8 genera mp3 válidos con
rate/pitch (duraciones cambian según lo esperado: base 9.0s, cálida 9.6s,
poética 10.2s, táctica 8.7s para el mismo texto). `ast.parse` en sol_api.py,
`node --check` en el JS extraído del HTML, MD5 idéntico post-upload.

**NOTA de arquitectura (sin cambios):** Red-team-tauri tiene un `sol_api.py`
legacy en su raíz (46KB, divergente del de sol 66KB) — omni.sh NUNCA lo
ejecuta (siempre `$HOME/sol/sol_api.py`), es residuo. No se tocó.

### 🔍 Verificar tras el UNICO republish de Harold:
- Holo: tocar las 4 auras (🌿🌸🗡🧭) y que diga algo en cada una — poética
  debe sonar lenta/íntima, táctica ágil, TODAS con la misma voz Salome (sin
  chipmunk). El ECG y el glow siguen vibrando con el audio (analyser intacto).
- sol.html: voz cálida por defecto sin ningún cambio de UI.
- Si el parámetro `persona` no llega (versión vieja cacheada del HTML):
  hard-refresh del navegador (Ctrl+Shift+R / limpiar caché de la webview).

## Regla #21 — Sesión Seal IA 2026-09-04 (fix urgente): pantalla negra al tocar ✨

Harold: republish en Replit, tocó ✨ y quedó pantalla negra total. Cerró y
reabrió el navegador, reinició en Replit — seguía igual.

**Causa raíz (bug real, mío, de la Regla #18):** `toggleHolo()` en `sol.html`
decidía si usar `/holo` (mismo servidor) o el fallback
`http://host:8006/holo` buscando la palabra LITERAL `"Holograma"` dentro del
HTML descargado. Al reescribir `sol_holo_live.html` completo para "Presencia
Total v4" ese texto ya no existe → la detección SIEMPRE fallaba → SIEMPRE
usaba el fallback `:8006` → en Replit ese puerto no está expuesto al público
→ el iframe nunca cargaba nada → pantalla negra (el fondo `#04070c` del
overlay, sin absolutamente nada encima — así se ve un iframe que nunca
resolvió su `src`).

**Fix (commit sol@930deffee2, RT@e91e648d56):** la detección ahora usa
SOLO el status HTTP real (`r.ok`), nunca el contenido de la página — así
nunca se vuelve a romper por cambiar texto/título del holo. Además tanto
`sol_api.py` (Replit) como `dashboard_server.py` (Termux :8001) YA sirven
`/holo` en su propio origen (confirmado leyendo el código de ambos), así que
el fallback a `:8006` casi nunca debería necesitarse — queda solo como red
de seguridad ante un fallo real de red/servidor.

**Verificado antes de subir:** `node --check` en los 2 bloques `<script>` de
cada archivo, MD5 idéntico entre `sol/static/sol.html` y
`Red-team-tauri/backend/static/sol.html` (son y deben seguir siendo el mismo
archivo), MD5 idéntico post-upload en GitHub.

**Lección para la próxima vez que se reescriba `sol_holo_live.html` por
completo:** buscar en `sol.html`/`sol_main.html` cualquier detección basada
en texto/contenido de otra página antes de cambiar esa página — ya no debería
pasar (la detección ahora es por status HTTP), pero es la 2da vez que un
rewrite grande del holo rompe algo en el lado que lo embebe.

### 🔍 Siguiente paso: Harold debe hacer republish en Replit UNA VEZ MÁS
(este fix vive en `sol.html`, no en `sol_holo_live.html` — el republish
anterior sirvió el holo nuevo correctamente, pero el BOTÓN que lo abre tenía
el bug). Tras el republish: tocar ✨ y confirmar que abre el holograma con
las 5 formas de ella y la voz encantada — no debería quedar más pantalla negra.
