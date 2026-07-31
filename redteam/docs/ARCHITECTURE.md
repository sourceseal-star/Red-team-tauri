# Arquitectura Unificada de Ciberseguridad Defensiva de Grado Enterprise

Implementada sobre el agente red team existente, esta arquitectura sigue los principios de **Zero Trust** y **Defensa en Profundidad (Defense-in-Depth)**.

## 1. Diagrama de Flujo y Malla de Integración

```
[ Cliente Móvil / APK ] -------> ( RASP + Keystore Hardware + Attestation API )
                                           |
[ Tráfico Entrante/Saliente ] -> ( Proxy Desencapsulador TLS ) ---> ( Motor NDR Comportamental )
                                           |                                   |
[ Control de Acceso / API ] ---> ( ZTNA Gateway + ABAC ) <--------------------|
                                           |
[ Entramado de Engaño ] -------> ( Dynamic Deception Mesh ) ------------------|
                                                                               |
                                                                               v
                                                             [ Correlador XDR + Motor SOAR ]
                                                                               |
                                                             ( Ejecución Automática de Playbooks )
```

## 2. Componentes Integrados del Sistema

### A. Protección Integrada en el Cliente (Mobile & Client-Side Security)

- **Runtime Application Self-Protection (RASP)** — `defense/rasp.py`
  Detectores: `detect_frida`, `detect_xposed`, `detect_emulator`, `detect_debugger`, `detect_memory_tamper`, `verify_binary` (hash SHA-256 contra allowlist). Cada señal se mapea a MITRE ATT&CK.

- **Criptografía Asistida por Hardware y Attestation** — `defense/attestation.py`
  `HardwareKeystore` (RSA-2048, sign/unwrap) + `AttestationVerifier` (cert chain, OS version, patch level, integrity).

- **Ofuscación C/C++ (NDK)** — Recomendada vía OLLVM; no incluida en runtime (build-time).

### B. Inspección y Analítica de Red (Network Defense)

- **Proxy de Desencapsulado TLS/SSL** — `defense/ndr.py` → `TLSInterceptionProxy`
  Intercepta, decodifica payloads y alimenta el motor NDR.

- **Network Detection and Response (NDR)** — `NDREngine`
  Detectores comportamentales: `detect_beaconing` (T1071.001), `detect_dns_tunneling` (T1071.004), `detect_low_and_slow_exfil` (T1048), `detect_icmp_tunnel` (T1095). Ventana deslizante de 5 min.

### C. Gobernanza de APIs y Modelo Cero Confianza (API Security & ZTNA)

- **Zero Trust Network Access (ZTNA)** — `defense/ztna.py`
  `ZTNAContext` + `PolicyEngine` con ABAC DSL (default-deny, allow explícito) + `PostureScorer` + `JWTIssuer`/`JWTValidator` con revocación inmediata.

- **API Gateway con ABAC** — `defense/api_gateway.py` → decorador `@protect(action, resource)`
  Previene BOLA/BPOA mediante `BOLAProtector.check(ctx, resource)`.

- **Fuzzing Continuo e Integración CI/CD** — ya presente en `ci/` del agente; integrado con `.github-workflow-defense.yml` (este repo).

### D. Deception Mesh e Inteligencia de Amenazas (Deception & Threat Intel)

- **Malla de Engaño Dinámica** — `defense/deception.py`
  - `DecoyToken` — JWT sintéticos con `decoy:true`.
  - `DecoyDB` — SQLite en memoria; cualquier query genera hit crítico.
  - `DecoyEndpoint` — rutas trampa (`/admin-old`, `/.git`, `/v0/test`).
  - `STIXExporter` — convierte hits a IoCs STIX 2.1 (bundle exportable).

- **Integración TIP (STIX/TAXII)** — `STIXExporter.bundle()` compatible con feeds TAXII; propagación vía `NDREngine.blocklist_add()`.

### E. Visibilidad y Respuesta Orquestada (XDR & SOAR)

- **Extended Detection and Response (XDR)** — `defense/xdr.py`
  - `EventBus` con buffer circular 100k.
  - `Correlator` con reglas multi-evento.
  - `MITREMapper` mapea cada evento a technique + tactic.
  - `IncidentStore` mantiene timeline.

- **Security Orchestration, Automation, and Response (SOAR)** — `defense/soar.py`
  Playbooks en YAML (carpeta `defense/playbooks/`):
  - `pb_revoke_jwt.yaml`
  - `pb_isolate_device.yaml`
  - `pb_block_ioc.yaml`
  - `pb_quarantine_apk.yaml`
  Latencia objetivo: < 500ms.

