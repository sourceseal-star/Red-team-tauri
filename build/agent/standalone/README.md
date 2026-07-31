# Agente Red Team — Standalone

Este agente es **completamente independiente** del software de ventas de la tienda.
Opera en su propio host/contenedor, sin credenciales compartidas, sin acceso al
backend de producción del cliente.

## Alcance del agente

| Hace | NO hace |
|---|---|
| Ataca builds de la app (APK/IPA) entregadas como artefacto | No se conecta al backend de ventas en producción |
| Ataca la API de **SOURCESEALCORP** (regeneración de hash + time-lock) | No comparte base de datos con la app |
| Opera honeypots en la subred aislada | No accede a datos de clientes reales |
| Audita el ciclo hash→blockchain→time-lock→regeneración | No roba ni exfiltra información |

## Uso

```bash
# Build del contenedor
docker build -t redteam-agent agent/standalone/

# Run con config mínima (modo dry-run si SOURCESEALCORP no está accesible)
docker run --rm \
  -e SOURCESEAL_API="https://api.sourcesealcorp.local/v1" \
  -e SOURCESEAL_KEY="tu-key-de-firma" \
  -v $(pwd)/reports:/agent/reports \
  redteam-agent

# Run contra una build específica
docker run --rm \
  -v /ruta/a/tu-app.apk:/agent/evidence/app.apk:ro \
  -e SOURCESEAL_API="https://api.sourcesealcorp.local/v1" \
  -e SOURCESEAL_KEY="tu-key" \
  -v $(pwd)/reports:/agent/reports \
  redteam-agent --target /agent/evidence/app.apk \
                --backend https://api.sourcesealcorp.local
```

## Aislamiento de red (recomendado)

```bash
# Crear red dedicada para el agente
docker network create --internal redteam-isolated
docker run --rm --network redteam-isolated redteam-agent
```

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `SOURCESEAL_API` | URL base de la API de SOURCESEALCORP | `https://api.sourcesealcorp.local/v1` |
| `SOURCESEAL_KEY` | Key HMAC para firmar requests | (vacía → dry-run con warning) |
| `AGENT_ID` | Identificador del agente para audit | `redteam-standalone-01` |
| `AGENT_TEST_SEED` | Seed para el ciclo de prueba de hash | (auto-generado) |

## Salida

- `reports/report-YYYYMMDD-HHMMSS.json` — datos estructurados
- `reports/latest.md` — resumen Markdown
- `evidence/*.json` — artefactos por escenario
- `evidence/honeypot/*.json` — capturas del honeypot

## Escenarios incluidos (10)

1. `rng` — entropía y CSPRNG
2. `pinning` — cert/key pinning
3. `sidechannel` — timing leaks, comparaciones no constant-time
4. `keyhandling` — claves hardcodeadas, KeyStore/Keychain
5. `payments` — PayPal/Stripe/Binance/MercadoPago
6. `biometric` — templates, bypass client-side
7. `business_logic` — IDOR, precios, race conditions, 2FA
8. `imei` — Luhn, blacklist
9. `multiplatform` — Android/iOS/Win/Linux/Ubuntu
10. `sourcesealcorp` — anclaje blockchain, time-lock, regeneración de hash
