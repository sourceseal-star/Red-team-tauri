#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SourceSeal Console v6.0 — ARRANQUE COMPLETO EN UN SOLO COMANDO
# Instala deps, configura API keys, compila frontend, levanta backend
# Uso:  bash arrancar.sh
#
# El dashboard (dashboard_server.py) es el ÚNICO backend que arranca.
# SEAL y KRAKEN son módulos independientes — ver info al final del script.
# =====================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; M='\033[0;35m'; N='\033[0m'
PORT="${PORT:-8001}"

banner() { echo -e "\n${C}══════════════════════════════════════════════════${N}"; echo -e "${G}  $1${N}"; echo -e "${C}══════════════════════════════════════════════════${N}\n"; }

banner "SourceSeal Console v6.0 — Arranque Completo"

# ─── 1. WAKE LOCK ──────────────────────────────────────────────────────
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock 2>/dev/null && echo -e "${G}[1/8] Wake-lock activo${N}"
else
  echo -e "${Y}[1/8] Instala termux-api: pkg install termux-api${N}"
fi

# ─── 2. GIT PULL ──────────────────────────────────────────────────────
echo -e "${C}[2/8] Sincronizando código...${N}"
git stash 2>/dev/null || true
git pull origin main 2>&1 | tail -2
git stash pop 2>/dev/null || true
echo -e "${G}  OK Código actualizado${N}"

# ─── 3. DEPENDENCIAS SISTEMA ───────────────────────────────────────────
echo -e "${C}[3/8] Verificando dependencias del sistema...${N}"
pkg install -y python nodejs-lts git nmap whois bind-utils openssl-tool jq curl tcpdump iproute2 2>/dev/null | tail -3 || true
# numpy via pkg (NUNCA pip en Termux/aarch64)
if ! python3 -c "import numpy" 2>/dev/null; then
  pkg install -y python-numpy 2>/dev/null || true
fi
echo -e "${G}  OK Sistema listo${N}"

# ─── 4. DEPENDENCIAS PYTHON ──────────────────────────────────────────
echo -e "${C}[4/8] Verificando dependencias Python...${N}"
python3 -c "import fastapi, uvicorn, httpx, pydantic, psutil, aiohttp" 2>/dev/null || {
  pip install -q fastapi uvicorn httpx pydantic psutil aiohttp 2>&1 | tail -3
}
# cryptography — necesario para SEAL tactical engine (reportes cifrados)
python3 -c "import cryptography" 2>/dev/null || {
  pip install -q cryptography 2>&1 | tail -2
}
# qrcode + reportlab — generacion de QR y PDFs
python3 -c "import qrcode, reportlab" 2>/dev/null || {
  pip install -q qrcode reportlab 2>&1 | tail -2
}
echo -e "${G}  OK Python listo${N}"

# ─── 5. .ENV + API KEYS ───────────────────────────────────────────────
echo -e "${C}[5/8] Configurando .env y API keys...${N}"

if [ ! -f "$ROOT/.env" ]; then
  API_KEY=$(openssl rand -hex 24)
  cat > "$ROOT/.env" << EOF
# SourceSeal Console — Configuracion
REDTEAM_API_KEY=${API_KEY}
HOST=0.0.0.0
PORT=${PORT}
ALLOWED_ORIGINS=http://localhost:${PORT},http://127.0.0.1:${PORT}

# === API KEYS OSINT (gratis) ===
# AbuseIPDB: https://www.abuseipdb.com/account/api — gratis, 1000 checks/dia
ABUSEIPDB_KEY=

# Shodan: https://www.shodan.io/dashboard — cuenta gratis
SHODAN_API_KEY=

# Hunter.io (emails): https://hunter.io/api-keys — opcional
HUNTER_API_KEY=
EOF
  chmod 600 "$ROOT/.env"
  echo -e "${G}  .env creado. API Key local: ${API_KEY:0:8}...${N}"
else
  echo -e "${G}  .env ya existe (preservado)${N}"
fi

# Verificar si las API keys estan configuradas
source "$ROOT/.env" 2>/dev/null || true
if [ -z "$ABUSEIPDB_KEY" ]; then
  echo -e "${Y}  ⚠ ABUSEIPDB_KEY no configurada${N}"
  echo -e "${Y}    Obtén gratis: https://www.abuseipdb.com/account/api${N}"
  echo -e "${Y}    Luego: echo 'ABUSEIPDB_KEY=tu-key' >> $ROOT/.env${N}"
