# SourceSeal Red Team — Estado del Proyecto y Próximos Pasos

**Última actualización:** 2026-07-22
**Repositorio:** https://github.com/sourceseal-star/Red-team
**Branch:** main
**Último commit:** c7b584c — Fusion: XDR kill_chain + attack_surface, RASP mobile, NDR, Deception, TIP, Native JNI bridge

---

## Lo que YA está hecho (verificado en GitHub)

### XDR (Extended Detection & Response)
- [x] `correlator.py` — Motor de correlación con 20 técnicas MITRE ATT&CK (original del remote)
- [x] `kill_chain.py` — Cyber Kill Chain analyzer (7 fases Lockheed Martin + MITRE mapping + predicción + visualización ASCII/Mermaid/JSON) **NUEVO**
- [x] `attack_surface.py` — Mapper de superficie de ataque con risk scoring y comparación histórica **NUEVO**
- [x] `test_correlator.py` — Unit tests para correlador + kill chain + attack surface **NUEVO**
- [x] `README.md` — Documentación completa del módulo **NUEVO**
- [x] `requirements.txt` — Sin deps externas (stdlib only) **NUEVO**
- [x] `__init__.py` — Exports actualizados con todos los componentes

### RASP (Runtime Application Self-Protection)
- [x] `agent.py` — RASP Agent Python (original del remote: RASPAgent, HookingDetector, EmulatorDetector, etc.)
- [x] `android_rasp.kt` — RASP nativo Android Kotlin (root, Frida, Xposed, debugger, emulador, Play Integrity) **NUEVO**
- [x] `ios_rasp.swift` — RASP nativo iOS Swift (jailbreak, Frida, debugger, emulador) **NUEVO**
- [x] `attestation_server.py` — FastAPI + HMAC-SHA256 + nonces anti-replay + Play Integrity + DeviceCheck **NUEVO**
- [x] `attestation_client.py` — Cliente Python para testing de atestación **NUEVO**
- [x] `requirements.txt` — fastapi, uvicorn, pydantic, httpx, PyJWT, cryptography **NUEVO**

### NDR (Network Detection & Response)
- [x] `engine.py` — NDREngine original del remote (TrafficFlow, AnomalyAlert, C2Detector, ExfilDetector)
- [x] `network_capture.py` — Captura Scapy/Pyshark + buffer circular 10K flujos + reconstrucción TCP/UDP bidireccional **NUEVO**
- [x] `ml_detector.py` — IsolationForest + heurísticas (C2 beaconing, DNS tunneling, ICMP exfiltration, DGA detection) **NUEVO**

### Deception (Active Defense)
- [x] `mesh.py` — DeceptionMesh original del remote (CanaryToken, DecoyEndpoint, SyntheticSession)
- [x] `stix_tip.py` — STIX 2.1 TIP con 25 técnicas MITRE ATT&CK + exportación + federación TAXII **NUEVO**
- [x] `auto_rotation.py` — Honeytokens (JWT, AWS keys, DB credentials, GitHub tokens) + rotación automática programable **NUEVO**

### TIP (Threat Intelligence Platform)
- [x] `platform.py` — ThreatIntelPlatform original del remote (gestión de IoCs, blocklists)
- [x] `stix_taxii.py` — STIX 2.1 + TAXII 2.1 con 50 técnicas MITRE ATT&CK + STIXBundle + TAXIIPublisher + TAXIISubscriber **NUEVO**

### Native (JNI Bridge)
- [x] `jni_bridge.c` — SHA-256 auto-contenido + ptrace anti-debug + detección Frida por puertos y librerías **NUEVO**
- [x] `CMakeLists.txt` — Configuración CMake NDK multi-ABI (arm64-v8a, x86_64) **NUEVO**
- [x] `build_android.sh` — Script de build NDK + soporte OLLVM opcional + verificación post-build **NUEVO**

### Otros módulos del remote (NO modificados, ya estaban)
- [x] `soar/engine.py` — SOAREngine con 8 playbooks básicos
- [x] `ztna/gateway.py` — ZTNA Gateway
- [x] `probe/real_scanner.py` — Scanner de vulnerabilidades
- [x] `runner/orchestrator.py` + `unified_orchestrator.py` — Orquestadores
- [x] `scenarios/` — 13 escenarios de pentest (biometric, payments, pegasus, etc.)
- [x] `honeypot/` — Honeypots y C2 sinkhole
- [x] `dashboard/` — Dashboard web PWA
- [x] `integrity/seal_manager.py` — Gestor de sellos SourceSeal
- [x] `scripts/` — Scripts de automatización (termux, pipeline)
- [x] `docs/` — RUNBOOK + OLLVM build guide
- [x] `verify_redteam.py` — Script de verificación de módulos

