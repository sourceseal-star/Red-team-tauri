#!/data/data/com.termux/files/usr/bin/env python3
"""
Corset Digital -- Adaptacion Termux (Android, sin root)
=======================================================
- No eBPF (requiere root)
- No /mnt/scope fisico ? usa almacenamiento interno cifrado
- Hook de socket en userspace
- Dead drops via Tor (Orbot proxy 127.0.0.1:9050)
"""
from __future__ import annotations

import socket
import hashlib
import ipaddress
import os
import sys
import time
import random
import json
import base64
from pathlib import Path
from typing import Set

TERMUX_HOME = Path(os.environ.get("HOME", "/data/data/com.termux/files/home"))
SCOPE_FILE = TERMUX_HOME / ".corset" / "scope.bin"
SCOPE_SIG  = TERMUX_HOME / ".corset" / "scope.sig"
TOR_PROXY = ("127.0.0.1", 9050)

_AUTHORIZED_NETWORKS: Set[ipaddress.IPv4Network] = set()
_AUTHORIZED_HOSTS: Set[str] = set()
_ORIGINAL_CONNECT = socket.socket.connect


class CorsetTermux:
    def __init__(self, enforce: bool = True):
        self.enforce = enforce
        self._ensure_dirs()
        self._load_scope()
        if enforce:
            self._hook_socket()
            self._install_signals()

    def _ensure_dirs(self):
        SCOPE_FILE.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(SCOPE_FILE.parent, 0o700)

    def _load_scope(self):
        if not SCOPE_FILE.exists():
            raise RuntimeError(
                f"[CORSET-TERMUX] Sin scope. Genera primero:\n"
                f"  python3 generate_scope.py --networks 192.168.1.0/24 "
                f"--output {SCOPE_FILE}"
            )
        raw = SCOPE_FILE.read_bytes()
        if SCOPE_SIG.exists():
            expected = SCOPE_SIG.read_bytes()
            actual = hashlib.sha3_256(raw).digest()[:32]
            if expected != actual:
                raise RuntimeError("[CORSET] Firma invalida. Scope comprometido.")
        self._parse_scope(raw)

    def _parse_scope(self, raw: bytes):
        import struct
        idx = 0
        num_nets = struct.unpack_from(">I", raw, idx)[0]; idx += 4
        for _ in range(num_nets):
            ip_int, mask = struct.unpack_from(">IB", raw, idx)
            idx += 5
            ip_str = socket.inet_ntoa(struct.pack(">I", ip_int))
            _AUTHORIZED_NETWORKS.add(ipaddress.IPv4Network(f"{ip_str}/{mask}"))
        num_hosts = struct.unpack_from(">I", raw, idx)[0]; idx += 4
        for _ in range(num_hosts):
            hlen = raw[idx]; idx += 1
            host = raw[idx:idx+hlen].decode("utf-8", errors="ignore")
            idx += hlen
            _AUTHORIZED_HOSTS.add(host)

    def _hook_socket(self):
        def _patched_connect(sock, address):
            ip, port = address
            resolved = self._resolve(ip)
            if not self._is_in_scope(resolved, ip):
                time.sleep(random.uniform(0.5, 2.5))
                self._log_to_dead_drop(resolved, "blocked")
                raise OSError(113, "No route to host")
            if random.random() < 0.15:
                time.sleep(random.uniform(0.05, 0.3))
            return _ORIGINAL_CONNECT(sock, address)
        socket.socket.connect = _patched_connect

    def _resolve(self, host: str) -> str:
        try:
            return socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
        except Exception:
            return host

    def _is_in_scope(self, resolved: str, original: str) -> bool:
        if original in _AUTHORIZED_HOSTS:
            return True
        try:
            ip_obj = ipaddress.IPv4Address(resolved)
            return any(ip_obj in net for net in _AUTHORIZED_NETWORKS)
        except ValueError:
            return False

    def _log_to_dead_drop(self, target: str, action: str):
        try:
            import urllib.request
            event = {
                "t": time.time(),
                "target": hashlib.sha3_256(target.encode()).hex()[:16],
                "action": action,
                "device": hashlib.sha3_256(os.uname().nodename.encode()).hex()[:8],
            }
            payload = base64.b64encode(json.dumps(event).encode())
            proxy = urllib.request.ProxyHandler({
                "http": f"socks5h://{TOR_PROXY[0]}:{TOR_PROXY[1]}",
                "https": f"socks5h://{TOR_PROXY[0]}:{TOR_PROXY[1]}",
            })
            opener = urllib.request.build_opener(proxy)
            req = urllib.request.Request(
                "http://dead-drop.onion/api/ingest",
                data=payload,
                headers={"Content-Type": "application/octet-stream"},
                method="POST"
            )
            opener.open(req, timeout=15)
        except Exception:
            pass

    def _install_signals(self):
        import signal
        def _ghost(signum, frame):
            self._enter_ghost_mode()
        signal.signal(signal.SIGUSR1, _ghost)

    def _enter_ghost_mode(self):
        socket.socket.connect = _ORIGINAL_CONNECT
        _AUTHORIZED_NETWORKS.clear()
        _AUTHORIZED_HOSTS.clear()
        try:
            import subprocess
            subprocess.Popen(
                ["termux-open", "https://www.wikipedia.org"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
        os.kill(os.getpid(), 9)

    @staticmethod
    def status() -> dict:
        return {
            "active": socket.socket.connect != _ORIGINAL_CONNECT,
            "scope_loaded": len(_AUTHORIZED_NETWORKS) > 0,
            "networks": len(_AUTHORIZED_NETWORKS),
            "hosts": len(_AUTHORIZED_HOSTS),
        }


if __name__ == "__main__":
    print("[CORSET-TERMUX] Inicializando...")
    c = CorsetTermux()
    print(f"[CORSET-TERMUX] Activado. Redes: {c.status()['networks']}")
