"""
Network IDS — Reglas de detección de tráfico IoC
=================================================
Define patrones de red que identifican comunicación con C2 de spyware conocido.
Pensado para integrarse con Suricata/Zeek, o para usar como firma de matching
en captura de tráfico (pcap).

IMPORTANTE: Estas firmas son DEFENSIVAS. Sirven para DETECTAR en tu propia red,
no para atacar.
"""
import re
import json
import pathlib
from typing import List, Dict


# Formato compatible con Suricata rules
SURICATA_RULES = """
# SOURCESEAL RedTeam — Reglas IDS para detectar spyware C2

# NSO Pegasus
alert http any any -> $HOME_NET any (msg:"POTENTIAL Pegasus C2 beacon"; flow:to_server,established; http_uri; content:"/collector/heartbeat"; nocase; sid:1000001; rev:1;)
alert http any any -> $HOME_NET any (msg:"POTENTIAL Pegasus checkin"; flow:to_server,established; http_uri; content:"/api/v1/checkin"; nocase; sid:1000002; rev:1;)
alert tls any any -> any 443 (msg:"POTENTIAL Pegasus TLS fingerprint"; tls.cert_subject; content:"apple-updates"; sid:1000003; rev:1;)

# FinFisher / FinSpy
alert dns any any -> any 53 (msg:"FinFisher DNS query"; dns.query; content:"finfisher"; nocase; sid:1000010; rev:1;)
alert dns any any -> any 53 (msg:"Gamma Group DNS query"; dns.query; content:"gamma-international"; nocase; sid:1000011; rev:1;)

# HackingTeam / RCS
alert http any any -> $HOME_NET any (msg:"HackingTeam RCS upload"; flow:to_server,established; http_uri; content:"/log/upload"; nocase; sid:1000020; rev:1;)
alert dns any any -> any 53 (msg:"HackingTeam DNS query"; dns.query; content:"hackingteam"; nocase; sid:1000021; rev:1;)

# Candiru / Sourgum
alert dns any any -> any 53 (msg:"Candiru Sourgum DNS"; dns.query; content:"sourgum"; nocase; sid:1000030; rev:1;)
alert dns any any -> any 53 (msg:"Candiru DNS"; dns.query; content:"candiru"; nocase; sid:1000031; rev:1;)

# Stalkerware comercial
alert dns any any -> any 53 (msg:"mSpy DNS"; dns.query; content:"mspy"; nocase; sid:1000040; rev:1;)
alert dns any any -> any 53 (msg:"FlexiSpy DNS"; dns.query; content:"flexispy"; nocase; sid:1000041; rev:1;)
alert dns any any -> any 53 (msg:"Hoverwatch DNS"; dns.query; content:"hoverwatch"; nocase; sid:1000042; rev:1;)

# Patrones genéricos de exfiltración
alert http any any -> any any (msg:"POSSIBLE exfil — large POST"; flow:to_server,established; http_content_len:>1000000; sid:1000090; rev:1;)
alert tls any any -> any 443 (msg:"TLS to known-bad ASN"; tls.cert_issuer; content:"Let's Encrypt"; sid:1000091; rev:1;)

# iMessage / WhatsApp / Signal abuse
alert tcp any any -> $HOME_NET 5223 (msg:"Suspicious APNs connection — possible 0-click"; flow:to_server,established; sid:1000100; rev:1;)
""".strip()


# Patrones para matching en pcap (sin Suricata)
PCAP_PATTERNS = [
    # NSO
    (b"/collector/heartbeat", "nso", "Pegasus collector beacon"),
    (b"/api/v1/checkin", "nso", "Pegasus checkin endpoint"),
    (b"X-Device-Fingerprint", "nso", "Pegasus fingerprint header"),
    (b"PEGASUS_BRIDGE", "nso", "Pegasus bridge marker"),
    # FinFisher
    (b"finfisher", "finfisher", "FinFisher marker"),
    (b"FinSpy", "finfisher", "FinSpy marker"),
    (b"Gamma International", "finfisher", "Gamma Group marker"),
    # HackingTeam
    (b"HackingTeam", "hackingteam", "HT marker"),
    (b"/log/upload", "hackingteam", "RCS log upload"),
    (b"HT-RCS", "hackingteam", "RCS protocol marker"),
    # Candiru
    (b"sourgum", "candiru", "Sourgum marker"),
    (b"DevilsTongue", "candiru", "DevilsTongue marker"),
    # Stalkerware
    (b"mspy", "stalkerware", "mSpy beacon"),
    (b"flexispy", "stalkerware", "FlexiSpy beacon"),
    (b"/api/track", "stalkerware", "generic stalkerware track"),
    (b"/api/call", "stalkerware", "generic stalkerware call log"),
    (b"/api/sms", "stalkerware", "generic stalkerware sms"),
    (b"/api/location", "stalkerware", "generic stalkerware location"),
]


def write_suricata_rules(output_path: str):
    p = pathlib.Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(SURICATA_RULES + "\n")
    return str(p)


def match_pcap_payload(payload: bytes) -> List[Dict]:
    """Busca IoC en un payload de red."""
    hits = []
    for pattern, family, desc in PCAP_PATTERNS:
        if pattern in payload:
            hits.append({"family": family, "description": desc,
                         "pattern": pattern.decode(errors="ignore")})
    return hits


if __name__ == "__main__":
    out = write_suricata_rules("honeypot/network-ids/suricata.rules")
    print(f"✓ Reglas Suricata escritas en {out}")
    print(f"  Patrones PCAP: {len(PCAP_PATTERNS)}")
    # Demo
    test = b"POST /api/v1/checkin HTTP/1.1\r\nX-Device-Fingerprint: abc\r\n"
    hits = match_pcap_payload(test)
    print(f"  Demo match en payload de prueba: {hits}")
