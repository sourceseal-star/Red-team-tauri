# -*- coding: utf-8 -*-
"""
=== FILE: ndr/network_capture.py ===
Módulo de Captura de Tráfico de Red en Tiempo Real y Carga de Archivos PCAP.
Provee capacidades de captura usando Scapy de manera primaria y Pyshark como fallback,
reconstrucción de flujos bidireccionales TCP/UDP con control de tamaño en memoria
usando un buffer circular, y soporte para el análisis forense de archivos PCAP.
"""

import os
import threading
from datetime import datetime
from collections import deque
from typing import List, Dict, Tuple, Optional

# Importamos la clase unificada de flujos de tráfico
from ndr.ml_detector import TrafficFlow

# Intentamos importar Scapy de forma segura
try:
    from scapy.all import sniff, IP, TCP, UDP, ICMP, DNS, DNSQR, rdpcap
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# Intentamos importar Pyshark de forma segura
try:
    import pyshark
    PYSHARK_AVAILABLE = True
except ImportError:
    PYSHARK_AVAILABLE = False


class NetworkCapture:
    """
    Controlador para la captura de paquetes en tiempo real y reconstrucción de flujos.
    Mantiene un buffer circular con un máximo de 10,000 flujos para evitar desbordamiento de memoria.
    """
    def __init__(self, max_flows: int = 10000):
        self.max_flows = max_flows
        self.circular_buffer = deque(maxlen=max_flows)
        # Diccionario para mapeo rápido y reconstrucción bidireccional en caliente
        self.active_flows: Dict[Tuple, TrafficFlow] = {}
        self.lock = threading.Lock()
        
        # Variables de control del hilo de sniffing
        self.sniff_thread: Optional[threading.Thread] = None
        self.running = False
        self.interface = 'eth0'
        
        # Objeto de captura de pyshark si se activa fallback
        self.pyshark_capture: Optional[Any] = None

    def start(self, interface: str = 'eth0'):
        """
        Inicia la captura de red en segundo plano (hilo independiente).
        """
        with self.lock:
            if self.running:
                print(f"[NDR-CAPTURE] Captura ya en ejecución en la interfaz {self.interface}.")
                return
            
            self.interface = interface
            self.running = True
            
        print(f"[NDR-CAPTURE] Iniciando captura de red en la interfaz: {interface}")
        
        # Hilo ejecutor de la captura
        self.sniff_thread = threading.Thread(
            target=self._run_capture,
            name=f"NDR-Sniffer-{interface}",
            daemon=True
        )
        self.sniff_thread.start()

    def stop(self):
        """
        Detiene la captura de red activa de forma segura.
        """
        with self.lock:
            if not self.running:
                return
            self.running = False
            
        print("[NDR-CAPTURE] Solicitando parada de la captura de red...")
        
        # Manejo de parada en caso de Pyshark
        if self.pyshark_capture:
            try:
                self.pyshark_capture.close()
            except Exception:
                pass
            self.pyshark_capture = None
            
        if self.sniff_thread:
            self.sniff_thread.join(timeout=3.0)
            self.sniff_thread = None
            
        print("[NDR-CAPTURE] Captura de red detenida correctamente.")

    def get_flows(self) -> List[TrafficFlow]:
        """
        Retorna una instantánea de todos los flujos de red acumulados en el buffer circular.
        """
        with self.lock:
            return list(self.circular_buffer)

    def _run_capture(self):
        """
        Método interno que ejecuta el bucle de captura usando Scapy (prioritario)
        o Pyshark (fallback). Si ambos fallan (por ej. falta de privilegios root),
        se registra de manera limpia y entra en modo pasivo.
        """
        if SCAPY_AVAILABLE:
            try:
                print("[NDR-CAPTURE] Ejecutando motor de captura con Scapy.")
                
                # Función que determina cuándo detener sniff() en Scapy
                def stop_filter(pkt):
                    return not self.running

                sniff(
                    iface=self.interface,
                    prn=self._process_scapy_packet,
                    stop_filter=stop_filter,
                    store=False
                )
                return
            except PermissionError:
                print("[NDR-CAPTURE] [ERROR] Permiso denegado al usar Scapy (se requieren privilegios root).")
                print("[NDR-CAPTURE] Intentando fallback con Pyshark...")
            except Exception as e:
                print(f"[NDR-CAPTURE] Error al usar Scapy: {e}. Intentando fallback con Pyshark...")

        if PYSHARK_AVAILABLE:
            try:
                print("[NDR-CAPTURE] Ejecutando motor de captura con Pyshark.")
                self.pyshark_capture = pyshark.LiveCapture(interface=self.interface)
                for pkt in self.pyshark_capture.sniff_continuously():
                    with self.lock:
                        if not self.running:
                            break
                    self._process_pyshark_packet(pkt)
                return
            except Exception as e:
                print(f"[NDR-CAPTURE] [ERROR] Falló el motor de captura de Pyshark: {e}")
        
        print("[NDR-CAPTURE] [CRÍTICO] No hay motores de captura de red disponibles o faltan permisos raw socket.")
        print("[NDR-CAPTURE] El sistema NDR continuará en modo pasivo/archivo (PCAP).")

    def _process_scapy_packet(self, pkt):
        """
        Procesa un paquete individual de Scapy y reconstruye flujos bidireccionales.
        """
        if not pkt.haslayer(IP):
            return
            
        ip_layer = pkt[IP]
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst
        protocol = 'OTHER'
        src_port = 0
        dst_port = 0
        bytes_sent = len(pkt)
        dns_query = None
        icmp_type = None
        icmp_code = None
        icmp_payload_len = None
        
        if pkt.haslayer(TCP):
            protocol = 'TCP'
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport
        elif pkt.haslayer(UDP):
            protocol = 'UDP'
            src_port = pkt[UDP].sport
            dst_port = pkt[UDP].dport
            # Extracción de DNS
            if pkt.haslayer(DNS) and pkt.haslayer(DNSQR):
                dns_layer = pkt[DNS]
                if dns_layer.qd:
                    qname = dns_layer.qd.qname
                    if isinstance(qname, bytes):
                        dns_query = qname.decode('utf-8', errors='ignore')
                    else:
                        dns_query = str(qname)
        elif pkt.haslayer(ICMP):
            protocol = 'ICMP'
            icmp_layer = pkt[ICMP]
            icmp_type = icmp_layer.type
            icmp_code = icmp_layer.code
            icmp_payload_len = len(icmp_layer.payload) if icmp_layer.payload else 0

        self._update_flow_data(
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            bytes_sent=bytes_sent,
            dns_query=dns_query,
            icmp_type=icmp_type,
            icmp_code=icmp_code,
            icmp_payload_len=icmp_payload_len
        )

    def _process_pyshark_packet(self, pkt):
        """
        Procesa un paquete individual de Pyshark para el fallback.
        """
        try:
            if 'IP' not in pkt:
                return
            src_ip = pkt.ip.src
            dst_ip = pkt.ip.dst
            protocol = pkt.transport_layer or 'OTHER'
            src_port = 0
            dst_port = 0
            bytes_sent = int(pkt.length)
            dns_query = None
            icmp_type = None
            icmp_code = None
            icmp_payload_len = None
            
            if hasattr(pkt, 'tcp'):
                protocol = 'TCP'
                src_port = int(pkt.tcp.srcport)
                dst_port = int(pkt.tcp.dstport)
            elif hasattr(pkt, 'udp'):
                protocol = 'UDP'
                src_port = int(pkt.udp.srcport)
                dst_port = int(pkt.udp.dstport)
                if hasattr(pkt, 'dns') and hasattr(pkt.dns, 'qry_name'):
                    dns_query = str(pkt.dns.qry_name)
            elif hasattr(pkt, 'icmp'):
                protocol = 'ICMP'
                if hasattr(pkt.icmp, 'type'):
                    icmp_type = int(pkt.icmp.type)
                if hasattr(pkt.icmp, 'code'):
                    icmp_code = int(pkt.icmp.code)
                if hasattr(pkt.icmp, 'length'):
                    icmp_payload_len = int(pkt.icmp.length)

            self._update_flow_data(
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                bytes_sent=bytes_sent,
                dns_query=dns_query,
                icmp_type=icmp_type,
                icmp_code=icmp_code,
                icmp_payload_len=icmp_payload_len
            )
        except Exception:
            pass

    def _update_flow_data(
        self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str,
        bytes_sent: int, dns_query: Optional[str] = None, icmp_type: Optional[int] = None,
        icmp_code: Optional[int] = None, icmp_payload_len: Optional[int] = None
    ):
        """
        Actualiza el mapa interno de flujos bidireccionales de manera thread-safe.
        """
        now = datetime.utcnow()
        forward_key = (src_ip, dst_ip, src_port, dst_port, protocol)
        reverse_key = (dst_ip, src_ip, dst_port, src_port, protocol)
        
        with self.lock:
            # Si el flujo existe en la dirección forward (origen -> destino original)
            if forward_key in self.active_flows:
                flow = self.active_flows[forward_key]
                flow.bytes_sent += bytes_sent
                flow.duration_ms = (now - flow.timestamp).total_seconds() * 1000.0
                if dns_query and not flow.dns_query:
                    flow.dns_query = dns_query
            
            # Si el flujo existe en la dirección reverse (destino -> origen original)
            elif reverse_key in self.active_flows:
                flow = self.active_flows[reverse_key]
                # Los bytes del paquete actual son recibidos en la perspectiva de la conexión original
                flow.bytes_recv += bytes_sent
                flow.duration_ms = (now - flow.timestamp).total_seconds() * 1000.0
                if dns_query and not flow.dns_query:
                    flow.dns_query = dns_query
                    
            # Si es una nueva conexión/flujo de datos
            else:
                # Si el búfer circular está lleno, eliminamos el flujo más viejo de active_flows
                if len(self.circular_buffer) >= self.max_flows:
                    oldest = self.circular_buffer[0]
                    oldest_fwd = (oldest.src_ip, oldest.dst_ip, oldest.src_port, oldest.dst_port, oldest.protocol)
                    oldest_rev = (oldest.dst_ip, oldest.src_ip, oldest.dst_port, oldest.src_port, oldest.protocol)
                    self.active_flows.pop(oldest_fwd, None)
                    self.active_flows.pop(oldest_rev, None)
                
                flow = TrafficFlow(
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=protocol,
                    bytes_sent=bytes_sent,
                    bytes_recv=0,
                    duration_ms=0.0,
                    timestamp=now,
                    dns_query=dns_query,
                    icmp_type=icmp_type,
                    icmp_code=icmp_code,
                    icmp_payload_len=icmp_payload_len
                )
                
                self.active_flows[forward_key] = flow
                self.circular_buffer.append(flow)


