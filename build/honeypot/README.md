# Honeypot — Subred Aislada

## Despliegue

```bash
# 1. Crear subred aislada (ya existe en tu infra, asumimos 10.99.0.0/24)
# 2. Levantar el señuelo en un host de esa subred
docker build -t crypto-honeypot honeypot/
docker run -d --name honeypot \
  --network none \          # o tu red aislada
  -p 8443:8443 \
  -e HONEYPOT_CANARY="$(openssl rand -hex 8)" \
  -v $(pwd)/evidence/honeypot:/app/evidence \
  crypto-honeypot
```

## Endpoints expuestos
- `GET /v1/health`     → respuesta rápida
- `GET /v1/keys`       → tarpit 2s, devuelve claves ficticias
- `GET /v1/auth`       → emite token canario (`X-Canary` header)
- `POST /v1/transactions` → tarpit 1.5s, captura payload

## Detección
Si el token canario aparece en logs de cualquier sistema tuyo,
ese sistema consumió datos del honeypot → compromiso interno.
