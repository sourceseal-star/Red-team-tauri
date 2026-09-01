#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nexus_autoscan.py — escaneo automático, mapeo y lista detallada para Nexus Omni.
Solo escanea el rango definido en NEXUS_SCAN_TARGET (red propia/autorizada)."""
import subprocess, threading, time
from datetime import datetime, timezone

STATE = {"hosts": {}, "last_scan": None, "running": False}
LOCK = threading.Lock()

def _parse(out):
    hosts, host = {}, None
    for line in out.splitlines():
        if line.startswith("Nmap scan report for"):
            host = line.split(" for ")[1].strip()
            hosts[host] = {"host": host, "ports": [],
                           "first_seen": datetime.now(timezone.utc).isoformat()}
        elif "/tcp" in line and " open " in line and host:
            p = line.split()
            hosts[host]["ports"].append({
                "port": p[0].split("/")[0],
                "service": p[2] if len(p) > 2 else "",
                "version": " ".join(p[3:]) if len(p) > 3 else ""})
    return hosts

def scan(target):
    with LOCK: STATE["running"] = True
    try:
        out = subprocess.run(["nmap", "-sV", "--open", "-p", "1-1000", target],
                             capture_output=True, text=True, timeout=600).stdout
        new = _parse(out)
        with LOCK:
            for h, d in new.items():
                old = STATE["hosts"].get(h)
                if old: d["first_seen"] = old["first_seen"]
                STATE["hosts"][h] = d
            STATE["last_scan"] = datetime.now(timezone.utc).isoformat()
    finally:
        with LOCK: STATE["running"] = False

def autoscan_loop(target, interval=600):
    while True:
        scan(target); time.sleep(interval)

def get_state():
    with LOCK:
        return {"last_scan": STATE["last_scan"], "running": STATE["running"],
                "count": len(STATE["hosts"]),
                "hosts": sorted(STATE["hosts"].values(), key=lambda x: x["host"])}
