# CMakeLists.txt for OLLVM Native Obfuscated Build
cmake_minimum_required(VERSION 3.22.1)

project("ollvm_native_bridge" VERSION 1.0.0 LANGUAGES CXX C)

# Force C++17 standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configure OLLVM obfuscation flags for Release builds
string(TOUPPER "${CMAKE_BUILD_TYPE}" UPPER_BUILD_TYPE)

set(OLLVM_COMPILER_FLAGS "")

if(UPPER_BUILD_TYPE STREQUAL "RELEASE")
    message(STATUS "[OLLVM] Release build detected. Applying full security obfuscation suite.")
    
    # -mllvm -fla : Control Flow Flattening (obscures basic blocks control-flow graph)
    # -mllvm -bcf : Bogus Control Flow (inserts dummy/junk code blocks and opaque predicates)
    # -mllvm -sub : Instruction Substitution (replaces simple arithmetic with complex equivalents)
    # -mllvm -sobf: String Encryption (obfuscates string literals in read-only data sections)
    set(OLLVM_COMPILER_FLAGS
        "-mllvm -fla"
        "-mllvm -bcf"
        "-mllvm -sub"
        "-mllvm -sobf"
    )
else()
    message(STATUS "[OLLVM] Debug build detected. Skipping obfuscation for maximum compiler efficiency.")
endif()

# Join compilation flags with spaces
string(REPLACE ";" " " OLLVM_FLAGS_JOINED "${OLLVM_COMPILER_FLAGS}")

# Append flags to global C/C++ compiler environments
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OLLVM_FLAGS_JOINED}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OLLVM_FLAGS_JOINED}")

# Look up essential NDK libraries
find_library(log-lib log)
find_library(android-lib android)

# Define the shared library target
add_library(ollvm_native_bridge SHARED
    native_bridge.cpp
)

# Specify target-level link libraries
target_link_libraries(ollvm_native_bridge
    ${log-lib}
    ${android-lib}
)
