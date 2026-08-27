"""
Utilidades para KRAKEN v3.0.
Helpers para IPs, CIDRs, validaciones, etc.
"""
import ipaddress
import socket
import re
import os
import hashlib
import random
import string
from typing import List, Tuple, Optional


def get_ips_from_cidr(cidr: str) -> List[str]:
    """
    Expande un CIDR a lista de IPs.
    Soporta: 192.168.1.0/24, 10.0.0.0/16, 192.168.1.5 (IP individual)
    """
    try:
        if "/" not in cidr:
            # IP individual
            ipaddress.ip_address(cidr)
            return [cidr]
        
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in network.hosts()]
    except ValueError as e:
        return []


def is_valid_ip(ip: str) -> bool:
    """Verifica si una IP es válida."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_cidr(cidr: str) -> bool:
    """Verifica si un CIDR es válido."""
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    """Verifica si una IP es privada."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def get_hostname(ip: str) -> Optional[str]:
    """Resuelve IP a hostname (DNS reverso)."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return None


def parse_ports(ports_str: str) -> List[int]:
    """
    Parsea string de puertos: '80,443,8080-8090' → [80, 443, 8080, ..., 8090]
    """
    result = []
    for part in ports_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            result.extend(range(int(start), int(end) + 1))
        elif part:
            result.append(int(part))
    return result


def random_id(length: int = 12) -> str:
    """Genera un ID aleatorio."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def hash_data(data: str, algorithm: str = "sha256") -> str:
    """Hash de datos."""
    h = hashlib.new(algorithm)
    h.update(data.encode())
    return h.hexdigest()


def format_bytes(size: int) -> str:
    """Formatea bytes a humano: 1.5 KB, 2.3 MB, etc."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