## 3. Matriz de Cobertura y Tiempos de Respuesta

| Capa de Seguridad | Mecanismo Integrado | Tipo de Threat / Vector | Tiempo de Respuesta |
| :--- | :--- | :--- | :--- |
| **Cliente / App** | RASP + Hardware Keystore + Attestation | Reverse Engineering, Tampering, Memory Injection | Inmediato (Local) |
| **Tráfico / Red** | Proxy TLS + NDR Comportamental | Malware, Exfiltración, C2 Cifrado | < 1 segundo |
| **Control de API** | ZTNA + ABAC Gateway + Fuzzing CI/CD | BOLA, BPOA, Inyecciones, Flujos Ilícitos | Preventivo / Tiempo Real |
| **Engaño** | Deception Mesh + TIP (STIX/TAXII) | Reconocimiento, Movimiento Lateral | Inmediato (Alerta Crítica) |
| **Operaciones** | XDR + SOAR (Playbooks Automáticos) | Ataques Multivectoriales y Movimiento Complejo | Automático (< 500 ms) |

## 4. Threat Model Resumido

### STRIDE

| Categoría | Amenaza | Mitigación |
|---|---|---|
| **S**poofing | Cert pinning, device fingerprint | RASP binary hash, AttestationVerifier, TLS pinning |
| **T**ampering | Binary patching, runtime injection | RASP detect_frida/xposed/debugger + allowlist |
| **R**epudiation | Action denial | XDR EventBus (audit trail inmutable) |
| **I**nformation Disclosure | C2 exfiltration | NDR (beaconing, dns_tunnel, low_and_slow) + DLP |
| **D**enial of Service | API flood, replay | ZTNA rate limiting + JWT nonce + NDR detect burst |
| **E**levation of Privilege | BOLA, BPOA, token replay | BOLAProtector + ABAC default-deny + JWT revokation |

### PASTA (resumen)

1. **Definir objetivos** — Proteger transacciones + identidades (PII + tokens JWT + hashes SOURCESEALCORP).
2. **Definir alcance técnico** — APK, API REST, página de recuperación, honeypot.
3. **Descomposición de la app** — Boundary: cliente ↔ API; trust: TLS + JWT + cert pinning.
4. **Análisis de amenazas** — STRIDE + MITRE ATT&CK (15+ técnicas cubiertas en `defense/mitre_map.yaml`).
5. **Análisis de vulnerabilidades** — `scenarios/` (red team agent original) corre 11 escenarios + 10 ataques dinámicos.
6. **Análisis de riesgo** — Severidad en `reports/latest.md` (critical/high/medium/low).

## 5. Mapeo MITRE ATT&CK

Ver `defense/mitre_map.yaml`. Cubre ≥10 técnicas:

- T1056 — Input Capture (keylogging via hooking) — RASP
- T1611 — Debugger Evasion (Escape to Host) — RASP
- T1071.001 — Application Layer Protocol (Web Protocols) — NDR beaconing
- T1071.004 — DNS — NDR dns_tunneling
- T1048 — Exfiltration Over Alternative Protocol — NDR low_and_slow
- T1095 — Non-Application Layer Protocol — NDR icmp_tunnel
- T1185 — Browser Session Hijacking (decoy tokens) — Deception
- T1530 — Data from Cloud Storage (decoy DB) — Deception
- T1595 — Active Scanning (decoy endpoints) — Deception
- T1078 — Valid Accounts (BOLA) — ZTNA
- T1134 — Access Token Manipulation (JWT revoke) — ZTNA + SOAR
- T1562 — Impair Defenses (playbook block_ioc) — SOAR

## 6. Integración con el Red Team Agent existente

`defense/integration.py` → `DefenseMesh.ingest()` acepta señales de los escenarios
originales (`scenarios/sourcesealcorp.py`, `scenarios/recovery_page.py`, `scenarios/pegasus.py`)
y los enruta al bus XDR → correlator → SOAR. El orchestrator acepta `--with-defense`.

## 7. Operación

```bash
# tests
python3 -m pytest tests/test_defense.py -v

# pipeline defensivo
bash scripts/run_defense_pipeline.sh

# smoke manual
python3 -c "from defense import DefenseMesh; m=DefenseMesh(); print(m.health_check())"
```

Dashboard extendido con tab "Defense Mesh" en `dashboard/defense.html`.
