#!/bin/bash
# =========================================================================
# SourceSeal Red Team - Android Native Library Build Script
# Compila la biblioteca compartida JNI para ARM64 y x86_64.
# Soporta compilación regular y ofuscación con OLLVM (Obfuscator-LLVM).
# =========================================================================

# Detener el script si ocurre algún error
set -e

# Configuración de colores para salida en terminal
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sin color

echo -e "${BLUE}===============================================================${NC}"
echo -e "${BLUE}          SourceSeal Native Builder - Android JNI NDK          ${NC}"
echo -e "${BLUE}===============================================================${NC}"

# 1. Validación de variables de entorno indispensables
if [ -z "$NDK_HOME" ]; then
    if [ -n "$ANDROID_NDK_HOME" ]; then
        NDK_HOME="$ANDROID_NDK_HOME"
    else
        echo -e "${RED}[ERROR] NDK_HOME no está definido. Por favor expórtalo antes de continuar:${NC}"
        echo -e "        export NDK_HOME=/ruta/a/tu/android-ndk"
        exit 1
    fi
fi
echo -e "${GREEN}[OK] Android NDK_HOME detectado en: $NDK_HOME${NC}"

# Comprobar la existencia del archivo de toolchain de CMake en el NDK
TOOLCHAIN_FILE="$NDK_HOME/build/cmake/android.toolchain.cmake"
if [ ! -f "$TOOLCHAIN_FILE" ]; then
    echo -e "${RED}[ERROR] No se pudo encontrar el archivo toolchain de CMake en: $TOOLCHAIN_FILE${NC}"
    exit 1
fi

# 2. Configurar compilador OLLVM si está definido
CMAKE_COMPILER_FLAGS=""
if [ -n "$OLLVM_HOME" ]; then
    if [ -d "$OLLVM_HOME" ] && [ -f "$OLLVM_HOME/bin/clang" ]; then
        echo -e "${GREEN}[OK] Compilador OLLVM detectado en: $OLLVM_HOME${NC}"
        # Forzar a CMake a usar el clang del directorio OLLVM
        CMAKE_COMPILER_FLAGS="-DCMAKE_C_COMPILER=$OLLVM_HOME/bin/clang -DCMAKE_CXX_COMPILER=$OLLVM_HOME/bin/clang++"
    else
        echo -e "${YELLOW}[ADVERTENCIA] OLLVM_HOME está definido pero no apunta a un directorio válido con bin/clang.${NC}"
        echo -e "${YELLOW}              Se continuará con el compilador Clang estándar provisto por el NDK.${NC}"
    fi
else
    echo -e "${YELLOW}[INFO] OLLVM_HOME no está definido. Se compilará con Clang estándar del NDK.${NC}"
fi

# 3. Definir directorios de salida jniLibs para el proyecto Android
JNI_LIBS_DIR="../jniLibs"
mkdir -p "$JNI_LIBS_DIR/arm64-v8a"
mkdir -p "$JNI_LIBS_DIR/x86_64"

# 4. Función de compilación genérica para ABIs
compile_abi() {
    ABI=$1
    BUILD_DIR="build_$ABI"
    OUT_DIR="$JNI_LIBS_DIR/$ABI"

    echo -e "\n${BLUE}[+] Iniciando compilación para arquitectura: ${YELLOW}$ABI${NC}"
    
    # Crear y entrar al directorio temporal de compilación
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"

    # Ejecutar configuración CMake
    cmake .. \
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_FILE" \
        -DANDROID_ABI="$ABI" \
        -DANDROID_NDK="$NDK_HOME" \
        -DANDROID_PLATFORM=android-21 \
        -DCMAKE_BUILD_TYPE=Release \
        $CMAKE_COMPILER_FLAGS

    # Compilar biblioteca compartida
    make -j$(nproc 2>/dev/null || echo 4)

    # Copiar archivo compilado
    if [ -f "libsourceseal_redteam.so" ]; then
        cp "libsourceseal_redteam.so" "../$OUT_DIR/"
        echo -e "${GREEN}[OK] Compilación exitosa para $ABI. Copiado a $OUT_DIR/libsourceseal_redteam.so${NC}"
    else
        echo -e "${RED}[ERROR] Error al generar libsourceseal_redteam.so para $ABI${NC}"
        exit 1
    fi

    # Regresar al directorio native/
    cd ..
    rm -rf "$BUILD_DIR"
}

