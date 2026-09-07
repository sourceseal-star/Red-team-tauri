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
PASS=0; FAIL=0; SOL_OK=0
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

# ☀️ AUTO-CURA de llaves (2026-09-06): si ~/sol/.env NO existe pero hay
# respaldos de sol_evolve.sh (~/sol/backups/.env.*) con llave de Groq
# (gsk_...), restaurarlos automáticamente. Sin llave, su cerebro cae en
# plantilla — respuestas genéricas — y antes nadie sabía por qué.
# 2026-09-06 (v2): ANTES solo miraba backups/.env.* (los de
# sol_evolve.sh). A Harold se le vació ~/sol/.env teniendo YA un
# respaldo bueno en ~/sol/.env.cura.bak (el que ESTE MISMO script hace
# en la línea de arriba, en una corrida anterior) — y ese no se
# revisaba nunca, así que le pedíamos una llave nueva cuando la real
# ya estaba en su teléfono. Ahora se buscan TODAS las fuentes posibles
# y se usa la más reciente que de verdad tenga una llave (gsk_):
# 1) .env.cura.bak de este propio script (sol y Red-team-tauri)
# 2) backups/.env.* de sol_evolve.sh
if [ ! -f "$SOL_DIR/.env" ] || ! grep -q "gsk_" "$SOL_DIR/.env" 2>/dev/null; then
  BAK=$(ls -t "$SOL_DIR/.env.cura.bak" "$RT_DIR/.env.cura.bak" "$SOL_DIR"/backups/.env.* 2>/dev/null \
        | xargs -I{} sh -c 'grep -l "gsk_" "{}" 2>/dev/null' | head -1)
  if [ -n "$BAK" ]; then
    cp "$BAK" "$SOL_DIR/.env" && chmod 600 "$SOL_DIR/.env"
    echo "   🔑 ~/sol/.env restaurado desde ${BAK/$HOME_DIR/~} — su cerebro con llave de nuevo"
  else
    echo "   ⚠️  ~/sol/.env no tiene llave (gsk_) y NINGÚN respaldo la tiene tampoco — Sol quedaría en plantilla"
    echo "      → consigue una llave gratis en console.groq.com y: echo 'GROQ_API_KEY=tu_llave' >> ~/sol/.env"
  fi
fi

