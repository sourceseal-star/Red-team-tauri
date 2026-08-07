# Reporte Red Team — 2026-07-31T12:15:57.421375
- **Target**: `build/app.apk`
- **Backend**: `http://localhost:3000`
- **Total hallazgos**: 14 (1 no ejecutados)
- **Severidad** (ejecutados): 🔴 1 críticos · 🟠 0 altos · 🟡 0 medios · 🔵 0 bajos · ⚪ 12 info

## ⚠️ Tests No Ejecutados

Los siguientes ataques **no se ejecutaron** porque el backend no responde:

- **sidechannel**: build/app.apk no existe; saltando side-channel estático.
  - Total no ejecutados: 1

> **Recomendación:** Verifica la configuración de `SOURCESEAL_API` y la conectividad de red antes de tomar acción sobre estos ataques.

## Hallazgos

| Estado | Severidad | Escenario | Título |
|--------|-----------|-----------|--------|
|  | ⚪ INFO | `rng` | ✅ Entropía del sistema OK |
|  | ⚪ INFO | `rng` | ✅ Auditar seeds en el binario |
|  | 🔴 CRITICAL | `pinning` | ❌ Backend no presenta certificado TLS válido |
| ⏭️ SKIPPED | ⚪ INFO | `sidechannel` | ⏭️ Target no accesible para análisis estático |
|  | ⚪ INFO | `keyhandling` | ✅ Target no disponible para análisis |
|  | ⚪ INFO | `payments` | ✅ Target no disponible |
|  | ⚪ INFO | `biometric` | ✅ Target no disponible |
|  | ⚪ INFO | `business_logic` | ✅ Target no disponible |
|  | ⚪ INFO | `imei` | ✅ Target no disponible |
|  | ⚪ INFO | `multiplatform` | ✅ Target no disponible |
| ⚠️ ERROR | ⚪ INFO | `sourcesealcorp` | Escenario sourcesealcorp no se ejecutó |
|  | ⚪ INFO | `recovery_page` | ✅ RECOVERY_PAGE no configurada |
|  | ⚪ INFO | `pegasus` | ✅ Análisis ejecutado en Linux 4.19.0-gvisor |
|  | ⚪ INFO | `pegasus` | ✅ Sin procesos sospechosos |

## Detalle de Hallazgos

### [INFO] Entropía del sistema OK
- **Escenario**: `rng`
- **Estado**: `executed`
- **Descripción**: Shannon entropy = 7.954 bits/byte
- **Evidencia**: `/app/Red-team-tauri/evidence/rng-sample.bin`
- **Remediación**: N/A

### [INFO] Auditar seeds en el binario
- **Escenario**: `rng`
- **Estado**: `executed`
- **Descripción**: Revisar manualmente el binario/app por uso de time/pid como seed. Detectado uso potencial de time.time(); Detectado uso potencial de os.getpid()
- **Evidencia**: `build/app.apk`
- **Remediación**: Usar exclusivamente CSPRNG del SO (SecRandomCopyBytes, getrandom, BCryptGenRandom).

### [CRITICAL] Backend no presenta certificado TLS válido
- **Escenario**: `pinning`
- **Estado**: `executed`
- **Descripción**: [SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1016)
- **Evidencia**: ``
- **Remediación**: Activar HTTPS en producción, configurar HSTS, deshabilitar HTTP plano.

### ⏭️ SKIPPED Target no accesible para análisis estático
- **Escenario**: `sidechannel`
- **Estado**: `skipped`
- **Descripción**: build/app.apk no existe; saltando side-channel estático.
- **Evidencia**: ``
- **Remediación**: Proporcionar APK/IPA o código fuente.

### [INFO] Target no disponible para análisis
- **Escenario**: `keyhandling`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto para análisis.

### [INFO] Target no disponible
- **Escenario**: `payments`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe; saltando análisis de pagos.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto.

### [INFO] Target no disponible
- **Escenario**: `biometric`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe; saltando análisis biométrico.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto.

### [INFO] Target no disponible
- **Escenario**: `business_logic`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto.

### [INFO] Target no disponible
- **Escenario**: `imei`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto.

### [INFO] Target no disponible
- **Escenario**: `multiplatform`
- **Estado**: `executed`
- **Descripción**: build/app.apk no existe.
- **Evidencia**: ``
- **Remediación**: Proporcionar artefacto.

### ⚠️ ERROR Escenario sourcesealcorp no se ejecutó
- **Escenario**: `sourcesealcorp`
- **Estado**: `error`
- **Descripción**: unknown url type: '/v1/regenerate'
- **Evidencia**: ``
- **Remediación**: Revisar dependencias y configuración del runner.

### [INFO] RECOVERY_PAGE no configurada
- **Escenario**: `recovery_page`
- **Estado**: `executed`
- **Descripción**: Configurar la variable de entorno RECOVERY_PAGE para auditar la página de recuperación.
- **Evidencia**: ``
- **Remediación**: Set RECOVERY_PAGE=https://recuperacion.tu-dominio.com

### [INFO] Análisis ejecutado en Linux 4.19.0-gvisor
- **Escenario**: `pegasus`
- **Estado**: `executed`
- **Descripción**: Plataforma: Linux, versión: #1 SMP Sun Jan 10 15:06:54 PST 2016
- **Evidencia**: ``
- **Remediación**: N/A

### [INFO] Sin procesos sospechosos
- **Escenario**: `pegasus`
- **Estado**: `executed`
- **Descripción**: No se detectaron patrones conocidos en la lista de procesos.
- **Evidencia**: ``
- **Remediación**: Mantener monitoreo continuo. Pegasus se esconde; análisis estático no es suficiente.