---

## ❌ Lo que FALTA (no se completó — sub-agentes se quedaron sin tiempo)

### SOAR — Módulo incompleto
El remote tiene `soar/engine.py` con 8 playbooks básicos inline, pero FALTA:

1. **`soar/dag_executor.py`** — Ejecutor DAG (Directed Acyclic Graph):
   - Topological sort de steps del playbook
   - Ejecución paralela de steps independientes (asyncio o ThreadPoolExecutor)
   - Mecanismo de rollback (ejecución en orden inverso de steps completados)
   - Tracking de estado por step (PENDING, RUNNING, SUCCESS, FAILED, SKIPPED, ROLLED_BACK)
   - Timeout handling por step
   - Dependencias entre steps (declarar qué steps deben completar primero)
   - Context dict pasado entre steps
   - MITRE ATT&CK technique tagging

2. **`soar/handlers.py`** — Handlers HTTP reales para acciones:
   - `block_ip_waf` — Bloquear IP en WAF (Cloudflare, AWS WAF)
   - `revoke_ztna_session` — Revocar sesión en ZTNA gateway
   - `disable_user_auth` — Deshabilitar usuario en Auth0/Keycloak
   - `quarantine_email` — Cuarentena de email (O365 / Google Workspace)
   - `dns_sinkhole` — Sinkhole DNS en servidor DNS interno
   - `slack_alert` — Enviar alerta a webhook de Slack
   - Cada handler: función async, toma context dict, retorna result dict con success/failure
   - Error handling y timeouts con httpx
   - Log de cada acción con timestamp, técnica MITRE y resultado

3. **`soar/incident_manager.py`** — Gestión del ciclo de vida de incidentes:
   - Crear incidente desde alerta XDR (acepta XDREvent-like input)
   - Track MTTR (Mean Time to Respond/Recover) con timestamps
   - Reglas de escalación de severidad (LOW→MEDIUM→HIGH→CRITICAL según técnicas MITRE)
   - Auto-asignación de playbooks según técnica MITRE o tipo de incidente
   - Estados: OPEN, INVESTIGATING, CONTAINED, ERADICATED, RECOVERED, CLOSED
   - Métricas: MTTR, MTTD, incident count por severidad
   - Exportar reporte de incidente como JSON

4. **`soar/playbooks/`** — 6 playbooks JSON (NO inline, archivos separados):
   - `playbook_phishing.json` — T1566: quarantine email → disable user if clicked → block sender → alert SOC
   - `playbook_ransomware.json` — T1486: isolate host → block C2 IPs → revoke sessions → verify backups → executive alert
   - `playbook_c2_beaconing.json` — T1071: sinkhole domain → block IPs at WAF → investigate hosts → revoke sessions
   - `playbook_credential_stuffing.json` — T1110: enforce MFA → lock accounts → block source IPs → alert users
   - `playbook_lateral_movement.json` — T1021: isolate hosts → revoke kerberos tickets → reset service accounts
   - `playbook_data_exfiltration.json` — T1041: block egress IPs → capture evidence → alert DPO (GDPR Art. 33) → freeze accounts

   Estructura de cada playbook JSON:
   ```json
   {
     "name": "...",
     "description": "...",
     "mitre_techniques": ["T1566"],
     "severity": "HIGH",
     "steps": [
       {
         "id": "step_1",
         "name": "Quarantine Email",
         "handler": "quarantine_email",
         "params": {"provider": "o365", "action": "move_to_quarantine"},
         "depends_on": [],
         "timeout_seconds": 30,
         "rollback_handler": "restore_email"
       }
     ]
   }
   ```

5. **`soar/test_dag_executor.py`** — Unit test que carga un playbook simple, ejecuta el DAG, verifica el orden de steps y el rollback ante fallo simulado
6. **`soar/requirements.txt`** — httpx, structlog
7. **`soar/README.md`** — Documentación del DAG executor, handlers, playbooks, incident manager

### Tests pendientes para módulos existentes
- [ ] `ndr/test_detector.py` — Test con datos sintéticos de TrafficFlow alimentando el ML detector
- [ ] `deception/test_honeytokens.py` — Test generando JWT/AWS/BD honeytokens y verificando formato
- [ ] `rasp/test_attestation.py` — Test de integración que arranca el server y ejecuta el client flow
- [ ] `tip/test_stix_export.py` — Test creando STIX bundle con indicators, verificando serialización

