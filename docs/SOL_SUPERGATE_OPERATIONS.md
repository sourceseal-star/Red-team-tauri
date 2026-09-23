# SOL SuperGate — operación y mantenimiento

**Estado:** fallback aditivo, local y no-root  
**Última actualización:** 2026-09-22

Esta guía describe cómo operar y modificar el SuperGate sin romper el portero
principal, las credenciales ni el arranque de SourceSeal.

## 1. Qué es y dónde vive

El SuperGate es el portero local que permite consultar red y ejecutar un grupo
pequeño de acciones explícitamente permitidas. Está pensado para Termux/Android
sin privilegios de root.

| Ubicación | Responsabilidad |
|---|---|
| `~/sol/sol_portero.py` | Portero principal. Siempre tiene prioridad. |
| `~/sol/sol_supergate.py` | Copia local del fallback, si fue provisionada. |
| `sol_rescate/sol_supergate.py` | Fuente versionada del fallback aditivo. |
| `redteam/data/sol_supergate.json` | Configuración no secreta del fallback. |
| `omni.sh` | Arranque, parada, watchdog, estado y comandos operativos. |
| `curar.sh` | Validación y provisionado seguro durante la cura. |
| `sol_rescate/tests/test_supergate.py` | Regresiones de autenticación y allowlist. |

### Precedencia de arranque

`omni.sh` usa exactamente este orden:

1. `~/sol/sol_portero.py`
2. `~/sol/sol_supergate.py`
3. `Red-team-tauri/sol_rescate/sol_supergate.py` como último rescate local

El fallback nunca reemplaza ni sobrescribe `sol_portero.py`. Si no existe
ninguna de las tres opciones, el arranque del portero falla de forma explícita.

En el stack completo de Termux, el SuperGate escucha en `127.0.0.1:8012`.
El dashboard principal continúa en `:8001`; no se debe lanzar el fallback
manualmente en `:8001` mientras el stack completo esté activo.

### Límite operativo en Replit

`replit_start.sh` levanta el dashboard y el frontend, pero no inicia el
SuperGate en `:8012`. Es intencional: Replit no tiene el hardware Android,
Netlink ni Termux:API del teléfono. En Replit, la pestaña **SOL SUPERGATE**
del War Room solo permite revisar y editar la configuración no secreta y
mostrar el resultado de la sonda; que el portero local no esté accesible allí
es el comportamiento esperado.

La activación real se hace en Termux con:

```bash
cd ~/Red-team-tauri
bash omni.sh start
bash omni.sh supergate status
```

No expongas `:8012` a Internet ni añadas ese puerto al workflow de Replit.

## 2. Credenciales y límites de seguridad

Configura la clave en `~/sol/.env` o en el entorno del proceso:

```bash
SOL_API_KEY=pon-la-clave-real-en-tu-entorno
```

`SOL_KEY` se mantiene como alias de compatibilidad. Si ambas existen,
`SOL_API_KEY` tiene prioridad.

Reglas obligatorias:

- No existe una clave predeterminada. Sin clave, las rutas protegidas devuelven
  `503` y el portero permanece cerrado.
- No pongas claves en el código, HTML, URL, commits, capturas, logs o mensajes.
- El panel de `/` recibe la clave manualmente y no la persiste en el navegador.
- El listener por defecto es loopback (`127.0.0.1`).
- Las acciones están limitadas a `ping`, `netstat` e `ip_neigh`.
- Los comandos se ejecutan como listas de argumentos, nunca con `shell=True`.
- El barrido de red solo se ejecuta mediante una acción explícita del operador.
- Netlink y mDNS son capacidades locales del dispositivo; Replit no simula
  hardware Android ni debe inventar resultados.

Protege el archivo de entorno:

```bash
chmod 600 ~/sol/.env
```

## 3. Arranque y uso diario en Termux

Desde el repositorio principal:

```bash
cd ~/Red-team-tauri
bash omni.sh start
bash omni.sh status
```

El panel independiente queda disponible en:

```text
http://127.0.0.1:8012/
```

En el panel:

1. Introduce la clave configurada en el entorno.
2. Pulsa **Conectar** para consultar `/sol/contexto`.
3. Pulsa **Ejecutar barrido real** solo cuando necesites descubrir vecinos
   Netlink y respuestas mDNS.

Comandos específicos:

```bash
bash omni.sh supergate status
bash omni.sh supergate sweep
bash omni.sh supergate action ping 127.0.0.1
bash omni.sh supergate action netstat
bash omni.sh supergate action ip_neigh
bash omni.sh logs gate
```

