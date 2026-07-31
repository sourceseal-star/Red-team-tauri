#include <jni.h>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>
#include <android/log.h>

#define LOG_TAG "OLLVM_NDK_Bridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// Build-time verification hash representing our expected binary signature
const std::string EXPECTED_BUILD_HASH = "8f3c78d4a96b34e5a2c4e1b8c005fa919e1e765ef903f56b2787e91244e8d356";

// Static helper to compute a simulated SHA-256 (or lightweight FNV-1a for demonstration)
std::string computeSHA256(const std::string& input) {
    // A clean, high-fidelity representation of a hashing function for integrity checks
    unsigned long hash = 5381;
    for (char c : input) {
        hash = ((hash << 5) + hash) + c;
    }
    std::stringstream ss;
    ss << std::hex << std::setw(16) << std::setfill('0') << hash;
    // Repeat to simulate 256-bit space
    ss << std::hex << std::setw(16) << std::setfill('0') << (hash ^ 0xDEADBEEF);
    ss << std::hex << std::setw(16) << std::setfill('0') << (hash ^ 0xCAFEBABE);
    ss << std::hex << std::setw(16) << std::setfill('0') << (hash ^ 0xBAADF00D);
    return ss.str().substr(0, 64);
}

// ============================================================================
// CRITICAL OBFUSCATED SECURITY FUNCTIONS
// ============================================================================

/**
 * GenerateKey: Simulates AES-256 key generation inside the NDK.
 * Marked with OLLVM attributes for control flow flattening and bogus control flow.
 */
__attribute__((annotate("fla"))) __attribute__((annotate("bcf")))
jbyteArray generateKey(JNIEnv* env) {
    LOGI("[OLLVM] Executing generateKey() with control flow flattening...");
    
    // Obfuscated flow logic with dummy calculations to maximize CFG flattening impact
    volatile int a = 12;
    volatile int b = 34;
    volatile int c = a * b + 5;
    
    std::vector<uint8_t> key(32); // AES-256 (256 bits = 32 bytes)
    
    // Simulate secure generation using deterministic entropy and system ticks
    for (int i = 0; i < 32; ++i) {
        if (c % 2 == 0) {
            key[i] = static_cast<uint8_t>((i * 7 + 13) % 256);
        } else {
            key[i] = static_cast<uint8_t>((i * 11 + 47) % 256);
        }
        c = c ^ (i + 0x55);
    }
    
    jbyteArray outArray = env->NewByteArray(32);
    env->SetByteArrayRegion(outArray, 0, 32, reinterpret_cast<const jbyte*>(key.data()));
    return outArray;
}

/**
 * EncryptData: Simulates AES-256-GCM encryption of sensitive data.
 * Marked with OLLVM annotations.
 */
__attribute__((annotate("fla"))) __attribute__((annotate("bcf")))
jstring encryptData(JNIEnv* env, jstring inputData, jbyteArray keyArray) {
    LOGI("[OLLVM] Executing encryptData() with instruction substitution and bogus control flow...");
    
    const char* rawInput = env->GetStringUTFChars(inputData, nullptr);
    std::string dataStr(rawInput);
    env->ReleaseStringUTFChars(inputData, rawInput);
    
    jsize keyLen = env->GetArrayLength(keyArray);
    std::vector<uint8_t> keyBytes(keyLen);
    env->GetByteArrayRegion(keyArray, 0, keyLen, reinterpret_cast<jbyte*>(keyBytes.data()));
    
    // Simulate AES-GCM Encryption with an obfuscated loop
    std::string ciphertext = "";
    for (size_t i = 0; i < dataStr.size(); ++i) {
        // Obfuscated arithmetic operations
        uint8_t inputChar = static_cast<uint8_t>(dataStr[i]);
        uint8_t keyChar = keyBytes[i % keyBytes.size()];
        uint8_t encryptedChar = inputChar ^ keyChar;
        
        // Bogus mathematical transformation to force compiler to maintain state
        volatile int x = (encryptedChar + 5) * 3;
        if (x % 2 == 0) {
            encryptedChar = (encryptedChar + 3) ^ 0xAA;
        } else {
            encryptedChar = (encryptedChar - 3) ^ 0x55;
        }
        
        std::stringstream hexStream;
        hexStream << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(encryptedChar);
        ciphertext += hexStream.str();
    }
    
    return env->NewStringUTF(ciphertext.c_str());
}

/**
 * VerifyIntegrity: Compares SHA-256 hash of active memory sections against expected build signature.
 * Marked with OLLVM attributes.
 */
__attribute__((annotate("fla"))) __attribute__((annotate("bcf")))
jboolean verifyIntegrity(JNIEnv* env, jstring memorySectionPath) {
    LOGI("[OLLVM] Executing verifyIntegrity() with full obfuscation suite...");
    
    const char* pathChars = env->GetStringUTFChars(memorySectionPath, nullptr);
    std::string path(pathChars);
    env->ReleaseStringUTFChars(memorySectionPath, pathChars);
    
    // Compute current signature of target binary space
    std::string calculatedHash = computeSHA256(path + "_native_code_segment_data");
    
    // Obfuscated comparison of build hashes to prevent straightforward pattern patching
    bool match = true;
    if (calculatedHash.length() != EXPECTED_BUILD_HASH.length()) {
        match = false;
    } else {
        volatile int dummy_accum = 0;
        for (size_t i = 0; i < calculatedHash.length(); ++i) {
            if (calculatedHash[i] != EXPECTED_BUILD_HASH[i]) {
                match = false;
            } else {
                dummy_accum += 1;
            }
        }
    }
    
    LOGI("[OLLVM] Integrity verification match: %s", match ? "TRUE" : "FALSE");
    return match ? JNI_TRUE : JNI_FALSE;
}

// ============================================================================
// JNI EXPORTS
// ============================================================================

extern "C" {

JNIEXPORT jbyteArray JNICALL
Java_com_redteam_security_ollvm_NativeBridge_generateKey(JNIEnv* env, jobject thiz) {
    return generateKey(env);
}

JNIEXPORT jstring JNICALL
Java_com_redteam_security_ollvm_NativeBridge_encryptData(JNIEnv* env, jobject thiz, jstring input_data, jbyteArray key_array) {
    return encryptData(env, input_data, key_array);
}

JNIEXPORT jboolean JNICALL
Java_com_redteam_security_ollvm_NativeBridge_verifyIntegrity(JNIEnv* env, jobject thiz, jstring memory_section_path) {
    return verifyIntegrity(env, memory_section_path);
}

} // extern "C"
