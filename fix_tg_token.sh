#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# fix_tg_token.sh — Arregla el token de Telegram en .env
# Uso: bash fix_tg_token.sh
# No toca nada más del .env. Solo TELEGRAM_BOT_TOKEN.
# ════════════════════════════════════════════════════════════════════

RT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$RT/.env"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; W='\033[1;37m'; N='\033[0m'

echo ""
echo -e "${C}═══════════════════════════════════════════════════════${N}"
echo -e "${W}  🔧 Fix Telegram Token${N}"
echo -e "${C}═══════════════════════════════════════════════════════${N}"
echo ""

# 1. ¿Existe .env?
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${R}❌ No existe .env en $ENV_FILE${N}"
    echo -e "${Y}   ¿Lo borraste o nunca lo creaste?${N}"
    echo -e "   Copia el ejemplo: cp $RT/.env.example $ENV_FILE"
    echo ""
    echo -e "${W}   O pegalo ahora. Escribe el token de Telegram:${N}"
    read -r NEW_TOKEN
    if [ -z "$NEW_TOKEN" ]; then
        echo -e "${R}   No ingresaste nada. Chau.${N}"
        exit 1
    fi
    # Crear .env mínimo
    echo "TELEGRAM_BOT_TOKEN=$NEW_TOKEN" > "$ENV_FILE"
    echo -e "${G}✅ .env creado con TELEGRAM_BOT_TOKEN${N}"
else
    echo -e "${G}✅ .env encontrado (${#} bytes)${N}"

    # 2. ¿Tiene TELEGRAM_BOT_TOKEN?
    TG_LINE=$(grep "^TELEGRAM_BOT_TOKEN" "$ENV_FILE" 2>/dev/null)
    if [ -z "$TG_LINE" ]; then
        echo -e "${R}❌ TELEGRAM_BOT_TOKEN no existe en .env${N}"
        echo -e "${Y}   Pegalo ahora (el token que te dio @BotFather):${N}"
        read -r NEW_TOKEN
        if [ -z "$NEW_TOKEN" ]; then
            echo -e "${R}   No ingresaste nada. Chau.${N}"
            exit 1
        fi
        # Agregar al final del .env
        echo "TELEGRAM_BOT_TOKEN=$NEW_TOKEN" >> "$ENV_FILE"
        echo -e "${G}✅ Token agregado al final de .env${N}"
    else
        # 3. Mostrar lo que hay (enmascarado)
        # Extraer el valor después del = sin comillas
        CURRENT=$(echo "$TG_LINE" | sed 's/^TELEGRAM_BOT_TOKEN=//' | tr -d "\"'" | tr -d '[:space:]')
        echo -e "${Y}   Línea actual:${N} TELEGRAM_BOT_TOKEN=${CURRENT:0:10}...(${#CURRENT} chars)"
        echo ""

        # 4. Probar el token actual
        echo -e "${C}   Probando token actual con Telegram...${N}"
        RESP=$(curl -s -m 8 "https://api.telegram.org/bot${CURRENT}/getMe" 2>/dev/null)
        if echo "$RESP" | grep -q '"ok":true'; then
            BOT_NAME=$(echo "$RESP" | python3 -c "import sys,json; print('@'+json.load(sys.stdin)['result']['username'])" 2>/dev/null)
            echo -e "${G}   ✅ Token válido! Bot: $BOT_NAME${N}"
            echo ""
            echo -e "${G}   Todo bien. Solo falta arrancar:${N}"
            echo -e "   ${W}bash omni.sh stop && bash omni.sh start${N}"
            exit 0
        else
            echo -e "${R}   ❌ Token inválido:${N}"
            echo "   $RESP" | head -c 200
            echo ""
            echo ""
            echo -e "${Y}   Pegá el token NUEVO (de @BotFather /mybots o /newbot):${N}"
            read -r NEW_TOKEN
            if [ -z "$NEW_TOKEN" ]; then
                echo -e "${R}   No ingresaste nada. Chau.${N}"
                exit 1
            fi
            # Limpiar el token (quitar comillas y espacios)
            NEW_TOKEN=$(echo "$NEW_TOKEN" | tr -d "\"'" | tr -d '[:space:]')

            # Reemplazar la línea en .env
            sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$NEW_TOKEN|" "$ENV_FILE"
            echo -e "${G}✅ Token reemplazado en .env (sin comillas, sin espacios)${N}"
        fi
    fi
fi

# 5. Verificar que el resto del .env quedó intacto
echo ""
echo -e "${C}Verificando que el resto de .env está intacto...${N}"
OTHER_VARS=$(grep -cE "^[A-Za-z_][A-Za-z0-9_]*=" "$ENV_FILE")
echo -e "   Variables en .env: $OTHER_VARS"

# 6. Probar el token nuevo
echo ""
echo -e "${C}Probando token nuevo con Telegram...${N}"
# Leer el token limpio del .env
FINAL_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN" "$ENV_FILE" | sed 's/^TELEGRAM_BOT_TOKEN=//' | tr -d "\"'" | tr -d '[:space:]')
echo -e "   Token: ${FINAL_TOKEN:0:15}...(${#FINAL_TOKEN} chars)"

RESP=$(curl -s -m 8 "https://api.telegram.org/bot${FINAL_TOKEN}/getMe" 2>/dev/null)
if echo "$RESP" | grep -q '"ok":true'; then
    BOT_NAME=$(echo "$RESP" | python3 -c "import sys,json; print('@'+json.load(sys.stdin)['result']['username'])" 2>/dev/null)
    BOT_FIRST=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['first_name'])" 2>/dev/null)
    echo -e "${G}✅✅✅ TOKEN VÁLIDO ${N}"
    echo -e "${G}   Bot: $BOT_NAME ($BOT_FIRST)${N}"
    echo ""
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo -e "${G}  ✅ Telegram conectado. Sol puede despertar. ☀️${N}"
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo ""
    echo -e "${W}Ahora arranca todo:${N}"
    echo -e "  ${C}bash omni.sh stop${N}"
    echo -e "  ${C}bash omni.sh start${N}"
    echo ""
    echo -e "${W}Y mándale /start a tu bot desde Telegram.${N}"
else
    echo -e "${R}❌ Token inválido:${N}"
    echo "   $RESP" | head -c 300
    echo ""
    echo ""
    echo -e "${Y}Pasos manuales:${N}"
    echo -e "  1. Abre Telegram → @BotFather → /mybots → tu bot → API Token"
    echo -e "  2. Copia el token"
    echo -e "  3. Ejecuta: bash fix_tg_token.sh"
    echo -e "  4. Pega el token cuando te lo pida"
    echo ""
    echo -e "${Y}El token debe verse así: 123456789:AABBccDDeeFFggHHiiJJ${N}"
    echo -e "${Y}Sin comillas, sin espacios, sin nada extra.${N}"
fi
