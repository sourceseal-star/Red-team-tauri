# OLLVM Build Guide — Ofuscación C/C++ NDK

Guía para compilar funciones críticas y constantes en bibliotecas nativas
usando Obfuscator-LLVM con aplanamiento del flujo de control y cifrado de cadenas.

## Requisitos

```bash
# En Termux (Android):
pkg install clang cmake ninja python git

# En Linux/macOS (para cross-compilación):
# Descargar Android NDK r26b
wget https://dl.google.com/android/repository/android-ndk-r26b-linux.zip
unzip android-ndk-r26b-linux.zip
export NDK_HOME=$(pwd)/android-ndk-r26b

# Clonar OLLVM (fork mantenido)
git clone https://github.com/bluesadi/obfuscator-llvm.git
cd obfuscator-llvm
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD="ARM;AArch64;X86" ..
make -j$(nproc)
export OLLVM_HOME=$(pwd)
```

## Estructura de Bibliotecas Nativas

```
native/
├── CMakeLists.txt
├── crypto_bridge.c      # Funciones criptográficas ofuscadas
├── attestation.c        # Validación de integridad del binario
├── anti_hook.c          # Detección de Frida/Xposed a nivel nativo
├── string_encrypt.c    # Cifrado de cadenas en compile-time
└── jni_bridge.c         # JNI bridge para Android
```

## CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.10)
project(sourceseal_native)

# Compilar con OLLVM
set(CMAKE_C_COMPILER ${OLLVM_HOME}/bin/clang)
set(CMAKE_CXX_COMPILER ${OLLVM_HOME}/bin/clang++)

# Flags de ofuscación
set(OLLVM_FLAGS
    -mllvm -fla                     # Control Flow Flattening
    -mllvm -sub                     # Instruction Substitution
    -mllvm -bcf                     # Bogus Control Flow
    -mllvm -bcf_loop=3              # 3 loops de bogus control flow
    -mllvm -split                   # Basic Block Splitting
    -mllvm -split_num=3             # 3 splits por bloque
)

# Cifrado de strings
set(STRING_ENCRYPT_FLAGS
    -mllvm -sobf                    # String Obfuscation
)

# Target: ARM64 (Android moderno)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -target aarch64-linux-android30 ${OLLVM_FLAGS} ${STRING_ENCRYPT_FLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -target aarch64-linux-android30 ${OLLVM_FLAGS} ${STRING_ENCRYPT_FLAGS}")

# Shared library para JNI
add_library(sourceseal_native SHARED
    crypto_bridge.c
    attestation.c
    anti_hook.c
    string_encrypt.c
    jni_bridge.c
)

# Linkear contra log de Android
target_link_libraries(sourceseal_native log)
```

## native/crypto_bridge.c — Funciones criptográficas ofuscadas

```c
#include <string.h>
#include <openssl/sha.h>
#include <openssl/aes.h>

// Esta función se compilará con control flow flattening + string encryption
// Nadie podrá leer las constantes ni el flujo en el binario resultante
__attribute__((annotate("fla,sub,bcf,sobf")))
int sourceseal_verify_key(const unsigned char *key, int key_len) {
    // Constante ofuscada — en el binario será irreconocible
    const unsigned char expected_hash[32] = {
        0x53, 0x6f, 0x75, 0x72, 0x63, 0x65, 0x53, 0x65,
        0x61, 0x6c, 0x50, 0x72, 0x6f, 0x74, 0x6f, 0x63,
        0x6f, 0x6c, 0x56, 0x32, 0x31, 0x44, 0x31, 0x32,
        0x38, 0x42, 0x42, 0x30, 0x44, 0x38, 0x37, 0x30,
    };

    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(key, key_len, hash);

    return CRYPTO_memcmp(hash, expected_hash, 32) == 0;
}
```

## native/anti_hook.c — Detección nativa de Frida

```c
#include <dlfcn.h>
#include <sys/ptrace.h>
#include <unistd.h>
#include <android/log.h>

// Detecta Frida verificando /proc/self/maps por bibliotecas inyectadas
__attribute__((annotate("fla,sobf")))
int sourceseal_detect_frida_native(void) {
    FILE *fp = fopen("/proc/self/maps", "r");
    if (!fp) return 0;

    char line[512];
    const char *suspicious[] = {
        "frida-agent", "frida-gadget", "libfrida",
        "gum-js-loop", "gmain", "linjector",
        NULL
    };

    while (fgets(line, sizeof(line), fp)) {
        for (int i = 0; suspicious[i]; i++) {
            if (strstr(line, suspicious[i])) {
                fclose(fp);
                __android_log_print(ANDROID_LOG_ERROR,
                    "SourceSeal", "Frida detected: %s", suspicious[i]);
                return 1;
            }
        }
    }
    fclose(fp);
    return 0;
}

// Anti-debug: ptrace self-attach
__attribute__((annotate("fla")))
int sourceseal_anti_debug(void) {
    if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
        // Ya hay un debugger attached
        return 1;
    }
    ptrace(PTRACE_DETACH, 0, 1, 0);
    return 0;
}
```

## native/jni_bridge.c — Bridge para Android

```c
#include <jni.h>
#include "anti_hook.c"
#include "crypto_bridge.c"

JNIEXPORT jint JNICALL
Java_com_sourceseal_security_NativeBridge_detectFrida(JNIEnv *env, jobject thiz) {
    return sourceseal_detect_frida_native();
}

JNIEXPORT jint JNICALL
Java_com_sourceseal_security_NativeBridge_antiDebug(JNIEnv *env, jobject thiz) {
    return sourceseal_anti_debug();
}

JNIEXPORT jboolean JNICALL
Java_com_sourceseal_security_NativeBridge_verifyKey(
    JNIEnv *env, jobject thiz, jbyteArray key) {
    jsize len = (*env)->GetArrayLength(env, key);
    jbyte *data = (*env)->GetByteArrayElements(env, key, NULL);
    int result = sourceseal_verify_key((unsigned char *)data, len);
    (*env)->ReleaseByteArrayElements(env, key, data, JNI_ABORT);
    return result ? JNI_TRUE : JNI_FALSE;
}
```

## Compilar para Android

```bash
# Usando OLLVM + NDK toolchain
mkdir build-android && cd build-android
cmake .. \
    -DCMAKE_TOOLCHAIN_FILE=$NDK_HOME/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-30 \
    -DCMAKE_C_COMPILER=$OLLVM_HOME/bin/clang \
    -DCMAKE_C_FLAGS="-mllvm -fla -mllvm -sub -mllvm -bcf -mllvm -sobf"

make -j$(nproc)

# Resultado: libsourceseal_native.so
# Copiar a: app/src/main/jniLibs/arm64-v8a/libsourceseal_native.so
```

## Verificar Ofuscación

```bash
# Desensamblar y verificar que el flujo está aplanado
$NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objdump \
    -d libsourceseal_native.so | head -100

# Strings no deben revelar constantes
strings libsourceseal_native.so | grep -i "source"
# No debe imprimir nada si string encryption funcionó
```

## Integrar con la App Android

```kotlin
// NativeBridge.kt
object NativeBridge {
    init {
        System.loadLibrary("sourceseal_native")
    }

    external fun detectFrida(): Int
    external fun antiDebug(): Int
    external fun verifyKey(key: ByteArray): Boolean

    fun runSecurityChecks(): Boolean {
        if (detectFrida() == 1) return false
        if (antiDebug() == 1) return false
        // verifyKey se llama con la clave del Keystore
        return true
    }
}
```
