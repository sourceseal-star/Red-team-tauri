# COM-LINK — Estado operativo y verificación

**Última verificación:** 2026-08-31  
**Versión del script:** 3.0  
**Regla:** la existencia de `commander/comlink/comlink.sh` no significa que
los siete canales estén disponibles.

## Resultado comprobado

En el entorno Replit, el estado real verificado es **0/7 canales listos**:
no existen las APIs de Termux, no hay hardware de radio/Bluetooth/satélite y
la configuración de Telegram/SIP está vacía. Esto es correcto: Replit no es
el teléfono y no puede enviar SMS ni acceder a sus periféricos.

En Termux, el dashboard debe iniciarse localmente con:

```bash
cd ~/Red-team-tauri
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

El backend ejecuta COM-LINK en el mismo entorno donde corre el dashboard. No
hay un túnel mágico desde Replit hacia Termux.

## Estado sin enviar mensajes

Ejecuta en Termux:

```bash
cd ~/Red-team-tauri
bash commander/comlink/comlink.sh status-json | jq
```

El resultado incluye `ready_count`, `ready_channels` y una entrada por canal
con `reason` y `requires`. `ready` solo confirma requisitos locales; no
confirma que el proveedor haya entregado un mensaje.

También puede consultarse desde el dashboard:

```bash
curl -H "Authorization: Bearer TU_TOKEN" \
  http://127.0.0.1:8001/api/commander/comlink/status
```

El dashboard ya no debe mostrar “7 canales” solo porque el archivo exista.

## Matriz de canales

| Canal | Estado del código | Requisitos reales | Qué confirma el estado |
|---|---|---|---|
| SMS | Implementado con Termux:API | Termux:API, permisos, SIM/cobertura, destino | Existe `termux-sms-send` y hay teléfono configurado |
| Telegram | Implementado con API HTTPS | token del bot, chat ID, Internet y permisos del bot | Token/chat ID están configurados; no garantiza entrega |
| VoIP/SIP | Llamada SIP condicionada | `linphonec`, servidor, usuario, contraseña y red | Cliente y credenciales presentes; falta confirmar registro |
| Mesh WiFi | Peer HTTP local | WiFi conectado y otro peer COM-LINK | WiFi local presente; falta confirmar peer |
| Mesh Bluetooth | RFCOMM condicionado | Bluetooth, `hcitool`, `rfcomm` y peer compatible | Herramientas y adaptador presentes; falta confirmar peer |
| Radio AX.25 | **No implementado** | TNC, driver y configuración de radio | Siempre no listo hasta integrar y probar un driver |
| Satélite | **No implementado** | Módem, proveedor y driver específico | Siempre no listo; no envía comandos AT genéricos |

Radio y satélite ya no devuelven éxito ni escriben en un puerto serie con una
implementación de ejemplo. Es preferible fallar explícitamente a reportar una
transmisión inexistente.

## Pruebas seguras

Estas comprobaciones no envían comunicaciones:

```bash
bash -n commander/comlink/comlink.sh \
  commander/comlink/channels/*.sh \
  commander/comlink/crypto/*.sh \
  commander/comlink/utils/*.sh
bash commander/comlink/comlink.sh status-json | jq -e '.ready_count >= 0'
```

Para probar un canal externo se necesita una prueba controlada con un destino
propio y consentimiento del operador. El endpoint y los comandos de envío son
acciones reales; no se ejecutan automáticamente durante el arranque.

## Preparación por canal

### SMS

1. Instala Termux desde F-Droid y la aplicación Termux:API desde la misma
   fuente.
2. En Termux instala el paquete cliente:

   ```bash
   pkg install termux-api
   ```

3. Concede permisos de SMS a Termux:API y configura
   `contacts.emergency.phone` en `commander/comlink/data/contacts.json`.
4. Ejecuta `status-json`; solo cuando indique SMS listo, prueba con un número
   propio.

### Telegram

Configura el token y el chat ID mediante el menú de configuración de COM-LINK.
No guardes tokens en el repositorio compartido ni los pegues en el dashboard.
El bot debe haber iniciado conversación con el chat de destino.

### VoIP

La ruta SIP requiere un servidor y credenciales reales. La ruta WebRTC del
menú es informativa y devuelve error: no existe un servidor de señalización
implementado.

### Mesh WiFi y Bluetooth

Son enlaces locales entre dos dispositivos compatibles. No son Internet,
no son multi-salto por sí solos y el peer debe ejecutar el protocolo esperado.
Mesh WiFi usa HTTP local y actualmente no debe describirse como TLS.

### Radio y satélite

No deben anunciarse como disponibles. La integración requiere definir el
hardware, protocolo, permisos y pruebas de recepción/transmisión antes de
habilitarla.

## Cifrado

El script no usa `openssl enc -aes-256-gcm`, porque esa combinación no está
disponible de forma funcional en las versiones actuales de OpenSSL. El formato
actual es `v1` con AES-256-CBC, IV aleatorio y HMAC-SHA256
(encrypt-then-MAC). Las claves de contacto deben provisionarse antes de
activar el cifrado; el cifrado no sustituye la seguridad del transporte.

## Qué no significa COM-LINK

- No es un broadcast simultáneo por siete canales.
- No garantiza cobertura, entrega, anonimato ni acceso satelital.
- No activa SMS, GPS, Bluetooth, mesh, radio o VoIP durante el arranque.
- No convierte el dashboard Replit en un controlador del hardware Android.