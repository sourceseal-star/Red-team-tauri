#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# SOURCESEAL — SINCRONIZACIÓN Y ACTUALIZACIÓN COMPLETA
# Ejecuta: bash termux_sync.sh
# ════════════════════════════════════════════════════════════════════
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; W='\033[1;37m'; N='\033[0m'
ok()   { echo -e "  ${G}✅${N} $1"; }
fail() { echo -e "  ${R}❌${N} $1"; }
warn() { echo -e "  ${Y}⚠️${N} $1"; }
info() { echo -e "  ${C}ℹ️${N} $1"; }

echo ""
echo -e "${C}╔══════════════════════════════════════════════╗${N}"
echo -e "${C}║  SOURCESEAL — Sincronización y Actualización  ║${N}"
echo -e "${C}╚══════════════════════════════════════════════╝${N}"
echo ""

# ─── 1. VERIFICAR GIT ─────────────────────────────────────────────────
echo -e "${W}── 1/6 Verificando git...${N}"
if ! command -v git >/dev/null 2>&1; then
    fail "git no instalado. Ejecuta: pkg install git"
    exit 1
fi
ok "git: $(git --version)"

# ─── 2. DETECTAR CAMBIOS LOCALES ─────────────────────────────────────
echo -e "\n${W}── 2/6 Verificando cambios locales...${N}"
LOCAL_CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$LOCAL_CHANGES" -gt 0 ]; then
    warn "Tienes $LOCAL_CHANGES archivos modificados localmente"
    echo ""
    git status --short | head -10
    echo ""
    echo -ne "${Y}¿Stash + actualizar? (s/n): ${N}"
    read -r confirm
    if [ "$confirm" = "s" ] || [ "$confirm" = "S" ]; then
        git stash 2>&1 | head -3
        ok "Cambios guardados en stash"
    else
        warn "Actualización cancelada. Haz commit de tus cambios primero."
        exit 0
    fi
else
    ok "Sin cambios locales — limpio"
fi

# ─── 3. PULL DESDE GITHUB ────────────────────────────────────────────
echo -e "\n${W}── 3/6 Descargando cambios desde GitHub...${N}"
git fetch origin 2>&1 | head -5
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
git pull origin "$CURRENT_BRANCH" 2>&1 | head -15
ok "Repositorio actualizado (branch: $CURRENT_BRANCH)"

# ─── 4. MOSTRAR COMMITS NUEVOS ───────────────────────────────────────
echo -e "\n${W}── 4/6 Commits recientes...${N}"
git log --oneline -10 2>/dev/null | while read -r line; do
    echo "  $line"
done

# ─── 5. ACTUALIZAR DEPENDENCIAS ──────────────────────────────────────
echo -e "\n${W}── 5/6 Actualizando dependencias...${N}"

# Python
echo -e "\n${C}Python:${N}"
if [ -f "$ROOT/requirements.txt" ]; then
    pip install -q -r requirements.txt 2>&1 | tail -3
    ok "requirements.txt instalado"
elif [ -f "$ROOT/redteam/requirements.txt" ]; then
    pip install -q -r redteam/requirements.txt 2>&1 | tail -3
    ok "redteam/requirements.txt instalado"
else
    warn "No se encontró requirements.txt"
fi

# Verificar pycryptodome (reemplazó cryptography)
python3 -c "from Crypto.Cipher import AES" 2>/dev/null && ok "pycryptodome OK" || {
    warn "pycryptodome no instalado — instalando..."
    pip install -q pycryptodome 2>&1 | tail -2
    ok "pycryptodome instalado"
}

# Verificar dependencias críticas (psutil aparte — ver abajo, es opcional y compila C)
for pkg in fastapi uvicorn httpx pydantic aiohttp; do
    python3 -c "import $pkg" 2>/dev/null && ok "$pkg OK" || warn "$pkg falta"
done

# psutil: opcional (el backend arranca sin él). En Termux la wheel puede
# fallar a compilar con clang moderno — se reintenta con CFLAGS de
# compatibilidad, pero nunca bloquea la sincronización.
if python3 -c "import psutil" 2>/dev/null; then
    ok "psutil OK"