### Docs pendientes
- [ ] `ndr/README.md` — Documentación de modos de captura, detectores ML, tipos de alerta
- [ ] `deception/README.md` — Documentación de tipos de honeytoken, política de rotación, export STIX
- [ ] `rasp/README.md` — Documentación de checks RASP, cómo correr attestation server, integración Android/iOS
- [ ] `tip/README.md` — Documentación de STIX 2.1 export, TAXII 2.1 pub/sub, MITRE mapping
- [ ] `native/README.md` — Documentación de JNI bridge, instrucciones de build NDK + OLLVM

### Infraestructura pendiente
- [ ] `rasp/Dockerfile` — Imagen Docker para el attestation server (python:3.11-slim, expose 8000)
- [ ] `rasp/docker-compose.yml` — Service definition con env vars
- [ ] `redteam/requirements.txt` (top-level) — Requirements agregando todos los módulos
- [ ] `redteam/run_all_tests.py` — Test runner que ejecuta todos los test_* files

---

## Cómo continuar (instrucciones para el agente)

### 1. Verificar estado actual
```bash
cd /tmp/redteam-remote  # o clonar de nuevo
git pull origin main
```

### 2. Orden recomendado de trabajo
1. **SOAR completo** (dag_executor.py, handlers.py, incident_manager.py, 6 playbooks JSON, test, README) — es lo más grande que falta
2. **Tests faltantes** para NDR, Deception, RASP, TIP
3. **Docs faltantes** para cada módulo
4. **Dockerfile + docker-compose** para RASP attestation server
5. **run_all_tests.py** + **requirements.txt** top-level

### 3. Después de completar, hacer push
```bash
cd /tmp/redteam-remote
git add -A
git config user.name "SourceSeal Security"
git config user.email "security@sourceseal.co"
git commit -m "SOAR: DAG executor + handlers + incident manager + 6 playbooks + tests + docs"
git push origin main
```

### 4. Credenciales de GitHub
El token de GitHub está disponible via el connector (get_connector_token integration_type=github).
El repo es: https://github.com/sourceseal-star/Red-team (branch: main)

---

## Arquitectura general del Red Team Toolkit

```
redteam/
├── xdr/           # ✅ Completo — Correlación + Kill Chain + Attack Surface
├── rasp/          # ✅ Completo — Android + iOS + Attestation server/client
├── ndr/           # ⚠️ Sin tests/docs — Capture + ML detector
├── deception/     # ⚠️ Sin tests/docs — STIX TIP + Honeytoken rotation
├── tip/           # ⚠️ Sin tests/docs — STIX 2.1 + TAXII 2.1
├── native/        # ⚠️ Sin README — JNI bridge C + NDK build
├── soar/          # ❌ INCOMPLETO — Falta DAG executor, handlers, incident manager, playbooks
├── ztna/          # ✅ (original del remote, no modificar)
├── probe/         # ✅ (original del remote)
├── runner/        # ✅ (original del remote)
├── scenarios/     # ✅ (original del remote)
├── honeypot/      # ✅ (original del remote)
├── dashboard/     # ✅ (original del remote)
├── integrity/     # ✅ (original del remote)
├── scripts/       # ✅ (original del remote)
├── docs/          # ✅ (original del remote)
├── agent/         # ✅ (original del remote)
├── api/           # ✅ (original del remote)
├── ci/            # ✅ (original del remote)
├── evidence/      # ✅ (original del remote)
├── reports/       # ✅ (original del remote)
├── tests/         # ✅ (original del remote)
├── tlsproxy/      # ✅ (original del remote)
└── verify_redteam.py  # ✅
```

**Leyenda:** ✅ Completo | ⚠️ Funcional pero falta tests/docs | ❌ Incompleto

---

## Resumen del commit actual (c7b584c)

24 archivos changed, 6010 insertions(+), 5 deletions(-)

Nuevos archivos:
- xdr: kill_chain.py (22KB), attack_surface.py (12KB), test_correlator.py (6KB), README.md, requirements.txt
- rasp: android_rasp.kt (27KB), ios_rasp.swift (13KB), attestation_server.py (16KB), attestation_client.py (9KB), requirements.txt
- ndr: network_capture.py (20KB), ml_detector.py (18KB)
- deception: stix_tip.py (22KB), auto_rotation.py (13KB)
- tip: stix_taxii.py (36KB)
- native: jni_bridge.c (13KB), CMakeLists.txt (3KB), build_android.sh (7KB)
- verify_redteam.py (5KB)
- __init__.py actualizados en xdr, rasp, ndr, deception, tip
