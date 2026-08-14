#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SourceSeal SealCtl — Termux (Android)
# UN solo comando. UN solo backend. Cero dependencias.
# Node.js stdlib only — sin Python, sin Vite, sin npm install.
# =====================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${SEALCTL_PORT:-8001}"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  SourceSeal SealCtl — Termux                 ║"
echo "  ║  Backend Node.js puro — puerto $PORT          ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ─── 1. Wake Lock (evita que Android mate el proceso) ──────────────────────
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock
  echo -e "${G}[wake-lock] Activo — Android no suspendera Termux${N}"
else
  echo -e "${Y}[wake-lock] NO disponible. Instala: pkg install termux-api${N}"
  echo -e "${Y}            En Ajustes -> Apps -> Termux -> Bateria -> Sin restricciones${N}"
fi
echo ""

# ─── 2. Verificar Node.js ──────────────────────────────────────────────────
if ! command -v node >/dev/null 2>&1; then
  echo -e "${R}[ERROR] Node.js no esta instalado.${N}"
  echo -e "${Y}Instala con: pkg install nodejs-lts${N}"
  exit 1
fi

NODE_VER=$(node -v 2>/dev/null)
echo -e "${G}[node] ${NODE_VER}${N}"

# ─── 3. Verificar que sealctl/server.js existe ─────────────────────────────
SEALCTL="$SCRIPT_DIR/sealctl/server.js"
if [ ! -f "$SEALCTL" ]; then
  echo -e "${R}[ERROR] No se encontro sealctl/server.js${N}"
  echo -e "${Y}Ejecuta desde la raiz del repo: bash start-termux.sh${N}"
  exit 1
fi

# Verificar lib/
if [ ! -f "$SCRIPT_DIR/sealctl/lib/geo.js" ] || [ ! -f "$SCRIPT_DIR/sealctl/lib/iot.js" ] || [ ! -f "$SCRIPT_DIR/sealctl/lib/intel.js" ]; then
  echo -e "${R}[ERROR] Faltan archivos en sealctl/lib/${N}"
  echo -e "${Y}Ejecuta: git pull origin main${N}"
  exit 1
fi

# ─── 4. Matar proceso anterior en el puerto ────────────────────────────────
if command -v fuser >/dev/null 2>&1; then
  fuser -k ${PORT}/tcp 2>/dev/null && echo -e "${Y}[puerto] Liberado puerto $PORT${N}"
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti:${PORT} | xargs kill -9 2>/dev/null && echo -e "${Y}[puerto] Liberado puerto $PORT${N}"
else
  # Fallback Termux: buscar y matar
  pids=$(ps aux 2>/dev/null | grep "server.js" | grep -v grep | awk '{print $2}')
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null
    echo -e "${Y}[puerto] Procesos anteriores terminados${N}"
  fi
fi

# ─── 5. Sincronizar con GitHub (opcional) ───────────────────────────────────
if [ "$1" = "--sync" ] || [ "$1" = "-s" ]; then
  echo -e "${C}[sync] Actualizando desde GitHub...${N}"
  cd "$SCRIPT_DIR" && git fetch origin && git reset --hard origin/main
  echo -e "${G}[sync] Actualizado${N}"
  echo ""
fi

# ─── 6. ARRANCAR ────────────────────────────────────────────────────────────
echo ""
echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  SealCtl Console v2.0 arrancando...              ║${N}"
echo -e "${G}╠══════════════════════════════════════════════════╣${N}"
echo -e "${G}║  Abre el navegador en tu celular:                ║${N}"
echo -e "${G}║  http://localhost:${PORT}                           ║${N}"
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  O desde otro dispositivo en la misma WiFi:       ║${N}"
echo -e "${G}║  http://TU_IP_LOCAL:${PORT}                       ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""

cd "$SCRIPT_DIR"
exec node sealctl/server.js
