#!/usr/bin/env python3
"""
DNS Sinkhole — Resuelve dominios IoC de spyware hacia el C2 sinkhole local
============================================================================
Cuando un dispositivo infectado intenta resolver un dominio de C2 conocido
(NSO, FinFisher, HackingTeam, Candiru, stalkerware comercial), este DNS
responde con la IP del sinkhole C2. El spyware termina hablando con nosotros
en vez de con su C2 real — y capturamos todo.

Solo usar en:
- Dispositivos donde el usuario dio consentimiento (app de seguridad con opt-in)
- Laboratorio de análisis forense
- Honeynet corporativo autorizado
"""
import os
import json
import socket
import struct
import threading
import time
import datetime
import secrets
import pathlib
from collections import defaultdict

EVIDENCE = pathlib.Path(__file__).parent.parent.parent / "evidence" / "dns-sinkhole"
EVIDENCE.mkdir(parents=True, exist_ok=True)

# Dominios IoC conocidos de C2 de spyware (whitelist de detección, NO para atacar)
KNOWN_C2_DOMAINS = {
    # NSO Group / Pegasus — dominios históricos
    "nso": [
        "nso-group.com", "nsogroup.com", "pegasus-c2.net", "cdn-icloud.com",
        "apple-updates.org", "push-apple.com", "ios-updates.net",
    ],
    # FinFisher / FinSpy
    "finfisher": [
        "finfisher.com", "finspy.info", "gamma-international.com",
        "support-intl.com", "eltels.net",
    ],
    # HackingTeam / RCS
    "hackingteam": [
        "hackingteam.com", "ht-cdn.com", "rcs-collector.net",
        "hackingteam.it",
    ],
    # Candiru / DevilsTongue / Sourgum
    "candiru": [
        "candiru.com", "sourgum.io", "devilstone.com",
    ],
    # Stalkerware comercial
    "stalkerware": [
        "mspy.com", "flexispy.com", "hoverwatch.com", "spybubble.com",
        "highster-mobile.com", "xnspy.com", "cocospy.com",
    ],
}

SINKHOLE_IP = os.environ.get("SINKHOLE_IP", "127.0.0.1")
STATS = defaultdict(int)
ATTACK_LOG = []


def _build_dns_response(query_data: bytes, answer_ip: str) -> bytes:
    """Construye una respuesta DNS A simple."""
    # Transaction ID + flags (respuesta estándar, no autoritativa)
    txn_id = query_data[:2]
    flags = struct.pack(">H", 0x8180)
    counts = struct.pack(">HHHH", 1, 1, 0, 0)  # 1 question, 1 answer
    question = query_data[12:]  # resto (query completa)
    # Answer: pointer al name, type A, class IN, TTL 300, rdlength 4, rdata
    answer = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + \
             socket.inet_aton(answer_ip)
    return txn_id + flags + counts + question + answer


def _extract_domain(query_data: bytes) -> str:
    """Extrae el dominio de un query DNS."""
    try:
        i = 12  # skip header
        labels = []
        while i < len(query_data):
            length = query_data[i]
            if length == 0:
                break
            i += 1
            labels.append(query_data[i:i+length].decode(errors="ignore"))
            i += length
        return ".".join(labels).lower()
    except Exception:
        return ""


def _classify_domain(domain: str) -> dict:
    """Clasifica un dominio contra las familias de IoC conocidas."""
    matches = []
    for family, domains in KNOWN_C2_DOMAINS.items():
        for d in domains:
            if d in domain or domain.endswith("." + d):
                matches.append({"family": family, "domain": d})
    return {
        "looks_like_c2": bool(matches),
        "matches": matches,
        "severity": "critical" if any(m["family"] in ("nso", "candiru") for m in matches)
                    else "high" if matches else "info",
    }


def _log_dns_event(client: str, domain: str, classification: dict):
    event = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "client": client,
        "domain": domain,
        "classification": classification,
        "sinkholed_to": SINKHOLE_IP,
    }
    ATTACK_LOG.append(event)
    fname = EVIDENCE / f"dns-{int(time.time()*1000)}-{secrets.token_hex(2)}.json"
    fname.write_text(json.dumps(event, indent=2, ensure_ascii=False))
    if classification["looks_like_c2"]:
        STATS["c2_queries"] += 1
        alert = EVIDENCE / f"!!DNS-C2-{int(time.time())}-{secrets.token_hex(2)}.json"
        alert.write_text(json.dumps({
            "alert": "POSIBLE C2 SPYWARE — DOMINIO IoC RESUELTO",
            **event,
        }, indent=2))
    STATS["total_queries"] += 1


def dns_handler(sock: socket.socket):
    """Loop principal del DNS sinkhole."""
    sock.settimeout(1.0)
    print(f"🍯  DNS Sinkhole UDP :53 → {SINKHOLE_IP} (C2 sinkhole)")
    while True:
        try:
            data, addr = sock.recvfrom(512)
            domain = _extract_domain(data)
            if not domain:
                continue
            classification = _classify_domain(domain)
            _log_dns_event(addr[0], domain, classification)
            response = _build_dns_response(data, SINKHOLE_IP)
            sock.sendto(response, addr)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[dns-sinkhole] error: {e}")


def start(port: int = 53, host: str = "0.0.0.0"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except PermissionError:
        print(f"[!] Puerto {port} requiere root. Usa 5353 o ejecuta como root.")
        port = 5353
        sock.bind((host, port))

    print(f"🍯  DNS Sinkhole activo en {host}:{port}")
    print(f"    Familias IoC: {', '.join(KNOWN_C2_DOMAINS.keys())}")
    print(f"    Evidencia: {EVIDENCE}")
    dns_handler(sock)


if __name__ == "__main__":
    port = int(os.environ.get("DNS_PORT", 53))
    start(port)
