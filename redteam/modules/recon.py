# -*- coding: utf-8 -*-
"""
RECON — Reconocimiento de red con nmap, masscan y subfinder.
Descubre hosts, puertos abiertos y servicios. Todo validado por engagement.
"""
import json, subprocess, shutil
from typing import Any
from redteam.modules.base import BaseModule


class ReconModule(BaseModule):
    name = "recon"
    description = "Reconocimiento de red: nmap, masscan, subfinder"
    version = "1.0"

    def _execute(self, target: str, **kwargs: Any) -> dict[str, Any]:
        mode = kwargs.get("mode", "fast")  # fast | full | stealth
        ports = kwargs.get("ports", None)
        results = {"host": target, "mode": mode, "hosts_found": [], "ports": []}

        # Auto-detectar si es IP/CIDR o dominio
        is_network = any(c in target for c in "/0123456789")

        if is_network:
            results["hosts_found"] = self._scan_network(target, mode, ports)
        else:
            results["ports"] = self._scan_host(target, mode, ports)
            results["subdomains"] = self._find_subdomains(target)

        return results

    def _scan_network(self, cidr: str, mode: str, ports: str | None) -> list:
        """Escaneo de red con nmap o masscan."""
        hosts = []

        # Masscan si está disponible (rápido)
        if shutil.which("masscan") and mode == "fast":
            port_arg = ports or "1-65535"
            try:
                cmd = ["masscan", cidr, "-p", port_arg, "--rate", "1000", "--json-only"]
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                for line in (out.stdout or "").strip().split("\n"):
                    if line.strip():
                        hosts.append(json.loads(line))
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass

        # Nmap fallback (siempre disponible en Termux)
        if not hosts and shutil.which("nmap"):
            args = ["nmap", "-sn", cidr, "-oG", "-"]
            if mode == "stealth":
                args = ["nmap", "-sS", "-sn", cidr, "-oG", "-"]
            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=300)
                for line in out.stdout.split("\n"):
                    if line.startswith("Host:") and "Up" in line:
                        parts = line.split()
                        ip = parts[1]
                        if len(parts) > 2 and parts[2].startswith("("):
                            hostname = parts[2].strip("()")
                            hosts.append({"ip": ip, "hostname": hostname, "status": "up"})
                        else:
                            hosts.append({"ip": ip, "status": "up"})
            except Exception:
                pass

        return hosts

    def _scan_host(self, host: str, mode: str, ports: str | None) -> list:
        """Escaneo de puertos en un host individual."""
        port_arg = ports or ("--top-ports 1000" if mode == "fast" else "-p-")

        if shutil.which("nmap"):
            args = ["nmap"]
            if mode == "stealth":
                args.append("-sS")
            args.extend(host.split() if " " in host else [host])

            if port_arg.startswith("--top-ports") or port_arg.startswith("-p"):
                args.extend(port_arg.split())
            else:
                args.extend(["-p", port_arg])

            args.extend(["-sV", "--version-intensity", "5" if mode == "full" else "3"])
            args.extend(["-oG", "-"])

            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=300)
                return self._parse_nmap_grepable(out.stdout)
            except Exception:
                pass

        # Fallback: TCP connect manual
        return self._tcp_connect_scan(host, ports or "1-1024")

    def _parse_nmap_grepable(self, output: str) -> list:
        """Parsea output -oG de nmap."""
        ports = []
        for line in output.split("\n"):
            if line.startswith("Host:"):
                # Host: 192.168.1.1 (hostname) Ports: 80/open/tcp//http
                if "Ports:" in line:
                    ports_section = line.split("Ports:")[1].strip()
                    for entry in ports_section.split(","):
                        parts = entry.strip().split("/")
                        if len(parts) >= 3:
                            ports.append({
                                "port": int(parts[0]),
                                "state": parts[1],
                                "protocol": parts[2],
                                "service": parts[3] if len(parts) > 3 else "",
                            })
        return ports

    def _tcp_connect_scan(self, host: str, port_range: str) -> list:
        """TCP connect scan sin nmap (Python puro)."""
        import socket
        ports = []
        start, end = 1, 1024
        if "-" in port_range:
            parts = port_range.split("-")
            start, end = int(parts[0]), int(parts[-1])

        for port in range(start, end + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((host, port))
                if result == 0:
                    service = socket.getservbyport(port, "tcp") if port < 1024 else "unknown"
                    ports.append({"port": port, "state": "open", "protocol": "tcp", "service": service})
                sock.close()
            except Exception:
                pass
        return ports

    def _find_subdomains(self, domain: str) -> list:
        """Busca subdominios con subfinder si disponible."""
        if not shutil.which("subfinder"):
            return []
        try:
            out = subprocess.run(
                ["subfinder", "-d", domain, "-silent"],
                capture_output=True, text=True, timeout=120
            )
            return [s.strip() for s in out.stdout.strip().split("\n") if s.strip()]
        except Exception:
            return []