# 5. Ejecutar la compilación para ARM64 y x86_64
compile_abi "arm64-v8a"
compile_abi "x86_64"

# 6. Verificación Post-Build mediante herramientas de análisis estático
echo -e "\n${BLUE}===============================================================${NC}"
echo -e "${BLUE}           Fase Post-Build: Verificación y Auditoría           ${NC}"
echo -e "${BLUE}===============================================================${NC}"

verify_library() {
    ABI=$1
    SO_PATH="$JNI_LIBS_DIR/$ABI/libsourceseal_redteam.so"
    
    echo -e "${YELLOW}[*] Inspeccionando $ABI (${SO_PATH}):${NC}"
    
    # A. Comprobar si los símbolos nativos están correctamente eliminados (Stripped)
    if command -v file &> /dev/null; then
        FILE_INFO=$(file "$SO_PATH")
        if [[ "$FILE_INFO" == *"stripped"* ]]; then
            echo -e "   ${GREEN}[OK] Símbolos eliminados (Stripped) correctamente.${NC}"
        else
            echo -e "   ${YELLOW}[WARN] Símbolos no eliminados (Not Stripped). Mayor peso y facilidad de ingeniería inversa.${NC}"
        fi
    else
        echo -e "   [INFO] Comando 'file' no disponible. Omitiendo prueba de stripped."
    fi

    # B. Verificar que las funciones exportadas de JNI están presentes
    if command -v objdump &> /dev/null; then
        echo -e "   ${BLUE}[+] Verificando funciones JNI exportadas con objdump...${NC}"
        # Listar la tabla de símbolos dinámicos
        EXPORTS=$(objdump -T "$SO_PATH" 2>/dev/null || objdump -t "$SO_PATH" 2>/dev/null || echo "")
        if [ -n "$EXPORTS" ]; then
            if echo "$EXPORTS" | grep -q "Java_com_sourceseal_redteam_NativeBridge"; then
                echo -e "   ${GREEN}[OK] Símbolos JNI de SourceSeal encontrados correctamente en la tabla de exportación.${NC}"
            else
                echo -e "   ${RED}[ERROR] No se encontraron los símbolos exportados de NativeBridge. Fallo de enlazado.${NC}"
            fi
        fi
    elif command -v nm &> /dev/null; then
        echo -e "   ${BLUE}[+] Verificando funciones JNI exportadas con nm...${NC}"
        EXPORTS=$(nm -D "$SO_PATH" 2>/dev/null || echo "")
        if echo "$EXPORTS" | grep -q "Java_com_sourceseal_redteam_NativeBridge"; then
             echo -e "   ${GREEN}[OK] Símbolos JNI de SourceSeal encontrados correctamente.${NC}"
        fi
    else
        echo -e "   [INFO] Herramientas de tabla de símbolos (objdump/nm) no disponibles. Omitiendo."
    fi

    # C. Verificar el estado de la ofuscación de strings
    if command -v strings &> /dev/null; then
        echo -e "   ${BLUE}[+] Buscando strings críticas en el binario...${NC}"
        STRINGS_FOUND=$(strings "$SO_PATH" | grep -E "frida|XposedBridge|anti_debug" || true)
        if [ -n "$STRINGS_FOUND" ]; then
            if [ -n "$OLLVM_HOME" ]; then
                echo -e "   ${RED}[WARN] Se encontraron cadenas en texto claro (como frida/anti_debug). La ofuscación de strings OLLVM (-soob) podría haber fallado o no aplicarse correctamente.${NC}"
            else
                echo -e "   ${YELLOW}[INFO] Cadenas críticas visibles (ej. 'frida'). Es normal ya que se compiló sin OLLVM.${NC}"
            fi
        else
            echo -e "   ${GREEN}[OK] No se encontraron strings críticas legibles en texto claro. Ofuscación de strings exitosa.${NC}"
        fi
    else
        echo -e "   [INFO] Comando 'strings' no disponible. Omitiendo."
    fi
}

verify_library "arm64-v8a"
verify_library "x86_64"

echo -e "\n${GREEN}===============================================================${NC}"
echo -e "${GREEN}      Proceso de Compilación y Verificación de SourceSeal OK    ${NC}"
echo -e "${GREEN}===============================================================${NC}"
