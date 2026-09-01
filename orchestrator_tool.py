mkdir -p ~/.orchestrator
cat > ~/.orchestrator/config.json << 'EOF'
{
  "repos": {
    "dashboard": {
      "path": "~/Red-team-tauri",
      "remote": "origin",
      "branch": "main"
    },
    "commander": {
      "path": "~/commander",
      "remote": "origin",
      "branch": "main"
    }
  },
  "telegram": {
    "bot_token": "TU_TOKEN_AQUI",
    "chat_id": "TU_CHAT_ID_AQUI",
    "allowed_users": ["TU_USER_ID"]
  },
  "api": {
    "secret": "cambia_esta_clave_en_produccion"
  },
  "monitor": {
    "enabled": true,
    "interval": 30,
    "cpu_threshold": 85.0,
    "ram_threshold": 90.0
  }
}
EOF