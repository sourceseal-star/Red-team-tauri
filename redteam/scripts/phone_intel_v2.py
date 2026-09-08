#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHONE INTEL v2.0 — SPECTRE HUNTER
Análisis defensivo de llamadas entrantes para Harold / SourceSeal.

PRINCIPIOS DE DISEÑO (leer antes de modificar):
- 100% LOCAL Y DE SOLO LECTURA: lee el log de llamadas con termux-call-log,
  guarda análisis en SQLite local (~/.spectre_hunter.db) y avisa al War Room
  (localhost:8001/api/v2/alerts) y al Telegram de Harold. NADA sale a
  servicios de terceros. Ningún metadato se exfiltra a ningún lado.
- NO hace bloqueos automáticos ni requiere root. Recomendar bloqueo es
  decisión humana; el script solo informa.
- HONESTIDAD TÉCNICA: este script NO puede detectar IMSI catchers ni
  inyecciones baseband — eso requiere hardware SDR y análisis de capa
  radio que un celular no expone. Lo que SÍ hace: detectar patrones de
  scam (wangiri, callback-bait), spoofing de formato, repetidores, y
  deja evidencia correlacionada para análisis posterior.
- NO LLAMAR de vuelta a números desconocidos: el wangiri vive de eso.

Uso:
  python3 phone_intel_v2.py --monitor            # demonio: vigila llamadas nuevas
  python3 phone_intel_v2.py --analyze NUMERO    # análisis puntual de un número
  python3 phone_intel_v2.py --list [N]          # historial de análisis
  python3 phone_intel_v2.py --watch 3600        # monitoreo por 1h y salir
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import re
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # Telegram/alertas quedan deshabilitadas; análisis local sigue

CONFIG = {
    "db_path": os.path.expanduser("~/.spectre_hunter.db"),
    "warroom_alerts": os.environ.get("WARROOM_ALERTS", "http://127.0.0.1:8001/api/v2/alerts"),
    "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat": os.environ.get("TELEGRAM_CHAT_ID", ""),
    "poll_seconds": 30,  # 30s: bastante y no drena batería
}

# ── Heurísticas locales (sin APIs externas) ──────────────────────────────
CO_PREFIXES = {  # Colombia, prefijos móviles principales
    "Claro":    {"300", "301", "302", "303", "304", "305"},
    "Tigo":     {"310", "311", "312", "313", "314", "315"},
    "Movistar": {"320", "321", "322", "323"},
    "WOM":      {"350", "351"},
}
US_AREA_HINTS = {"323": "Los Angeles, US (formato sin país)"}


