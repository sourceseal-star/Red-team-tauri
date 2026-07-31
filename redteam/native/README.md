# Native — JNI Bridge (C Layer)

Capa nativa en C que implementa verificaciones de seguridad a bajo nivel para integración con Android vía JNI. El binario resultante (`libsourceseal_redteam.so`) se carga desde la app Android/iOS y expone funciones de detección anti-tampering, anti-debug y anti-Frida.

---

## Estructura

```
native/
├── jni_bridge.c       # Implementación principal: SHA-256 + ptrace + Frida detection
├── CMakeLists.txt     # Configuración CMake NDK multi-ABI con soporte OLLVM
└── build_android.sh   # Script de build automatizado + verificación post-build
```

---

## Componentes

### SHA-256 Auto-contenido

Implementación completa de SHA-256 escrita desde cero (sin OpenSSL ni dependencias externas). Se usa para:

- Verificación de integridad del binario APK/SO
- Hashing de configuraciones críticas
- Attestation de device fingerprint

**Por qué sin OpenSSL:** Evita dependencias que pueden ser hookeadas o reemplazadas. El código SHA-256 está compilado dentro de la propia librería, dificultando la intercepción.

### Anti-Debug (ptrace)

Usa `ptrace(PTRACE_TRACEME)` para detectar debuggers adjuntos al proceso:

```c
if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
    // Un debugger ya está adjunto — posible análisis dinámico
    return -1;
}
```

Técnica clásica anti-debugging: si otro proceso ya hizo `ptrace` attach, la llamada falla. El debugger (gdb, lldb, Frida) necesita `ptrace` para funcionar.

### Detección de Frida

Detección dual de Frida:

1. **Por puertos:** Frida-server escucha por defecto en el puerto 27042. Se intenta conectar a puertos conocidos de Frida.
2. **Por librerías:** Escanea `/proc/self/maps` buscando nombres de librerías sospechosas (`frida-agent`, `frida-gadget`, `XposedBridge`).

### JNI Bridge

Expone funciones nativas a Java/Kotlin vía JNI con el prefijo `Java_com_sourceseal_redteam_NativeBridge_`. Las funciones exportadas incluyen:

- Verificación de integridad (SHA-256 del binario)
- Detección de Frida/Xposed
- Anti-debug check
- Device attestation hash

---

## Compilación

### Requisitos

- Android NDK r26b o superior
- CMake 3.10+
- (Opcional) OLLVM para ofuscación de código

### Build con Clang estándar (NDK)

```bash
export NDK_HOME=/ruta/a/android-ndk
cd native/
./build_android.sh
```

### Build con OLLVM (Obfuscator-LLVM)

```bash
export NDK_HOME=/ruta/a/android-ndk
export OLLVM_HOME=/ruta/a/obfuscator-llvm/build
cd native/
./build_android.sh
```

OLLVM aplica tres técnicas de ofuscación:

| Bandera | Técnica | Efecto |
|---------|---------|--------|
| `-mllvm -fla` | Control Flow Flattening | Aplana el flujo de control, dificulta análisis estático |
| `-mllvm -sub` | Instruction Substitution | Sustituye instrucciones por equivalentes ofuscadas |
| `-mllvm -bcf` | Bogus Control Flow | Inserta bloques de control falsos |
| `-mllvm -soob` | String Obfuscation | Cifra cadenas en compile-time |

Si OLLVM no está disponible, el build hace fallback automático a Clang estándar del NDK.

---

## ABIs Soportadas

- `arm64-v8a` (ARM 64-bit — dispositivos modernos)
- `x86_64` (emuladores y dispositivos Intel)

El script `build_android.sh` compila ambas arquitecturas y copia las librerías a `../jniLibs/{ABI}/libsourceseal_redteam.so`.

---

## Verificación Post-Build

El script `build_android.sh` ejecuta automáticamente verificaciones post-build para cada ABI:

1. **Stripped check** — Verifica que los símbolos estén eliminados (`file` command)
2. **JNI exports** — Confirma que las funciones `Java_com_sourceseal_redteam_NativeBridge_*` estén presentes (`objdump`/`nm`)
3. **String obfuscation** — Busca strings críticas (`frida`, `XposedBridge`, `anti_debug`) en el binario. Si se compila con OLLVM, no deberían estar en texto claro

---

## CMake — Opciones de Compilación

```cmake
# Símbolos ocultos por defecto (solo JNI exports visibles)
-fvisibility=hidden

# Secciones separadas para permitir garbage collection
-fdata-sections -ffunction-sections

# Linker: eliminar código muerto y strip total
-Wl,--gc-sections -Wl,-strip-all
```

Estas opciones reducen el tamaño del binario y dificultan el análisis con Ghidra/IDA al eliminar la tabla de símbolos.

---

## Integración con RASP

El módulo Native complementa a `rasp/`:

- **RASP (Kotlin/Swift):** Detecta amenazas a nivel Java/Obj-C (root, Xposed, emulador)
- **Native (C/JNI):** Detección a bajo nivel que sobrevive a hooks de Java (Frida puede hookear métodos Java pero no código nativo ofuscado)

Flujo típico:
1. App Android carga `libsourceseal_redteam.so` vía `System.loadLibrary("sourceseal_redteam")`
2. `NativeBridge` llama a funciones C para integrity check + anti-debug
3. Resultado se envía al RASP attestation server para validación HMAC
4. Server responde con token de attestación válido o rechaza el device

---

## Consideraciones de Seguridad

- Las funciones nativas **no son infalibles** — un atacante determinado con hardware JTAG puede eludirlas
- OLLVM retrasa el análisis pero no lo imposibilita
- Combinar con RASP attestation server para defense-in-depth
- Rotar las claves HMAC del attestation server periódicamente
- Considerar Play Integrity API como capa adicional de Google
