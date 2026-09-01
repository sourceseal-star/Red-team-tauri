#!/data/data/com.termux/files/usr/bin/bash
# Instalación mínima de COMMANDER + dashboard para Termux.
# Uso: bash termux_setup.sh

set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v pkg >/dev/null 2>&1; then
    echo "❌ Este instalador debe ejecutarse dentro de Termux."
    exit 1
fi

echo "📦 Instalando dependencias de Termux..."
pkg update -y
pkg install -y python nmap whois jq sqlite curl openssl git

echo "🐍 Instalando dependencias Python..."
"$PYTHON_BIN" -m pip install -r "$ROOT/requirements.txt"

if command -v termux-setup-storage >/dev/null 2>&1; then
    echo "📁 Solicita acceso al almacenamiento cuando Android lo pida..."
    termux-setup-storage || true
fi

chmod +x "$ROOT"/*.sh "$ROOT"/comlink/*.sh 2>/dev/null || true

echo ""
echo "✅ COMMANDER listo."
echo "   CLI:       cd \"$ROOT\" && python3 commander.py --list"
echo "   Dashboard: BACKEND_API=http://127.0.0.1:8001 bash \"$ROOT/arrancar_commander.sh\""
echo "   Smoke test: bash \"$ROOT/quickstart.sh\" --test-only"
echo ""
echo "⚠️ Ejecuta escaneos solo sobre objetivos autorizados."