def init_db():
    Path(CONFIG["db_path"]).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CONFIG["db_path"])
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT NOT NULL, normalized TEXT, call_time TEXT,
        duration INTEGER, status TEXT, anomaly TEXT,
        carrier TEXT, country TEXT, line_type TEXT,
        spam_score INTEGER, risk_level TEXT, tags TEXT,
        UNIQUE(number, call_time))""")
    c.execute("""CREATE TABLE IF NOT EXISTS number_intel (
        number TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT,
        total_calls INTEGER DEFAULT 1, max_risk TEXT,
        tags TEXT)""")
    conn.commit()
    conn.close()


def normalize_number(number: str) -> str:
    clean = re.sub(r"[^\d+]", "", str(number or ""))
    if clean.startswith("00"):
        clean = "+" + clean[2:]  # 0057... -> +57... (formato internacional forzado)
    return clean


def analyze_number(number: str, context: dict | None = None) -> dict:
    """Análisis heurístico LOCAL. Cero llamadas a internet."""
    n = normalize_number(number)
    r = {
        "number": number, "normalized": n,
        "country": "Desconocido", "carrier": "Desconocido", "line_type": "Desconocido",
        "spam_score": 0, "risk_level": "LOW", "tags": [],
        "anomaly": (context or {}).get("anomaly"),
    }

    # ── Formato internacional forzado (00... o +... entrante inusual)
    if str(number).startswith("00"):
        r["spam_score"] += 25
        r["tags"].append("formato_00_internacional_forzado")
    if len(n.replace("+", "")) < 10:
        r["spam_score"] += 60
        r["tags"].append("numero_corto_sospechoso")

    # ── Colombia con código de país explícito (+57...)
    digits = n.replace("+", "")
    if n.startswith("+57") and len(n) >= 12:
        r["country"] = "Colombia"
        pref = n[3:6]
        for carrier, prefs in CO_PREFIXES.items():
            if pref in prefs:
                r["carrier"] = carrier
                r["line_type"] = "Móvil"
                break
        else:
            r["line_type"] = "Móvil (prefijo no mapeado)"

    # ── Colombia SIN código de país: móviles locales son 10 dígitos y
    #    empiezan en 3 (300-350). Hay que chequear esto ANTES de asumir NANP,
    #    porque prefijos como 323 (Movistar) y 350 (WOM) son válidos en
    #    AMBOS esquemas y se confunden con área codes de EE.UU./Canadá.
    elif len(digits) == 10 and digits.startswith("3") and not n.startswith("+"):
        pref = digits[:3]
        matched = False
        for carrier, prefs in CO_PREFIXES.items():
            if pref in prefs:
                r["country"], r["carrier"], r["line_type"] = "Colombia", carrier, "Móvil (local, sin +57)"
                matched = True
                break
        if not matched:
            r["country"], r["line_type"] = "Colombia (prefijo móvil no mapeado)", "Móvil"
        r["tags"].append("colombia_sin_codigo_pais")

    # ── Números de 10-11 dígitos sin código de país que NO calzan con
    #    Colombia (típico VoIP scam NANP/US)
    elif len(digits) == 11 and digits.startswith("1") and not n.startswith("+"):
        r["country"] = US_AREA_HINTS.get(digits[1:4], "US/CA con código de país '1'")
        r["line_type"] = "VoIP/fijo NANP"
        r["spam_score"] += 15
        r["tags"].append("nanp_con_codigo_pais")
    elif len(digits) == 10 and not n.startswith("+"):
        r["country"] = US_AREA_HINTS.get(digits[:3], "Formato NANP (US/CA) sin país")
        r["line_type"] = "VoIP/fijo NANP"
        r["spam_score"] += 15
        r["tags"].append("nanp_sin_formato_internacional")

    # ── Repetidor: ya nos llamó antes y puntuó alto
    conn = sqlite3.connect(CONFIG["db_path"])
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM calls WHERE normalized=? AND spam_score > 40", (n,))
    if c.fetchone()[0] > 0:
        r["spam_score"] += 30
        r["tags"].append("reincidente")

    # ── Anomalías de contexto (pasadas por el monitor)
    if r["anomaly"] == "instant_hangup":
        r["spam_score"] += 40
        r["tags"].append("wangiri_probable_timbra_y_corta")

    score = r["spam_score"]
    if score >= 80:
        r["risk_level"] = "CRITICAL"
    elif score >= 50:
        r["risk_level"] = "HIGH"
    elif score >= 25:
        r["risk_level"] = "MEDIUM"
    conn.close()
    return r


def save_analysis(r: dict, call: dict | None = None):
    conn = sqlite3.connect(CONFIG["db_path"])
    c = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    c.execute("""INSERT OR IGNORE INTO calls
        (number, normalized, call_time, duration, status, anomaly, carrier,
         country, line_type, spam_score, risk_level, tags)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (r["number"], r["normalized"],
         (call or {}).get("call_time", now),
         (call or {}).get("duration", -1),
         (call or {}).get("status", "unknown"),
         r["anomaly"], r["carrier"], r["country"], r["line_type"],
         r["spam_score"], r["risk_level"], json.dumps(r["tags"])))
    c.execute("""INSERT INTO number_intel (number, first_seen, last_seen, total_calls, max_risk, tags)
        VALUES (?,?,?,1,?,?)
        ON CONFLICT(number) DO UPDATE SET
          last_seen=excluded.last_seen, total_calls=total_calls+1,
          max_risk=CASE WHEN excluded.max_risk='CRITICAL' THEN 'CRITICAL'
                        WHEN excluded.max_risk='HIGH' AND max_risk!='CRITICAL' THEN 'HIGH'
                        ELSE max_risk END""",
        (r["normalized"], now, now, r["risk_level"], json.dumps(r["tags"])))
    conn.commit()
    conn.close()


def get_call_log(limit=20) -> list:
    """Lee el log de llamadas vía termux-call-log (Termux:API)."""
    try:
        out = subprocess.run(["termux-call-log", "-l", str(limit)],
                            capture_output=True, text=True, timeout=8)
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except FileNotFoundError:
        print("❌ termux-call-log no existe: pkg install termux-api (y la app Termux:API desde F-Droid)")
    except Exception as e:
        print(f"⚠️ termux-call-log falló (¿puente colgado? ver docs/TERMUX_API_SALUD.md): {e}")
    return []


