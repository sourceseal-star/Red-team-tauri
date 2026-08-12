#!/usr/bin/env python3
"""
TRIAGE MODULE -- Deteccion de compromiso para Android/Termux
Expone endpoint /api/triage en dashboard_server.py
"""
import os
import re
import json
import time
import subprocess
from typing import Dict, List
from pathlib import Path


class TriageScanner:
    """Escanea el dispositivo Android via Termux buscando signos de spyware/implants."""

    def __init__(self):
        self.findings = []

    def run_full_scan(self) -> Dict:
        self.findings = []
        result = {
            "timestamp": int(time.time()),
            "device": self._get_device_info(),
            "processes": self._scan_processes(),
            "network": self._scan_network(),
            "thermal": self._scan_thermal(),
            "battery": self._scan_battery(),
            "spyware_iocs": self._scan_spyware_iocs(),
            "alerts": self.findings,
            "risk_score": 0,
        }
        result["risk_score"] = self._calculate_risk(result)
        return result

    def _get_device_info(self) -> Dict:
        try:
            model = subprocess.getoutput("getprop ro.product.model").strip()
            android = subprocess.getoutput("getprop ro.build.version.release").strip()
            kernel = subprocess.getoutput("uname -r").strip()
            return {"model": model, "android": android, "kernel": kernel}
        except Exception:
            return {}

    def _scan_processes(self) -> List[Dict]:
        procs = []
        try:
            output = subprocess.getoutput("ps -eo pid,ppid,%cpu,%mem,args 2>/dev/null | head -30")
            for line in output.splitlines()[1:]:
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    pid, ppid, cpu, mem, args = parts[:5]
                    procs.append({"pid": pid, "cpu": cpu, "mem": mem, "cmd": args[:80]})
                    if float(cpu) > 5.0 and len(args) < 20:
                        self.findings.append(f"Proceso sospechoso: PID {pid} ({args}) consumiendo {cpu}% CPU")
        except Exception:
            pass
        return procs

    def _scan_network(self) -> Dict:
        net = {"connections": [], "interfaces": []}
        try:
            output = subprocess.getoutput("ss -tunap 2>/dev/null | grep ESTAB | head -15")
            for line in output.splitlines():
                net["connections"].append(line.strip()[:120])
        except Exception:
            pass
        return net

    def _scan_thermal(self) -> List[Dict]:
        temps = []
        try:
            for zone in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
                t = zone.read_text().strip()
                typ = zone.parent.joinpath("type").read_text().strip() if zone.parent.joinpath("type").exists() else "unknown"
                if t and t != "0":
                    temps.append({"zone": typ, "temp_c": int(t) // 1000})
                    if int(t) // 1000 > 45:
                        self.findings.append(f"Temperatura anormal: {typ} a {int(t)//1000} deg C")
        except Exception:
            pass
        return temps

    def _scan_battery(self) -> Dict:
        batt = {}
        try:
            cap = Path("/sys/class/power_supply/battery/capacity")
            if cap.exists():
                batt["level"] = cap.read_text().strip()
            curr = Path("/sys/class/power_supply/battery/current_now")
            if curr.exists():
                c = int(curr.read_text().strip())
                batt["current_ua"] = c
                if c < -500000:
                    self.findings.append(f"Descarga de bateria alta: {c} uA en standby")
        except Exception:
            pass
        return batt

    def _scan_spyware_iocs(self) -> List[str]:
        iocs = []
        patterns = ["mSpy", "FlexiSpy", "Pegasus", "NSO", "FinSpy", "HackingTeam", "RCS", "Candiru"]
        try:
            procs = subprocess.getoutput("ps -eo args 2>/dev/null")
            for p in patterns:
                if p.lower() in procs.lower():
                    iocs.append(f"IOC detectado en procesos: {p}")
                    self.findings.append(f"POSIBLE SPYWARE: {p} encontrado en procesos")
        except Exception:
            pass
        try:
            files = subprocess.getoutput("find /sdcard /data/local/tmp 2>/dev/null | grep -iE 'spy|track|monitor|keylog|screenrec|callrec' | head -10")
            for line in files.splitlines():
                iocs.append(line.strip())
                self.findings.append(f"Archivo sospechoso: {line.strip()}")
        except Exception:
            pass
        return iocs

    def _calculate_risk(self, result: Dict) -> int:
        score = 0
        score += len(result["alerts"]) * 10
        for t in result["thermal"]:
            if t["temp_c"] > 45:
                score += 15
        if result["battery"].get("current_ua", 0) < -500000:
            score += 20
        return min(score, 100)


def get_triage_report() -> Dict:
    """Funcion para llamar desde el backend."""
    scanner = TriageScanner()
    return scanner.run_full_scan()