else
    warn "psutil falta — intentando instalar..."
    pip install -q psutil 2>/dev/null || {
        pkg install -y clang >/dev/null 2>&1 || true
        CFLAGS="-Wno-error=implicit-function-declaration" pip install -q psutil 2>/dev/null
    }
    python3 -c "import psutil" 2>/dev/null && ok "psutil instalado" || warn "psutil no disponible (no crítico — el dashboard funciona sin métricas de sistema)"
fi

# Node (frontend)
echo -e "\n${C}Node:${N}"
if [ -d "$ROOT/tauri-frontend" ]; then
    if command -v npm >/dev/null 2>&1; then
        cd "$ROOT/tauri-frontend"
        if [ ! -d "node_modules" ]; then
            info "Instalando node_modules..."
            npm install --legacy-peer-deps 2>&1 | tail -5
            ok "node_modules instalado"
        else
            # Verificar si package.json cambió
            npm install --legacy-peer-deps 2>&1 | tail -3
            ok "Dependencias npm verificadas"
        fi
        cd "$ROOT"
    else
        warn "npm no instalado — el frontend no se actualizará"
    fi
else
    warn "tauri-frontend/ no encontrado"
fi

# ─── 6. REBUILD FRONTEND (si hay cambios) ───────────────────────────
echo -e "\n${W}── 6/6 Rebuild frontend...${N}"
if [ -d "$ROOT/tauri-frontend" ] && command -v npm >/dev/null 2>&1; then
    # Verificar si el código fuente cambió
    NEWEST_SRC=$(find "$ROOT/tauri-frontend/src" \( -name "*.tsx" -o -name "*.ts" \) 2>/dev/null | xargs stat -c '%Y %n' 2>/dev/null | sort -rn | head -1 | awk '{print $1}')
    DIST_TS=$(stat -c '%Y' "$ROOT/tauri-frontend/dist/index.html" 2>/dev/null || echo 0)

    if [ -n "$NEWEST_SRC" ] && [ "$NEWEST_SRC" -gt "$DIST_TS" ]; then
        info "Rebuild necesario (código fuente más reciente que dist/)"
        cd "$ROOT/tauri-frontend"
        npm run build 2>&1 | tail -10
        cd "$ROOT"
        if [ -f "$ROOT/tauri-frontend/dist/index.html" ]; then
            ok "Frontend compilado OK"
        else
            fail "Build falló — el backend usará dist anterior si existe"
        fi
    else
        ok "Frontend actualizado — no necesita rebuild"
    fi
else
    warn "No se puede rebuild (falta tauri-frontend o npm)"
fi

# ─── RESTAURAR STASH SI HAY ──────────────────────────────────────────
if git stash list | head -1 | grep -q "stash@{0}" 2>/dev/null; then
    echo -e "\n${W}Restaurando cambios locales...${N}"
    git stash pop 2>&1 | head -5 || warn "Conflicto al restaurar stash — revisa con: git stash list"
fi

# ─── LIMPIEZA DE PUERTOS ─────────────────────────────────────────────
echo -e "\n${W}Liberando puertos en uso...${N}"
for port in 8001 8002 8003 8004 8005 8080; do
    pid=$(lsof -t -i :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        warn "Puerto :$port ocupado por PID $pid — liberando"
        kill "$pid" 2>/dev/null || true
        sleep 0.5
    fi
done
ok "Puertos liberados"

# ─── FINAL ───────────────────────────────────────────────────────────
echo ""
echo -e "${G}╔══════════════════════════════════════════════╗${N}"
echo -e "${G}║  ✅ SINCRONIZACIÓN COMPLETADA                 ║${N}"
echo -e "${G}║                                               ║${N}"
echo -e "${G}║  Ahora ejecuta: bash termux_start.sh          ║${N}"
echo -e "${G}╚══════════════════════════════════════════════╝${N}"
echo ""
