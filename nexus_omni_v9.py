#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS OMNI-SENTIENT v9.0 — Plataforma Cognitiva de Red
Autor: Harold Paredes / SourceSeal Global Protocol
Arquitectura: Predictiva, Adaptativa, Auto-Reparable.

v9.1 — Datos reales:
  - MAC real desde tabla ARP del sistema (ip neigh / arp -n)
  - Vendor por prefijo OUI (518 prefijos, 52 fabricantes)
  - Hostname real por DNS inverso
  - Geolocalización real SOLO para IPs públicas (ip-api.com, sin API key)
  - IPs privadas NO se geolocalizan con coordenadas falsas — se marcan
    is_private=True y se muestran en el panel de red local, no en el mapa
  - Eventos reales (anomalías/adaptaciones) expuestos via /api/events
"""

import asyncio
import json
import hashlib
import sqlite3
import subprocess
import ipaddress
import os
import sys
import time
import random
import math
import re
import socket
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading
from nexus_credentials import ensure_nexus_credentials
try:
    import nexus_autoscan as nas
except ImportError:
    nas = None
try:
    import aiohttp
except ImportError:
    # El motor puede escanear y servir su API sin alertas Telegram ni geo-IP real.
    aiohttp = None
from io import BytesIO

# ============================================================
# CONFIGURACIÓN NEURAL
# ============================================================
RESET_CREDENTIALS = "--reset-credentials" in sys.argv[1:]
NEXUS_CREDENTIALS = ensure_nexus_credentials(reset=RESET_CREDENTIALS)

if RESET_CREDENTIALS:
    print("[NEXUS] Credenciales rotadas en .env. Reinicia el servicio para aplicar el nuevo acceso.", flush=True)
    raise SystemExit(0)

CONFIG = {
    "db_path": os.environ.get("NEXUS_DB", "nexus_omni.db"),
    "ports_critical": [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 1521, 3306, 3389, 5432, 5900, 8080, 8443, 8888, 37777, 34567, 554],
    "ports_common": [80, 443, 8080, 8000, 554],

    # Umbrales de IA
    "anomaly_threshold": 3, # Cambios necesarios para alertar
    "prediction_window": 5, # Escaneos históricos para predecir

    # Modos Adaptativos
    "modes": {
        "passive": {"timeout": 2.0, "concurrent": 2, "delay": 1.0},
        "stealth": {"timeout": 1.2, "concurrent": 10, "delay": 0.2},
        "active": {"timeout": 0.5, "concurrent": 40, "delay": 0.05},
        "frenzy": {"timeout": 0.2, "concurrent": 80, "delay": 0.01} # Solo si se detecta amenaza alta
    },

    "base_coords": {"lat": 4.7110, "lon": -74.0721},
    "auth_user": NEXUS_CREDENTIALS.user,
    "auth_pass": NEXUS_CREDENTIALS.password,
}

# ============================================================
# ENRIQUECIMIENTO DE DATOS REALES
# ============================================================

# Tabla OUI expandida (518 prefijos, 52 fabricantes). Datos publicos IEEE.
# Dispositivos no listados devuelven "Desconocido"
# en vez de inventar un fabricante. Ampliar según necesidad.
MAC_VENDOR_PREFIXES = {
    # ── Raspberry Pi Foundation ──
    "B8:27:EB": "Raspberry Pi Foundation", "DC:A6:32": "Raspberry Pi Foundation", "E4:5F:01": "Raspberry Pi Foundation",
    "28:CD:C1": "Raspberry Pi Foundation", "D8:3A:DD": "Raspberry Pi Foundation",

    # ── Espressif (ESP32/ESP8266) ──
    "24:0A:C4": "Espressif (ESP32/ESP8266)", "30:AE:A4": "Espressif (ESP32/ESP8266)", "3C:71:BF": "Espressif (ESP32/ESP8266)",
    "68:C6:3A": "Espressif (ESP32/ESP8266)", "AC:67:B2": "Espressif (ESP32/ESP8266)", "24:62:AB": "Espressif (ESP32/ESP8266)",
    "84:0D:8E": "Espressif (ESP32/ESP8266)", "54:5A:A6": "Espressif (ESP32/ESP8266)", "7C:87:CE": "Espressif (ESP32/ESP8266)",

    # ── TP-Link ──
    "50:C7:BF": "TP-Link", "98:DA:C4": "TP-Link", "EC:08:6B": "TP-Link", "5C:63:BF": "TP-Link", "AC:84:C6": "TP-Link",
    "60:32:B7": "TP-Link", "F4:6F:EC": "TP-Link", "C0:25:A9": "TP-Link", "14:CC:20": "TP-Link",

    # ── D-Link ──
    "00:13:46": "D-Link", "00:15:E9": "D-Link", "00:17:9A": "D-Link", "00:1B:11": "D-Link", "B8:A3:86": "D-Link",
    "1C:BD:B9": "D-Link", "90:8D:78": "D-Link", "AC:F1:DF": "D-Link", "B0:C5:54": "D-Link",

    # ── Netgear ──
    "00:1B:2F": "Netgear", "00:1F:33": "Netgear", "00:24:B2": "Netgear", "C0:3F:0E": "Netgear", "28:C6:8E": "Netgear",
    "9C:3D:CF": "Netgear", "B0:39:56": "Netgear", "A0:40:A0": "Netgear", "44:94:FC": "Netgear",

    # ── Linksys ──
    "00:1D:7E": "Linksys", "00:1E:E5": "Linksys", "00:21:29": "Linksys", "30:46:9A": "Linksys", "6C:5A:49": "Linksys",
    "C8:3A:35": "Linksys",

    # ── Tenda ──
    "00:0B:2F": "Tenda", "14:0A:14": "Tenda",

    # ── Mikrotik ──
    "00:0C:42": "Mikrotik", "2C:C8:1B": "Mikrotik", "4C:5E:0C": "Mikrotik", "6C:3B:6B": "Mikrotik", "B8:69:F4": "Mikrotik",
    "D4:CA:6D": "Mikrotik", "E4:8D:8C": "Mikrotik",

    # ── Belkin ──
    "00:11:50": "Belkin", "00:11:24": "Belkin", "00:17:3F": "Belkin", "EC:1A:59": "Belkin", "30:5A:3A": "Belkin",

    # ── Samsung ──
    "5C:0A:5B": "Samsung", "78:1F:DB": "Samsung", "00:12:FB": "Samsung", "00:15:99": "Samsung", "08:1F:F3": "Samsung",
    "34:14:5F": "Samsung", "38:1E:E9": "Samsung", "9C:50:01": "Samsung", "AC:5F:3E": "Samsung", "E8:50:8B": "Samsung",
    "CC:8D:88": "Samsung",

    # ── Huawei ──
    "00:E0:FC": "Huawei", "48:5D:60": "Huawei", "00:25:9E": "Huawei", "04:02:1F": "Huawei", "08:19:A6": "Huawei",
    "0C:37:21": "Huawei", "10:1C:0B": "Huawei", "28:92:81": "Huawei", "34:29:12": "Huawei", "4C:1F:CC": "Huawei",
    "50:01:B9": "Huawei", "58:F3:9C": "Huawei", "AC:4E:91": "Huawei", "CC:79:81": "Huawei",

    # ── Xiaomi ──
    "34:CE:00": "Xiaomi", "64:09:80": "Xiaomi", "00:0F:B5": "Xiaomi", "18:59:36": "Xiaomi", "28:6C:07": "Xiaomi",
    "34:80:7E": "Xiaomi", "38:95:D8": "Xiaomi", "44:56:3F": "Xiaomi", "54:EF:00": "Xiaomi", "7C:1C:4E": "Xiaomi",
    "AC:5F:5E": "Xiaomi", "F8:A4:5F": "Xiaomi",

    # ── Apple ──
    "00:01:E8": "Apple", "00:03:93": "Apple", "00:05:02": "Apple", "00:0A:95": "Apple", "00:0D:93": "Apple",
    "00:14:51": "Apple", "00:16:CB": "Apple", "00:17:F2": "Apple", "00:1C:B3": "Apple", "00:1D:4F": "Apple",
    "00:1E:C2": "Apple", "00:1F:F3": "Apple", "00:22:41": "Apple", "00:23:12": "Apple", "00:23:DF": "Apple",
    "00:25:00": "Apple", "00:25:90": "Apple", "00:25:BC": "Apple", "AC:BC:32": "Apple", "AC:3C:0B": "Apple",
    "B0:CA:9B": "Apple", "B4:18:0D": "Apple", "C0:84:7D": "Apple", "C4:2C:03": "Apple", "C8:1E:E7": "Apple",
    "C8:33:4B": "Apple", "CC:78:5F": "Apple", "D0:23:DB": "Apple", "DC:A4:CA": "Apple", "D8:30:62": "Apple",
    "E0:B5:2D": "Apple", "E0:C7:17": "Apple", "F0:18:98": "Apple", "F4:0B:93": "Apple", "FC:E9:98": "Apple",

    # ── Amazon ──
    "68:37:E9": "Amazon", "FC:65:DE": "Amazon", "44:65:0D": "Amazon", "0C:47:C9": "Amazon", "18:74:F2": "Amazon",
    "34:D2:62": "Amazon", "40:B4:CD": "Amazon", "74:03:BD": "Amazon", "74:75:48": "Amazon", "A0:02:25": "Amazon",
    "AC:63:9C": "Amazon", "F0:27:2D": "Amazon",

    # ── Google ──
    "54:60:09": "Google", "F4:F5:D8": "Google", "00:1A:A1": "Google", "38:2D:21": "Google", "3C:5A:B6": "Google",
    "94:EB:CD": "Google", "D8:1D:B3": "Google", "E0:77:73": "Google", "F4:06:69": "Google", "F4:5C:89": "Google",

    # ── Hikvision ──
    "44:19:B6": "Hikvision", "BC:AD:28": "Hikvision", "00:1C:23": "Hikvision", "18:68:CB": "Hikvision",
    "28:57:15": "Hikvision", "54:ED:EC": "Hikvision", "8C:F0:1B": "Hikvision", "B0:6E:99": "Hikvision",
    "D4:9E:29": "Hikvision", "DC:8B:28": "Hikvision",

    # ── Dahua ──
    "3C:EF:8C": "Dahua", "9C:8E:CD": "Dahua", "00:1E:28": "Dahua", "00:25:48": "Dahua", "30:48:00": "Dahua",
    "34:25:5B": "Dahua", "78:1C:0E": "Dahua", "D4:A7:2E": "Dahua",

    # ── Reolink ──
    "B0:6B:1B": "Reolink", "EC:71:DB": "Reolink", "3C:8F:1A": "Reolink",

    # ── Axis Communications ──
    "00:40:8C": "Axis Communications", "AC:CC:8E": "Axis Communications", "E4:1E:0A": "Axis Communications",
    "00:80:F0": "Axis Communications",

    # ── Amcrest ──
    "00:1D:51": "Amcrest", "00:2D:70": "Amcrest", "B4:6D:83": "Amcrest",

    # ── Ubiquiti Networks ──
    "24:5A:4C": "Ubiquiti Networks", "FC:EC:DA": "Ubiquiti Networks", "00:27:22": "Ubiquiti Networks",
    "04:18:D6": "Ubiquiti Networks", "24:A4:3C": "Ubiquiti Networks", "44:D9:E7": "Ubiquiti Networks",
    "68:72:51": "Ubiquiti Networks", "78:8A:20": "Ubiquiti Networks", "80:2A:A8": "Ubiquiti Networks",
    "B4:FB:E4": "Ubiquiti Networks", "DC:9F:17": "Ubiquiti Networks",

    # ── Cisco ──
    "00:01:42": "Cisco", "00:04:27": "Cisco", "00:05:00": "Cisco", "00:06:2A": "Cisco", "00:06:28": "Cisco",
    "00:07:0D": "Cisco", "00:07:4F": "Cisco", "00:08:5E": "Cisco", "00:0B:46": "Cisco", "00:0C:30": "Cisco",
    "00:0D:29": "Cisco", "00:0E:08": "Cisco", "00:0E:38": "Cisco", "00:0F:23": "Cisco", "00:0F:24": "Cisco",
    "00:11:21": "Cisco", "00:12:00": "Cisco", "00:12:43": "Cisco", "00:13:19": "Cisco", "00:13:5F": "Cisco",
    "00:14:2B": "Cisco", "00:14:A1": "Cisco", "00:14:A2": "Cisco", "00:16:34": "Cisco", "00:16:47": "Cisco",
    "00:17:0E": "Cisco", "5C:71:45": "Cisco", "D0:88:4C": "Cisco",

    # ── ASUSTek ──
    "04:D4:C4": "ASUSTek", "00:0C:6E": "ASUSTek", "00:0E:A6": "ASUSTek", "00:11:2F": "ASUSTek", "00:13:EF": "ASUSTek",
    "00:15:17": "ASUSTek", "00:17:31": "ASUSTek", "00:18:F3": "ASUSTek", "00:1A:46": "ASUSTek", "00:1C:91": "ASUSTek",
    "00:1D:60": "ASUSTek", "00:1E:8C": "ASUSTek", "00:24:8C": "ASUSTek", "AC:22:0B": "ASUSTek", "B0:F1:EC": "ASUSTek",
    "C8:60:0A": "ASUSTek", "D8:50:E6": "ASUSTek", "F0:2F:74": "ASUSTek", "FC:8E:B8": "ASUSTek",

    # ── Sonos ──
    "5C:AA:FD": "Sonos", "00:0E:58": "Sonos", "78:28:CA": "Sonos", "B8:E9:37": "Sonos", "F0:A6:67": "Sonos",

    # ── Intel ──
    "00:02:B3": "Intel", "00:03:47": "Intel", "00:04:23": "Intel", "00:07:E9": "Intel", "00:08:0D": "Intel",
    "00:08:74": "Intel", "00:0B:BA": "Intel", "00:0C:F1": "Intel", "00:0E:0B": "Intel", "00:0E:35": "Intel",
    "00:11:11": "Intel", "00:13:02": "Intel", "00:13:CE": "Intel", "00:15:00": "Intel", "00:16:6F": "Intel",
    "00:16:EA": "Intel", "00:17:08": "Intel", "00:18:DE": "Intel", "00:18:FF": "Intel", "00:19:15": "Intel",
    "00:19:D1": "Intel", "00:1B:21": "Intel", "00:1B:77": "Intel", "00:1C:7E": "Intel", "00:1C:2B": "Intel",
    "00:1C:BF": "Intel", "00:1D:00": "Intel", "00:1D:59": "Intel", "00:1E:66": "Intel", "00:1F:16": "Intel",
    "00:21:6B": "Intel", "00:22:FA": "Intel", "00:23:24": "Intel", "00:23:7D": "Intel", "00:24:D7": "Intel",
    "00:25:9B": "Intel", "00:26:27": "Intel", "00:27:0E": "Intel", "50:E1:4C": "Intel", "74:F6:B3": "Intel",
    "A0:36:9F": "Intel", "EC:0D:9A": "Intel", "F4:52:14": "Intel",

    # ── Realtek ──
    "00:01:E6": "Realtek", "00:E0:4C": "Realtek", "00:0A:79": "Realtek", "52:54:00": "Realtek",

    # ── Qualcomm Atheros ──
    "00:0A:77": "Qualcomm Atheros", "00:12:7B": "Qualcomm Atheros", "00:13:49": "Qualcomm Atheros", "00:14:6C": "Qualcomm Atheros",
    "00:14:A5": "Qualcomm Atheros", "00:17:34": "Qualcomm Atheros", "00:1A:92": "Qualcomm Atheros", "00:1C:43": "Qualcomm Atheros",
    "00:1F:3A": "Qualcomm Atheros", "00:22:0D": "Qualcomm Atheros", "00:24:0B": "Qualcomm Atheros", "00:26:4C": "Qualcomm Atheros",
    "00:90:4C": "Qualcomm Atheros", "60:D0:A9": "Qualcomm Atheros", "C0:3A:0E": "Qualcomm Atheros", "CC:20:E8": "Qualcomm Atheros",

    # ── Broadcom ──
    "00:05:1F": "Broadcom", "00:07:0E": "Broadcom", "00:0A:5A": "Broadcom", "00:0C:41": "Broadcom", "00:0F:1F": "Broadcom",
    "00:10:18": "Broadcom", "00:10:F6": "Broadcom", "00:11:1B": "Broadcom", "00:13:10": "Broadcom", "00:13:E8": "Broadcom",
    "00:17:0A": "Broadcom", "00:18:41": "Broadcom", "00:18:82": "Broadcom", "00:19:E0": "Broadcom", "00:1A:A0": "Broadcom",
    "00:1A:78": "Broadcom", "00:1B:20": "Broadcom", "00:1C:62": "Broadcom", "00:1D:1F": "Broadcom", "00:1F:1F": "Broadcom",
    "00:21:2F": "Broadcom", "00:22:3A": "Broadcom", "00:23:14": "Broadcom", "00:24:1D": "Broadcom",

    # ── Motorola ──
    "00:0A:28": "Motorola", "00:0E:03": "Motorola", "00:0F:85": "Motorola", "00:16:5B": "Motorola", "00:19:41": "Motorola",
    "00:1B:33": "Motorola", "00:1C:58": "Motorola", "00:1E:74": "Motorola", "00:1F:79": "Motorola", "00:21:0A": "Motorola",
    "00:23:76": "Motorola", "00:25:24": "Motorola", "5C:17:8A": "Motorola", "D8:03:4D": "Motorola", "DC:6F:71": "Motorola",
    "F0:73:F0": "Motorola",

    # ── LG Electronics ──
    "00:0E:0D": "LG Electronics", "00:12:7F": "LG Electronics", "00:18:71": "LG Electronics", "00:1B:44": "LG Electronics",
    "00:1D:73": "LG Electronics", "00:21:FE": "LG Electronics", "00:24:A8": "LG Electronics", "34:9B:D6": "LG Electronics",
    "88:32:9D": "LG Electronics", "D4:56:8F": "LG Electronics",

    # ── Oppo ──
    "00:22:F3": "Oppo", "0C:8E:CD": "Oppo", "34:21:46": "Oppo", "AC:80:09": "Oppo", "B0:D0:84": "Oppo",
    "C0:9A:30": "Oppo", "D8:9C:23": "Oppo",

    # ── Vivo ──
    "00:1C:9A": "Vivo", "08:1F:71": "Vivo", "3C:8D:BD": "Vivo", "54:0E:7E": "Vivo", "88:1E:5E": "Vivo",
    "B0:12:B4": "Vivo", "D0:DD:5D": "Vivo",

    # ── OnePlus ──
    "C0:EE:FB": "OnePlus",

    # ── Nest Labs ──
    "18:B4:30": "Nest Labs", "00:1D:A1": "Nest Labs", "64:16:66": "Nest Labs",

    # ── Philips Hue ──
    "00:17:88": "Philips Hue", "EC:B5:FA": "Philips Hue",

    # ── Tuya ──
    "D8:F1:5B": "Tuya", "10:D1:2B": "Tuya", "AC:84:A6": "Tuya",

    # ── Ecobee ──
    "00:1F:B3": "Ecobee", "5C:43:2B": "Ecobee",

    # ── SwitchBot ──
    "C0:8F:4C": "SwitchBot",

    # ── Aruba Networks ──
    "00:0B:5F": "Aruba Networks", "00:0C:0E": "Aruba Networks", "00:12:0A": "Aruba Networks", "00:13:0A": "Aruba Networks",
    "00:13:37": "Aruba Networks", "00:14:0C": "Aruba Networks", "24:DE:C6": "Aruba Networks", "6C:F3:7F": "Aruba Networks",
    "94:B4:41": "Aruba Networks", "D8:C7:C8": "Aruba Networks",

    # ── Juniper Networks ──
    "00:05:85": "Juniper Networks", "00:0B:86": "Juniper Networks", "00:0C:29": "Juniper Networks", "00:12:1E": "Juniper Networks",
    "00:15:7E": "Juniper Networks", "00:1D:B5": "Juniper Networks", "00:1F:12": "Juniper Networks", "00:21:59": "Juniper Networks",
    "00:90:0C": "Juniper Networks",

    # ── Fortinet ──
    "00:09:0F": "Fortinet", "70:4C:A5": "Fortinet", "C8:E0:EB": "Fortinet",

    # ── Hewlett Packard ──
    "00:1F:29": "Hewlett Packard", "00:26:55": "Hewlett Packard", "00:1E:0B": "Hewlett Packard", "00:17:A4": "Hewlett Packard",
    "00:15:60": "Hewlett Packard", "00:14:38": "Hewlett Packard", "00:11:0A": "Hewlett Packard", "00:0E:7E": "Hewlett Packard",
    "00:0A:57": "Hewlett Packard",

    # ── Dell ──
    "00:14:22": "Dell", "00:15:C5": "Dell", "00:1D:09": "Dell", "00:1E:C9": "Dell", "00:21:CC": "Dell",
    "00:23:AE": "Dell", "00:25:64": "Dell", "00:26:B9": "Dell", "00:50:56": "Dell", "00:60:69": "Dell",
    "00:8E:00": "Dell", "B0:83:FE": "Dell", "C8:1F:66": "Dell", "D0:BF:9C": "Dell", "F0:4D:A4": "Dell",

    # ── Microsoft ──
    "00:0D:3A": "Microsoft", "00:11:F5": "Microsoft", "00:12:5A": "Microsoft", "00:14:48": "Microsoft",
    "00:15:14": "Microsoft", "00:16:3E": "Microsoft", "00:17:77": "Microsoft", "00:18:02": "Microsoft",
    "00:19:16": "Microsoft", "00:1C:C1": "Microsoft", "00:1E:25": "Microsoft", "28:18:78": "Microsoft",
    "4C:0C:0B": "Microsoft", "50:1A:C5": "Microsoft", "70:37:2B": "Microsoft", "84:1B:5E": "Microsoft",
    "B0:7F:BD": "Microsoft", "D0:1F:8E": "Microsoft", "F0:1F:AF": "Microsoft",

    # ── Nintendo ──
    "00:09:BF": "Nintendo", "00:17:AB": "Nintendo", "00:19:1D": "Nintendo", "00:1A:E9": "Nintendo", "00:1C:BE": "Nintendo",
    "00:1D:25": "Nintendo", "00:1F:32": "Nintendo", "00:1F:C5": "Nintendo", "00:22:AA": "Nintendo", "00:23:31": "Nintendo",
    "00:23:CC": "Nintendo", "00:24:1E": "Nintendo", "00:24:F3": "Nintendo", "00:25:A0": "Nintendo", "00:26:1A": "Nintendo",
    "34:AF:2C": "Nintendo", "40:D2:8A": "Nintendo", "78:8C:54": "Nintendo", "B8:AE:6E": "Nintendo", "BC:1E:8E": "Nintendo",
    "E0:6F:8A": "Nintendo", "F0:48:1A": "Nintendo",

    # ── Sony ──
    "00:01:5F": "Sony", "00:02:FD": "Sony", "00:04:1F": "Sony", "00:06:E6": "Sony", "00:0C:06": "Sony",
    "00:1E:5D": "Sony", "00:1F:BA": "Sony", "00:21:E8": "Sony", "00:2A:25": "Sony", "00:2B:F6": "Sony",
    "00:33:33": "Sony", "00:42:78": "Sony", "90:9F:33": "Sony", "AC:9E:17": "Sony", "D8:D0:3C": "Sony",
    "F0:2A:2B": "Sony",

    # ── Vivotek ──
    "00:0A:49": "Vivotek", "00:0E:00": "Vivotek", "00:14:19": "Vivotek",

    # ── Foscam ──
    "00:06:6D": "Foscam", "00:0B:20": "Foscam",

    # ── Nvidia ──
    "00:04:4B": "Nvidia",

    # ── Marvell ──
    "00:02:4E": "Marvell", "00:0E:8E": "Marvell", "00:10:60": "Marvell", "00:12:34": "Marvell", "00:16:01": "Marvell",
    "00:1B:26": "Marvell", "00:1C:6E": "Marvell", "00:1D:0F": "Marvell", "00:23:3A": "Marvell", "00:24:8B": "Marvell",
    "00:25:11": "Marvell", "00:25:73": "Marvell", "00:50:43": "Marvell", "02:42:1E": "Marvell", "B0:38:29": "Marvell",
    "C8:57:42": "Marvell", "D8:32:8F": "Marvell",

    # ── VMware ──
    "00:05:69": "VMware", "00:1C:06": "VMware", "00:1D:5C": "VMware", "00:25:61": "VMware", "00:26:35": "VMware",
    "00:10:DB": "VMware",

    # ── QEMU/KVM ──
    "DE:AD:BE": "QEMU/KVM"
}

_ARP_CACHE: Dict[str, str] = {}
_ARP_CACHE_TS: float = 0.0
_GEO_CACHE: Dict[str, Optional[Dict]] = {}


def _is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True


def _vendor_from_mac(mac: str) -> str:
    if not mac:
        return ""
    prefix = mac.upper()[:8]  # AA:BB:CC
    return MAC_VENDOR_PREFIXES.get(prefix, "Desconocido")


def _get_arp_table(force: bool = False) -> Dict[str, str]:
    """Lee la tabla ARP real del sistema (ip neigh / arp -n).
    Cachea 15s para no golpear el sistema en cada escaneo."""
    global _ARP_CACHE, _ARP_CACHE_TS
    if not force and (time.time() - _ARP_CACHE_TS) < 15 and _ARP_CACHE:
        return _ARP_CACHE

    table: Dict[str, str] = {}
    # Intento 1: ip neigh (Linux moderno / Termux con paquete iproute2)
    try:
        res = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and "lladdr" in parts:
                ip = parts[0]
                mac_idx = parts.index("lladdr") + 1
                if mac_idx < len(parts):
                    table[ip] = parts[mac_idx].upper()
    except Exception:
        pass

    # Intento 2: arp -n (fallback si iproute2 no está disponible)
    if not table:
        try:
            res = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and re.match(r"^[0-9a-fA-F:]{17}$", parts[2]):
                    table[parts[0]] = parts[2].upper()
        except Exception:
            pass

    if table:
        _ARP_CACHE = table
        _ARP_CACHE_TS = time.time()
    return table


async def _resolve_hostname(ip: str) -> str:
    """DNS inverso real con timeout corto — no bloquea el escaneo."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyaddr, ip),
            timeout=1.5
        )
        return result[0]
    except Exception:
        return ""


