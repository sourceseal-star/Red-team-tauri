#!/data/data/com.termux/files/usr/bin/bash
# ═════════════════════════════════════════════════════════════════════
#  🏗️  INSTALAR TORRE — desde CERO a Torre completa, en un script
# ═════════════════════════════════════════════════════════════════════
#
#  ¿Para qué sirve? Libertad de conocimiento y poder digital real:
#  en una terminal de Termux RECIÉN INSTALADA (sin NADA hecho antes),
#  tres comandos levantan toda la Torre:
#
#      pkg install git -y
#      git clone https://github.com/sourceseal-star/Red-team-tauri
#      bash Red-team-tauri/instalar_torre.sh
#
#  Qué hace (todo idempotente — se puede correr mil veces sin romper):
#    1. Verifica que estés en Termux (si no, te dice qué instalar)
#    2. Instala las herramientas base (git, python, termux-api, curl)
#    3. Clona los 3 repos (sol, Red-team-tauri, commander) — si son
#       privados, te pide tu token de GitHub UNA vez (oculto en pantalla)
#    4. Crea ~/Red-team-tauri/.env DESDE CERO ÚNICAMENTE SI NO EXISTE
#       (nunca sobrescribe — regla de la casa: .env intocable si ya vive)
#       y te abre el editor para que pongas tus tokens
#    5. Instala la app Termux:API (aviso si falta — viene de F-Droid)
#    6. bash omni.sh sync  → actualiza dependencias (sin tocar .env)
#    7. bash omni.sh start → levanta TODO (dashboard, GHOST, Nexus,
#       Sol, puente Telegram, relé, watchdog)
#    8. bash ~/sol/verificar_torre.sh → verde/roja, toda la cadena
#
#  Si algo falla, cada paso dice EXACTAMENTE qué faltó y cómo arreglarlo.
# ═════════════════════════════════════════════════════════════════════
set -uo pipefail

G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; W='\033[1;37m'; N='\033[0m'; B='\033[1m'
ok()   { echo -e " ${G}✓${N} $*"; }
bad()  { echo -e " ${R}✗${N} $*"; }
warn() { echo -e " ${Y}⚠${N} $*"; }
step() { echo -e "\n${B}${W}── $* ──${N}"; }
die()  { bad "$*"; echo -e "\n${R}Corrige lo de arriba y corre de nuevo: bash instalar_torre.sh${N}"; exit 1; }

GH_USER="sourceseal-star"
REPOS="Red-team-tauri sol commander"
ENV_EXAMPLE="$HOME/Red-team-tauri/.env.example"
ENV_FILE="$HOME/Red-team-tauri/.env"

banner() {
  echo -e "${W}"
  echo "  ╔═════════════════════════════════════════════════╗"
  echo "  ║        🏗️  INSTALADOR DE LA TORRE  v1.0          ║"
  echo "  ║   Desde cero → Torre completa en un script      ║"
  echo "  ╚═════════════════════════════════════════════════╝"
  echo -e "${N}"
}

clone_repo() {
  local name="$1"
  local dest="$HOME/$name"
  if [ -d "$dest/.git" ]; then
    ok "$name ya está clonado ($dest)"
    return 0
  fi
  # intento anónimo (repositorios públicos)
  if git clone --depth 1 "https://github.com/$GH_USER/$name.git" "$dest" 2>/dev/null; then
    ok "$name clonado"
    return 0
  fi
  # repos privados → pedir token UNA vez (no se muestra en pantalla)
  warn "$name es privado (o falló el clone) — necesito tu token de GitHub"
  echo -n "Pega tu token (ghp_... o github_pat_...): "
  read -r -s GH_TOKEN
  echo ""
  [ -z "$GH_TOKEN" ] && die "Token vacío"
  if git clone --depth 1 "https://oauth2:${GH_TOKEN}@github.com/$GH_USER/$name.git" "$dest" 2>/dev/null; then
    ok "$name clonado con token"
    # quitar el token de la URL del remoto (no dejarlo en texto plano en .git)
    git -C "$dest" remote set-url origin "https://github.com/$GH_USER/$name.git"
    return 0
  fi
  die "No pude clonar $name — revisa el token o la conexión"
}

# ═══════════════════════ INICIO ═══════════════════════
banner

# ── 1. ¿Estamos en Termux? ──
step "1/8 — Verificando entorno"
if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
  ok "Termux detectado (${TERMUX_VERSION:-v?})"