def alert_warroom(r: dict):
    if not requests:
        return
    try:
        requests.post(CONFIG["warroom_alerts"], json={
            "severity": {"CRITICAL": "critical", "HIGH": "high"}.get(r["risk_level"], "warning"),
            "title": f"Phone Intel: {r['number']}",
            "message": f"Riesgo {r['risk_level']} ({r['spam_score']}/100) · {r['country']} · {r['carrier']} · {', '.join(r['tags']) or 'sin tags'}",
            "source": "phone_intel_v2",
            "metadata": r,
        }, timeout=4)
    except Exception:
        pass  # War Room abajo ≠ pérdida de datos: SQLite ya guardó todo


def alert_telegram(r: dict):
    if not (requests and CONFIG["telegram_token"] and CONFIG["telegram_chat"]):
        return
    try:
        msg = (f"📡 Phone Intel — {r['risk_level']}\n"
               f"📞 {r['number']} ({r['normalized']})\n"
               f"🌍 {r['country']} · {r['carrier']} · {r['line_type']}\n"
               f"🎯 Score: {r['spam_score']}/100\n"
               f"🏷️ {', '.join(r['tags']) or '—'}\n"
               f"🚫 NO devolver la llamada (wangiri vive del callback).")
        requests.post(
            f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage",
            json={"chat_id": CONFIG["telegram_chat"], "text": msg}, timeout=6)
    except Exception:
        pass


def process_call(raw: dict) -> dict | None:
    number = str(raw.get("number") or raw.get("phone_number") or "").strip()
    if number in ("", "-1", "Unknown", "unknown"):
        return None
    duration = int(raw.get("duration", 0) or 0)
    # simid/sim_slot lo entrega termux-call-log: es la LÍNEA de Harold que
    # recibió la llamada (SIM física / eSIM), NUNCA el operador de quien llama.
    sim_hint = raw.get("simid") or raw.get("sim_slot")
    context = {"anomaly": "instant_hangup" if duration == 0 else None}
    r = analyze_number(number, context)
    r["call_time"] = datetime.fromtimestamp(
        int(raw.get("date", raw.get("timestamp", 0)) or 0) / 1000
    ).isoformat(timespec="seconds")
    r["duration"], r["status"] = duration, raw.get("type", "incoming")
    save_analysis(r, {"call_time": r["call_time"], "duration": duration, "status": r["status"]})
    if r["risk_level"] in ("HIGH", "CRITICAL"):
        alert_warroom(r)
        alert_telegram(r)
    return r


def monitor(seconds: float | None = None):
    print(f"📡 [SPECTRE HUNTER] Monitoreo activo (poll cada {CONFIG['poll_seconds']}s). Ctrl+C para parar.")
    seen: set[int] = set()
    for call in get_call_log(50):  # semilla inicial: marcar lo ya existente
        seen.add(int(call.get("date", 0) or 0))
    t0 = time.time()
    while True:
        for call in get_call_log(5):
            ts = int(call.get("date", 0) or 0)
            if ts and ts not in seen:
                seen.add(ts)
                r = process_call(call)
                if r:
                    print(f"🔔 {r['number']} → {r['risk_level']} ({r['spam_score']}/100) {r['tags']}")
        if seconds and time.time() - t0 > seconds:
            print("⏱️ Tiempo de vigilancia agotado.")
            return
        time.sleep(CONFIG["poll_seconds"])


def cli_list(limit=15):
    conn = sqlite3.connect(CONFIG["db_path"])
    rows = conn.execute(
        "SELECT call_time, number, risk_level, spam_score, tags, carrier "
        "FROM calls ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    print(f"\n{'FECHA':<20}{'NÚMERO':<18}{'RIESGO':<10}{'SCORE':<7}{'OPERADOR':<10}TAGS")
    print("─" * 90)
    for t, n, rl, sc, tags, car in rows:
        icon = {"CRITICAL": "🟥", "HIGH": "🟨"}.get(rl, "⬜")
        print(f"{t:<20}{n:<18}{icon} {rl:<7}{sc:<7}{car:<10}{', '.join(json.loads(tags or '[]'))}")


def cli_analyze(number: str):
    r = analyze_number(number, {"anomaly": None})
    print(json.dumps(r, indent=2, ensure_ascii=False))
    save_analysis(r)


if __name__ == "__main__":
    args = sys.argv[1:]
    init_db()
    if "--monitor" in args:
        monitor()
    elif "--watch" in args:
        monitor(float(args[args.index("--watch") + 1]) if len(args) > args.index("--watch") + 1 else 3600)
    elif "--analyze" in args:
        cli_analyze(args[args.index("--analyze") + 1])
    elif "--list" in args:
        cli_list(int(args[args.index("--list") + 1]) if len(args) > args.index("--list") + 1 else 15)
    else:
        print(__doc__)
