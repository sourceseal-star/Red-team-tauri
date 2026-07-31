# Reporte Red Team — 2026-07-22T09:41:26.400646
- **Target**: `evidence/dummy.apk`
- **Backend**: `https://x`
- **Total hallazgos**: 23
- **Severidad**: 🔴 2 críticos · 🟠 10 altos · 🟡 2 medios · 🔵 0 bajos

## Hallazgos

### [INFO] Entropía del sistema OK
- **Escenario**: `rng`
- **Descripción**: Shannon entropy = 7.958 bits/byte
- **Evidencia**: `reports/rng-sample.bin`
- **Remediación**: N/A

### [INFO] Auditar seeds en el binario
- **Escenario**: `rng`
- **Descripción**: Revisar manualmente el binario/app por uso de time/pid como seed. Detectado uso potencial de time.time(); Detectado uso potencial de os.getpid()
- **Evidencia**: `evidence/dummy.apk`
- **Remediación**: Usar exclusivamente CSPRNG del SO (SecRandomCopyBytes, getrandom, BCryptGenRandom).

### [CRITICAL] Backend no presenta certificado TLS válido
- **Escenario**: `pinning`
- **Descripción**: [Errno -2] Name or service not known
- **Evidencia**: ``
- **Remediación**: Activar HTTPS en producción, configurar HSTS, deshabilitar HTTP plano.

### [HIGH] Sin evidencia de pinning en el APK
- **Escenario**: `pinning`
- **Descripción**: No se encontraron marcadores típicos (NetworkSecurityConfig, pin-set, OkHttp CertificatePinner).
- **Evidencia**: `reports/apk-strings.txt`
- **Remediación**: Implementar pinning vía OkHttp CertificatePinner o NSP en res/xml/.

### [INFO] Sin comparación naive evidente
- **Escenario**: `sidechannel`
- **Descripción**: No se detectaron patrones sospechosos en el análisis estático.
- **Evidencia**: `reports/sidechannel-strings.txt`
- **Remediación**: Validar con microbenchmarks (medir tiempo en comparaciones válidas vs inválidas).

### [HIGH] Sin uso detectable de KeyStore/Keychain nativo
- **Escenario**: `keyhandling`
- **Descripción**: No se encontraron marcadores de AndroidKeyStore ni iOS Keychain.
- **Evidencia**: `reports/keyhandling-strings.txt`
- **Remediación**: Migrar claves a KeyStore (Android) o Keychain (iOS) con protección StrongBox/biometric.

### [HIGH] Sin evidencia de verificación de firma en webhooks
- **Escenario**: `payments`
- **Descripción**: No se detectaron constructEvent/verifyWebhookSignature/validateWebhook. Riesgo de webhook spoofing → pagos falsos confirmados.
- **Evidencia**: `reports/payments-strings.txt`
- **Remediación**: Implementar verificación criptográfica de TODOS los webhooks antes de marcar como pagado.

### [MEDIUM] Sin evidencia de validación Luhn de IMEI
- **Escenario**: `imei`
- **Descripción**: No se encontraron marcadores de algoritmo Luhn. Riesgo: aceptar IMEIs malformados.
- **Evidencia**: `reports/imei-strings.txt`
- **Remediación**: Implementar Luhn check antes de aceptar IMEI. Validar también TAC (primeros 8 dígitos) contra base de GSMA.

### [MEDIUM] Sin evidencia de consulta a blacklist (IMEI robado/perdido)
- **Escenario**: `imei`
- **Descripción**: No se detectan referencias a GSMA blacklist. Riesgo: vender celular reportado como robado.
- **Evidencia**: `reports/imei-strings.txt`
- **Remediación**: Integrar API de blacklist (GSMA, Stolen Phone Check, etc.) antes de aceptar IMEI.

### [INFO] Plataforma detectada: Android
- **Escenario**: `multiplatform`
- **Descripción**: Archivo: dummy.apk, extensión: .apk
- **Evidencia**: `evidence/dummy.apk`
- **Remediación**: N/A

### [HIGH] Sin uso del almacén seguro nativo de Android
- **Escenario**: `multiplatform`
- **Descripción**: Esperado alguno de: AndroidKeyStore
- **Evidencia**: `reports/multiplatform-strings.txt`
- **Remediación**: Usar el mecanismo nativo: AndroidKeyStore. Nunca cifrar claves con contraseña hardcodeada.

### [HIGH] Sin uso del CSPRNG nativo de Android
- **Escenario**: `multiplatform`
- **Descripción**: Esperado: SecureRandom|getRandom
- **Evidencia**: `reports/multiplatform-strings.txt`
- **Remediación**: Usar SIEMPRE el CSPRNG del SO. Nunca implementar RNG propio.

### [INFO] Check de servidor backend
- **Escenario**: `multiplatform`
- **Descripción**: Backend actual: https://x. Verificar manualmente que el servidor Ubuntu tenga: ufw activo, fail2ban, TLS 1.2+ only, AppArmor/SELinux, logrotate, backups cifrados.
- **Evidencia**: `https://x`
- **Remediación**: Auditar hardening del servidor con lynis / oscap. Rotar claves SSH. Desactivar login con password.

### [CRITICAL] 5 controles de seguridad de SOURCESEALCORP FALLARON
- **Escenario**: `sourcesealcorp`
- **Descripción**: Ataques que NO pasaron: A1(Reuso de hash anterior), A2(Time-lock bypass), A4(Rate limiting), A5(Validación de firma HMAC), A6(Replay attack)
- **Evidencia**: `reports/sourceseal-attacks.json`
- **Remediación**: Revisar inmediatamente cada control. Detalle por ataque en el JSON.

### [HIGH] [A1] Reuso de hash anterior — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: rechazado (4xx) | Actual: 0
- **Evidencia**: `reports/A1-hash-reuse.json`
- **Remediación**: Corrige el control del ataque A1.

### [HIGH] [A2] Time-lock bypass — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: rechazado con 423/425/409 | Actual: 0
- **Evidencia**: `reports/A2-timelock.json`
- **Remediación**: Corrige el control del ataque A2.

### [HIGH] [A4] Rate limiting — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: 429 tras umbral | Actual: {0: 100}
- **Evidencia**: `reports/A4-ratelimit.json`
- **Remediación**: Corrige el control del ataque A4.

### [HIGH] [A5] Validación de firma HMAC — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: 401 sin firma y firma inválida | Actual: no_sig=0 bad_sig=0
- **Evidencia**: `reports/A5-signature.json`
- **Remediación**: Corrige el control del ataque A5.

### [HIGH] [A6] Replay attack — FALLÓ
- **Escenario**: `sourcesealcorp`
- **Descripción**: Esperado: segundo envío rechazado | Actual: 0 → 0
- **Evidencia**: `reports/A6-replay.json`
- **Remediación**: Corrige el control del ataque A6.

### [INFO] [A10] Blockchain confirm — no evaluado (config faltante)
- **Escenario**: `sourcesealcorp`
- **Descripción**: SOURCESEAL_NODE no configurado
- **Evidencia**: ``
- **Remediación**: Proporcionar SOURCESEAL_KEY/NODE/RECOVERY_PAGE para habilitar.

### [INFO] RECOVERY_PAGE no configurada
- **Escenario**: `recovery_page`
- **Descripción**: Configurar la variable de entorno RECOVERY_PAGE para auditar la página de recuperación.
- **Evidencia**: ``
- **Remediación**: Set RECOVERY_PAGE=https://recuperacion.tu-dominio.com

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
