# -*- coding: utf-8 -*-
"""
ENUMERATION — Enumeración de servicios: SMB, RPC, LDAP, NetBIOS.
Usa smbclient, enum4linux, rpcclient cuando están disponibles.
"""
import subprocess, shutil, re
from typing import Any
from redteam.modules.base import BaseModule


class EnumerationModule(BaseModule):
    name = "enumeration"
    description = "Enumeración de servicios: SMB, RPC, LDAP, NetBIOS"
    version = "1.0"

    def _execute(self, target: str, **kwargs: Any) -> dict[str, Any]:
        services = kwargs.get("services", ["smb", "rpc", "ldap"])
        results = {"host": target, "enumeration": {}}

        if "smb" in services:
            results["enumeration"]["smb"] = self._enum_smb(target)
        if "rpc" in services:
            results["enumeration"]["rpc"] = self._enum_rpc(target)
        if "ldap" in services:
            results["enumeration"]["ldap"] = self._enum_ldap(target)
        if "netbios" in services:
            results["enumeration"]["netbios"] = self._enum_netbios(target)

        return results

    def _enum_smb(self, host: str) -> dict:
        """Enumeración SMB con enum4linux o smbclient."""
        result = {"shares": [], "users": [], "os": "", "workgroup": ""}

        if shutil.which("enum4linux"):
            try:
                out = subprocess.run(
                    ["enum4linux", "-a", host],
                    capture_output=True, text=True, timeout=120
                )
                text = out.stdout + out.stderr

                # Shares
                for m in re.finditer(r"\\\\(\S+)\s+(Disk|IPC|Printer)", text):
                    result["shares"].append({"name": m.group(1), "type": m.group(2)})

                # OS info
                os_match = re.search(r"Os=(.+?)\s", text)
                if os_match:
                    result["os"] = os_match.group(1)
                wk_match = re.search(r"Domain=(.+?)\s", text)
                if wk_match:
                    result["workgroup"] = wk_match.group(1)

            except Exception:
                pass

        elif shutil.which("smbclient"):
            try:
                out = subprocess.run(
                    ["smbclient", "-L", f"//{host}", "-N", "--no-pass"],
                    capture_output=True, text=True, timeout=30
                )
                for line in out.stdout.split("\n"):
                    m = re.match(r"\s+(\S+)\s+(Disk|IPC|Printer)\s+(.*)", line)
                    if m:
                        result["shares"].append({
                            "name": m.group(1),
                            "type": m.group(2),
                            "comment": m.group(3).strip()
                        })
            except Exception:
                pass

        return result

    def _enum_rpc(self, host: str) -> dict:
        """Enumeración RPC con rpcclient."""
        result = {"shares": [], "users": [], "groups": []}

        if not shutil.which("rpcclient"):
            return result

        # Listar usuarios
        try:
            out = subprocess.run(
                ["rpcclient", "-U", "%", "-N", host, "-c", "enumdomusers"],
                capture_output=True, text=True, timeout=60
            )
            for line in out.stdout.strip().split("\n"):
                if line.strip() and "user:" not in line.lower():
                    result["users"].append(line.strip())
        except Exception:
            pass

        # Listar grupos
        try:
            out = subprocess.run(
                ["rpcclient", "-U", "%", "-N", host, "-c", "enumdomgroups"],
                capture_output=True, text=True, timeout=60
            )
            for line in out.stdout.strip().split("\n"):
                if line.strip():
                    result["groups"].append(line.strip())
        except Exception:
            pass

        return result

    def _enum_ldap(self, host: str) -> dict:
        """Enumeración LDAP básica."""
        result = {"base_dn": "", "users": [], "computers": []}

        if not shutil.which("ldapsearch"):
            return result

        try:
            # Buscar base DN
            out = subprocess.run(
                ["ldapsearch", "-x", "-H", f"ldap://{host}", "-s", "base",
                 "(objectclass=*)", "namingContexts"],
                capture_output=True, text=True, timeout=30
            )
            for line in out.stdout.split("\n"):
                if line.startswith("namingContexts:"):
                    result["base_dn"] = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

        return result

    def _enum_netbios(self, host: str) -> dict:
        """Enumeración NetBIOS con nmblookup."""
        result = {"names": [], "mac": "", "domain": ""}

        if not shutil.which("nmblookup"):
            return result

        try:
            out = subprocess.run(
                ["nmblookup", "-A", host],
                capture_output=True, text=True, timeout=30
            )
            for line in out.stdout.split("\n"):
                if "<00>" in line or "<1E>" in line or "<20>" in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        name = parts[0]
                        result["names"].append(name)
                        if "<1E>" in line:
                            result["domain"] = name

            # MAC address
            mac_match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", out.stdout)
            if mac_match:
                result["mac"] = mac_match.group(0)

        except Exception:
            pass

        return result