else
  echo -e "${G}  ✓ AbuseIPDB configurado${N}"
fi
if [ -z "$SHODAN_API_KEY" ]; then
  echo -e "${Y}  ⚠ SHODAN_API_KEY no configurada${N}"
  echo -e "${Y}    Obtén gratis: https://www.shodan.io/dashboard${N}"
  echo -e "${Y}    Luego: echo 'SHODAN_API_KEY=tu-key' >> $ROOT/.env${N}"
else
  echo -e "${G}  ✓ Shodan configurado${N}"
fi
if [ -z "$HUNTER_API_KEY" ]; then
  echo -e "${Y}  ⚠ HUNTER_API_KEY no configurada (opcional, emails OSINT)${N}"
  echo -e "${Y}    Obtén: https://hunter.io/api-keys${N}"
  echo -e "${Y}    Luego: echo 'HUNTER_API_KEY=tu-key' >> $ROOT/.env${N}"
else
  echo -e "${G}  ✓ Hunter.io configurado${N}"
fi

# ─── 6. FRONTEND ──────────────────────────────────────────────────────
echo -e "${C}[6/8] Compilando frontend...${N}"
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
  npm install --legacy-peer-deps 2>&1 | tail -3
fi
npm run build 2>&1 | tail -5
# CRITICO: el backend sirve estaticamente desde redteam/scripts/dist/
# Si no se copia el build, sirve el dist viejo del repo
echo -e "${C}  Copiando build a redteam/scripts/dist/...${N}"
if [ -d "$ROOT/redteam/scripts/dist" ]; then
  find "$ROOT/redteam/scripts/dist" -mindepth 1 -delete 2>/dev/null
fi
cp -r "$ROOT/tauri-frontend/dist/." "$ROOT/redteam/scripts/dist/"
cd "$ROOT"
echo -e "${G}  OK Frontend compilado y copiado${N}"

# ─── 7. ARRANCAR BACKEND ──────────────────────────────────────────────
echo -e "${C}[7/8] Arrancando backend...${N}"

# FIX CRITICO: "pkill + sleep 1" no garantizaba que el proceso viejo
# soltara el puerto a tiempo. Si el nuevo proceso arrancaba con el puerto
# aun ocupado (o el kernel hace SO_REUSEPORT), quedaban DOS backends vivos
# respondiendo en el mismo puerto 8001 -> el navegador le pegaba a veces
# al viejo (roto/con token distinto) y a veces al nuevo -> 401 random,
# "Archivos" vacios, "Servicios no cargan", etc. Ahora se mata con -9,
# se espera activamente a que el puerto quede libre (hasta 10s), y si
# sigue ocupado se aborta en vez de arrancar un segundo proceso fantasma.
echo -e "${C}  Deteniendo procesos anteriores...${N}"
pkill -9 -f "dashboard_server.py" 2>/dev/null || true

for i in $(seq 1 10); do
  if command -v fuser >/dev/null 2>&1; then
    PORT_BUSY=$(fuser "${PORT}/tcp" 2>/dev/null || true)
  else
    PORT_BUSY=$(python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.3)
try:
    s.connect(('127.0.0.1', ${PORT}))
    print('busy')
except Exception:
    pass
finally:
    s.close()
" 2>/dev/null)
  fi
  if [ -z "$PORT_BUSY" ]; then
    break
  fi
  echo -e "${Y}  Puerto ${PORT} aun ocupado, esperando... (${i}/10)${N}"
  pkill -9 -f "dashboard_server.py" 2>/dev/null || true
  sleep 1
done

if [ -n "$PORT_BUSY" ]; then
  echo -e "${R}  ERROR: el puerto ${PORT} sigue ocupado por otro proceso y no se pudo liberar.${N}"
  echo -e "${R}  Cierra Termux por completo (quitalo de apps recientes) y vuelve a correr este script.${N}"
  exit 1
fi
echo -e "${G}  OK Puerto ${PORT} libre${N}"

IP_LOCAL=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || echo "TU_IP")

