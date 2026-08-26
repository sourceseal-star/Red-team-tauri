#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VENDOR DICTIONARIES - Diccionarios de Credenciales por Fabricante
=============================================================
Diccionarios completos de credenciales por defecto para diferentes fabricantes de dispositivos IoT.

Fabricantes soportados:
- Hikvision, Dahua, Axis, Uniview (Cámaras)
- Tenda, TP-Link, ASUS, Netgear, Linksys, Mercury (Routers)
- Xiongmai, Lorex, Swann, Annke (DVRs/NVRs)
- Xiaomi, Ezviz, Wyze (IoT)

Autor: Harold Paredes / SourceSeal Red Team
Uso: from seal.utils.vendor_dicts import VENDOR_CREDS
"""

from typing import Dict, List, Tuple


# ============================================================
# CÁMARAS DE SEGURIDAD
# ============================================================

HIKVISION_CREDS: List[Tuple[str, str]] = [
    # Credenciales por defecto
    ("admin", "12345"),
    ("admin", "admin"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", ""),
    ("12345", "12345"),
    
    # Credenciales comunes
    ("admin", "abc123"),
    ("admin", "1234"),
    ("admin", "111111"),
    ("admin", "666666"),
    ("admin", "888888"),
    ("admin", "000000"),
    ("admin", "12345678"),
    ("admin", "123456789"),
    ("admin", "qwerty"),
    ("admin", "letmein"),
    ("admin", "welcome"),
    ("admin", "monkey"),
    ("admin", "dragon"),
    ("admin", "passw0rd"),
    ("admin", "password1"),
    
    # Backdoors conocidas
    ("admin", "Hik12345"),
    ("admin", "Hikvision@123"),
    ("admin", "hik12345"),
    ("admin", "12345hik"),
    ("admin", "Hikvision123"),
    ("admin", "HikVision123"),
    ("admin", "hikvision123"),
    ("admin", "123456hik"),
    ("admin", "Hik@123"),
    ("admin", "Hik@2020"),
    
    # Variantes
    ("root", "root"),
    ("root", "12345"),
    ("root", "admin"),
    ("root", "toor"),
    ("root", "password"),
    
    ("user", "user"),
    ("user", "12345"),
    ("user", "password"),
    
    ("administrator", "administrator"),
    ("administrator", "admin"),
    ("administrator", "12345"),
    ("administrator", "password"),
]

DAHUA_CREDS: List[Tuple[str, str]] = [
    # Credenciales por defecto
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", ""),
    
    # Credenciales comunes
    ("admin", "dahua123"),
    ("admin", "Dahua123"),
    ("admin", "DAHUA123"),
    ("admin", "12345dahua"),
    ("admin", "dahua12345"),
    ("admin", "111111"),
    ("admin", "666666"),
    ("admin", "888888"),
    
    # Backdoors
    ("admin", "dahuatech"),
    ("admin", "DahuaTech"),
    ("admin", "DAHUATECH"),
    
    # Variantes
    ("root", "root"),
    ("root", "toor"),
    ("user", "user"),
    ("administrator", "administrator"),
]

AXIS_CREDS: List[Tuple[str, str]] = [
    # Credenciales por defecto
    ("root", "pass"),
    ("root", "root"),
    ("root", "12345"),
    ("root", "admin"),
    ("root", "password"),
    ("root", ""),
    
    # Credenciales comunes
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    
    # Backdoors
    ("root", "AXIS123"),
    ("root", "axis123"),
    ("admin", "AXIS123"),
    ("admin", "axis123"),
]

UNIVIEW_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "uniview"),
    ("admin", "UniView"),
    ("admin", "UNIVIEW"),
    ("admin", "12345uniview"),
    ("root", "root"),
    ("root", "toor"),
]

HONEYWELL_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "honeywell"),
    ("admin", "Honeywell"),
    ("admin", "HONEYWELL"),
    ("root", "root"),
]

BOSCH_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "bosch"),
    ("admin", "Bosch"),
    ("admin", "BOSCH"),
    ("root", "root"),
    ("service", "service"),
]


# ============================================================
# ROUTERS
# ============================================================

TENDA_CREDS: List[Tuple[str, str]] = [
    # Credenciales por defecto
    ("admin", "admin"),
    ("admin", ""),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    
    # Credenciales comunes
    ("admin", "tenda"),
    ("admin", "Tenda"),
    ("admin", "TENDA"),
    ("admin", "12345678"),
    ("admin", "88888888"),
    
    # Backdoors
    ("admin", "adminadmin"),
    ("admin", "11111111"),
    ("admin", "00000000"),
    
    # Variantes
    ("root", "root"),
    ("user", "user"),
]

TPLINK_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "tp-link"),
    ("admin", "TP-Link"),
    ("admin", "TPLINK"),
    ("root", "root"),
    ("user", "user"),
]

ASUS_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "12345"),
    ("admin", "asus"),
    ("admin", "ASUS"),
    ("admin", "Asus"),
    ("root", "root"),
    ("user", "user"),
]

NETGEAR_CREDS: List[Tuple[str, str]] = [
    ("admin", "password"),
    ("admin", "1234"),
    ("admin", "admin"),
    ("admin", ""),
    ("admin", "12345"),
    ("admin", "netgear"),
    ("admin", "NETGEAR"),
    ("root", "root"),
    ("user", "user"),
]

LINKSYS_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "1234"),
    ("admin", "12345"),
    ("admin", "linksys"),
    ("admin", "LINKSYS"),
    ("root", "root"),
    ("user", "user"),
]

MERCURY_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "1234"),
    ("admin", "12345"),
    ("admin", "mercury"),
    ("admin", "MERCURY"),
    ("root", "root"),
]


# ============================================================
# DVRs/NVRs
# ============================================================

XIONGMAI_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "xm"),
    ("admin", "Xiongmai"),
    ("admin", "XIONGMAI"),
    ("admin", "goolink"),
    ("admin", "GOOLINK"),
    ("root", "root"),
    ("root", "toor"),
    ("user", "user"),
]

LOREX_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "lorex"),
    ("admin", "Lorex"),
    ("admin", "LOREX"),
    ("root", "root"),
]

SWANN_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "swann"),
    ("admin", "SWANN"),
    ("root", "root"),
]

ANNKE_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "annke"),
    ("admin", "ANNKE"),
    ("root", "root"),
]


# ============================================================
# IoT
# ============================================================

XIAOMI_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("root", "root"),
    ("root", "toor"),
    ("user", "user"),
    ("developer", "developer"),
]

EZVIZ_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "ezviz"),
    ("admin", "EZVIZ"),
]

WYZE_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("wyze", "wyze"),
]


# ============================================================
# DICCIONARIO PRINCIPAL
# ============================================================

VENDOR_CREDS: Dict[str, List[Tuple[str, str]]] = {
    # Cámaras
    "hikvision": HIKVISION_CREDS,
    "dahua": DAHUA_CREDS,
    "axis": AXIS_CREDS,
    "uniview": UNIVIEW_CREDS,
    "honeywell": HONEYWELL_CREDS,
    "bosch": BOSCH_CREDS,
    
    # Routers
    "tenda": TENDA_CREDS,
    "tp-link": TPLINK_CREDS,
    "tp_link": TPLINK_CREDS,
    "asus": ASUS_CREDS,
    "netgear": NETGEAR_CREDS,
    "linksys": LINKSYS_CREDS,
    "mercury": MERCURY_CREDS,
    
    # DVRs/NVRs
    "xiongmai": XIONGMAI_CREDS,
    "lorex": LOREX_CREDS,
    "swann": SWANN_CREDS,
    "annke": ANNKE_CREDS,
    
    # IoT
    "xiaomi": XIAOMI_CREDS,
    "ezviz": EZVIZ_CREDS,
    "wyze": WYZE_CREDS,
    "wyzecam": WYZE_CREDS,
}

# Credenciales genéricas (para dispositivos desconocidos)
GENERIC_CREDS: List[Tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", ""),
    ("root", "root"),
    ("root", "toor"),
    ("root", "password"),
    ("user", "user"),
    ("user", "password"),
    ("administrator", "administrator"),
    ("administrator", "admin"),
    ("administrator", "password"),
    ("guest", "guest"),
    ("guest", "12345"),
    ("operator", "operator"),
    ("supervisor", "supervisor"),
    ("service", "service"),
    ("ubnt", "ubnt"),
    ("admin", "admin123"),
    ("support", "support"),
]


# ============================================================
# FUNCIONES ÚTILES
# ============================================================

def get_vendor_creds(vendor: str) -> List[Tuple[str, str]]:
    """Obtiene las credenciales para un fabricante específico."""
    vendor_lower = vendor.lower()
    return VENDOR_CREDS.get(vendor_lower, GENERIC_CREDS)


def get_all_creds() -> List[Tuple[str, str]]:
    """Obtiene todas las credenciales de todos los fabricantes."""
    all_creds = []
    for creds in VENDOR_CREDS.values():
        all_creds.extend(creds)
    
    # Eliminar duplicados
    seen = set()
    unique_creds = []
    for cred in all_creds:
        if cred not in seen:
            seen.add(cred)
            unique_creds.append(cred)
    
    return unique_creds + GENERIC_CREDS


def get_creds_for_type(device_type: str) -> List[Tuple[str, str]]:
    """Obtiene credenciales según el tipo de dispositivo."""
    type_creds = {
        "camera": HIKVISION_CREDS + DAHUA_CREDS + AXIS_CREDS + UNIVIEW_CREDS + GENERIC_CREDS,
        "dvr": XIONGMAI_CREDS + LOREX_CREDS + SWANN_CREDS + ANNKE_CREDS + GENERIC_CREDS,
        "nvr": XIONGMAI_CREDS + LOREX_CREDS + SWANN_CREDS + ANNKE_CREDS + GENERIC_CREDS,
        "router": TENDA_CREDS + TPLINK_CREDS + ASUS_CREDS + NETGEAR_CREDS + LINKSYS_CREDS + MERCURY_CREDS + GENERIC_CREDS,
        "iot": XIAOMI_CREDS + EZVIZ_CREDS + WYZE_CREDS + GENERIC_CREDS,
    }
    
    return type_creds.get(device_type.lower(), GENERIC_CREDS)


# ============================================================
# ESTADÍSTICAS
# ============================================================

def get_stats() -> Dict:
    """Obtiene estadísticas de los diccionarios."""
    stats = {
        "total_vendors": len(VENDOR_CREDS),
        "total_credentials": 0,
        "vendors": {}
    }
    
    for vendor, creds in VENDOR_CREDS.items():
        stats["total_credentials"] += len(creds)
        stats["vendors"][vendor] = len(creds)
    
    stats["total_credentials"] += len(GENERIC_CREDS)
    stats["generic_credentials"] = len(GENERIC_CREDS)
    
    return stats


if __name__ == "__main__":
    print("="*70)
    print("  VENDOR DICTIONARIES - Estadísticas")
    print("="*70)
    
    stats = get_stats()
    
    print(f"\n📊 Estadísticas:")
    print(f"  Fabricantes: {stats['total_vendors']}")
    print(f"  Credenciales totales: {stats['total_credentials']}")
    print(f"  Credenciales genéricas: {stats['generic_credentials']}")
    
    print(f"\n📋 Por fabricante:")
    for vendor, count in sorted(stats["vendors"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {vendor:15} : {count} credenciales")
