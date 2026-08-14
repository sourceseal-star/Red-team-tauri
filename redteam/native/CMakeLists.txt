# CMakeLists.txt para compilación de jni_bridge.c de SourceSeal Red Team
# Soporta ofuscación mediante OLLVM (Obfuscator-LLVM) con fallback seguro a Clang estándar.

cmake_minimum_required(VERSION 3.10)

# Definir el nombre del proyecto y lenguaje
project(sourceseal_redteam C)

# Forzar estándar C99
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Incluir módulo para comprobación de banderas de compilación
include(CheckCCompilerFlag)

# Definir lista de banderas OLLVM tradicionales
# -mllvm -fla: Control Flow Flattening (Aplanamiento de flujo de control)
# -mllvm -sub: Instruction Substitution (Sustitución de instrucciones)
# -mllvm -bcf: Bogus Control Flow (Inserción de bloques de control falsos)
# -mllvm -soob: String Obfuscation (Ofuscación de cadenas de texto en memoria)
set(OLLVM_TEST_FLAG "-mllvm -fla")
set(OLLVM_OBFUSCATION_FLAGS "")

# Comprobación de si el compilador soporta banderas OLLVM
check_c_compiler_flag(${OLLVM_TEST_FLAG} COMPILER_SUPPORTS_OLLVM)

if(COMPILER_SUPPORTS_OLLVM)
    message(STATUS "[SourceSeal] COMPILADOR OLLVM DETECTADO. Aplicando parámetros avanzados de ofuscación anti-ingeniería inversa.")
    # Agregamos las banderas de ofuscación nativa completas
    set(OLLVM_OBFUSCATION_FLAGS 
        "-mllvm" "-fla"
        "-mllvm" "-sub"
        "-mllvm" "-bcf"
        "-mllvm" "-soob"
    )
else()
    message(STATUS "[SourceSeal] OLLVM no está disponible en este entorno de compilación. Fallback a Clang normal.")
endif()

# Definir el target de biblioteca compartida para Android JNI
add_library(sourceseal_redteam SHARED
    jni_bridge.c
)

# Configurar las opciones de compilación privadas del target
# -fvisibility=hidden: Ocultar símbolos que no sean exportados explícitamente (JNIEXPORT) para evitar inspección estática
target_compile_options(sourceseal_redteam PRIVATE
    ${OLLVM_OBFUSCATION_FLAGS}
    -Wall
    -Wextra
    -Werror
    -fvisibility=hidden
    -fdata-sections
    -ffunction-sections
)

# Configurar opciones de enlazado privadas
# -Wl,--gc-sections: Eliminar código y datos no utilizados durante el enlazado para reducir tamaño y complejidad
# -Wl,-strip-all: Eliminar tabla de símbolos y depuración para dificultar el análisis con herramientas como Ghidra/IDA
target_link_options(sourceseal_redteam PRIVATE
    "-Wl,--gc-sections"
    "-Wl,-strip-all"
)

# Buscar y enlazar biblioteca de logs nativos de Android y utilidades
find_library(log-lib log)
find_library(android-lib android)

target_link_libraries(sourceseal_redteam PRIVATE
    ${log-lib}
    ${android-lib}
)
