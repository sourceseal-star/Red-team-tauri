# ─── AÑADIR ESTO DENTRO DE omni.sh, EN LA FUNCIÓN start ───
start_sol_stack() {
  local root="$HOME/Red-team-tauri"
  pgrep -f sol_api.py      >/dev/null || ( cd "$root" && nohup python3 sol_api.py >>"$HOME/.sol/sol_api.log" 2>&1 & )
  pgrep -f sol_watchdog.sh >/dev/null || { chmod +x "$root/sol_watchdog.sh" 2>/dev/null; nohup bash "$root/sol_watchdog.sh" >>"$HOME/.sol/watchdog.log" 2>&1 & }
  echo "[omni] ✅ stack de Sol vigilado"
}
# Llamar a esta función desde start()
start_sol_stack