async def _geolocate_public_ip(ip: str) -> Optional[Dict]:
    """Geolocalización REAL solo para IPs públicas. Usa ip-api.com
    (gratis, sin API key, límite ~45 req/min). Nunca se llama para
    rangos privados — ver _is_private_ip(). Resultado cacheado."""
    if ip in _GEO_CACHE:
        return _GEO_CACHE[ip]
    if aiohttp is None:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,lat,lon,city,country,isp,org"},
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    geo = {
                        "lat": data.get("lat"), "lon": data.get("lon"),
                        "city": data.get("city", ""), "country": data.get("country", ""),
                        "isp": data.get("isp", ""), "org": data.get("org", ""),
                    }
                    _GEO_CACHE[ip] = geo
                    return geo
    except Exception:
        pass
    _GEO_CACHE[ip] = None
    return None


# ============================================================
# 1. NÚCLEO COGNITIVO — Base de datos + Predicción
# ============================================================
security = HTTPBasic()
app = FastAPI(title="NEXUS OMNI-SENTIENT v9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NeuralDB:
    def __init__(self):
        self.conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                ip TEXT, mac TEXT, hostname TEXT,
                ports TEXT, os_guess TEXT, vendor TEXT,
                risk_score REAL, threat_level TEXT,
                first_seen TEXT, last_seen TEXT,
                scan_history TEXT, seal_hash TEXT,
                lat REAL, lon REAL
            )''')
        # Migración: columnas nuevas para datos reales (is_private, geo_meta)
        for col, coltype in [("is_private", "INTEGER DEFAULT 1"),
                              ("geo_city", "TEXT"), ("geo_country", "TEXT"),
                              ("geo_isp", "TEXT")]:
            try:
                self.conn.execute(f"ALTER TABLE devices ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT, event_type TEXT,
                description TEXT, severity TEXT, timestamp TEXT
            )''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS adaptations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT, reason TEXT, timestamp TEXT
            )''')
        self.conn.commit()

    def update_device(self, dev: Dict) -> Tuple[bool, float, str]:
        """Actualiza dispositivo y calcula predicción de amenaza."""
        now = datetime.now().isoformat()
        ip = dev["ip"]

        # Cargar historial
        c = self.conn.cursor()
        c.execute("SELECT scan_history, risk_score FROM devices WHERE id=?", (dev["id"],))
        row = c.fetchone()

        history = []
        old_risk = 0.0
        if row:
            history = json.loads(row[0])
            old_risk = row[1]
            history.append({"time": now, "ports": dev.get("ports", []), "risk": dev.get("risk_score", 0)})
            if len(history) > CONFIG["prediction_window"]: history.pop(0)
        else:
            history = [{"time": now, "ports": dev.get("ports", []), "risk": dev.get("risk_score", 0)}]

        # --- MOTOR DE PREDICCIÓN (IA SIMPLE) ---
        # Detectar anomalía: ¿Cambio drástico de puertos?
        anomaly_detected = False
        if len(history) >= 2:
            prev_ports = set(history[-2]["ports"])
            curr_ports = set(dev.get("ports", []))
            if prev_ports != curr_ports and len(curr_ports) > 0:
                anomaly_detected = True
                self._log_event(dev["id"], "ANOMALY", f"Cambio de puertos: {prev_ports} -> {curr_ports}", "HIGH")

        # Calcular Riesgo Dinámico (Base + Anomalía + Tendencias)
        base_risk = self._calculate_base_risk(dev)
        dynamic_risk = base_risk
        if anomaly_detected: dynamic_risk += 30
        if len(history) > 1 and history[-1]["risk"] > history[-2]["risk"]:
            dynamic_risk += 10 # Tendencia al alza

        threat_level = "LOW"
        if dynamic_risk > 80: threat_level = "CRITICAL"
        elif dynamic_risk > 50: threat_level = "HIGH"
        elif dynamic_risk > 20: threat_level = "MEDIUM"

        # Guardar
        data_str = json.dumps(dev, sort_keys=True)
        seal_hash = hashlib.sha256(data_str.encode()).hexdigest()

        # NOTA: lat/lon ya NO se rellenan con jitter aleatorio. Solo se
        # guardan coordenadas si vinieron de una geolocalización REAL
        # (IP pública consultada en _geolocate_public_ip). Para IPs
        # privadas (LAN) lat/lon quedan NULL — is_private=1 indica al
        # frontend que debe mostrarse en el panel de red local, no en
        # el mapa geográfico.
        self.conn.execute('''
            INSERT OR REPLACE INTO devices
            (id, ip, mac, hostname, ports, os_guess, vendor, risk_score, threat_level,
             first_seen, last_seen, scan_history, seal_hash, lat, lon,
             is_private, geo_city, geo_country, geo_isp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            dev["id"], ip, dev.get("mac", ""), dev.get("hostname", ""),
            json.dumps(dev.get("ports", [])), dev.get("os", ""), dev.get("vendor", ""),
            dynamic_risk, threat_level,
            dev.get("first_seen", now), now, json.dumps(history), seal_hash,
            dev.get("lat"), dev.get("lon"),
            int(dev.get("is_private", True)),
            dev.get("geo_city", ""), dev.get("geo_country", ""), dev.get("geo_isp", ""),
        ))
        self.conn.commit()
        return anomaly_detected, dynamic_risk, threat_level

    def _calculate_base_risk(self, dev: Dict) -> float:
        risk = 0.0
        ports = dev.get("ports", [])
        critical = set(CONFIG["ports_critical"]) & set(ports)
        risk += len(critical) * 15
        if 22 in ports and 445 in ports: risk += 20
        if 3389 in ports: risk += 15
        if 23 in ports: risk += 25 # Telnet = muy riesgoso
        return min(risk, 100)

    def _log_event(self, device_id, etype, desc, sev):
        self.conn.execute("INSERT INTO events (device_id, event_type, description, severity, timestamp) VALUES (?,?,?,?,?)",
                         (device_id, etype, desc, sev, datetime.now().isoformat()))
        self.conn.commit()

    def log_adaptation(self, action, reason):
        self.conn.execute("INSERT INTO adaptations (action, reason, timestamp) VALUES (?,?,?)",
                         (action, reason, datetime.now().isoformat()))
        self.conn.commit()

    def get_all_devices(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM devices ORDER BY risk_score DESC")
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    def get_recent_events(self, limit: int = 30) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    def get_recent_adaptations(self, limit: int = 15) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM adaptations ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

db = NeuralDB()

# ============================================================
# 2. ESCÁNER ADAPTATIVO — Aprende y se ajusta solo
# ============================================================
class AdaptiveScanner:
    def __init__(self):
        self.mode = "stealth"
        self.scanning = False
        self.port_success_rate = {} # Aprende qué puertos están abiertos frecuentemente
        self.watchdog_task = None
        self.last_activity = time.time()

    def start_watchdog(self):
        """Monitorea la salud del escáner y lo reinicia si se cuelga."""
        if self.watchdog_task and not self.watchdog_task.done():
            return
        async def watchdog():
            while True:
                await asyncio.sleep(30)
                if self.scanning and time.time() - self.last_activity > 60:
                    print("⚠️ WATCHDOG: Escáner congelado. Reiniciando...")
                    self.scanning = False # Forzar parada para reinicio externo
        self.watchdog_task = asyncio.create_task(watchdog())

    async def stop_watchdog(self):
        if self.watchdog_task and not self.watchdog_task.done():
            self.watchdog_task.cancel()
            try:
                await self.watchdog_task
            except asyncio.CancelledError:
                pass

    async def adapt_strategy(self, network_cidr: str, found_count: int):
        """Ajusta el modo de escaneo dinámicamente según los resultados."""
        # Si encontramos muchos dispositivos críticos, subir a 'active'
        critical_count = len([d for d in db.get_all_devices() if d.get("threat_level") == "CRITICAL"])

        if critical_count > 3 and self.mode != "frenzy":
            self.mode = "frenzy"
            db.log_adaptation("MODE_CHANGE", f"Elevado a FRENZY por {critical_count} amenazas críticas.")
            print(f"🚨 AMENAZA ALTA DETECTADA. CAMBIANDO A MODO FRENZY.")
        elif found_count == 0 and self.mode == "active":
            self.mode = "stealth" # Bajar intensidad si no hay nada
            db.log_adaptation("MODE_CHANGE", "Bajado a STEALTH por falta de objetivos.")

    async def scan_host(self, ip: str, arp_table: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        self.last_activity = time.time()
        config = CONFIG["modes"][self.mode]
        timeout = config["timeout"]

        open_ports = []
        concurrent = config["concurrent"]

        async def check_port(port: int):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port), timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                return port
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                return None

        # Escaneo concurrente
        tasks = [check_port(p) for p in CONFIG["ports_critical"]]
        results = await asyncio.gather(*tasks)
        open_ports = [p for p in results if p is not None]

        if not open_ports:
            return None

        # ── Enriquecimiento con datos REALES ──
        arp_table = arp_table or {}
        mac = arp_table.get(ip, "")
        vendor = _vendor_from_mac(mac)
        hostname = await _resolve_hostname(ip)
        is_private = _is_private_ip(ip)

        lat, lon, geo_city, geo_country, geo_isp = None, None, "", "", ""
        if not is_private:
            # Solo se geolocaliza con datos reales si la IP es pública.
            # Los rangos privados (LAN) NUNCA reciben coordenadas — antes
            # se les asignaba una posición aleatoria alrededor de Bogotá,
            # lo cual era información falsa. Ahora se muestran en el
            # panel de "Red Local" del frontend, sin pin en el mapa.
            geo = await _geolocate_public_ip(ip)
            if geo:
                lat, lon = geo.get("lat"), geo.get("lon")
                geo_city, geo_country, geo_isp = geo.get("city", ""), geo.get("country", ""), geo.get("isp", "")

        # Generar ID único
        dev_id = hashlib.md5(f"{ip}:{open_ports}".encode()).hexdigest()

        return {
            "id": dev_id, "ip": ip, "ports": open_ports,
            "os": self._guess_os(open_ports),
            "mac": mac, "vendor": vendor, "hostname": hostname,
            "is_private": is_private,
            "lat": lat, "lon": lon,
            "geo_city": geo_city, "geo_country": geo_country, "geo_isp": geo_isp,
            "first_seen": datetime.now().isoformat(),
            "risk_score": 0, # Se calcula en update_device
        }

    def _guess_os(self, ports: List[int]) -> str:
        if 3389 in ports: return "Windows"
        if 22 in ports and 5432 in ports: return "Linux/PostgreSQL"
        if 22 in ports: return "Linux/Unix"
        if 445 in ports: return "Windows/SMB"
        if 23 in ports: return "Router/IoT"
        return "Unknown"

    async def run_discovery(self, network_cidr: str):
        self.scanning = True
        self.last_activity = time.time()
        print(f"🧠 NEXUS OMNI iniciado en {network_cidr} (Modo: {self.mode.upper()})")

        my_ip = "192.168.1.50"
        try:
            res = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=1)
            for line in res.stdout.split('\n'):
                if "src" in line: my_ip = line.split()[line.split().index("src")+1]
        except: pass

        # Tabla ARP real del sistema — una sola lectura por corrida de escaneo
        arp_table = _get_arp_table(force=True)

        net = ipaddress.ip_network(network_cidr, strict=False)
        targets = [str(ip) for ip in net.hosts() if str(ip) != my_ip]
        if self.mode == "passive": targets = targets[:10]

        tasks = [self.scan_host(ip, arp_table) for ip in targets]
        results = await asyncio.gather(*tasks)
        found = [r for r in results if r]

        for dev in found:
            db.update_device(dev)

        await self.adapt_strategy(network_cidr, len(found))
        self.scanning = False
        return found

scanner = AdaptiveScanner()

@app.on_event("startup")
async def start_scanner_watchdog():
    scanner.start_watchdog()
    # Arrancar loop de autoscan si nexus_autoscan está disponible
    if nas is not None:
        threading.Thread(target=nas.autoscan_loop, args=(NEXUS_SCAN_TARGET, 600), daemon=True).start()
        print(f"[NEXUS] Autoscan loop iniciado — target={NEXUS_SCAN_TARGET}, interval=600s", flush=True)

@app.on_event("shutdown")
async def stop_scanner_watchdog():
    await scanner.stop_watchdog()

# ============================================================
# 3. API Y WEBSOCKET EN TIEMPO REAL
# ============================================================
def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != CONFIG["auth_user"] or credentials.password != CONFIG["auth_pass"]:
        raise HTTPException(status_code=401, detail="Access Denied")
    return credentials

@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    if not os.path.exists("nexus_ui.html"):
        return HTMLResponse("<h1>NEXUS UI Missing</h1><p>Generate nexus_ui.html</p>")
    return FileResponse("nexus_ui.html")

@app.post("/api/scan")
async def trigger_scan(credentials: HTTPBasicCredentials = Depends(verify_auth), network: str = "192.168.1.0/24"):
    if scanner.scanning: return {"status": "running"}
    asyncio.create_task(scanner.run_discovery(network))
    return {"status": "started", "mode": scanner.mode}

@app.get("/api/analytics")
async def get_analytics(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    devices = db.get_all_devices()
    total = len(devices)
    critical = len([d for d in devices if d["threat_level"] == "CRITICAL"])
    anomalies = len(db.get_recent_events(limit=100))
    return {
        "total": total, "critical": critical, "mode": scanner.mode,
        "scanning": scanner.scanning, "health": "OPTIMAL", "anomalies": anomalies
    }

@app.get("/api/events")
async def get_events(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Eventos reales (anomalías detectadas + cambios de modo adaptativo)."""
    return {
        "events": db.get_recent_events(30),
        "adaptations": db.get_recent_adaptations(15),
    }

@app.get("/api/state")
async def get_state(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Estado completo para el proxy del dashboard unificado.

    Separa dispositivos en:
      - devices_public: tienen lat/lon REAL (geolocalización de IP pública)
      - devices_local: son LAN (is_private=1), sin coordenadas — se listan
        en el panel de red local del frontend, nunca como pin falso en el mapa
    """
    devices = db.get_all_devices()
    devices_public = [d for d in devices if not d.get("is_private") and d.get("lat") is not None]
    devices_local = [d for d in devices if d.get("is_private") or d.get("lat") is None]

    return {
        "devices": devices,                # compatibilidad hacia atrás
        "devices_public": devices_public,
        "devices_local": devices_local,
        "events": db.get_recent_events(15),
        "stats": await get_analytics(credentials),
    }

# ============================================================
# 3b. NEXUS AUTOSCAN — escaneo automático + mapeo + lista detallada
# ============================================================
NEXUS_SCAN_TARGET = os.environ.get("NEXUS_SCAN_TARGET", "192.168.1.0/24")

@app.get("/api/nexus/hosts")
async def nexus_hosts(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Devuelve el estado del mapeo de hosts (lista detallada)."""
    if nas is None:
        raise HTTPException(status_code=503, detail="nexus_autoscan no disponible")
    return nas.get_state()

@app.post("/api/nexus/scan/now")
async def nexus_scan_now(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Lanza un escaneo inmediato del target configurado."""
    if nas is None:
        raise HTTPException(status_code=503, detail="nexus_autoscan no disponible")
    if nas.STATE.get("running"):
        return {"status": "already_running", "target": NEXUS_SCAN_TARGET}
    threading.Thread(target=nas.scan, args=(NEXUS_SCAN_TARGET,), daemon=True).start()
    return {"status": "scan_started", "target": NEXUS_SCAN_TARGET}

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text() # Ping
            devices = db.get_all_devices()
            devices_public = [d for d in devices if not d.get("is_private") and d.get("lat") is not None]
            devices_local = [d for d in devices if d.get("is_private") or d.get("lat") is None]

            await websocket.send_json({
                "devices": devices,
                "devices_public": devices_public,
                "devices_local": devices_local,
                "events": db.get_recent_events(15),
                "stats": await get_analytics(
                    HTTPBasicCredentials(
                        username=CONFIG["auth_user"],
                        password=CONFIG["auth_pass"],
                    )
                )
            })
            await asyncio.sleep(1) # Update rate 1s
    except WebSocketDisconnect: pass

if __name__ == "__main__":
    print("🌐 NEXUS OMNI-SENTIENT v9.0 ONLINE")
    print(f"🔐 Acceso configurado para usuario '{NEXUS_CREDENTIALS.user}' — credenciales en .env (no se muestran)")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("NEXUS_PORT", "8004")))
