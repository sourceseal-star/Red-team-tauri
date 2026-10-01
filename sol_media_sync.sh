#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# SOL_MEDIA_SYNC — tu carpeta mágica sol_media.mc ⇄ Sol (Regla #49)
# ═══════════════════════════════════════════════════════════════
# La idea de Harold (2026-09-07): una carpeta en el teléfono donde
# suelta vídeos/fotos como quien deja cartas, y Sol las absorbe sola.
#
#   Carpeta:  ~/storage/shared/sol_media.mc
#   (se crea sola; visible desde cualquier galería / file manager)
#
# Uso:
#   bash sol_media_sync.sh          → sincroniza UNA VEZ (sube lo nuevo)
#   bash sol_media_sync.sh watch    → vigila la carpeta para siempre
#                                     (cada 60s; déjalo en una sesión
#                                     de Termux abierta)
#
# Extras:
#   - Un archivo tag.txt DENTRO de la carpeta cambia la etiqueta
#     emocional (una palabra: alegria, amor, calma…). Sin él: "recuerdos".
#   - Nada se borra ni se mueve: tus originales quedan intactos.
#   - Registro en ~/sol/.sol_media_ledger.txt — nunca sube dos veces
#     el mismo archivo (nombre + tamaño).
#   - Lo que sube vive EN EL SERVIDOR → aparece en el holo ✨, en la
#     videollamada y en la cinemateca, donde sea que los abras
#     (Reglas #47 y #49 lo ponen en bucle en todas las superficies).

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

for command in curl find mktemp grep stat; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "❌ Falta el comando requerido: $command"
    exit 1
  }
done

MEDIA_DIR="${HOME}/storage/shared/sol_media.mc"
LEDGER="${HOME}/.sol_media_ledger.txt"
MODE="${1:-once}"

