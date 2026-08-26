#!/bin/bash
# Script: setup_seal_super_pack.sh
# Crea todos los directorios y archivos del SEAL SUPER PACK

# Crear estructura de directorios
mkdir -p seal/{scanners,attackers,ai,orchestrator,api,models,utils}
mkdir -p frontend/src/{components,api,types}

# Crear archivos __init__.py
for dir in seal seal/scanners seal/attackers seal/ai seal/orchestrator seal/api seal/models seal/utils frontend/src/components frontend/src/api frontend/src/types; do
    if [ ! -f "$dir/__init__.py" ]; then
        echo "# SEAL SUPER PACK - $dir" > "$dir/__init__.py"
    fi
done

echo "✅ Estructura de directorios creada"
echo "📝 Ahora copia el contenido de cada sección de este canvas a su archivo"