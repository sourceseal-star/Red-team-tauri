# RASP — Runtime Application Self-Protection

Agente embebido que monitorea el runtime del ejecutable y detecta hooking (Frida, Xposed, Substrate), emuladores, análisis en memoria, tampering, debugger attachment y root/jailbreak. Incluye servidor de atestación con HMAC-SHA256 y nonces anti-replay, integración con Google Play Integrity y Apple DeviceCheck.

---

## Estructura

```
rasp/
├── __init__.py              # Exports: RASPAgent, RASPAlert, HookingDetector, EmulatorDetector, TamperDetector, AttestationChecker, SourceSealAttestationClient
├── agent.py                 # RASPAgent + detectores (hooking, emulator, tamper, debugger, root)
├── attestation_server.py    # FastAPI server con HMAC-SHA256 + Play Integrity + DeviceCheck
├── attestation_client.py    # Cliente Python para testing de atestación
├── android/                 # RASP nativo Kotlin (AntiEmulator, AntiFrida, RaspDetector, TamperDetection)
├── ios/                     # RASP nativo Swift (RaspDetector)
├── Dockerfile               # Imagen Docker para attestation server
├── docker-compose.yml       # Service definition con env vars
├── requirements.txt         # fastapi, uvicorn, pydantic, httpx, PyJWT, cryptography
└── test_attestation.py      # Unit tests
```

---

## Detectores (agent.py)

| Detector | Tipo | MITRE | Detección |
|----------|------|-------|-----------|
| `HookingDetector` | hooking | T1622 | Frida (frida-server, frida-agent, gum-js-loop), Xposed (XposedBridge, Substrate) |
| `EmulatorDetector` | emulator | T1497 | QEMU, goldfish, propiedades build de emulador |
| `TamperDetector` | tampering | T1622 | Hash del binario, repackaging detection |
| `AttestationChecker` | attestation | — | Validación Play Integrity / DeviceCheck |

Cada detector retorna una lista de `RASPAlert` con tipo, severidad, evidencia y técnica MITRE.

---

## Attestation Server (attestation_server.py)

Servidor FastAPI que valida la integridad del dispositivo móvil:

### Flujo de Atestación

```
Cliente                    Server
  |                          |
  |--- POST /challenge ----->|  (device_id)
  |<-- nonce + HMAC sig -----|  (TTL 5 min)
  |                          |
  |--- POST /verify -------->|  (challenge, token, platform, signature)
  |<-- valid + risk score ---|  (Play Integrity / DeviceCheck)
  |                          |
```

### Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/v1/attestation/challenge` | Genera nonce criptográfico + firma HMAC |
| POST | `/v1/attestation/verify` | Verifica token de Play Integrity / DeviceCheck |
| GET | `/health` | Health check |

### Mecanismos de Seguridad

- **HMAC-SHA256** — Firma del challenge con `SOURCESEAL_SECRET_KEY`
- **Nonce anti-replay** — Cada challenge tiene TTL de 5 minutos, no se puede reutilizar
- **Thread-safe** — Lock para acceso concurrente a `ACTIVE_CHALLENGES`
- **Play Integrity API** — Integración con Google (credenciales de servicio o mock mode)
- **Apple DeviceCheck** — Integración con Apple (JWT ES256 o mock mode)

### Modo Mock (desarrollo)

Sin credenciales de Google/Apple configuradas, el server usa mock mode:
- Token que empieza con `mock-secure` → pasa la verificación
- Token que empieza con `mock-compromised` → falla la verificación

---

## Attestation Client (attestation_client.py)

Cliente Python para testing de integración:

```python
from rasp.attestation_client import SourceSealAttestationClient

client = SourceSealAttestationClient("http://localhost:8000")

# 1. Solicitar challenge
challenge = client.request_challenge(device_id="test-device")

# 2. Verificación local (offline)
report = {
    "isDeviceCompromised": False,
    "findings": [...]
}
is_safe = client.verify_local(report)

# 3. Enviar atestación al server
result = client.submit_attestation(
    challenge=challenge,
    token="mock-secure-token",
    platform="android"
)
print(f"Valid: {result['attestation_valid']}, Risk: {result['risk_score']}")
```

---

## Integración Android (Kotlin)

```
rasp/android/
├── AntiEmulator.kt     # Detección de QEMU, goldfish, build props
├── AntiFrida.kt        # Detección de Frida por puertos y /proc/self/maps
├── RaspDetector.kt     # Detector principal que orquesta todos los checks
├── TamperDetection.kt  # Integrity check del APK (signature hash)
└── android_rasp.kt     # Punto de entrada para la app Android
```

## Integración iOS (Swift)

```
rasp/ios/
├── RaspDetector.swift  # Detección de jailbreak, Frida, debugger, emulador
└── ios_rasp.swift      # Punto de entrada para la app iOS
```

---

## Despliegue con Docker

```bash
# Variables de entorno
export SOURCESEAL_SECRET_KEY="your-hmac-secret"
export ANDROID_PACKAGE_NAME="com.sourceseal.app"
export IOS_BUNDLE_ID="com.sourceseal.app"

# Levantar el server
cd rasp/
docker-compose up -d

# Verificar
curl http://localhost:8000/health
```

---

## Tests

```bash
cd rasp/
python -m pytest test_attestation.py -v
# o
python test_attestation.py
```

Cobertura: RASPAlert, HookingDetector (mock processes), EmulatorDetector, RASPAgent, HMAC, FastAPI endpoints (TestClient), attestation client local verification, Play Integrity mock, Apple DeviceCheck mock.

---

## Dependencias

```
# Server
fastapi>=0.104
uvicorn>=0.24
pydantic>=2.0
httpx>=0.25
PyJWT>=2.8
cryptography>=41.0

# Android (Gradle)
# Ver archivos .kt para dependencias nativas

# iOS (SPM)
# Ver archivos .swift para dependencias nativas
```
