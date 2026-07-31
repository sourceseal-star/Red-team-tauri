# Deception — Active Defense

Módulo de defensa activa que genera honeytokens realistas (JWT, AWS keys, DB credentials, API keys) con rotación automática, mesh de deception con canary tokens y exportación de inteligencia a STIX 2.1 con mapeo MITRE ATT&CK (25 técnicas).

---

## Estructura

```
deception/
├── __init__.py          # Exports: DeceptionMesh, CanaryToken, DecoyEndpoint, SyntheticSession, HoneyTokenGenerator
├── mesh.py              # DeceptionMesh original (canary tokens, decoy endpoints, synthetic sessions)
├── auto_rotation.py     # HoneyTokenGenerator + TokenRotationManager
├── dynamic_mesh.py      # Mesh dinámico con rotación automática
├── stix_tip.py          # STIX 2.1 TIP con 25 técnicas MITRE + federación TAXII
└── test_honeytokens.py  # Unit tests
```

---

## Componentes

### HoneyTokenGenerator (auto_rotation.py)

Genera honeytokens de alta fidelidad que parecen credenciales reales:

| Tipo | Método | Formato |
|------|--------|---------|
| JWT | `generate_jwt(user_id)` | `header.payload.signature` (HS256, 3 partes base64url) |
| API Key | `generate_api_key(prefix)` | `sk-live-<40 hex chars>` (formato OpenAI/Stripe) |
| AWS Credentials | `generate_aws_credentials()` | `AKIA<16 chars>` + secret de 40 chars |
| DB Connection | `generate_db_connection_string()` | PostgreSQL / MongoDB / MySQL / SQL Server con password embebida |

Características:
- JWT firmado con HMAC-SHA256 (verificable pero con clave de deception)
- AWS credentials cumplen el formato regex estándar
- DB strings rotan entre 4 motores de base de datos
- Todos usan `secrets.token_hex` para aleatoriedad criptográfica

### TokenRotationManager (auto_rotation.py)

Administra el ciclo de vida de los honeytokens:

- **Rotación automática** — Invalida todos los tokens activos y genera un conjunto nuevo
- **TTL configurable** — Expiración por token (default: 3600s)
- **Callbacks** — Registra funciones que se ejecutan cuando un token es accedido
- **Thread-safe** — Lock para operaciones concurrentes
- **Tracking** — Estado por token: type, created_at, expires_at, active, metadata

```python
from deception.auto_rotation import HoneyTokenGenerator, TokenRotationManager

gen = HoneyTokenGenerator()

# Generar tokens individuales
jwt = gen.generate_jwt(user_id="lure_admin")
aws = gen.generate_aws_credentials()
api_key = gen.generate_api_key()
db = gen.generate_db_connection_string()

# Rotación automática
mgr = TokenRotationManager(default_ttl=3600)
tokens = mgr.rotate_all()  # Genera JWT + API Key + AWS + DB
print(f"Active tokens: {len(mgr.active_tokens)}")

# Registrar callback de alerta
def on_access(token_type, value, meta):
    print(f"ALERT: Honeytoken {token_type} accessed!")

mgr.callbacks.append(on_access)
```

### DeceptionMesh (mesh.py)

Mesh de deception con componentes activos:

- **CanaryToken** — Tokens canary que generan alertas al ser accedidos
- **DecoyEndpoint** — Endpoints falsos que simulan servicios reales
- **SyntheticSession** — Sesiones sintéticas para confundir atacantes

### STIX TIP (stix_tip.py)

Plataforma de inteligencia de amenazas integrada:

- **STIX 2.1** — Exportación de IoCs en formato STIX con la librería `stix2`
- **MITRE ATT&CK** — 25 técnicas mapeadas (T1566, T1190, T1133, T1059, T1203, T1547, ...)
- **Federación TAXII** — Publicación y suscripción a servidores TAXII 2.1
- **Mapeo automático** — Alertas de red → técnicas MITRE ATT&CK

---

## Tests

```bash
cd deception/
python -m pytest test_honeytokens.py -v
# o
python test_honeytokens.py
```

Cobertura: generación de cada tipo de honeytoken, verificación de formato, unicidad, rotación, invalidación de tokens viejos, y callbacks.

---

## Dependencias

```
# STIX TIP (opcional — graceful fallback si no está instalado)
stix2>=3.0
requests>=2.31
```
