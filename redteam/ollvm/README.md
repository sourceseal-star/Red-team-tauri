# Android NDK Obfuscation with OLLVM (Obfuscator-LLVM)

This directory contains the NDK compilation configuration and JNI bridge to implement OLLVM protection for critical mobile app modules.

## What is OLLVM?
**Obfuscator-LLVM (OLLVM)** is a fork of the LLVM compiler suite designed to provide native code security through advanced binary obfuscation techniques. It works directly at the LLVM Intermediate Representation (IR) level, meaning it transforms the code after compilation but before generating target machine instructions.

Using OLLVM protects against reverse engineering (via tools like IDA Pro, Ghidra, and Jadx) by complicating the control flow graph (CFG), flattening function blocks, substituting instructions, and encrypting constant string arrays.

---

## Technical Features & Build Flags

The following OLLVM security transformations are enabled in `CMakeLists.txt` for **Release** builds:

| Flag | Name | Description |
|---|---|---|
| `-mllvm -fla` | **Control Flow Flattening** | Flattens the Basic Blocks of functions. Standard code branching is replaced by a single massive switch statement controlled by a state variable, rendering binary disassembly in decompilers extremely complex to follow. |
| `-mllvm -bcf` | **Bogus Control Flow** | Inserts fake basic blocks containing random computations controlled by opaque predicates (conditions whose values are known at compile time but appear variable to decompilers). This increases code complexity exponentially. |
| `-mllvm -sub` | **Instruction Substitution** | Replaces standard assembly/binary arithmetic operators (like `add`, `sub`, `and`) with equivalent, significantly more complex mathematical expressions. |
| `-mllvm -sobf` | **String Encryption** | Encrypts literal strings within the binary's read-only memory sections. These strings are decrypted dynamically on stack memory at runtime when accessed, and wiped immediately after, preventing static signature extraction. |

---

## Build Environment (Docker Container Setup)

Since OLLVM requires a custom-built Clang/LLVM toolchain, it is best built in a reproducible Docker container.

### 1. Dockerfile for OLLVM Compiler Build
Create a `Dockerfile.ollvm` or use the following script:

```dockerfile
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    git cmake build-essential python3 python3-pip \
    ninja-build wget unzip curl
# Cloned and compiled below

WORKDIR /build
RUN git clone -b llvm-9.0.1 https://github.com/obfuscator-llvm/obfuscator.git

# Compile the OLLVM compiler
RUN mkdir build-ollvm && cd build-ollvm && \
    cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLVM_INCLUDE_TESTS=OFF ../obfuscator && \
    ninja -j$(nproc)
```

Build and run:
```bash
docker build -t ollvm-toolchain -f Dockerfile.ollvm .
```

---

## Integration with Existing Android Projects

### Step 1: Copy Native Files
Copy the `ollvm/` folder into your Android project, typically under `app/src/main/cpp/`.

### Step 2: Configure `build.gradle`
Reference the custom OLLVM toolchain inside your module-level `build.gradle` as specified in our predefined config:

```groovy
android {
    ...
    defaultConfig {
        externalNativeBuild {
            cmake {
                abiFilters 'arm64-v8a', 'armeabi-v7a', 'x86_64'
            }
        }
    }
    
    buildTypes {
        release {
            externalNativeBuild {
                cmake {
                    cFlags "-mllvm -fla -mllvm -bcf -mllvm -sub -mllvm -sobf"
                    cppFlags "-mllvm -fla -mllvm -bcf -mllvm -sub -mllvm -sobf -std=c++17"
                }
            }
        }
    }
    
    externalNativeBuild {
        cmake {
            path "CMakeLists.txt"
        }
    }
    ndkVersion "25.2.9519653"
}
```

---

## Performance Impact & Usage Guidelines

> ⚠️ **Warning:** Obfuscating native binaries incurs a performance and size overhead.
- **Speed Penalty:** Code compiled with `-fla` and `-bcf` runs approximately **2x to 3x slower** due to extra dispatch states and dummy conditions.
- **Binary Size Growth:** Compiled `.so` size can increase by **150% - 300%**.

### Recommended Action Plan:
1. **Never obfuscate performance-critical loops** (like real-time video, audio processing, or low-latency graphics).
2. **Obfuscate only cryptographic, key storage, dynamic integrity checks, and licensing logic.**
3. Use JNI annotations on specific functions as done in `native_bridge.cpp` rather than applying flags globally to the entire library if performance degrades.
4. Keep **Debug builds standard** to preserve rapid compilation speeds during development.

---

## Verifying Obfuscation (Binary Analysis)

You can verify that your compiled shared library (`libollvm_native_bridge.so`) is successfully obfuscated using `objdump` or `readelf` from the NDK toolchain:

### 1. Checking Control Flow Flattening
Run disassembly on `generateKey`:
```bash
$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objdump -d libollvm_native_bridge.so | grep -A 50 "generateKey"
```
* **Unobfuscated:** You will see a linear flow of instructions ending in a standard return.
* **Obfuscated:** You will see an immediate jump to a central dispatcher and countless loop/conditional transitions indicating a flattened state-machine.

### 2. Checking String Encryption
Extract readable strings using the command line:
```bash
strings libollvm_native_bridge.so | grep -E "generateKey|encryptData|verifyIntegrity"
```
Because of the `-sobf` option, string constants like sensitive system paths or custom key tags will **not** appear in the output, demonstrating they are fully encrypted.
