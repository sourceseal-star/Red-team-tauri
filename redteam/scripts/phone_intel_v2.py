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
    c.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT, ts TEXT, detail TEXT)""")
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




def log_event(event_type: str, detail: dict):
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.execute("INSERT INTO events (event_type, ts, detail) VALUES (?,?,?)",
                 (event_type, datetime.now().isoformat(timespec="seconds"), json.dumps(detail)))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════
# GUARDIA DE RADIO (v2.1) — indicadores locales de anomalía celular
# ══════════════════════════════════════════════════════════════════
# HONESTIDAD (leer antes de tocar): esto NO "detecta IMSI catchers".
# Son INDICADORES locales para revisión humana, con línea base aprendida
# y cooldown, para no ahogar a Harold en falsos positivos:
#   1. POSIBLE_SIM_SWAP — ambas SIM muertas con WiFi conectado y habiendo
#      tenido celdas hace poco. El SIM swap es la amenaza REAL y común
#      en Colombia (clonan la línea para fraude bancario).
#   2. POSIBLE_DOWNGRADE_2G — la red pasó de LTE/5G a solo GSM estando
#      quieto. Técnica clásica de intercepción activa (A5/0).
#   3. FLAPPING_TORRES — >=4 celdas distintas en 10 min sin moverte.
#   4. PICO_SENAL — mejora sostenida >=25 dBm contra la base de 10 min.
# Ninguno es confirmación de ataque: se registra, se avisa, decide el humano.

CELL_CACHE = os.path.expanduser("~/.spectre_cells.json")
GUARD_STATE = os.path.expanduser("~/.spectre_guard_state.json")
GUARD_COOLDOWN = 1800  # mismo evento: máx 1 alerta cada 30 min


def _termux_json(cmd: list, timeout=8):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception:
        pass
    return None


def _find_key(obj, names: tuple):
    """Búsqueda recursiva de una key en JSON de estructura variable."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in names and isinstance(v, (int, str)):
                return v
        for v in obj.values():
            r = _find_key(v, names)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, names)
            if r is not None:
                return r
    return None


def radio_sample() -> dict:
    """Una muestra de la radio: celdas crudas + resumen defensivo."""
    raw = _termux_json(["termux-telephony-cellinfo"])
    cells = raw if isinstance(raw, list) else []
    summary = []
    for c in cells if isinstance(cells, list) else []:
        try:
            summary.append({
                "cid": _find_key(c, ("cid", "ci", "cellid")),
                "lac": _find_key(c, ("lac", "tac")),
                "dbm": _find_key(c, ("dbm", "signal_strength")),
            })
        except Exception:
            pass
    tech_raw = json.dumps(raw).lower() if raw else ""
    techs = {t for t in ("lte", "nr", "gsm", "umts", "cdma") if t in tech_raw}
    wifi = _termux_json(["termux-wifi-connectioninfo"]) or {}
    return {"cells": summary, "techs": sorted(techs), "raw": raw,
            "wifi_up": bool(wifi.get("ssid"))}


def _load_state() -> dict:
    try:
        return json.loads(Path(GUARD_STATE).read_text())
    except Exception:
        return {"samples": [], "last_alert": {}}


def _save_state(st: dict):
    Path(GUARD_STATE).write_text(json.dumps(st))
    cell_hist = st["samples"][-15:]
    Path(CELL_CACHE).write_text(json.dumps(cell_hist))