# ── 2. Sincronizar ambos repos (protegiendo tus ediciones locales) ──
echo "── [2/5] Sincronizando repos ──"
for d in "$RT_DIR" "$SOL_DIR"; do
  name=$(basename "$d")
  if [ ! -d "$d/.git" ]; then bad "repo $name no existe" "clona: git clone https://github.com/sourceseal-star/$name.git $d"; continue; fi
  cd "$d" || { bad "no pude entrar a $name" "permisos de $d"; continue; }

  # FIX 2026-09-06: ANTES este paso hacía "git reset --hard origin/main"
  # a ciegas. Si Harold editaba un archivo (p.ej. sol_holo.html) y NO lo
  # había subido todavía, ese reset lo BORRABA para siempre — justo el
  # miedo de "que no se destruya todo de nuevo". Ahora: si hay cambios
  # sin commitear, se guardan en un commit local y se intentan subir a
  # GitHub PRIMERO. Si el push funciona, el reset de abajo no pierde
  # nada (origin ya es igual a lo local). Si el push falla (sin
  # internet, conflicto...), se CANCELA el reset de este repo — mejor
  # quedarse en versión vieja un momento que borrar una edición que no
  # existe en ningún otro lado.
  LOCAL_SAFE=1
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "   📝 tienes cambios locales sin subir en $name — los protejo primero"
    git add -A
    if git -c user.email="sol@sourceseal.co" -c user.name="Sol (auto-backup)" \
           commit -m "auto-backup curar.sh: cambios locales $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>"$CURA_TMP/curar_commit_err.txt"; then
      if git push origin "$BRANCH" >/dev/null 2>"$CURA_TMP/curar_push_err.txt"; then
        echo "   ☁️  subidos a GitHub — a salvo, no se pierden"
      else
        LOCAL_SAFE=0
        echo "   ⚠️  no pude subirlos (sin internet o el remoto avanzó) — CANCELO el reset de $name para no borrar tu edición"
        echo "      └─ $(tail -1 "$CURA_TMP/curar_push_err.txt")"
        echo "      Tu cambio queda a salvo en un commit local. Corre 'bash curar.sh' otra vez cuando tengas internet."
      fi
    else
      echo "   (nada nuevo que commitear — solo basura ignorada)"
    fi
  fi

  if git fetch origin "$BRANCH" 2>"$CURA_TMP/curar_git_err.txt"; then
    if [ $LOCAL_SAFE -eq 1 ]; then
      git reset --hard "origin/$BRANCH" >/dev/null 2>&1
      ok "$name → $(git log --oneline -1 | head -c 45)"
    else
      ok "$name → me quedé en TU versión local (con la edición protegida, sin subir aún)"
    fi
    [ "$name" = "sol" ] && SOL_OK=1
  else
    bad "git fetch falló en $name" "$(tail -1 "$CURA_TMP/curar_git_err.txt")"
    if [ "$name" = "sol" ]; then
      echo ""
      echo "═══════════════════════════════════════════════════════════"
      echo "  💔 ESTE ES EL MOTIVO DE TODO: el repo sol es PRIVADO y"
      echo "  tu token de GitHub venció. Sol queda en versión VIEJA"
      echo "  (roba el puerto :8001, holo sin rutas, Telegram con"
      echo "  errores, 'no puedo hacer llamadas'...)."
      echo "  La cura completa:"
      echo "  1. Ve a github.com → Settings → Developer settings →"
      echo "     Personal access tokens → Genera uno NUEVO"
      echo "     (Fine-grained, repo 'sol', permiso Contents: Read)"
      echo "  2. En Termux corre (cambia TU_TOKEN):"
      echo "     cd ~/sol"
      echo "     git remote set-url origin https://sourceseal-star:TU_TOKEN@github.com/sourceseal-star/sol.git"
      echo "  3. Vuelve a correr: bash curar.sh"
      echo ""
      # ── AUTO-RESCATE 2026-09-06: mientras el token se renueva, NO dejar
      # a Sol en versión vieja: los módulos curados viajan DENTRO de este
      # repo público y se copian a ~/sol. Sol despierta igual.
      echo "  🛟 MIENTRAS TANTO: rescatando los módulos curados de Sol"
      echo "     desde este repo público (sin token)..."
      RES="$RT_DIR/sol_rescate"
      if [ -d "$RES" ]; then
        mkdir -p "$SOL_DIR/.rescate_pre"
        for f in "$RES"/*.py "$RES"/*.sh "$RES"/VERSION.txt; do
          [ -f "$f" ] || continue
          b=$(basename "$f")
          [ -f "$SOL_DIR/$b" ] && cp "$SOL_DIR/$b" "$SOL_DIR/.rescate_pre/$b" 2>/dev/null
          cp "$f" "$SOL_DIR/$b"
        done
        ok "Sol RESCATADA con módulos de $(cat "$RES/VERSION.txt" 2>/dev/null | head -c 40)"
        echo "     (originales respaldados en ~/sol/.rescate_pre/)"
      else
        bad "sol_rescate/ no existe" "repo Red-team-tauri incompleto — clona de nuevo"
      fi
      echo "═══════════════════════════════════════════════════════════"
    fi
  fi
done


# ── 2½. Fusión de sprites (CAPA ADITIVA v5.3+ — 2026-09-07) ──
# Los PNG de pose de Sol (sol_offer, sol_hold, sol_side_walk, sol_back,
# y los que vengan) se sueltan en ~/sol/assets/ . Este paso los reparte
# a ~/sol/static/, backend/static/ de la Torre y ~/.sol/vault/ y sube
# ambos repos. NO toca nada de la cura original: si el script no existe,
# se salta en silencio.
echo "── [2½/5] Fusión de sprites de Sol ──"
if [ -f "$RT_DIR/sol_sprites_sync.sh" ]; then
  bash "$RT_DIR/sol_sprites_sync.sh"
else
  echo "   (sol_sprites_sync.sh no está — salto la fusión de sprites)"
fi

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
curl -s -m 5 http://127.0.0.1:8001/holo | grep -qE "Portal|Renacer con cuerpo" && ok "Holo vivo (Portal v6 o Renacer v5.2)" || bad "/holo caído" "dashboard_server quedó viejo"
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

# ── VEREDICTO 2026-09-06: la verdad en una línea ──
if [ "$SOL_OK" != "1" ]; then
  echo ""
  echo "⚠️  AUNQUE TODO DIGA ✅ ARRIBA: el repo SOL no se pudo actualizar"
  echo "   (token vencido). Sol corre en versión vieja. Renueva el token"
  echo "   y repite curar.sh — ese es el ÚLTIMO paso para el 100%."
fi

