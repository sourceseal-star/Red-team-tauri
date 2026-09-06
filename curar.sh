#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  ☀️ CURAR.SH — La cura completa de Sol y la War Room, en UN comando
#  Creado 2026-09-06 para Harold: "siempre falla y no sé por qué"
#
#  Este script NO asume nada. Lo cura TODO por sí solo:
#    1. Sincroniza ambos repos a fuerza (borra corrupción local)
#    2. Protege tus .env (llaves) antes de tocar nada
#    3. Mata procesos viejos que se quedan zombis
#    4. Arranca todo (omni.sh o fallback directo)
#    5. Verifica cada pieza y muestra ✅ o ❌ con el motivo EXACTO
#
#  Si algo sale ❌, copia y pega TODO lo que imprime este script
#  — ahí está el diagnóstico exacto, no más adivinanzas.
# ═══════════════════════════════════════════════════════════════════
HOME_DIR="$HOME"
RT_DIR="$HOME_DIR/Red-team-tauri"
SOL_DIR="$HOME_DIR/sol"
BRANCH="main"
# FIX 2026-09-06: en Termux/Android /tmp NO es escribible ("Permission
# denied" en cascada — así falló para Harold la primera vez). Usamos
# un directorio DENTRO de $HOME, que siempre es escribible.
CURA_TMP="$HOME_DIR/.cache/sol_cura"
mkdir -p "$CURA_TMP" 2>/dev/null || CURA_TMP="$RT_DIR/.cura_tmp" && mkdir -p "$CURA_TMP" 2>/dev/null
if [ ! -w "$CURA_TMP" ]; then
  echo "❌ No encuentro ningún directorio escribible (ni \$HOME/.cache ni el repo)."
  echo "   Corre: echo \$HOME   y dime qué imprime — algo raro pasa con tus permisos."
  exit 1
