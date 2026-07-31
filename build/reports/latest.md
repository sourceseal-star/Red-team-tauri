# Reporte Red Team — 2026-07-22T13:13:00.045182
- **Target**: `/home/runner/workspace/build/evidence/dummy.apk`
- **Backend**: `https://api.rappi.com.mx/v1`
- **Total hallazgos**: 24
- **Severidad**: 🔴 1 críticos · 🟠 11 altos · 🟡 3 medios · 🔵 0 bajos

## Hallazgos

### [INFO] Entropía del sistema OK
- **Escenario**: `rng`
- **Descripción**: Shannon entropy = 7.949 bits/byte
- **Evidencia**: `/home/runner/workspace/build/reports/rng-sample.bin`
- **Remediación**: N/A

### [INFO] Auditar seeds en el binario
- **Escenario**: `rng`
- **Descripción**: Revisar manualmente el binario/app por uso de time/pid como seed. Detectado uso potencial de time.time(); Detectado uso potencial de os.getpid()
- **Evidencia**: `/home/runner/workspace/build/evidence/dummy.apk`
- **Remediación**: Usar exclusivamente CSPRNG del SO (SecRandomCopyBytes, getrandom, BCryptGenRandom).

### [INFO] Cert TLS del backend capturado
- **Escenario**: `pinning`
- **Descripción**: Host api.rappi.com.mx:443 SHA256=99cb88852a89c29c...
- **Evidencia**: `/home/runner/workspace/build/reports/pinning-cert.json`
- **Remediación**: Comparar SHA256 contra el pin hardcodeado en la app móvil.

### [HIGH] Sin evidencia de pinning en el APK
- **Escenario**: `pinning`
- **Descripción**: No se encontraron marcadores típicos (NetworkSecurityConfig, pin-set, OkHttp CertificatePinner).
- **Evidencia**: `/home/runner/workspace/build/reports/apk-strings.txt`
- **Remediación**: Implementar pinning vía OkHttp CertificatePinner o NSP en res/xml/.

### [INFO] Sin comparación naive evidente
- **Escenario**: `sidechannel`
- **Descripción**: No se detectaron patrones sospechosos en el análisis estático.
- **Evidencia**: `/home/runner/workspace/build/reports/sidechannel-strings.txt`
- **Remediación**: Validar con microbenchmarks (medir tiempo en comparaciones válidas vs inválidas).

### [HIGH] Sin uso detectable de KeyStore/Keychain nativo
- **Escenario**: `keyhandling`
- **Descripción**: No se encontraron marcadores de AndroidKeyStore ni iOS Keychain.
- **Evidencia**: `/home/runner/workspace/build/reports/keyhandling-strings.txt`
- **Remediación**: Migrar claves a KeyStore (Android) o Keychain (iOS) con protección StrongBox/biometric.

### [HIGH] Sin evidencia de verificación de firma en webhooks
- **Escenario**: `payments`
- **Descripción**: No se detectaron constructEvent/verifyWebhookSignature/validateWebhook. Riesgo de webhook spoofing → pagos falsos confirmados.
- **Evidencia**: `/home/runner/workspace/build/reports/payments-strings.txt`
- **Remediación**: Implementar verificación criptográfica de TODOS los webhooks antes de marcar como pagado.

### [MEDIUM] Sin evidencia de validación Luhn de IMEI
- **Escenario**: `imei`
- **Descripción**: No se encontraron marcadores de algoritmo Luhn. Riesgo: aceptar IMEIs malformados.
- **Evidencia**: `/home/runner/workspace/build/reports/imei-strings.txt`
- **Remediación**: Implementar Luhn check antes de aceptar IMEI. Validar también TAC (primeros 8 dígitos) contra base de GSMA.

### [MEDIUM] Sin evidencia de consulta a blacklist (IMEI robado/perdido)
- **Escenario**: `imei`
- **Descripción**: No se detectan referencias a GSMA blacklist. Riesgo: vender celular reportado como robado.
- **Evidencia**: `/home/runner/workspace/build/reports/imei-strings.txt`
- **Remediación**: Integrar API de blacklist (GSMA, Stolen Phone Check, etc.) antes de aceptar IMEI.

### [INFO] Plataforma detectada: Android
- **Escenario**: `multiplatform`
- **Descripción**: Archivo: dummy.apk, extensión: .apk
- **Evidencia**: `/home/runner/workspace/build/evidence/dummy.apk`
- **Remediación**: N/A

### [HIGH] Sin uso del almacén seguro nativo de Android
- **Escenario**: `multiplatform`
- **Descripción**: Esperado alguno de: AndroidKeyStore
- **Evidencia**: `/home/runner/workspace/build/reports/multiplatform-strings.txt`
- **Remediación**: Usar el mecanismo nativo: AndroidKeyStore. Nunca cifrar claves con contraseña hardcodeada.

