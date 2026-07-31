#include <jni.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <android/log.h>

#define LOG_TAG "SourceSeal_Native"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

/* ========================================================================= */
/* IMPL DE SHA-256 NATIVO (Auto-contenido, para verificación de integridad)   */
/* ========================================================================= */

#define ROTRIGHT(word,bits) (((word) >> (bits)) | ((word) << (32-(bits))))
#define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

typedef struct {
    uint8_t data[64];
    uint32_t datalen;
    uint64_t bitlen;
    uint32_t state[8];
} SHA256_CTX;

static const uint32_t k[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static void sha256_transform(SHA256_CTX *ctx, const uint8_t data[]) {
    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];

    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
    for ( ; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];

    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];

    for (i = 0; i < 64; ++i) {
        t1 = h + EP1(e) + CH(e, f, g) + k[i] + m[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void sha256_init(SHA256_CTX *ctx) {
    ctx->datalen = 0;
    ctx->bitlen = 0;
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
}

static void sha256_update(SHA256_CTX *ctx, const uint8_t data[], size_t len) {
    uint32_t i;

    for (i = 0; i < len; ++i) {
        ctx->data[ctx->datalen] = data[i];
        ctx->datalen++;
        if (ctx->datalen == 64) {
            sha256_transform(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

static void sha256_final(SHA256_CTX *ctx, uint8_t hash[]) {
    uint32_t i;

    i = ctx->datalen;

    if (ctx->datalen < 56) {
        ctx->data[i++] = 0x80;
        while (i < 56)
            ctx->data[i++] = 0x00;
    } else {
        ctx->data[i++] = 0x80;
        while (i < 64)
            ctx->data[i++] = 0x00;
        sha256_transform(ctx, ctx->data);
        memset(ctx->data, 0, 56);
    }

    ctx->bitlen += ctx->datalen * 8;
    ctx->data[56] = ctx->bitlen >> 56;
    ctx->data[57] = ctx->bitlen >> 48;
    ctx->data[58] = ctx->bitlen >> 40;
    ctx->data[59] = ctx->bitlen >> 32;
    ctx->data[60] = ctx->bitlen >> 24;
    ctx->data[61] = ctx->bitlen >> 16;
    ctx->data[62] = ctx->bitlen >> 8;
    ctx->data[63] = ctx->bitlen;
    sha256_transform(ctx, ctx->data);

    for (i = 0; i < 4; ++i) {
        hash[i]      = (ctx->state[0] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 4]  = (ctx->state[1] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 8]  = (ctx->state[2] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 12] = (ctx->state[3] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 16] = (ctx->state[4] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 20] = (ctx->state[5] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 24] = (ctx->state[6] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 28] = (ctx->state[7] >> (24 - i * 8)) & 0x000000ff;
    }
}

/* ========================================================================= */
/* FUNCIONES DE DETECCIÓN DE AMENAZAS                                        */
/* ========================================================================= */

/**
 * 1. fuenteseal_detect_frida_native:
 * Analiza el mapa de memoria de este proceso en búsqueda de firmas o hilos de Frida.
 */
jboolean sourceseal_detect_frida_native() {
    FILE* fp = fopen("/proc/self/maps", "r");
    if (!fp) {
        return JNI_FALSE;
    }

    char line[512];
    jboolean detected = JNI_FALSE;

    while (fgets(line, sizeof(line), fp)) {
        // Buscar cadenas comunes que indican inyección de hilos o binarios Frida
        if (strstr(line, "frida") != NULL ||
            strstr(line, "gum-js") != NULL ||
            strstr(line, "libfrida") != NULL ||
            strstr(line, "frida-server") != NULL ||
            strstr(line, "re.frida.server") != NULL) {
            detected = JNI_TRUE;
            LOGE("[SourceSeal] Frida detectado en mapas de memoria: %s", line);
            break;
        }
    }
    fclose(fp);
    return detected;
}

/**
 * 2. sourceseal_detect_xposed_native:
 * Busca indicios de Xposed Framework en el disco y mediante llamadas a JNI.
 */
jboolean sourceseal_detect_xposed_native(JNIEnv* env) {
    // A. Comprobar existencia física del binario puente de Xposed
    const char* xposed_paths[] = {
        "/system/framework/XposedBridge.jar",
        "/data/data/de.robv.android.xposed.installer",
        "/data/clat/xposed",
        "/system/bin/app_process_xposed"
    };

    for (int i = 0; i < 4; i++) {
        if (access(xposed_paths[i], F_OK) == 0) {
            LOGE("[SourceSeal] Archivo de Xposed encontrado en ruta: %s", xposed_paths[i]);
            return JNI_TRUE;
        }
    }

    // B. Comprobación por ClassLoader JNI de la clase central de Xposed
    // FindClass lanza una excepción si no encuentra la clase, debemos manejarla y limpiarla.
    jclass xposed_class = (*env)->FindClass(env, "de/robv/android/xposed/XposedBridge");
    if (xposed_class != NULL) {
        (*env)->DeleteLocalRef(env, xposed_class);
        LOGE("[SourceSeal] Clase de XposedBridge detectada en el runtime de Java.");
        return JNI_TRUE;
    }

    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionClear(env); // Limpiar NoClassDefFoundError de la JVM
    }

    return JNI_FALSE;
}

/**
 * 3. sourceseal_anti_debug:
 * Bloquea la conexión de depuradores a nivel de proceso del sistema operativo.
 */
void sourceseal_anti_debug() {
    // PTRACE_TRACEME le indica al kernel que este proceso ya está siendo rastreado.
    // Si un debugger nativo (gdb, lldb) intenta acoplarse, fallará inmediatamente.
    // Si el proceso ya estaba bajo control de un debugger antes de llamar a esta función,
    // ptrace retornará un código de error menor a 0.
    if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
        LOGE("[SourceSeal] Depurador Nativo Detectado mediante ptrace! Abortando proceso de forma inmediata.");
        // Auto-terminar el proceso para evitar depuración
        exit(1);
    }
    LOGI("[SourceSeal] Protección Anti-depuración ptrace aplicada con éxito.");
}

/**
 * 4. sourceseal_verify_integrity:
 * Abre el paquete APK especificado y retorna su hash SHA-256 en hexadecimal.
 */
jstring sourceseal_verify_integrity(JNIEnv* env, const char* apk_path) {
    FILE* file = fopen(apk_path, "rb");
    if (!file) {
        LOGE("[SourceSeal] No se pudo abrir el archivo para verificación de integridad: %s", apk_path);
        return (*env)->NewStringUTF(env, "ERROR_OPENING_FILE");
    }

    SHA256_CTX ctx;
    sha256_init(&ctx);

    uint8_t buffer[8192];
    size_t bytes_read;
    while ((bytes_read = fread(buffer, 1, sizeof(buffer), file)) > 0) {
        sha256_update(&ctx, buffer, bytes_read);
    }
    fclose(file);

    uint8_t hash[32];
    sha256_final(&ctx, hash);

    char hex_hash[65];
    for (int i = 0; i < 32; i++) {
        sprintf(&hex_hash[i * 2], "%02x", hash[i]);
    }
    hex_hash[64] = '\0';

    LOGI("[SourceSeal] Integridad verificada. Hash calculado: %s", hex_hash);
    return (*env)->NewStringUTF(env, hex_hash);
}

/**
 * 5. sourceseal_detect_emulator_native:
 * Comprueba si el binario se está ejecutando sobre emuladores mediante marcas de build y pipes QEMU.
 */
jboolean sourceseal_detect_emulator_native() {
    // A. Comprobar tuberías de comunicación y archivos de hardware virtual
    const char* emu_paths[] = {
        "/dev/socket/qemud",
        "/dev/qemu_pipe",
        "/system/bin/qemu-props",
        "/system/lib/libc_malloc_debug_qemu.so",
        "/sys/qemu_trace",
        "/system/lib/libgoogle_hotword_internal.so"
    };

    for (int i = 0; i < 6; i++) {
        if (access(emu_paths[i], F_OK) == 0) {
            LOGE("[SourceSeal] Archivo o interfaz de emulador encontrada: %s", emu_paths[i]);
            return JNI_TRUE;
        }
    }

    // B. Leer parámetros del sistema en build.prop
    FILE* fp = fopen("/system/build.prop", "r");
    if (fp) {
        char line[512];
        jboolean detected = JNI_FALSE;
        while (fgets(line, sizeof(line), fp)) {
            // Convertir la línea a minúsculas para un control case-insensitive
            for (int i = 0; line[i]; i++) {
                if (line[i] >= 'A' && line[i] <= 'Z') {
                    line[i] = line[i] + 32;
                }
            }
            if (strstr(line, "goldfish") != NULL ||
                strstr(line, "ranchu") != NULL ||
                strstr(line, "qemu") != NULL ||
                strstr(line, "sdk_gphone") != NULL ||
                strstr(line, "vbox") != NULL ||
                strstr(line, "nox") != NULL ||
                strstr(line, "andy") != NULL ||
                strstr(line, "genymotion") != NULL ||
                strstr(line, "google_sdk") != NULL) {
                detected = JNI_TRUE;
                LOGE("[SourceSeal] Cadena de emulador detectada en build.prop: %s", line);
                break;
            }
        }
        fclose(fp);
        if (detected) {
            return JNI_TRUE;
        }
    }

    return JNI_FALSE;
}

/* ========================================================================= */
/* IMPLEMENTACIÓN DE EXPORTS JNI (Mapeo a la clase com.sourceseal.redteam.NativeBridge) */
/* ========================================================================= */

JNIEXPORT jboolean JNICALL
Java_com_sourceseal_redteam_NativeBridge_detectFrida(JNIEnv* env, jobject obj) {
    (void)env;
    (void)obj;
    return sourceseal_detect_frida_native();
}

JNIEXPORT jboolean JNICALL
Java_com_sourceseal_redteam_NativeBridge_detectXposed(JNIEnv* env, jobject obj) {
    (void)obj;
    return sourceseal_detect_xposed_native(env);
}

JNIEXPORT void JNICALL
Java_com_sourceseal_redteam_NativeBridge_antiDebug(JNIEnv* env, jobject obj) {
    (void)env;
    (void)obj;
    sourceseal_anti_debug();
}

JNIEXPORT jstring JNICALL
Java_com_sourceseal_redteam_NativeBridge_verifyIntegrity(JNIEnv* env, jobject obj, jstring apk_path_obj) {
    (void)obj;
    if (apk_path_obj == NULL) {
        return (*env)->NewStringUTF(env, "ERROR_NULL_PATH");
    }

    const char* apk_path = (*env)->GetStringUTFChars(env, apk_path_obj, NULL);
    if (apk_path == NULL) {
        return (*env)->NewStringUTF(env, "ERROR_OUT_OF_MEMORY");
    }

    jstring hash_result = sourceseal_verify_integrity(env, apk_path);

    (*env)->ReleaseStringUTFChars(env, apk_path_obj, apk_path);
    return hash_result;
}

JNIEXPORT jboolean JNICALL
Java_com_sourceseal_redteam_NativeBridge_detectEmulator(JNIEnv* env, jobject obj) {
    (void)env;
    (void)obj;
    return sourceseal_detect_emulator_native();
}
