#!/usr/bin/env python3
"""
Corset Digital -- Adaptacion Replit (Cloud Container)
====================================================
- Sin acceso a raw sockets
- Sin eBPF
- Sin archivos persistentes entre reinicios
- Scope se carga desde variable de entorno CORSET_SCOPE_B64
- Hook de socket en userspace
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
from typing import Set

_AUTHORIZED_NETWORKS: Set[ipaddress.IPv4Network] = set()
_AUTHORIZED_HOSTS: Set[str] = set()
_ORIGINAL_CONNECT = socket.socket.connect


class CorsetReplit:
    def __init__(self, enforce: bool = True):
        self.enforce = enforce
        self._load_scope_from_env()
        if enforce:
            self._hook_socket()

    def _load_scope_from_env(self):
        scope_b64 = os.environ.get("CORSET_SCOPE_B64", "")
        if not scope_b64:
            raise RuntimeError(
                "[CORSET-REPLIT] Sin scope. Configura el Secret CORSET_SCOPE_B64:\n"
                '  {"networks": ["192.168.1.0/24"], "hosts": ["target.local"]}'
            )
        try:
            raw = base64.b64decode(scope_b64)
            data = json.loads(raw)
            for net in data.get("networks", []):
                _AUTHORIZED_NETWORKS.add(ipaddress.IPv4Network(net))
            for host in data.get("hosts", []):
                _AUTHORIZED_HOSTS.add(host)
        except Exception as e:
            raise RuntimeError(f"[CORSET] Scope invalido: {e}")

    def _hook_socket(self):
        def _patched_connect(sock, address):
            ip, port = address
            resolved = self._resolve(ip)
            if not self._is_in_scope(resolved, ip):
                time.sleep(random.uniform(0.5, 2.0))
                raise OSError(113, "No route to host")
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

    @staticmethod
    def status() -> dict:
        return {
            "active": socket.socket.connect != _ORIGINAL_CONNECT,
            "networks": len(_AUTHORIZED_NETWORKS),
            "hosts": len(_AUTHORIZED_HOSTS),
        }


if __name__ == "__main__":
    print("[CORSET-REPLIT] Inicializando...")
    c = CorsetReplit()
    print(f"[CORSET-REPLIT] Activado. Redes: {c.status()['networks']}")
