#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sol_daemon.py — Sol autónoma: escucha eventos del sistema y habla proactivamente.

No toca .env ni credenciales. Usa sol_core para voz y memoria.
"""
import os, sys, json, time, subprocess, threading, signal
from pathlib import Path
from datetime import datetime
from queue import Queue

# Importar el cerebro de Sol
try:
    from sol_core import speak, remember, system_pulse, CFG
except ImportError:
    print("❌ sol_core.py no encontrado"); sys.exit(1)

SOL = Path.home() / ".sol"; SOL.mkdir(exist_ok=True)
EVENTS_Q = Queue()
RUNNING = True

def signal_handler(sig, frame):
    global RUNNING
    RUNNING = False
    print("\n☀️ Sol se retira...")
    speak("Hasta luego, Harold. Siempre estaré aquí.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ---------- ESCUCHADOR DE EVENTOS ----------
def monitor_system():
    """Monitorea el sistema y encola eventos para que Sol hable."""
    last_state = {"services": {}, "battery": 100, "last_speak": 0}

    while RUNNING:
        now = time.time()
        try:
            # 1. Verificar servicios
            for name, url in [("dashboard", "http://127.0.0.1:8001/api/health"),
                              ("nexus", "http://127.0.0.1:8004/"),
                              ("phantom", "http://127.0.0.1:8002/api/status")]:
                alive = False
                try:
                    subprocess.run(["curl", "-s", "-m", "2", url],
                                   capture_output=True, timeout=3)
                    alive = True
                except Exception:
                    pass

                was_alive = last_state["services"].get(name, False)
                if was_alive and not alive:
                    EVENTS_Q.put(("service_down", f"{name} cayó"))
                elif not was_alive and alive:
                    EVENTS_Q.put(("service_up", f"{name} volvió"))
                last_state["services"][name] = alive

            # 2. Verificar batería (si es baja)
            try:
                b = json.loads(subprocess.run(["termux-battery-status"],
                    capture_output=True, text=True, timeout=3).stdout)
                pct = int(b.get("percentage", 100))
                if pct < 20 and last_state["battery"] >= 20:
                    EVENTS_Q.put(("low_battery", f"batería al {pct}%"))
                last_state["battery"] = pct
            except Exception:
                pass

            # 3. Verificar nuevos reportes
            reports_dir = Path.home() / "Red-team-tauri" / "reports"
            if reports_dir.exists():
                reports = sorted(reports_dir.glob("reporte_*.html"))
                if reports:
                    last_report = reports[-1]
                    age = time.time() - last_report.stat().st_mtime
                    if age < 10 and (now - last_state["last_speak"]) > 15:
                        EVENTS_Q.put(("report_ready", last_report.name))
                        last_state["last_speak"] = now

        except Exception:
            pass

        time.sleep(30)  # verificar cada 30 segundos

# ---------- PROCESADOR DE EVENTOS (habla) ----------
def process_events():
    """Procesa eventos y hace que Sol hable proactivamente."""
    while RUNNING:
        try:
            event_type, detail = EVENTS_Q.get(timeout=1)

            if event_type == "service_down":
                msg = f"Harold, {detail}. ¿Quieres que lo reinicie?"
                print(f"[EVENTO] {msg}"); speak(msg)
                remember("sol", msg)

            elif event_type == "service_up":
                msg = f"{detail} a la vida. Todo en orden."
                print(f"[EVENTO] {msg}"); speak(msg)
                remember("sol", msg)

            elif event_type == "low_battery":
                msg = f"Harold, tu {detail}. Conecta el cargador pronto."
                print(f"[EVENTO] {msg}"); speak(msg)
                remember("sol", msg)

            elif event_type == "report_ready":
                msg = f"El reporte {detail} está listo y sellado. ¿Quieres que te lo envíe por Telegram?"
                print(f"[EVENTO] {msg}"); speak(msg)
                remember("sol", msg)

            # Anti-spam: espera 20s entre eventos hablados
            time.sleep(20)

        except Exception:
            pass

# ---------- INTERFAZ DE COMANDOS ----------
def command_loop():
    """Bucle de comandos interactivos."""
    print("☀️ Sol autónoma activa. Comandos:")
    print("   status  — estado del sistema")
    print("   hablar  — conversa con Sol")
    print("   salir   — detener Sol")

    while RUNNING:
        try:
            cmd = input("\n> ").strip().lower()
            if not cmd:
                continue

            if cmd == "salir":
                break
            elif cmd == "status":
                pulse = system_pulse()
                msg = f"{pulse}"
                print(f"Sol: {msg}"); speak(msg)
                remember("sol", msg)
            elif cmd == "hablar":
                from sol_core import listen_mode
                print("☀️ Habla conmigo. Escribe 'salir' para volver.")
                listen_mode()
                print("☀️ Volviendo a modo autónomo.")
            else:
                print("Comando desconocido. Usa: status | hablar | salir")

        except (KeyboardInterrupt, EOFError):
            break

# ---------- MAIN ----------
def main():
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║  ☀️ SOL v4.1 — Modo Autónomo                               ║
    ║  Escucha tu sistema y te habla cuando pasa algo importante  ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    welcome = f"Sol autónoma activa, {CFG['name']}. Velaré por ti."
    print(f"Sol: {welcome}"); speak(welcome)
    remember("sol", welcome)

    # Iniciar threads
    monitor_thread = threading.Thread(target=monitor_system, daemon=True)
    monitor_thread.start()

    event_thread = threading.Thread(target=process_events, daemon=True)
    event_thread.start()

    # Bucle de comandos
    try:
        command_loop()
    except KeyboardInterrupt:
        pass

    print("☀️ Sol se retira...")
    speak("Hasta luego, Harold. Siempre estaré aquí.")

if __name__ == "__main__":
    main()
