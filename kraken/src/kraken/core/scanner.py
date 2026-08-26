import subprocess
import re
import time
import ipaddress
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import xml.etree.ElementTree as ET

from kraken.config.settings import settings
from kraken.core.logger import logger
from kraken.core.cache import cache
from kraken.core.utils import get_ips_from_cidr

@dataclass
class Service:
    port: int
    name: str
    version: Optional[str] = None
    product: Optional[str] = None
    cpe: Optional[str] = None

@dataclass
class Vulnerability:
    port: int
    service: str
    script: str
    output: str
    cve: Optional[str] = None
    cvss: float = 0.0
    severity: str = "unknown"

@dataclass
class Host:
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    os_family: Optional[str] = None
    os_accuracy: int = 0
    uptime: Optional[str] = None
    tcp_ports: List[Service] = None
    udp_ports: List[Service] = None
    vulnerabilities: List[Vulnerability] = None
    mac: Optional[str] = None
    vendor: Optional[str] = None

    def __post_init__(self):
        self.tcp_ports = self.tcp_ports or []
        self.udp_ports = self.udp_ports or []
        self.vulnerabilities = self.vulnerabilities or []

class Scanner:
    """Motor de escaneo de red con Nmap y Masscan."""

    def __init__(self):
        self.nmap_path = "nmap"
        self.masscan_path = "masscan"
        self.timeout = settings.SCAN_TIMEOUT

    def _parse_nmap_xml(self, xml_data: str) -> Optional[Host]:
        """Parsea la salida XML de Nmap."""
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error(f"Error parseando XML de Nmap: {e}")
            return None

        host_data = None
        for host in root.findall('host'):
            addr = host.find('address')
            if addr is None:
                continue
            ip = addr.get('addr')
            if not ip:
                continue

            status = host.find('status')
            if status is not None and status.get('state') != 'up':
                continue

            host_data = Host(ip=ip)

            # OS Detection
            os_elem = host.find('os/osmatch')
            if os_elem is not None:
                host_data.os = os_elem.get('name')
                host_data.os_family = os_elem.get('osfamily')
                host_data.os_accuracy = int(os_elem.get('accuracy', 0))

            # Uptime
            uptime = host.find('uptime')
            if uptime is not None:
                host_data.uptime = uptime.get('seconds')

            # Hostnames
            hostnames = host.find('hostnames')
            if hostnames is not None:
                for hostname in hostnames.findall('hostname'):
                    host_data.hostname = hostname.get('name')
                    break

            # MAC Address
            mac = host.find('address[@addrtype="mac"]')
            if mac is not None:
                host_data.mac = mac.get('addr')
                host_data.vendor = mac.get('vendor')

            # Ports and Services
            ports = host.find('ports')
            if ports is not None:
                for port in ports.findall('port'):
                    port_id = int(port.get('portid'))
                    protocol = port.get('protocol', 'tcp')

                    service = port.find('service')
                    service_name = service.get('name') if service is not None else "unknown"
                    service_version = service.get('version') if service is not None else None
                    service_product = service.get('product') if service is not None else None
                    service_cpe = service.get('cpe') if service is not None else None

                    svc = Service(
                        port=port_id,
                        name=service_name,
                        version=service_version,
                        product=service_product,
                        cpe=service_cpe
                    )

                    if protocol == 'tcp':
                        host_data.tcp_ports.append(svc)
                    else:
                        host_data.udp_ports.append(svc)

                    # Vulnerabilities from NSE scripts
                    for script in port.findall('script'):
                        script_id = script.get('id')
                        output = script.get('output', '')
                        if "VULNERABLE" in output or "CVE" in output:
                            # Extract CVEs
                            cves = re.findall(r'CVE-\d{4}-\d{4,7}', output)
                            cve = cves[0] if cves else None

                            # Estimate CVSS based on script output
                            cvss = 0.0
                            severity = "unknown"
                            if "critical" in output.lower():
                                cvss = 9.8
                                severity = "critical"
                            elif "high" in output.lower():
                                cvss = 7.5
                                severity = "high"
                            elif "medium" in output.lower():
                                cvss = 5.0
                                severity = "medium"
                            elif "low" in output.lower():
                                cvss = 2.5
                                severity = "low"

                            vuln = Vulnerability(
                                port=port_id,
                                service=service_name,
                                script=script_id,
                                output=output[:500],
                                cve=cve,
                                cvss=cvss,
                                severity=severity
                            )
                            host_data.vulnerabilities.append(vuln)
        return host_data

    def scan_with_nmap(self, target: str) -> Optional[Host]:
        """Escanea un objetivo con Nmap."""
        cmd = [
            self.nmap_path,
            "-sV", "-O", "--script", settings.NMAP_SCRIPTS,
            "-p", settings.DEFAULT_PORTS,
            "--script-timeout", str(self.timeout - 10),
            "-oX", "-", target
        ]
        logger.debug(f"Ejecutando: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = proc.communicate(timeout=self.timeout)

            if proc.returncode != 0:
                logger.error(f"Nmap falló para {target}: {err[:200]}")
                return None

            return self._parse_nmap_xml(out)

        except subprocess.TimeoutExpired:
            proc.kill()
            logger.warning(f"Timeout en Nmap para {target}")
            return None
        except Exception as e:
            logger.error(f"Error en Nmap para {target}: {e}")
            return None

    def scan_with_masscan(self, target: str) -> List[int]:
        """Escaneo rápido con Masscan para descubrir puertos abiertos."""
        cmd = [
            self.masscan_path,
            target,
            "-p", settings.DEFAULT_PORTS,
            "--rate", str(settings.MASSCAN_RATE),
            "--banners",
            "-oG", "-"
        ]
        logger.debug(f"Ejecutando Masscan: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = proc.communicate(timeout=60)

            if proc.returncode != 0:
                logger.error(f"Masscan falló para {target}: {err[:200]}")
                return []

            # Parsear salida grepable de Masscan
            open_ports = []
            for line in out.split('\n'):
                if 'open' in line.lower():
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[1]
                        port = int(parts[3])
                        open_ports.append(port)
            return open_ports

        except subprocess.TimeoutExpired:
            proc.kill()
            logger.warning(f"Timeout en Masscan para {target}")
            return []
        except Exception as e:
            logger.error(f"Error en Masscan para {target}: {e}")
            return []

    def scan_host(self, ip: str) -> Optional[Host]:
        """Escanea una IP individual (con cache)."""
        # Verificar cache
        cached = cache.get(f"scan:{ip}")
        if cached:
            return cached

        # Escaneo con Masscan primero (rápido)
        open_ports = self.scan_with_masscan(ip)
        if not open_ports:
            logger.debug(f"No se encontraron puertos abiertos en {ip} (Masscan)")
            return None

        # Escaneo detallado con Nmap
        host = self.scan_with_nmap(ip)
        if host:
            # Filtrar puertos que no estaban abiertos en Masscan
            host.tcp_ports = [p for p in host.tcp_ports if p.port in open_ports]
            host.udp_ports = [p for p in host.udp_ports if p.port in open_ports]

            # Guardar en cache
            cache.set(f"scan:{ip}", host, ttl=settings.CACHE_EXPIRY)
            return host
        return None

    def scan_network(self, target: str) -> List[Host]:
        """Escanea una red completa en paralelo."""
        ips = get_ips_from_cidr(target)
        if not ips:
            logger.error(f"No se pudo resolver el target: {target}")
            return []

        logger.info(f"Escaneando {len(ips)} IPs con {settings.MAX_WORKERS} workers...")

        results = []
        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            future_to_ip = {
                executor.submit(self.scan_host, ip): ip
                for ip in ips
            }

            for future in as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    host = future.result(timeout=self.timeout + 10)
                    if host:
                        results.append(host)
                        logger.info(f"✅ {ip}: {len(host.tcp_ports)} puertos abiertos, {len(host.vulnerabilities)} vulnerabilidades")
                except Exception as e:
                    logger.error(f"Error escaneando {ip}: {e}")

        return results