echo ""
echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  ✅ SOURCESEAL CONSOLE v6.0 LISTO                 ║${N}"
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  Navegador:  http://localhost:${PORT}             ║${N}"
echo -e "${G}║  WiFi:       http://${IP_LOCAL}:${PORT}            ║${N}"
echo -e "${G}║                                                  ║${N}"
echo -e "${G}║  Ctrl+C para detener                              ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""
echo -e "${C}Endpoints principales:${N}"
echo -e "  ${G}Health:${N}           curl localhost:${PORT}/api/health"
echo -e "  ${G}ARTO status:${N}      curl localhost:${PORT}/api/arto/status"
echo -e "  ${G}ARTO iniciar:${N}     curl -X POST localhost:${PORT}/api/arto/start"
echo -e "  ${G}OSINT WHOIS:${N}      curl -H 'Authorization: Bearer TOKEN' localhost:${PORT}/api/osint/whois/dominio.com"
echo -e "  ${G}Geo IP:${N}           curl -H 'Authorization: Bearer TOKEN' 'localhost:${PORT}/api/geo?ip=8.8.8.8'"
echo ""

cd "$ROOT/redteam/scripts"
export $(grep -v '^#' "$ROOT/.env" | xargs)
python3 dashboard_server.py &

# ─── 8. INFO MÓDULOS OPCIONALES ───────────────────────────────────────
echo -e "${C}[8/8] Módulos independientes disponibles:${N}"
echo ""
echo -e "${M}  ┌─ 🔱 SEAL SUPER PACK v2.1 ────────────────────────────┐${N}"
echo -e "${M}  │ Escaneo de red, cámaras IP, explotación Hikvision    │${N}"
echo -e "${M}  │                                                      │${N}"
echo -e "${M}  │   python3 seal/scanners/network_sweep_ultimate.py \\  │${N}"
echo -e "${M}  │     --network 192.168.0.0/24                         │${N}"
echo -e "${M}  │                                                      │${N}"
echo -e "${M}  │   python3 -m seal.core.tactical_engine \\             │${N}"
echo -e "${M}  │     --network 192.168.0.0/24                         │${N}"
echo -e "${M}  │                                                      │${N}"
echo -e "${M}  │   python3 seal/attackers/hikvision_killer.py \\       │${N}"
echo -e "${M}  │     192.168.0.7 --brute                              │${N}"
echo -e "${M}  │                                                      │${N}"
echo -e "${M}  │   Guía: seal/docs/README.md                          │${N}"
echo -e "${M}  └──────────────────────────────────────────────────────┘${N}"
echo ""
echo -e "${B}  ┌─ 🐙 KRAKEN v3.0 ──────────────────────────────────────┐${N}"
echo -e "${B}  │ Motor de explotación autónomo (SSH, SMB, etc.)       │${N}"
echo -e "${B}  │                                                      │${N}"
echo -e "${B}  │   cd kraken && bash termux_install.sh                │${N}"
echo -e "${B}  │   python3 -m kraken.cli.commands --help              │${N}"
echo -e "${B}  │                                                      │${N}"
echo -e "${B}  │   Guía: kraken/docs/README.md                        │${N}"
echo -e "${B}  └──────────────────────────────────────────────────────┘${N}"
echo ""

echo -e "${C}  ╔══════════════════════════════════════════════════════╗${N}"
echo -e "${C}  ║  🦑 LEVIATHAN v3.0 — Módulos de Red Team             ║${N}"
echo -e "${C}  ╠══════════════════════════════════════════════════════╣${N}"
echo -e "${C}  │  22 módulos: scanners, exploiters, AI, reporters    │${N}"
echo -e "${C}  │  API: /api/leviathan/* (router opcional)              │${N}"
echo -e "${C}  │                                                      │${N}"
echo -e "${C}  │  Activar en dashboard_server.py:                     │${N}"
echo -e "${C}  │    from leviathan_core.api.leviathan_router import   │${N}"
echo -e "${C}  │        router as leviathan_router                    │${N}"
echo -e "${C}  │    app.include_router(leviathan_router)              │${N}"
echo -e "${C}  │                                                      │${N}"
echo -e "${C}  │  Frontend: cd leviathan-frontend && npm run dev      │${N}"
echo -e "${C}  │  Guía: leviathan_core/README.md                      │${N}"
echo -e "${C}  ╚══════════════════════════════════════════════════════╝${N}"
echo ""
echo -e "${Y}  ℹ️  Estos módulos NO se ejecutan automáticamente.${N}"
echo -e "${Y}     El dashboard (:${PORT}) es el único proceso activo.${N}"
echo ""

# Mantener el script vivo mientras el backend corre
wait