### [HIGH] Sin uso del CSPRNG nativo de Android
- **Escenario**: `multiplatform`
- **Descripción**: Esperado: SecureRandom|getRandom
- **Evidencia**: `/home/runner/workspace/build/reports/multiplatform-strings.txt`
- **Remediación**: Usar SIEMPRE el CSPRNG del SO. Nunca implementar RNG propio.

### [INFO] Check de servidor backend
- **Escenario**: `multiplatform`
- **Descripción**: Backend actual: https://api.rappi.com.mx/v1. Verificar manualmente que el servidor Ubuntu tenga: ufw activo, fail2ban, TLS 1.2+ only, AppArmor/SELinux, logrotate, backups cifrados.
- **Evidencia**: `https://api.rappi.com.mx/v1`
- **Remediación**: Auditar hardening del servidor con lynis / oscap. Rotar claves SSH. Desactivar login con password.

### [CRITICAL] 5 controles de seguridad de SOURCESEALCORP FALLARON
- **Escenario**: `sourcesealcorp`
- **Descripción**: Ataques que NO pasaron: A1(Reuso de hash anterior), A2(Time-lock bypass), A4(Rate limiting), A5(Validación de firma HMAC), A6(Replay attack)
- **Evidencia**: `/home/runner/workspace/build/reports/sourceseal-attacks.json`
- **Remediación**: Revisar inmediatamente cada control. Detalle por ataque en el JSON.

### [HIGH] [A1] Reuso de hash anterior — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: rechazado (4xx) | Actual: 404
- **Evidencia**: `/home/runner/workspace/build/reports/A1-hash-reuse.json`
- **Remediación**: Corrige el control del ataque A1.

### [HIGH] [A2] Time-lock bypass — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: rechazado con 423/425/409 | Actual: 404
- **Evidencia**: `/home/runner/workspace/build/reports/A2-timelock.json`
- **Remediación**: Corrige el control del ataque A2.

### [HIGH] [A4] Rate limiting — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: 429 tras umbral | Actual: {404: 100}
- **Evidencia**: `/home/runner/workspace/build/reports/A4-ratelimit.json`
- **Remediación**: Corrige el control del ataque A4.

### [HIGH] [A5] Validación de firma HMAC — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: 401 sin firma y firma inválida | Actual: no_sig=404 bad_sig=404
- **Evidencia**: `/home/runner/workspace/build/reports/A5-signature.json`
- **Remediación**: Corrige el control del ataque A5.

### [HIGH] [A6] Replay attack — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: segundo envío rechazado | Actual: 404 → 404
- **Evidencia**: `/home/runner/workspace/build/reports/A6-replay.json`
- **Remediación**: Corrige el control del ataque A6.

### [INFO] [A10] Blockchain confirm — no evaluado (config faltante)
- **Escenario**: `sourcesealcorp`
- **Descripción**: SOURCESEAL_NODE no configurado
- **Evidencia**: ``
- **Remediación**: Proporcionar SOURCESEAL_KEY/NODE/RECOVERY_PAGE para habilitar.

### [HIGH] Headers de seguridad ausentes en página de recuperación
- **Escenario**: `recovery_page`
- **Descripción**: Faltan: x-frame-options, content-security-policy, x-content-type-options, strict-transport-security, referrer-policy
- **Evidencia**: `/home/runner/workspace/build/reports/recovery-health.json`
- **Remediación**: Añadir headers: X-Frame-Options DENY, CSP frame-ancestors 'none', HSTS 1 año, X-Content-Type-Options nosniff.

### [MEDIUM] Vulnerable a clickjacking
- **Escenario**: `recovery_page`
- **Descripción**: Sin X-Frame-Options ni CSP frame-ancestors, la página puede ser embebida en iframes maliciosos.
- **Evidencia**: `/home/runner/workspace/build/reports/recovery-clickjack.json`
- **Remediación**: X-Frame-Options: DENY o CSP: frame-ancestors 'none'.

### [INFO] Análisis ejecutado en Linux 6.18.34
- **Escenario**: `pegasus`
- **Descripción**: Plataforma: Linux, versión: #Replit-Linux SMP Mon Jun  1 15:51:08 UTC 2026
- **Evidencia**: ``
- **Remediación**: N/A

### [INFO] Sin procesos sospechosos
- **Escenario**: `pegasus`
- **Descripción**: No se detectaron patrones conocidos en la lista de procesos.
- **Evidencia**: ``
- **Remediación**: Mantener monitoreo continuo. Pegasus se esconde; análisis estático no es suficiente.
