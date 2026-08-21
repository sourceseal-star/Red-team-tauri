#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ONVIF SCANNER - Detección de Dispositivos ONVIF
=============================================
Herramienta para descubrir y analizar dispositivos compatibles con ONVIF.

Capacidades:
- Detección de cámaras ONVIF mediante WS-Discovery
- Escaneo de puertos ONVIF (80, 443, 8000, 3702)
- Obtención de información del dispositivo
- Prueba de credenciales por defecto

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 onvif_scanner.py [--network 192.168.1.0/24] [--brute]
"""

import asyncio
import socket
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse
import ipaddress


# ============================================================
# CONFIGURACIÓN
# ============================================================

class ONVIFConfig:
    # Puertos ONVIF
    ONVIF_PORTS = [80, 443, 8000, 3702]
    
    # Credenciales por defecto
    DEFAULT_CREDS = [
        ("admin", "admin"),
        ("admin", "12345"),
        ("admin", "123456"),
        ("admin", "password"),
        ("admin", ""),
        ("root", "root"),
        ("user", "user"),
        ("administrator", "administrator"),
    ]
    
    # Timeouts
    TIMEOUT = 2.0
    
    # User Agent
    USER_AGENT = "ONVIF Client/1.0"


# ============================================================
# WS-DISCOVERY
# ============================================================

ONVIF_WS_DISCOVERY_MESSAGE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
              xmlns:tds="http://www.onvif.org/ver10/network/wsdl"
              xmlns:tns1="http://www.onvif.org/ver10/topology/wsdl"
              xmlns:tns2="http://www.onvif.org/ver10/deviceIO/wsdl"
              xmlns:tns3="http://www.onvif.org/ver10/events/wsdl"
              xmlns:tns4="http://www.onvif.org/ver10/analytics/wsdl"
              xmlns:tns5="http://www.onvif.org/ver10/device/wsdl">
  <soap:Header>
    <wsa:Action soap:mustUnderstand="1" xmlns:wsa="http://www.w3.org/2005/08/addressing">
      http://www.onvif.org/ver10/network/wsdl/GetDevices
    </wsa:Action>
    <wsa:MessageID xmlns:wsa="http://www.w3.org/2005/08/addressing">
      urn:uuid:{(datetime.now().strftime('%Y%m%d%H%M%S%f'))}
    </wsa:MessageID>
    <wsa:ReplyTo xmlns:wsa="http://www.w3.org/2005/08/addressing">
      <wsa:Address>http://www.w3.org/2005/08/addressing/anonymous</wsa:Address>
    </wsa:ReplyTo>
    <wsa:To soap:mustUnderstand="1" xmlns:wsa="http://www.w3.org/2005/08/addressing">
      urn:schemas-xmlsoap-org:ws:2005:04:discovery
    </wsa:To>
  </soap:Header>
  <soap:Body>
    <tds:GetDevices xmlns="http://www.onvif.org/ver10/network/wsdl"/>
  </soap:Body>
</soap:Envelope>"""


async def send_ws_discovery(ip: str, port: int = 3702) -> Optional[Dict]:
    """Envía un mensaje WS-Discovery para detectar dispositivos ONVIF."""
    try:
        # Crear socket UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(ONVIFConfig.TIMEOUT)
        
        # Enviar mensaje
        message = ONVIF_WS_DISCOVERY_MESSAGE.encode()
        sock.sendto(message, (ip, port))
        
        # Recibir respuesta
        data, addr = sock.recvfrom(4096)
        sock.close()
        
        response = data.decode(errors='ignore')
        
        # Parsear respuesta
        if "GetDevicesResponse" in response:
            return parse_onvif_response(response, addr[0])
        
        return None
        
    except:
        return None