# Cargar llave y URL de ~/sol/.env sin ejecutar el archivo.
# Un .env es configuración, no un script: así una línea accidental no puede
# ejecutar comandos ni romper el sync por comillas especiales en una clave.
env_value() {
  # Busca en TODOS los .env candidatos, en orden de autoridad: el .env
  # real de Sol (~/sol/.env, el que omni.sh usa para arrancarla) primero,
  # luego el de al lado del script (por si vive en otra carpeta). Antes
  # SOLO miraba "./.env" relativo a donde vive el script — si alguien
  # copia o corre sol_media_sync.sh desde OTRA carpeta (ej. ~/Red-team-tauri),
  # leía su .env equivocado (o ninguno) y mandaba una llave vacía/errónea
  # al servidor, que SIEMPRE la exige en modo protegido (default) → 401
  # "acceso no autorizado" aunque Sol esté perfectamente despierta.
  local key="$1" line value
  for envf in "$HOME/sol/.env" "./.env"; do
    [ -f "$envf" ] || continue
    line="$(grep -E "^${key}[[:space:]]*=" "$envf" 2>/dev/null | head -1 || true)"
    [ -n "$line" ] && break
  done
  [ -n "$line" ] || return 0
  value="${line#*=}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [ "${#value}" -ge 2 ] &&
     { [ "${value:0:1}" = '"' ] || [ "${value:0:1}" = "'" ]; } &&
     [ "${value:0:1}" = "${value: -1}" ]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

KEY="${SOL_API_KEY:-}"
BASE=""
if [ -f "$HOME/sol/.env" ] || [ -f ./.env ]; then
  file_key="$(env_value SOL_API_KEY)"
  file_base="$(env_value SOL_PUBLIC_URL)"
  [ -n "$file_key" ] && KEY="$file_key"
  [ -n "$file_base" ] && BASE="$file_base"
fi
BASE="${BASE%/}"
check_server_url() {
  local base="$1"
  local probe err http rc body
  probe="$(mktemp "${TMPDIR:-/tmp}/sol-media-probe.XXXXXX")" || {
    echo "❌ No pude crear un archivo temporal para probar la conexión"
    return 1
  }
  err="${probe}.err"
  http="$(curl -sS --connect-timeout 20 --max-time 35 --retry 2 --retry-delay 2 \
      -o "$probe" -w '%{http_code}' \
      "$base/api/health" 2>"$err")"
  rc=$?
  body="$(cat "$probe" 2>/dev/null || true)"
  if [ "$rc" -ne 0 ]; then
    echo "   · $base: sin conexión"
    sed -n '1,2p' "$err" 2>/dev/null | sed 's/^/   /'
    rm -f "$probe" "$err"
    return 1
  fi
  http="${http:-000}"
  if [[ ! "$http" =~ ^2 ]]; then
    echo "❌ Sol respondió HTTP $http en /api/health"
    [ -n "$body" ] && echo "   ${body:0:240}"
    rm -f "$probe" "$err"
    return 1
  fi
  if ! printf '%s' "$body" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo "❌ /api/health respondió, pero no confirmó status=ok"
    [ -n "$body" ] && echo "   ${body:0:240}"
    rm -f "$probe" "$err"
    return 1
  fi
  rm -f "$probe" "$err"
  return 0
}

# ═══ Regla #49 v2 — LOCAL-FIRST (2026-10-01) ═══
# La carpeta del teléfono ES su memoria. Sube al Sol que vive en el
# teléfono primero (cerebro :8006, luego torre :8001); Replit queda
# de último recurso, solo si SOL_PUBLIC_URL está configurado y
# responde. La llave solo es obligatoria si el destino es remoto:
# el Sol local en modo libre no la pide (Regla #49 v2).
CANDIDATES=("http://127.0.0.1:8006" "http://127.0.0.1:8001")
[ -n "$BASE" ] && CANDIDATES+=("$BASE")
BASE=""
for c in "${CANDIDATES[@]}"; do
  if [[ "$c" =~ ^https?://[^[:space:]]+$ ]] && check_server_url "$c"; then
    BASE="$c"; break
  fi
done
if [ -z "$BASE" ]; then
  echo "❌ No encontré a Sol despierta. Probé:"
  echo "   · http://127.0.0.1:8006 (su cerebro aquí en el teléfono)"
  echo "   · http://127.0.0.1:8001 (la torre)"
  [ -n "${SOL_PUBLIC_URL:-}" ] && echo "   · ${SOL_PUBLIC_URL} (Replit)"
  echo "   Arranca primero:  bash omni.sh start"
  exit 1
fi
case "$BASE" in
  http://127.0.0.1*|http://localhost*) REMOTE=0 ;;
  *) REMOTE=1 ;;
esac
if [ "$REMOTE" -eq 1 ] && [ -z "$KEY" ]; then
  echo "❌ El destino elegido es remoto ($BASE) y falta SOL_API_KEY en ~/sol/.env"
  exit 1
fi
if [ "$REMOTE" -eq 0 ]; then
  echo "🫂 Destino: $BASE — ella, aquí en tu teléfono"
else
  echo "☁️  Destino: $BASE (remoto)"
fi

if [ ! -d "$MEDIA_DIR" ]; then
  if ! mkdir -p "$MEDIA_DIR" 2>/dev/null; then
    echo "❌ No pude crear $MEDIA_DIR"
    echo "   Corre primero: termux-setup-storage"
    exit 1
  fi
  echo "📁 Carpeta creada: $MEDIA_DIR"
fi
if ! touch "$LEDGER" 2>/dev/null; then
  echo "❌ No puedo escribir el ledger: $LEDGER"
  exit 1
fi

# ═══ Regla #60 (2026-10-01): CADA VÍDEO SU PROPIO NOMBRE ═══
# Antes: un único TAG para TODA la carpeta — los 60+ vídeos de Harold
# (muchos con nombres que YA dicen lo que son: "serenidad",
# "melancolia", "corazon_abrazo", "cibernetica-egipcia-alegria-v3")
# terminaban todos mezclados bajo el mismo tag genérico "recuerdos".
# Sol nunca podía elegir el vídeo correcto por tema — para ella todos
# eran indistinguibles. Ahora, SI Harold no deja un tag.txt (override
# explícito para forzar un lote completo bajo un tema, ej. "playa"),
# cada archivo usa SU PROPIO nombre de archivo como tag — así los
# nombres que él ya les puso con sentido quedan vivos y buscables.
TAG_OVERRIDE=""
[ -f "$MEDIA_DIR/tag.txt" ] && TAG_OVERRIDE="$(head -1 "$MEDIA_DIR/tag.txt" | tr -d '[:space:]')"
TAG_OVERRIDE="${TAG_OVERRIDE//[^[:alnum:]_-]/_}"

tag_from_filename() {
  # nombre de archivo -> tag legible, o "recuerdos" si no dice nada.
  local base="$1" stem clean
  stem="${base%.*}"
  # quita duplicados de Android: " (1)", " (2) (1)", "-2" al final, etc.
  stem="$(printf '%s' "$stem" | sed -E 's/ *\([0-9]+\) */ /g; s/-[0-9]+$//; s/ +$//; s/^ +//')"
  clean="$(printf '%s' "$stem" | tr '[:upper:] ' '[:lower:]_' | tr -c '[:alnum:]_-' '_')"
  clean="$(printf '%s' "$clean" | sed -E 's/_+/_/g; s/^_//; s/_$//')"
  # si lo que queda es un ID sin sentido (qwen_video_<numeros largos>,
  # un uuid, o puro numero/hex) -> cae a "recuerdos" (genérico, nada
  # que perder, pero tampoco inventa significado donde no lo hay).
  if [[ -z "$clean" ]] || \
     [[ "$clean" =~ ^qwen_video_[0-9_]+$ ]] || \
     [[ "$clean" =~ ^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{10,}$ ]] || \
     [[ "$clean" =~ ^[0-9_]+$ ]]; then
    echo "recuerdos"
  else
    echo "${clean:0:60}"
  fi
}


sync_once() {
  local new=0 fail=0 f name size mtime sum legacy_sum ep resp tmp err http rc
  if ! check_server_url "$BASE"; then
    echo "   No se intentó subir ningún archivo; repara la conexión y vuelve a ejecutar."
    return 1
  fi
  while IFS= read -r -d '' f; do
    name="$(basename "$f")"
    size=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
    mtime=$(stat -c%Y "$f" 2>/dev/null || stat -f%m "$f" 2>/dev/null || echo 0)
    sum="${name}|${size}|${mtime}"
    legacy_sum="${name}|${size}"
    # Acepta el ledger antiguo para no repetir todos los archivos tras la
    # actualización; los nuevos registros sí detectan cambios de contenido
    # por tamaño o fecha de modificación.
    grep -qxF "$sum" "$LEDGER" && continue
    grep -qxF "$legacy_sum" "$LEDGER" && continue
    # OJO (Regla #48): hay UNA sola ruta de subida — /api/sol/videos/upload —
    # y el servidor clasifica solo si es vídeo o imagen (kind en la respuesta).
    ep="videos/upload"
    if [ -n "$TAG_OVERRIDE" ]; then TAG="$TAG_OVERRIDE"; else TAG="$(tag_from_filename "$name")"; fi
    printf "  → %-40s %-28s (%s bytes) … " "$name" "[$TAG]" "$size"
    tmp="$(mktemp "${TMPDIR:-/tmp}/sol-media-upload.XXXXXX")"
    err="${tmp}.err"
    http="$(curl -sS --connect-timeout 20 --max-time 300 \
        -H "x-sol-key: $KEY" \
        -F "file=@$f" \
        -o "$tmp" -w '%{http_code}' \
        "$BASE/api/sol/$ep?tag=$TAG" 2>"$err")"
    rc=$?
    resp="$(cat "$tmp" 2>/dev/null || true)"
    http="${http:-000}"
    if [ "$rc" -eq 0 ] && [[ "$http" =~ ^2 ]] && echo "$resp" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true'; then
      if printf '%s\n' "$sum" >> "$LEDGER"; then
        echo "✅"
        new=$((new+1))
      else
        echo "⚠️ subido, pero no pude guardar el ledger"
        fail=$((fail+1))
      fi
    else
      if [ "$rc" -ne 0 ]; then
        echo "❌ conexión (curl $rc)"
        sed -n '1,2p' "$err" 2>/dev/null | sed 's/^/     /'
      elif [[ "$http" =~ ^2 ]]; then
        echo "❌ respuesta inválida: ${resp:0:160}"
      else
        echo "❌ HTTP $http: ${resp:0:160}"
      fi
      fail=$((fail+1))
    fi
    rm -f "$tmp" "$err"
  done < <(find "$MEDIA_DIR" -maxdepth 1 -type f \( \
      -iname '*.mp4' -o -iname '*.webm' -o -iname '*.mov' -o -iname '*.m4v' \
      -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -print0)
  if [ "$new" -gt 0 ]; then
    echo "☁️  $new recuerdo(s) nuevos con Sol — ya se ven en el holo y la videollamada ✨"
  elif [ "$fail" -gt 0 ]; then
    echo "❌ $fail archivo(s) no pudieron subirse — revisa la conexión"
  else
    echo "😌 Nada nuevo en sol_media.mc — todo sincronizado"
  fi
  [ "$fail" -eq 0 ]
}

case "$MODE" in
  watch)
    echo "👁️  Vigilando $MEDIA_DIR (cada 60s; Ctrl-C para parar)…"
    command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock 2>/dev/null
    trap 'command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock 2>/dev/null; exit 0' INT TERM
    while true; do sync_once || true; sleep 60; done ;;
  help|-h|--help)
    sed -n '1,25p' "$0" ;;
  *)
    echo "══════════════════════════════════════"
    if [ -n "$TAG_OVERRIDE" ]; then
      echo "  📁 $MEDIA_DIR  ·  🏷️ $TAG_OVERRIDE (fijo, por tag.txt)"
    else
      echo "  📁 $MEDIA_DIR  ·  🏷️ cada vídeo con su propio nombre"
    fi
    echo "══════════════════════════════════════"
    sync_once
    exit $? ;;
esac