def load_pcap(path: str) -> List[TrafficFlow]:
    """
    Carga de manera estática un archivo PCAP y reconstruye sus flujos de datos.
    Soporta lectura mediante Scapy y Pyshark como respaldo.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"El archivo PCAP en la ruta '{path}' no existe.")
        
    flows: List[TrafficFlow] = []
    local_flows: Dict[Tuple, TrafficFlow] = {}
    
    if SCAPY_AVAILABLE:
        try:
            print(f"[NDR-CAPTURE] Cargando PCAP con Scapy: {path}")
            packets = rdpcap(path)
            for pkt in packets:
                if not pkt.haslayer(IP):
                    continue
                ip_layer = pkt[IP]
                src_ip = ip_layer.src
                dst_ip = ip_layer.dst
                protocol = 'OTHER'
                src_port = 0
                dst_port = 0
                bytes_sent = len(pkt)
                dns_query = None
                icmp_type = None
                icmp_code = None
                icmp_payload_len = None
                
                if pkt.haslayer(TCP):
                    protocol = 'TCP'
                    src_port = pkt[TCP].sport
                    dst_port = pkt[TCP].dport
                elif pkt.haslayer(UDP):
                    protocol = 'UDP'
                    src_port = pkt[UDP].sport
                    dst_port = pkt[UDP].dport
                    if pkt.haslayer(DNS) and pkt.haslayer(DNSQR):
                        dns_layer = pkt[DNS]
                        if dns_layer.qd:
                            qname = dns_layer.qd.qname
                            if isinstance(qname, bytes):
                                dns_query = qname.decode('utf-8', errors='ignore')
                            else:
                                dns_query = str(qname)
                elif pkt.haslayer(ICMP):
                    protocol = 'ICMP'
                    icmp_layer = pkt[ICMP]
                    icmp_type = icmp_layer.type
                    icmp_code = icmp_layer.code
                    icmp_payload_len = len(icmp_layer.payload) if icmp_layer.payload else 0
                    
                forward_key = (src_ip, dst_ip, src_port, dst_port, protocol)
                reverse_key = (dst_ip, src_ip, dst_port, src_port, protocol)
                
                # Timestamp del paquete PCAP (en segundos epoch)
                pkt_time = datetime.utcfromtimestamp(float(pkt.time))
                
                if forward_key in local_flows:
                    flow = local_flows[forward_key]
                    flow.bytes_sent += bytes_sent
                    flow.duration_ms = (pkt_time - flow.timestamp).total_seconds() * 1000.0
                    if dns_query and not flow.dns_query:
                        flow.dns_query = dns_query
                elif reverse_key in local_flows:
                    flow = local_flows[reverse_key]
                    flow.bytes_recv += bytes_sent
                    flow.duration_ms = (pkt_time - flow.timestamp).total_seconds() * 1000.0
                    if dns_query and not flow.dns_query:
                        flow.dns_query = dns_query
                else:
                    flow = TrafficFlow(
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=src_port,
                        dst_port=dst_port,
                        protocol=protocol,
                        bytes_sent=bytes_sent,
                        bytes_recv=0,
                        duration_ms=0.0,
                        timestamp=pkt_time,
                        dns_query=dns_query,
                        icmp_type=icmp_type,
                        icmp_code=icmp_code,
                        icmp_payload_len=icmp_payload_len
                    )
                    local_flows[forward_key] = flow
                    flows.append(flow)
            return flows
        except Exception as e:
            print(f"[NDR-CAPTURE] Error leyendo PCAP con Scapy: {e}. Intentando fallback con Pyshark...")
            
    if PYSHARK_AVAILABLE:
        try:
            print(f"[NDR-CAPTURE] Cargando PCAP con Pyshark: {path}")
            cap = pyshark.FileCapture(path)
            for pkt in cap:
                if 'IP' not in pkt:
                    continue
                src_ip = pkt.ip.src
                dst_ip = pkt.ip.dst
                protocol = pkt.transport_layer or 'OTHER'
                src_port = 0
                dst_port = 0
                bytes_sent = int(pkt.length)
                dns_query = None
                icmp_type = None
                icmp_code = None
                icmp_payload_len = None
                
                if hasattr(pkt, 'tcp'):
                    protocol = 'TCP'
                    src_port = int(pkt.tcp.srcport)
                    dst_port = int(pkt.tcp.dstport)
                elif hasattr(pkt, 'udp'):
                    protocol = 'UDP'
                    src_port = int(pkt.udp.srcport)
                    dst_port = int(pkt.udp.dstport)
                    if hasattr(pkt, 'dns') and hasattr(pkt.dns, 'qry_name'):
                        dns_query = str(pkt.dns.qry_name)
                elif hasattr(pkt, 'icmp'):
                    protocol = 'ICMP'
                    if hasattr(pkt.icmp, 'type'):
                        icmp_type = int(pkt.icmp.type)
                    if hasattr(pkt.icmp, 'code'):
                        icmp_code = int(pkt.icmp.code)
                    if hasattr(pkt.icmp, 'length'):
                        icmp_payload_len = int(pkt.icmp.length)
                        
                forward_key = (src_ip, dst_ip, src_port, dst_port, protocol)
                reverse_key = (dst_ip, src_ip, dst_port, src_port, protocol)
                
                pkt_time = datetime.utcfromtimestamp(float(pkt.sniff_timestamp))
                
                if forward_key in local_flows:
                    flow = local_flows[forward_key]
                    flow.bytes_sent += bytes_sent
                    flow.duration_ms = (pkt_time - flow.timestamp).total_seconds() * 1000.0
                    if dns_query and not flow.dns_query:
                        flow.dns_query = dns_query
                elif reverse_key in local_flows:
                    flow = local_flows[reverse_key]
                    flow.bytes_recv += bytes_sent
                    flow.duration_ms = (pkt_time - flow.timestamp).total_seconds() * 1000.0
                    if dns_query and not flow.dns_query:
                        flow.dns_query = dns_query
                else:
                    flow = TrafficFlow(
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=src_port,
                        dst_port=dst_port,
                        protocol=protocol,
                        bytes_sent=bytes_sent,
                        bytes_recv=0,
                        duration_ms=0.0,
                        timestamp=pkt_time,
                        dns_query=dns_query,
                        icmp_type=icmp_type,
                        icmp_code=icmp_code,
                        icmp_payload_len=icmp_payload_len
                    )
                    local_flows[forward_key] = flow
                    flows.append(flow)
            cap.close()
            return flows
        except Exception as e:
            print(f"[NDR-CAPTURE] Error leyendo PCAP con Pyshark: {e}")
            
    print("[NDR-CAPTURE] [CRÍTICO] No fue posible analizar el PCAP. Instale Scapy o Pyshark en el entorno.")
    return flows