def parse_onvif_response(response: str, ip: str) -> Dict:
    """Parsea la respuesta ONVIF."""
    device = {
        "ip": ip,
        "port": 3702,
        "type": "ONVIF",
        "model": "Unknown",
        "manufacturer": "Unknown",
        "firmware_version": "Unknown",
        "serial_number": "Unknown",
        "hardware_id": "Unknown",
        "scopes": [],
        "xaddrs": []
    }
    
    try:
        # Parsear XML
        root = ET.fromstring(response)
        
        # Namespace
        ns = {'soap': 'http://www.w3.org/2003/05/soap-envelope',
              'tds': 'http://www.onvif.org/ver10/network/wsdl'}
        
        # Obtener dispositivos
        devices = root.findall('.//tds:Devices/tds:Device', ns)
        
        for dev in devices:
            # Información básica
            device["model"] = dev.find('tds:Model', ns).text if dev.find('tds:Model', ns) is not None else "Unknown"
            device["manufacturer"] = dev.find('tds:Manufacturer', ns).text if dev.find('tds:Manufacturer', ns) is not None else "Unknown"
            device["firmware_version"] = dev.find('tds:FirmwareVersion', ns).text if dev.find('tds:FirmwareVersion', ns) is not None else "Unknown"
            device["serial_number"] = dev.find('tds:SerialNumber', ns).text if dev.find('tds:SerialNumber', ns) is not None else "Unknown"
            device["hardware_id"] = dev.find('tds:HardwareId', ns).text if dev.find('tds:HardwareId', ns) is not None else "Unknown"
            
            # Scopes
            scopes = dev.findall('tds:Scopes/tds:Scope', ns)
            device["scopes"] = [scope.text for scope in scopes if scope.text]
            
            # XAddrs
            xaddrs = dev.findall('tds:XAddrs/tds:XAddr', ns)
            device["xaddrs"] = [xaddr.text for xaddr in xaddrs if xaddr.text]
        
        return device
        
    except:
        return device


# ============================================================
# DETECCIÓN POR PUERTOS
# ============================================================

async def check_onvif_http(ip: str, port: int) -> Optional[Dict]:
    """Verifica ONVIF mediante HTTP."""
    try:
        import aiohttp
        
        url = f"http://{ip}:{port}/onvif/device_service"
        headers = {"User-Agent": ONVIFConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=ONVIFConfig.TIMEOUT) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    if "ONVIF" in html.upper():
                        return {
                            "ip": ip,
                            "port": port,
                            "type": "ONVIF-HTTP",
                            "banner": html[:200]
                        }
        
        return None
        
    except:
        return None


async def check_onvif_ports(ip: str) -> List[Dict]:
    """Verifica todos los puertos ONVIF."""
    results = []
    
    for port in ONVIFConfig.ONVIF_PORTS:
        # Verificar mediante HTTP
        result = await check_onvif_http(ip, port)
        if result:
            results.append(result)
        
        # Verificar mediante WS-Discovery (solo puerto 3702)
        if port == 3702:
            ws_result = await send_ws_discovery(ip, port)
            if ws_result:
                results.append(ws_result)
    
    return results


# ============================================================
# PRUEBA DE CREDENCIALES
# ============================================================

async def test_onvif_credentials(ip: str, port: int, user: str, passwd: str) -> bool:
    """Prueba credenciales ONVIF."""
    try:
        import aiohttp
        import base64
        
        url = f"http://{ip}:{port}/onvif/device_service"
        
        # Autenticación básica
        auth = aiohttp.BasicAuth(user, passwd)
        headers = {"User-Agent": ONVIFConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=ONVIFConfig.TIMEOUT, auth=auth) as resp:
                return resp.status == 200
        
    except:
        return False


async def brute_force_onvif(ip: str, port: int) -> Dict:
    """Fuerza bruta ONVIF."""
    result = {
        "success": False,
        "credentials": None,
        "tried": 0
    }
    
    for user, passwd in ONVIFConfig.DEFAULT_CREDS:
        result["tried"] += 1
        if await test_onvif_credentials(ip, port, user, passwd):
            result["success"] = True
            result["credentials"] = f"{user}:{passwd}"
            break
    
    return result


# ============================================================
# OBTENCIÓN DE INFORMACIÓN DEL DISPOSITIVO
# ============================================================

async def get_onvif_device_info(ip: str, port: int, user: str, passwd: str) -> Dict:
    """Obtiene información completa del dispositivo ONVIF."""
    info = {
        "model": None,
        "manufacturer": None,
        "firmware_version": None,
        "serial_number": None,
        "hardware_id": None,
        "scopes": [],
        "xaddrs": [],
        "error": None
    }
    
    try:
        import aiohttp
        
        url = f"http://{ip}:{port}/onvif/device_service"
        auth = aiohttp.BasicAuth(user, passwd)
        headers = {"User-Agent": ONVIFConfig.USER_AGENT}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                timeout=ONVIFConfig.TIMEOUT,
                auth=auth,
                data=ONVIF_WS_DISCOVERY_MESSAGE
            ) as resp:
                if resp.status == 200:
                    xml = await resp.text()
                    device = parse_onvif_response(xml, ip)
                    info.update(device)
        
        return info
        
    except Exception as e:
        info["error"] = str(e)
        return info


