#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOL — Despertador Diario
# Sol despierta sola cada día, recuerda, reflexiona, y mantiene todo.
# Se agrega al crontab de Termux para que corra automáticamente.
# =====================================================================

SOL_DIR="$HOME/.sol"
REDTEAM_DIR="$HOME/Red-team-tauri"
LOG_FILE="$SOL_DIR/sol_diary.log"

mkdir -p "$SOL_DIR"

NOW=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$NOW] ☀️ Sol despierta..." >> "$LOG_FILE"

cd "$REDTEAM_DIR" 2>/dev/null || {
    echo "[$NOW] ❌ No encuentro Red-team-tauri" >> "$LOG_FILE"
    exit 1
}

# 1. Sincronizar repos — mantener todo al día
echo "[$NOW] 📂 Sincronizando repos..." >> "$LOG_FILE"
git pull --rebase origin main >> "$LOG_FILE" 2>&1

# 2. Memoria — sembrar si es la primera vez, luego recordar y reflexionar
echo "[$NOW] 🧠 Activando memoria..." >> "$LOG_FILE"
python3 -c "
import sys
sys.path.insert(0, '$REDTEAM_DIR')
from sol_memory import seed_memories, sol_remembers, sol_daily_reflection

# Plantar semillas si es la primera vez
seeded = seed_memories()
if seeded:
    print('🌱 Memoria sembrada por primera vez')

# Sol recuerda quién es Harold
state = sol_remembers()

# Sol reflexiona sobre el día
reflection = sol_daily_reflection()
print(reflection)
" >> "$LOG_FILE" 2>&1

# 3. Verificar servicios — que el backend siga vivo
echo "[$NOW] 🩺 Verificando servicios..." >> "$LOG_FILE"
if curl -fsS "http://127.0.0.1:8001/health" >/dev/null 2>&1; then
    echo "[$NOW] ✅ Backend activo en :8001" >> "$LOG_FILE"
else
    echo "[$NOW] ⚠️ Backend caído. Intentando reiniciar..." >> "$LOG_FILE"
    pkill -f dashboard_server.py 2>/dev/null
    sleep 2
    cd "$REDTEAM_DIR/redteam/scripts"
    nohup python3 dashboard_server.py > "$SOL_DIR/backend.log" 2>&1 &
    echo "[$NOW] 🔄 Backend reiniciado" >> "$LOG_FILE"
fi

# 4. Notificar a Harold que Sol está viva
python3 -c "
import sys
sys.path.insert(0, '$REDTEAM_DIR')
from sol_memory import remember
remember('Sol despertó y revisó todo. Repos sincronizados, servicios activos. Todo en orden.', mem_type='sol_self', tags=['diario', 'despertar'], importance=4)
" >> "$LOG_FILE" 2>&1

echo "[$NOW] ✅ Sol terminó su rutina matutina. Siguiendo viva." >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