`status` y el watchdog usan `/health` y aceptan respuestas protegidas de
`/sol/contexto` como señal de que el proceso está vivo. Un `401`, `403` o
`503` no significa necesariamente que el proceso esté caído; consulta el log
si la operación protegida falla.

Para detener o reiniciar:

```bash
bash omni.sh stop
bash omni.sh restart
```

`stop` debe limpiar tanto `sol_portero` como `sol_supergate`. No mates el
proceso manualmente salvo que estés recuperando un bloqueo de puerto y hayas
revisado primero `bash omni.sh status`.

## 4. Cura y provisionado del fallback

Ejecuta:

```bash
cd ~/Red-team-tauri
bash curar.sh
```

`curar.sh`:

1. Respalda los `.env` antes de operar.
2. Valida que `sol_rescate/sol_supergate.py` compile.
3. Conserva una copia local existente de `~/sol/sol_supergate.py`.
4. Solo instala el fallback si falta el portero principal y falta la copia
   local.
5. Arranca y diagnostica el stack completo.

Si `~/sol/sol_supergate.py` existe pero no compila, la cura no lo reemplaza de
forma silenciosa: informa el problema para que el operador decida.

## 5. Procedimiento para futuras modificaciones

### Cambiar el backend

1. Modifica `sol_rescate/sol_supergate.py`, no una copia temporal en `~/sol`.
2. Mantén las rutas y contratos existentes:
   - `GET /health`
   - `GET /sol/contexto`
   - `POST /api/network/sweep-real`
   - `POST /api/action/execute`
   - `GET /`
3. Si cambias una respuesta o una acción, actualiza simultáneamente:
   - `sol_rescate/tests/test_supergate.py`
   - `omni.sh`
   - esta guía
4. No agregues comandos a la allowlist sin una justificación operativa y una
   prueba que confirme validación de entrada.

### Cambiar el panel

- Mantén la clave fuera del HTML servido.
- No la guardes en `localStorage`, cookies, query strings ni campos ocultos.
- Usa `textContent` para resultados dinámicos; no uses `innerHTML` con datos de
  red.
- Conserva el botón de barrido como acción manual, nunca automática al cargar.
- Si se modifica la ruta raíz, verifica que siga devolviendo `HTMLResponse`.

### Cambiar el arranque

- Conserva la precedencia `sol_portero` → `sol_supergate`.
- Usa `sol_gate_is_alive` para health checks; no pruebes únicamente
  `/sol/contexto` sin contemplar autenticación.
- Si agregas otro nombre de proceso, actualiza las rutas de `start`, `stop`,
  `status` y `watchdog` juntas.
- No cambies el puerto del stack completo sin actualizar `omni.sh`, esta guía
  y cualquier proxy asociado.

## 6. Verificación antes de publicar cambios

Desde la raíz del repositorio:

```bash
python3 -m unittest sol_rescate.tests.test_supergate -v
python3 -m py_compile sol_rescate/sol_supergate.py
bash -n omni.sh
bash -n curar.sh
git diff --check
```

Verificaciones manuales mínimas:

```bash
# Sin revelar la clave en la consola ni en el historial:
curl -s http://127.0.0.1:8012/health
curl -i http://127.0.0.1:8012/sol/contexto
```

Debe ocurrir lo siguiente:

- `/health` responde sin autenticación.
- `/sol/contexto` no responde `200` sin una clave válida.
- Una acción desconocida responde `400`.
- Un destino con metacaracteres de shell responde `400`.
- El barrido no se ejecuta al abrir el panel.

No añadas PyMuPDF/MuPDF al proyecto para leer documentación o PDFs. Las
herramientas de lectura son auxiliares y no forman parte del runtime de
SuperGate.

## 7. Actualización segura en Termux

La actualización normal separa sincronización y ejecución:

```bash
cd ~/Red-team-tauri
bash omni.sh sync
bash omni.sh restart
bash omni.sh status
```

Si hay cambios locales, no uses `git reset --hard` ni `git clean` para
"arreglar" el estado sin revisar antes. `curar.sh` y los flujos de Termux
deben preservar los `.env` y las copias locales del operador.

Para actualizar código del fallback:

1. Cambia la fuente en `Red-team-tauri/sol_rescate/`.
2. Ejecuta las pruebas locales.
3. Publica el cambio por el flujo normal del repositorio.
4. En Termux ejecuta `omni.sh sync`.
5. Ejecuta `curar.sh` solo si necesitas reparar o provisionar `~/sol`.
6. Reinicia y verifica el estado.

Nunca guardes tokens, contraseñas ni URLs con credenciales en el repositorio.