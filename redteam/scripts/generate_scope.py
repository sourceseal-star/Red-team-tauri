#!/usr/bin/env python3
"""
Generador de scope universal.
Uso:
  # Termux / local (archivo binario)
  python3 generate_scope.py --networks 192.168.1.0/24,10.0.0.0/8 --output ~/.corset/scope.bin

  # Replit (base64 para Secrets)
  python3 generate_scope.py --networks 192.168.1.0/24 --replit
"""
import struct
import argparse
import ipaddress
import hashlib
import json
import base64
from pathlib import Path


def generate_binary(networks, hosts, output: Path):
    data = bytearray()
    nets = [ipaddress.IPv4Network(n) for n in networks]
    data += struct.pack(">I", len(nets))
    for net in nets:
        ip_int = int(net.network_address)
        mask = net.prefixlen
        data += struct.pack(">IB", ip_int, mask)
    data += struct.pack(">I", len(hosts))
    for host in hosts:
        hbytes = host.encode("utf-8")
        data += struct.pack(">B", len(hbytes))
        data += hbytes
    output.write_bytes(data)
    sig = hashlib.sha3_256(data).digest()[:32]
    output.with_suffix(".sig").write_bytes(sig)
    print(f"[GEN] Scope binario: {output}")
    print(f"[GEN] Firma: {output.with_suffix('.sig')}")


def generate_replit(networks, hosts):
    data = json.dumps({"networks": networks, "hosts": hosts}).encode()
    b64 = base64.b64encode(data).decode()
    print("[GEN] Copia esto en Replit Secrets como CORSET_SCOPE_B64:")
    print(b64)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--networks", required=True)
    parser.add_argument("--hosts", default="")
    parser.add_argument("--output", default="~/.corset/scope.bin")
    parser.add_argument("--replit", action="store_true")
    args = parser.parse_args()

    nets = [n.strip() for n in args.networks.split(",") if n.strip()]
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]

    if args.replit:
        generate_replit(nets, hosts)
    else:
        generate_binary(nets, hosts, Path(args.output).expanduser())
