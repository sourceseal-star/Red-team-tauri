# ☀️ Termux:API — Salud del puente y blindaje

**Fecha:** 2026-09-03 · **Estado:** ✅ RESUELTO y blindado
**Contexto:** Motorola Edge 50 · Termux + Termux:API (F-Droid) · Sol corriendo en `~/sol` vía omni.sh

---

## El problema (y por qué "funcionaba y luego se dañaba solo")

Los comandos `termux-*` (linterna, batería, GPS, portapapeles) se quedaban
**colgados sin responder** — ni error, ni salida. `termux-torch on` no prendía
el flash; `termux-battery-status` se congelaba 3+ minutos hasta Ctrl+C
(exit code 130).

**Causa raíz:** el paquete CLI `termux-api` (instalado con `pkg`) y la **app
Termux:API** (F-Droid) quedaron **desincronizados de versión**. El CLI manda
su mensaje a la app; la app vieja/nueva ya no lo entiende → silencio eterno.

**Cómo se desincronizan:**
- `pkg upgrade` manual actualiza el CLI y no la app
- F-Droid actualiza la app y no el CLI
- Las DOS fuentes se actualizan por separado, en momentos distintos

**Dato importante:** `sol_evolve.sh` NO toca paquetes del sistema (solo
`requirements.txt` de Python) — el daemon evolve es inocente. La
desincronización siempre vino de actualizaciones separadas de CLI o app.

**Nota histórica:** antes del commit `2fec056` (repo sol), `tool_flashlight`
reportaba "encendida" SIN verificar el resultado — mentía. El fix la hizo
honesta: ahora verifica `returncode` y dice exactamente qué falla. Parte del
"funcionaba antes" era la linterna mintiendo.

---

## La cura (receta confirmada funcionando — 2026-09-03)

1. **Actualizar el CLI:**
   ```
   pkg upgrade
   ```
2. **Actualizar la app Termux:API desde F-Droid** (NO Play Store — la de Play
   está obsoleta y no sirve): https://f-droid.org/en/packages/com.termux.api/
3. **Quitar la optimización de batería** (Motorola es agresivo matando apps):
   Ajustes → Batería → optimización → **Termux** y **Termux:API** → "Sin
   restricciones"
4. Reiniciar el stack: `bash omni.sh restart`
5. Validar escribiéndole a Sol: **«diagnóstico»** (prueba linterna, batería,
   GPS, portapapeles, wake-lock y WiFi en vivo)

**Verificación rápida del puente (sin Sol):**
```
termux-battery-status
```
Debe responder con un JSON en 2–3 segundos. Si se cuelga → volver al paso 1.

**Extra:** la linterna requiere permiso de **Cámara** en la app Termux:API
(el flash es parte del módulo de cámara de Android).

---

## El blindaje (para que nunca más falle)

### 1. Guard automático en omni.sh (`termux_guard`)

Agregado a `start` y `status`. En cada arranque/chequeo:
- Si no es Termux (Replit/servidor) → no hace nada
- Si falta el paquete CLI → avisa con la solución exacta
- **Prueba el puente en vivo** (`timeout 4 termux-battery-status`):
  - Responde → `✅ Puente Termux:API sano`
  - Se cuelga → `❌ Puente COLGADO` + los 4 pasos de la cura
- El diagnóstico de Sol («diagnóstico») hace la prueba profunda por herramienta

### 2. Prevención de desincronización futura (recomendado, manual)

**Congelar el CLI** para que ningún `pkg upgrade` lo mueva solo:
```
apt-mark hold termux-api
```
Y en F-Droid: no auto-actualizar Termux:API (desactivar "Auto-update" para
esa app, o actualizarla conscientemente).

**Regla de oro:** CLI y app se actualizan JUNTOS o no se tocan:
```
apt-mark unhold termux-api
pkg upgrade
# actualizar app Termux:API en F-Droid al mismo tiempo
apt-mark hold termux-api
```

### 3. Memoria del agente (Solene)

Guardado como memoria confirmada: síntoma → causa → cura, para diagnóstico
inmediato en futuras sesiones sin re-investigar.

---

## Resultado confirmado

- ✅ `termux-torch on/off` — linterna física del Edge 50 responde
- ✅ Sol responde con voz: "Linterna encendida, Harold"
- ✅ Puente CLI ↔ app sano; stack completo reiniciado

*SourceSeal — Operational Link · El escudo que aprendió a decir la verdad 🔦*