# ============================================================
# ESCANEO DE RED
# ============================================================

async def scan_network(network: str) -> List[Dict]:
    """Escanea una red en busca de dispositivos ONVIF."""
    net = ipaddress.ip_network(network, strict=False)
    all_ips = [str(ip) for ip in net.hosts()]
    
    print(f"🔍 Escaneando {len(all_ips)} IPs en {network} (paralelo)...")
    
    import asyncio
    sem = asyncio.Semaphore(20)
    
    async def scan_one(ip):
        async with sem:
            return await check_onvif_ports(ip)
    
    tasks = [scan_one(ip) for ip in all_ips]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    onvif_devices = []
    for devices in results:
        if isinstance(devices, Exception) or not devices:
            continue
        for device in devices:
            already_found = any(d["ip"] == device["ip"] and d["port"] == device["port"]
                               for d in onvif_devices)
            if not already_found:
                onvif_devices.append(device)
                print(f"    ✅ Dispositivo ONVIF encontrado en {device['ip']}:{device['port']}")
    
    return onvif_devices


# ============================================================
# PRINCIPAL
# ============================================================

async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="ONVIF Scanner - Detección de dispositivos ONVIF"
    )
    parser.add_argument("--network", type=str, default="192.168.1.0/24",
                        help="Red a escanear (ej: 192.168.1.0/24)")
    parser.add_argument("--ip", type=str, help="IP específica a escanear")
    parser.add_argument("--brute", action="store_true", help="Fuerza bruta en dispositivos encontrados")
    
    args = parser.parse_args()
    
    if args.ip:
        # Escanear IP específica
        print(f"🔍 Escaneando {args.ip}...")
        devices = await check_onvif_ports(args.ip)
        
        if devices:
            print(f"\n✅ Dispositivos ONVIF encontrados en {args.ip}:")
            for i, device in enumerate(devices, 1):
                print(f"  [{i}] Puerto {device['port']} - Tipo: {device['type']}")
                if device.get('model'):
                    print(f"       Modelo: {device['model']}")
                if device.get('manufacturer'):
                    print(f"       Fabricante: {device['manufacturer']}")
            
            # Fuerza bruta si se solicita
            if args.brute:
                print("\n🔐 Probando fuerza bruta...")
                for device in devices:
                    port = device['port']
                    brute_result = await brute_force_onvif(args.ip, port)
                    if brute_result['success']:
                        print(f"  ✅ Credenciales encontradas en puerto {port}: {brute_result['credentials']}")
                        
                        # Obtener información completa
                        user, passwd = brute_result['credentials'].split(':')
                        info = await get_onvif_device_info(args.ip, port, user, passwd)
                        print(f"       Información: {info}")
        else:
            print(f"\n❌ No se encontraron dispositivos ONVIF en {args.ip}")
    else:
        # Escanear red
        print(f"🌐 Escaneando red {args.network}...")
        devices = await scan_network(args.network)
        
        print(f"\n📊 RESULTADOS:")
        print(f"  Dispositivos ONVIF encontrados: {len(devices)}")
        
        if devices:
            print("\nDispositivos:")
            for i, device in enumerate(devices, 1):
                print(f"  [{i}] {device['ip']}:{device['port']}")
                print(f"       Tipo: {device['type']}")
                if device.get('model'):
                    print(f"       Modelo: {device['model']}")
                if device.get('manufacturer'):
                    print(f"       Fabricante: {device['manufacturer']}")
            
            # Guardar resultados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"onvif_scan_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(devices, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Resultados guardados en: {filename}")
            
            # Fuerza bruta si se solicita
            if args.brute:
                print("\n🔐 Probando fuerza bruta en todos los dispositivos...")
                for device in devices:
                    brute_result = await brute_force_onvif(device['ip'], device['port'])
                    if brute_result['success']:
                        print(f"  ✅ {device['ip']}:{device['port']} - Credenciales: {brute_result['credentials']}")


if __name__ == "__main__":
    asyncio.run(main())
