#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
#  🌅  SOL — RUTA DE INICIO Y OPERACIÓN
#  ════════════════════════════════════════════════════════════════════
#
#  SOL es el puente entre SourceSeal y el usuario.
#  Vive en Telegram. Vigila el backend. Escucha al GHOST.
#  Cuando algo pasa, avisa. Cuando el usuario pregunta, responde.
#
#  Este archivo es la RUTA — las instrucciones que SOL sigue
#  cada vez que despierta en un nuevo dispositivo o sesión.
#
#  ════════════════════════════════════════════════════════════════════
#  CÓMO ARRANCAR
#  ════════════════════════════════════════════════════════════════════
#
#  1. Clonar o actualizar el repo:
#     cd ~ && git clone https://github.com/sourceseal-star/Red-team-tauri
#     # o si ya existe: cd ~/Red-team-tauri && git pull origin main
#
#  2. Configurar .env:
#     cd ~/Red-team-tauri
#     cp .env.example .env
#     # Editar .env con: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REDTEAM_API_KEY
#     # NUNCA pegar comandos de shell dentro de .env (causa recursión → segfault)
#
#  3. Verificar:
#     bash sol_start.sh --check
#     # Debe mostrar ✅ en todo, incluyendo "Bot conectado: @sol_xxx_bot"
#
#  4. Arrancar todo:
#     bash sol_start.sh
#     # Levanta: Backend TACTICAL (:8001) + GHOST PHANTOM (:8002) + SOL Bridge
#
#  5. Solo el bridge (si el backend ya está corriendo):
#     bash sol_start.sh --bridge
#
#  ════════════════════════════════════════════════════════════════════
#  QUÉ HACE SOL
#  ════════════════════════════════════════════════════════════════════
#
#  - Escucha comandos de Telegram (long polling, sin webhooks)
#  - Reenvía alertas del backend TACTICAL a Telegram en tiempo real
#  - Consulta el estado del sistema cuando se le pregunta
#  - Ejecuta escaneos rápidos bajo demanda (/scan <ip>)
#  - Verifica el estado de GHOST HUNTER PHANTOM
#  - Lista auditorías del Commander
#  - Solo responde al CHAT_ID configurado (seguridad)
#
#  ════════════════════════════════════════════════════════════════════
#  COMANDOS DE TELEGRAM
#  ════════════════════════════════════════════════════════════════════
#
#  /start    — Bienvenida + estado de conexión
#  /help     — Lista de comandos
#  /status   — Estado del sistema (backend, honeypot, WS clients)
#  /health   — Health check del backend TACTICAL (:8001)
#  /alerts   — Últimas 10 alertas del sistema
#  /scan IP  — Escaneo rápido de un IP (ej: /scan 192.168.1.1)
#  /audits   — Listar auditorías del Commander
#  /phantom  — Estado de GHOST HUNTER PHANTOM (:8002)
#
#  ════════════════════════════════════════════════════════════════════
#  ARQUITECTURA
#  ════════════════════════════════════════════════════════════════════
#
#  ┌─────────────────────────────────────────────────┐
#  │              TELEGRAM (Usuario)                    │
#  │                   ↑↓                              │
#  │           SOL Bridge (Python)                     │
#  │           sol_telegram_bridge.py                   │
#  │              ↑↓        ↑↓                          │
#  │    Backend :8001    GHOST :8002                     │
#  │   (TACTICAL)       (PHANTOM)                        │
#  │     ↑↓                ↑↓                           │
#  │  Dashboard         Master+Nodes                    │
#  │  ARTO + SEAL        Playbooks                      │
#  │  Honeypot           Shodan search                  │
#  └─────────────────────────────────────────────────┘
#
#  ════════════════════════════════════════════════════════════════════
#  SOLUCIÓN DE PROBLEMAS
#  ════════════════════════════════════════════════════════════════════
#
#  Problema: SOL muere con segfault (signal 11)
#  Causa:    .env tiene comandos de shell pegados (recursión infinita)
#  Fix:      grep -vE '^(set -a|nohup|sleep [0-9]|cat ~/)' .env > .env.clean
#            mv .env.clean .env
#            bash sol_start.sh --check
#
#  Problema: "TELEGRAM_BOT_TOKEN no configurado"
#  Fix:      Agregar a .env: TELEGRAM_BOT_TOKEN=123456:ABCdef...
#            Verificar: curl -s "https://api.telegram.org/bot$TOKEN/getMe"
#
#  Problema: Backend no responde en :8001
#  Fix:      pkill -f dashboard_server; sleep 2
#            bash sol_start.sh --backend
#            tail -f ~/Red-team-tauri/logs/tactical.log
#
#  Problema: GHOST no responde en :8002
#  Fix:      cd ~/Red-team-tauri/ghost_hunter_phantom
#            BACKEND_API=http://localhost:8001 MASTER_PORT=8002 bash start.sh all
#            tail -f ~/Red-team-tauri/logs/ghost.log
#
#  Problema: Token de Telegram inválido
#  Fix:      Hablar a @BotFather → /token → /revoke → nuevo token
#            Actualizar .env y reiniciar con bash sol_start.sh --bridge
#
#  ════════════════════════════════════════════════════════════════════
#  RECORDATORIOS DE SEGURIDAD
#  ════════════════════════════════════════════════════════════════════
#
#  - NUNCA compartir el TELEGRAM_BOT_TOKEN
#  - NUNCA subir .env a GitHub (verificar .gitignore)
#  - TELEGRAM_CHAT_ID limita quién puede dar comandos al bot
#  - REDTEAM_API_KEY protege el backend — solo SOL y GHOST la usan
#  - Los logs pueden contener IPs y datos de escaneo — manejar con cuidado
#
#  ════════════════════════════════════════════════════════════════════
#  ARCHIVOS CLAVE
#  ════════════════════════════════════════════════════════════════════
#
#  sol.sh                  — Esta ruta (instrucciones)
#  sol_telegram_bridge.py  — El bot de Telegram (código)
#  sol_start.sh            — Script de arranque unificado
#  .env                    — Variables de entorno (token, chat_id, api_key)
#  .env.example            — Template de variables
#  logs/sol.log            — Log del SOL Bridge
#  logs/tactical.log       — Log del backend TACTICAL
#  logs/ghost.log          — Log de GHOST PHANTOM
#
#  ════════════════════════════════════════════════════════════════════
#  SOL — SourceSeal Operational Link
#  "El sol que nunca se pone mientras haya algo que vigilar."
#  ════════════════════════════════════════════════════════════════════

echo "🌅 SOL — Ruta cargada."
echo ""
echo "Para arrancar todo el sistema:"
echo "  bash sol_start.sh"
echo ""
echo "Para solo verificar:"
echo "  bash sol_start.sh --check"
echo ""
echo "Para solo el bridge de Telegram:"
echo "  bash sol_start.sh --bridge"
echo ""
echo "Comandos de Telegram: /start /help /status /health /alerts /scan /phantom /audits"