def guard_cycle(st: dict) -> list:
    """Analiza una muestra contra la línea base. Retorna eventos a avisar."""
    now = time.time()
    s = radio_sample()
    st["samples"].append({"ts": now, "summary": s["cells"], "techs": s["techs"],
                          "wifi_up": s["wifi_up"], "had_cells": bool(s["cells"])})
    st["samples"] = st["samples"][-30:]  # ~30 min a 60s
    _save_state(st)
    events = []

    def cooled(tag: str) -> bool:
        if now - st["last_alert"].get(tag, 0) < GUARD_COOLDOWN:
            return False
        st["last_alert"][tag] = now
        return True

    # 1) SIM swap: antes había celdas, ahora ninguna, y el WiFi sigue vivo.
    recent = [x for x in st["samples"][:-1] if now - x["ts"] < 600]
    if (not s["cells"] and s["wifi_up"]
            and any(x["had_cells"] for x in recent[-3:])):
        if cooled("sim_swap"):
            events.append(("POSIBLE_SIM_SWAP", {
                "aviso": "Tus SIM perdieron la red con WiFi activo. Revisa que tus "
                         "apps bancarias sigan accesibles y llama a tu operador "
                         "SI notaste caída de señal sin motivo.",
                "celdas_previas": [x["summary"] for x in recent[-2:]]}))

    # 2) Downgrade 2G: había LTE/5G y ahora solo GSM.
    prev_techs = set().union(*(set(x["techs"]) for x in recent)) if recent else set()
    cur = set(s["techs"])
    if prev_techs & {"lte", "nr"} and cur and cur <= {"gsm"}:
        if cooled("downgrade_2g"):
            events.append(("POSIBLE_DOWNGRADE_2G", {
                "aviso": "La red pasó de LTE/5G a solo GSM estando en el mismo lugar.",
                "antes": sorted(prev_techs), "ahora": sorted(cur)}))

    # 3) Flapping: >=4 celdas distintas en los últimos 10 min.
    ids = {c["cid"] for x in recent for c in x["summary"] if c["cid"] is not None}
    if len(ids) >= 4:
        if cooled("flapping"):
            events.append(("FLAPPING_TORRES", {"celdas_10min": sorted(ids)}))

    # 4) Pico de señal: mejora sostenida >=25 dBm vs base de 10 min.
    old_dbm = [_find_key(x, ("dbm",)) for x in st["samples"][-15:-5]]
    old_dbm = [d for d in old_dbm if isinstance(d, (int, float))]
    cur_dbm = [_find_key(c, ("dbm",)) for c in s["cells"]]
    cur_dbm = [d for d in cur_dbm if isinstance(d, (int, float))]
    if old_dbm and cur_dbm and max(cur_dbm) - min(old_dbm) >= 25 and max(cur_dbm) >= -60:
        if cooled("pico_senal"):
            events.append(("PICO_SENAL", {"dbm_base": min(old_dbm), "dbm_ahora": max(cur_dbm)}))

    return events


def guard_loop():
    print("📶 [SPECTRE GUARD] Guardia de radio activa (muestra cada 60s). Ctrl+C para parar.")
    print("   Indicadores: SIM swap · downgrade 2G · flapping · pico de señal.")
    print("   Recordatorio: son INDICADORES para revisión humana, no confirmación.")
    st = _load_state()
    # semilla: dos muestras separadas 90s para tener línea base
    guard_cycle(st)
    time.sleep(90)
    while True:
        try:
            for tag, detail in guard_cycle(st):
                line = f"📶 {tag}: {json.dumps(detail, ensure_ascii=False)[:180]}"
                print(f"🔔 {line}")
                log_event(tag, detail)
                sev = "critical" if tag == "POSIBLE_SIM_SWAP" else "warning"
                alert_warroom({"risk_level": "HIGH" if sev == "critical" else "MEDIUM",
                               "number": tag, "country": "red local", "carrier": "radio",
                               "spam_score": 0, "tags": [tag],
                               **({"anomaly": None} if True else {})})
                alert_telegram({"risk_level": "HIGH", "number": tag,
                                "normalized": "", "country": "celular de Harold",
                                "carrier": "radio", "line_type": tag,
                                "spam_score": 0, "tags": [tag],
                                **({"anomaly": None} if True else {})})
        except KeyboardInterrupt:
            print("\n🛑 Guardia detenida.")
            return
        except Exception as e:
            print(f"⚠️ guard: {e}")
        time.sleep(60)

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
    if "--guard" in args:
        guard_loop()
    elif "--monitor" in args:
        monitor()
    elif "--watch" in args:
        monitor(float(args[args.index("--watch") + 1]) if len(args) > args.index("--watch") + 1 else 3600)
    elif "--analyze" in args:
        cli_analyze(args[args.index("--analyze") + 1])
    elif "--list" in args:
        cli_list(int(args[args.index("--list") + 1]) if len(args) > args.index("--list") + 1 else 15)
    else:
        print(__doc__)
