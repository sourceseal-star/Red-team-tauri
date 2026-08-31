#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# control_claves.sh — Harold es el dueño de las credenciales
#
#   bash control_claves.sh set       Define TUS claves + crea respaldo cifrado
#   bash control_claves.sh status    Verifica sin revelar valores
#   bash control_claves.sh restore   Recupera desde respaldo cifrado
#   bash control_claves.sh rotate    Rota REDTEAM_API_KEY + re-hashes
#
# .env es la única fuente de verdad. Este script es el instrumento del operador.
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
ENV=.env
AUTH_JSON=redteam/scripts/.auth/password.json
BACKUP_DIR="$HOME/.c2"
BACKUP_FILE="$BACKUP_DIR/env_respaldo.aes"

gen_strong() { head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c "${1:-24}"; }

case "${1:-set}" in

set)
  echo "═════════════════════════════════════════════════════════"
  echo "  CONTROL DE CLAVES — Define TUS credenciales"
  echo "═════════════════════════════════════════════════════════"
  echo ""
  echo "  Enter = generar una clave fuerte automáticamente."
  echo ""

  read -rsp "  ADMIN_PASSWORD (dashboard :8001): " AP; echo
  read -rsp "  NEXUS_PASS (nexus :8004): " NP; echo

  [ -z "$AP" ] && AP=$(gen_strong 20)
  [ -z "$NP" ] && NP=$(gen_strong 20)

  # Escribir o actualizar .env sin perder las demás variables
  touch "$ENV"
  # ADMIN_PASSWORD
  if grep -q '^ADMIN_PASSWORD=' "$ENV"; then
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$AP|" "$ENV"
  else
    echo "ADMIN_PASSWORD=$AP" >> "$ENV"
  fi
  # NEXUS_PASS
  if grep -q '^NEXUS_PASS=' "$ENV"; then
    sed -i "s|^NEXUS_PASS=.*|NEXUS_PASS=$NP|" "$ENV"
  else
    echo "NEXUS_PASS=$NP" >> "$ENV"
  fi
  # NEXUS_USER
  grep -q '^NEXUS_USER=' "$ENV" || echo "NEXUS_USER=admin" >> "$ENV"
  # ADMIN_EMAIL
  grep -q '^ADMIN_EMAIL=' "$ENV" || echo "ADMIN_EMAIL=admin@redteam.local" >> "$ENV"
  # REDTEAM_API_KEY — generar si no existe
  if ! grep -q '^REDTEAM_API_KEY=' "$ENV" || grep -q '^REDTEAM_API_KEY=$' "$ENV"; then
    RAK=$(gen_strong 48)
    sed -i "s|^REDTEAM_API_KEY=.*|REDTEAM_API_KEY=$RAK|" "$ENV" 2>/dev/null || \
      echo "REDTEAM_API_KEY=$RAK" >> "$ENV"
  fi

  # Hash viejo fuera — el launcher re-hará el hash desde TU .env
  rm -f "$AUTH_JSON"

  chmod 600 "$ENV"

  echo ""
  echo "  ✅ TUS claves quedaron en .env:"
  echo "     ADMIN_PASSWORD = $AP"
  echo "     NEXUS_PASS     = $NP"
  echo "     NEXUS_USER     = admin"
  echo "     ADMIN_EMAIL    = admin@redteam.local"
  echo "     REDTEAM_API_KEY = (presente en .env)"
  echo ""

  # Respaldo cifrado
  mkdir -p "$BACKUP_DIR"
  read -rsp "  Passphrase para el respaldo cifrado: " PP; echo
  openssl enc -aes-256-cbc -salt -pbkdf2 -in "$ENV" -out "$BACKUP_FILE" -pass pass:"$PP"
  chmod 600 "$BACKUP_FILE"
  echo "  ✅ Respaldo cifrado: $BACKUP_FILE"
  echo "     Solo tú con tu passphrase puedes recuperarlo."
  echo ""
  echo "  Ahora reinicia el stack:"
  echo "    bash replit_start.sh        # Replit"
  echo "    bash iniciar_unificado.sh   # Termux"
  echo ""
  ;;

status)
  echo "═════════════════════════════════════════════════════════"
  echo "  ESTADO DE CREDENCIALES"
  echo "═════════════════════════════════════════════════════════"
  echo ""
  if [ ! -f "$ENV" ]; then
    echo "  ❌ .env no existe en $ROOT"
    exit 1
  fi
  echo "  Archivo .env:"
  grep -E '^(ADMIN_EMAIL|ADMIN_PASSWORD|NEXUS_USER|NEXUS_PASS|REDTEAM_API_KEY)=' "$ENV" \
    | sed -E 's/=(.*)$/= ● presente/' 2>/dev/null || echo "  (vacío o sin claves)"
  echo ""
  echo "  Permisos: $(ls -la "$ENV" | awk '{print $1}')"
  echo "  Hash de password: $([ -f "$AUTH_JSON" ] && echo '✅ existe' || echo '❌ falta — se creará al arrancar')"
  echo "  Respaldo: $([ -f "$BACKUP_FILE" ] && echo "✅ $BACKUP_FILE" || echo '❌ no hay')"
  echo ""
  ;;

restore)
  echo "═════════════════════════════════════════════════════════"
  echo "  RECUPERAR DESDE RESPALDO CIFRADO"
  echo "═════════════════════════════════════════════════════════"
  echo ""
  if [ ! -f "$BACKUP_FILE" ]; then
    echo "  ❌ No hay respaldo en $BACKUP_FILE"
    echo "     Ejecuta 'bash control_claves.sh set' para crear uno."
    exit 1
  fi
  read -rsp "  Passphrase del respaldo: " PP; echo
  TMP=$(mktemp)
  if openssl enc -d -aes-256-cbc -salt -pbkdf2 -in "$BACKUP_FILE" -pass pass:"$PP" -out "$TMP" 2>/dev/null; then
    echo "  ✅ Respaldo descifrado."
    echo ""
    echo "  Claves recuperadas:"
    grep -E '^(ADMIN_PASSWORD|NEXUS_PASS|REDTEAM_API_KEY)=' "$TMP" | sed -E 's/=(.*)/= ● recuperado/'
    echo ""
    read -rp "  ¿Restaurar a .env? (s/N): " CONF
    if [ "$CONF" = "s" ] || [ "$CONF" = "S" ]; then
      cp "$TMP" "$ENV"
      chmod 600 "$ENV"
      rm -f "$AUTH_JSON"
      echo "  ✅ .env restaurado. Hash viejo borrado (se recreará al arrancar)."
      echo "  Reinicia el stack ahora."
    else
      echo "  Cancelado."
    fi
  else
    echo "  ❌ Passphrase incorrecta o archivo corrupto."
    exit 1
  fi
  rm -f "$TMP"
  echo ""
  ;;

rotate)
  echo "═════════════════════════════════════════════════════════"
  echo "  ROTACIÓN DE API KEY"
  echo "═════════════════════════════════════════════════════════"
  NEW_KEY=$(gen_strong 48)
  if grep -q '^REDTEAM_API_KEY=' "$ENV"; then
    sed -i "s|^REDTEAM_API_KEY=.*|REDTEAM_API_KEY=$NEW_KEY|" "$ENV"
  else
    echo "REDTEAM_API_KEY=$NEW_KEY" >> "$ENV"
  fi
  echo "  ✅ REDTEAM_API_KEY rotada en .env (valor no mostrado)."
  echo "  Reinicia el stack para aplicar."
  echo ""
  ;;

*)
  echo "Uso: bash control_claves.sh {set|status|restore|rotate}"
  exit 1
  ;;

esac