fi
PASS=0; FAIL=0
ok(){  PASS=$((PASS+1)); echo "✅ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "❌ $1"; echo "   └─ $2"; }

echo "══════════════════════════════════════════════"
echo "  ☀️  CURANDO A SOL — $(date '+%H:%M:%S')"
echo "══════════════════════════════════════════════"

# ── 1. Proteger las llaves antes de todo ──
echo "── [1/5] Protegiendo tus llaves ──"
for f in "$SOL_DIR/.env" "$RT_DIR/.env"; do
  [ -f "$f" ] && cp "$f" "$f.cura.bak" && echo "   💾 respaldo: ${f/$HOME_DIR/~}"
done

# ── 2. Sincronizar a fuerza ambos repos ──
echo "── [2/5] Sincronizando repos (fuerza total) ──"
for d in "$RT_DIR" "$SOL_DIR"; do
  name=$(basename "$d")
  if [ ! -d "$d/.git" ]; then bad "repo $name no existe" "clona: git clone https://github.com/sourceseal-star/$name.git $d"; continue; fi
  cd "$d" || { bad "no pude entrar a $name" "permisos de $d"; continue; }
  if git fetch origin "$BRANCH" 2>"$CURA_TMP/curar_git_err.txt"; then
    git reset --hard "origin/$BRANCH" >/dev/null 2>&1
    ok "$name → $(git log --oneline -1 | head -c 45)"
  else
    bad "git fetch falló en $name" "sin red: $(tail -1 "$CURA_TMP/curar_git_err.txt")"
  fi
done

# ── 3. Matar zombis viejos ──
echo "── [3/5] Matando procesos viejos ──"
pkill -f dashboard_server.py 2>/dev/null && echo "   🧟 dashboard viejo eliminado" || echo "   (no había dashboard corriendo)"
pkill -f sol_api.py         2>/dev/null && echo "   🧟 sol_api viejo eliminado"   || echo "   (no había sol_api corriendo)"
sleep 2

# ── 4. Arrancar todo ──
echo "── [4/5] Encendiendo todo ──"
cd "$RT_DIR" 2>/dev/null || { bad "no encuentro $RT_DIR" "clona el repo primero"; exit 1; }
if [ -f omni.sh ]; then
  bash omni.sh start > "$CURA_TMP/curar_start.log" 2>&1 &
else
  bad "omni.sh no existe" "repo clonado incompleto: borra $RT_DIR y clona de nuevo"
  exit 1
fi

# Esperar a que ambos puertos despierten (máx 75s)
echo "   ⏳ esperando a que despierten (máx 75s)…"
DASH_OK=0; SOL_OK=0
for i in $(seq 1 75); do
  curl -s -m 2 -o /dev/null http://127.0.0.1:8001/ && DASH_OK=1
  curl -s -m 2 -o /dev/null http://127.0.0.1:8006/api/sol/status && SOL_OK=1
  [ $DASH_OK -eq 1 ] && [ $SOL_OK -eq 1 ] && break
  sleep 1
done

# ── 5. Diagnóstico pieza por pieza ──
echo "── [5/5] Diagnóstico ──"
echo ""
echo "━━━ LA WAR ROOM ━━━"
[ $DASH_OK -eq 1 ] && ok "Dashboard :8001 vivo" || bad "Dashboard :8001 NO responde" "log de arranque abajo ⬇"
curl -s -m 5 http://127.0.0.1:8001/ | grep -q "assets/" && ok "War Room cargada" || bad "War Room no sirve HTML" "dist roto — copia esto para Seal"
BUNDLE=$(curl -s -m 5 http://127.0.0.1:8001/ | grep -o 'assets/index-[^"]*\.js' | head -1 | cut -d/ -f2)
[ -n "$BUNDLE" ] && curl -s -m 5 -o /dev/null "http://127.0.0.1:8001/assets/$BUNDLE" && ok "Bundle del frontend sirve" || bad "Bundle no sirve" "dist incompleto"

echo ""
echo "━━━ SOL — SU CUERPO ━━━"
curl -s -m 5 http://127.0.0.1:8001/sol.html | grep -q "Videollamada" && ok "Videollamada /sol.html" || bad "/sol.html caída" "copia esto para Seal"
curl -s -m 5 http://127.0.0.1:8001/holo | grep -q "Portal" && ok "Portal /holo (v6)" || bad "/holo caído" "dashboard_server quedó viejo"
curl -s -m 5 -o /dev/null http://127.0.0.1:8001/sol_avatar_full.png && ok "Su cuerpo completo (frame base)" || bad "Frame base no sirve" "assets sin ruta"
curl -s -m 5 -o /dev/null http://127.0.0.1:8001/sol_avatar_full_talk.png && ok "Frame de habla" || bad "Frame talk no sirve" ""
curl -s -m 5 -o /dev/null http://127.0.0.1:8001/sol_avatar_full_blink.png && ok "Frame de parpadeo" || bad "Frame blink no sirve" ""

echo ""
echo "━━━ SOL — SU CEREBRO Y SU VOZ ━━━"
# FIX 2026-09-06 (v3): la arquitectura real monta el cerebro de Sol
# EN PROCESO dentro del dashboard (:8001, vía sol_router.py) — el
# puerto :8006 (sol_api.py) es solo un fallback LEGACY para extras
# (groq/knowledge/repos/security/sil-advanced), no para pensar ni
# hablar. Antes probábamos /api/sol/chat, /api/sol/voice, /api/sol/state
# — endpoints que NUNCA existieron, así que siempre caían al proxy
# :8006 y reportaban "Ella no responde" aunque su cerebro estuviera
# perfectamente viva en :8001. Los endpoints REALES son:
#   GET  /api/sol/status
#   GET  /api/sol/think?q=...   (o POST {"message":"..."})
#   GET  /api/sol/tts?text=...
ST=$(curl -s -m 8 http://127.0.0.1:8001/api/sol/status)
echo "$ST" | grep -q '"brain"' && ok "Estado: $(echo $ST | head -c 70)" || bad "Estado no responde" "revisa que sol_router se haya montado — mira el log abajo"
CH=$(curl -s -m 25 "http://127.0.0.1:8001/api/sol/think?q=hola%20Sol")
echo "$CH" | grep -q '"response"' && ok "Ella RESPONDE: $(echo $CH | head -c 80)" || bad "Ella no responde al pensar" "mira si '~/sol/sol_core.py' existe y compila: python3 -m py_compile ~/sol/sol_core.py"
curl -s -m 30 -o "$CURA_TMP/curar_voz.mp3" "http://127.0.0.1:8001/api/sol/tts?text=hola%20Harold"
SZ=$(wc -c < "$CURA_TMP/curar_voz.mp3" 2>/dev/null || echo 0)
[ "$SZ" -gt 2000 ] && ok "Su VOZ habla (${SZ}B de audio real)" || bad "Su voz no genera audio" "pip install gtts"
# El puerto :8006 es OPCIONAL (extras) — se informa, nunca bloquea el veredicto
if curl -s -m 3 -o /dev/null http://127.0.0.1:8006/api/sol/status 2>/dev/null; then
  echo "   ℹ️  (extra) sol_api.py :8006 también activo — groq/knowledge/sil-advanced disponibles"
else
  echo "   ℹ️  (extra, opcional) sol_api.py :8006 no está activo — Sol vive igual, solo sin groq/knowledge/sil-advanced"
fi

# ── Veredicto ──
echo ""
echo "══════════════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
  echo "  ☀️☀️☀️  SOL ESTÁ VIVA. TODO VERIFICADO.  ☀️☀️☀️"
  echo ""
  echo "  War Room:  http://localhost:8001"
  echo "  Su portal: http://localhost:8001/sol.html  → botón ✨"
  echo "  Holo:      http://localhost:8001/holo"
else
  echo "  ⚠️  $FAIL pieza(s) fallaron. NO estás a ciegas:"
  echo "  Copia TODO lo de arriba y pégaselo a Seal"
  echo "  — con eso el diagnóstico es exacto."
  echo ""
  echo "  Últimas líneas del arranque:"
  echo "  ─────────────────────────────────"
  tail -15 "$CURA_TMP/curar_start.log" 2>/dev/null | sed 's/^/  /'
  echo "  ─────────────────────────────────"
fi
echo "══════════════════════════════════════════════"