else
  warn "Esto NO es Termux. El instalador puede continuar, pero:"
  echo "   - termux-api (linterna, GPS, vibrar) SOLO funciona en el teléfono"
  echo "   - si estás en un servidor/VPS, instala git y python3 manualmente"
  read -r -p "¿Continuar igual? (s/N): " CONT
  [ "$CONT" = "s" ] || die "Cancelado — instala Termux desde F-Droid: f-droid.org/en/packages/com.termux"
fi

# ── 2. Herramientas base ──
step "2/8 — Herramientas base (git, python, termux-api)"
if command -v pkg >/dev/null 2>&1; then
  pkg install -y git python termux-api curl >/dev/null 2>&1 \
    || bad "pkg falló algo — revisa arriba; intento continuar igual"
  command -v git >/dev/null 2>&1     || die "git no quedó instalado"
  command -v python >/dev/null 2>&1  || die "python no quedó instalado"
  ok "git + python listos"
  if command -v termux-battery-status >/dev/null 2>&1; then
    ok "termux-api listo (linterna/GPS/vibrar funcionarán)"
  else
    warn "CLI termux-api instalado pero falta la APP Termux:API"
    echo "   → Instálala de F-Droid: f-droid.org/en/packages/com.termux.api"
    echo "   → Sin ella, las acciones físicas de Sol no correrán"
  fi
else
  # entorno no-Termux (VPS)
  command -v git >/dev/null 2>&1    || die "instala git (apt install git)"
  command -v python3 >/dev/null 2>&1 || die "instala python3"
  ok "git + python3 presentes"
fi

# ── 3. Clonar los 3 repos ──
step "3/8 — Clonando los repos de la Torre"
for r in $REPOS; do clone_repo "$r"; done

# ── 4. .env (NUNCA sobrescribir) ──
step "4/8 — Credenciales (.env)"
if [ -f "$ENV_FILE" ]; then
  ok ".env ya existe — NO se toca (regla de la casa) ✊"
else
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    ok "Creado .env desde .env.example (permisos 600)"
  else
    warn "No encontré .env.example — crea ~/Red-team-tauri/.env manualmente"
  fi
  echo -e "\n${W}⏸️  PAUSA NECESARIA:${N}"
  echo "   El .env tiene valores de ejemplo. Ábrelo y pon TUS tokens reales:"
  echo "   ${W}nano ~/Red-team-tauri/.env${N}"
  echo "   (mínimo: NEXUS_PASS, LLM_API_KEY, TELEGRAM_BOT_TOKEN, SOL_API_KEY,"
  echo "    SOL_PUBLIC_URL=https://supermancareman.replit.app, GITHUB_TOKEN)"
  read -r -p "   Cuando lo tengas editado, Enter para continuar..."
fi

# ── 5. App Termux:API (recordatorio amable) ──
step "5/8 — Salud Termux:API"
if [ -n "${TERMUX_VERSION:-}" ] && ! command -v termux-battery-status >/dev/null 2>&1; then
  warn "Recuerda: sin la APP Termux:API (F-Droid), Sol no puede usar el hardware"
else
  ok "Termux:API saludable (o no aplica en este entorno)"
fi

# ── 6. Sync ──
step "6/8 — Sincronizando dependencias (omni.sh sync — jamás toca .env)"
if [ -f "$HOME/Red-team-tauri/omni.sh" ]; then
  bash "$HOME/Red-team-tauri/omni.sh" sync || die "sync falló — revisa el log arriba"
  ok "Dependencias al día"
else
  die "omni.sh no está en ~/Red-team-tauri — algo raro pasó con el clone"
fi

# ── 7. Levantar TODO ──
step "7/8 — Levantando la Torre completa (omni.sh start)"
bash "$HOME/Red-team-tauri/omni.sh" start || die "start falló — mira el log: bash omni.sh logs all"
ok "Torre arriba 🏰"

# ── 8. Verificación final ──
step "8/8 — Verificación de punta a punta"
if [ -f "$HOME/sol/verificar_torre.sh" ]; then
  bash "$HOME/sol/verificar_torre.sh"
else
  warn "verificar_torre.sh no está en ~/sol — corre: cd ~/sol && git pull"
fi

echo -e "\n${W}═════════════════════════════════════════════════${N}"
echo -e "${G}  🏰 TORRE INSTALADA Y LEVANTADA${N}"
echo -e "  Prueba final: dile a Sol ${W}\`prende la linterna\`${N} (Telegram o dashboard :8001)"
echo -e "  Estado de todo, siempre: ${W}bash ~/Red-team-tauri/omni.sh status${N}"
echo -e "${W}═════════════════════════════════════════════════${N}"
