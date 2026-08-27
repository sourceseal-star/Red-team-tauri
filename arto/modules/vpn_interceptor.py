"""
VPN Interceptor - Captura de Tráfico Real vía VpnService
=====================================================
Recibe paquetes de Android VpnService y los analiza.
Integra con el attack_simulator existente.
"""

import asyncio
import datetime
import json
import struct
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import socket


class TrafficType(Enum):
    """Tipos de tráfico"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"
    ARP = "arp"
    UNKNOWN = "unknown"


class SeverityLevel(Enum):
    """Niveles de severidad"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CapturedPacket:
    """Paquete capturado"""
    packet_id: str
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: TrafficType
    payload: bytes
    length: int
    
    def to_dict(self) -> Dict:
        return {
            "packet_id": self.packet_id,
            "timestamp": self.timestamp,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol.value,
            "payload": self.payload.hex()[:200],
            "length": self.length
        }


@dataclass
class TrafficAnalysis:
    """Análisis de tráfico"""
    analysis_id: str
    timestamp: str
    packet_count: int
    threats: List[Dict]
    anomalies: List[Dict]
    statistics: Dict
    top_connections: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp,
            "packet_count": self.packet_count,
            "threats": self.threats,
            "anomalies": self.anomalies,
            "statistics": self.statistics,
            "top_connections": self.top_connections
        }


class VpnInterceptor:
    """
    Interceptor de Tráfico vía VpnService
    ====================================
    Recibe paquetes de Android VpnService y los analiza.
    """
    
    def __init__(self):
        self.running = False
        self.packet_queue = asyncio.Queue()
        self.analysis_rules = self._load_default_rules()
        self.captured_packets: List[CapturedPacket] = []
        self.traffic_stats: Dict = self._init_stats()
        self.connection_tracker: Dict[str, Dict] = {}
        self.threat_detected_callback: Optional[Callable] = None
        self.anomaly_detected_callback: Optional[Callable] = None
        self.tauri_connection = None
    
    def _init_stats(self) -> Dict:
        """Inicializa estadísticas"""
        return {
            "total_packets": 0,
            "packets_by_protocol": {t.value: 0 for t in TrafficType},
            "total_bytes": 0,
            "connections": {},
            "threats_detected": 0,
            "anomalies_detected": 0,
            "start_time": datetime.datetime.now().isoformat()
        }
    
    def _load_default_rules(self) -> List[Dict]:
        """Carga reglas de análisis por defecto"""
        return [
            {
                "id": "port_scan",
                "name": "Port Scanning",
                "type": "behavioral",
                "condition": self._detect_port_scan,
                "severity": SeverityLevel.HIGH,
                "description": "Múltiples conexiones a diferentes puertos en poco tiempo"
            },
            {
                "id": "brute_force",
                "name": "Brute Force Attack",
                "type": "behavioral",
                "condition": self._detect_brute_force,
                "severity": SeverityLevel.CRITICAL,
                "description": "Múltiples intentos de conexión fallidos a mismo destino"
            },
            {
                "id": "data_exfiltration",
                "name": "Data Exfiltration",
                "type": "behavioral",
                "condition": self._detect_data_exfiltration,
                "severity": SeverityLevel.HIGH,
                "description": "Transferencia de grandes cantidades de datos a servidor externo"
            },
            {
                "id": "c2_communication",
                "name": "C2 Communication",
                "type": "threat",
                "condition": self._detect_c2_communication,
                "severity": SeverityLevel.CRITICAL,
                "description": "Comunicación con servidor conocido de C2"
            },
            {
                "id": "dns_tunneling",
                "name": "DNS Tunneling",
                "type": "threat",
                "condition": self._detect_dns_tunneling,
                "severity": SeverityLevel.HIGH,
                "description": "Tráfico DNS sospechoso (posible tunneling)"
            },
            {
                "id": "beaconing",
                "name": "Beaconing",
                "type": "threat",
                "condition": self._detect_beaconing,
                "severity": SeverityLevel.MEDIUM,
                "description": "Comunicación periódica con servidor externo"
            }
        ]
    
    async def start(self, tauri_connection=None):
        """Inicia el interceptor de tráfico"""
        print("🔌 Iniciando VpnInterceptor...")
        self.tauri_connection = tauri_connection
        self.running = True
        self._init_stats()
        asyncio.create_task(self._process_packets())
        print("✅ VpnInterceptor listo para recibir paquetes")
    
    async def stop(self):
        """Detiene el interceptor de tráfico"""
        print("🛑 Deteniendo VpnInterceptor...")
        self.running = False
        while not self.packet_queue.empty():
            try:
                self.packet_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        print("✅ VpnInterceptor detenido")
    
    async def receive_packet(self, packet_data: Dict):
        """Recibe un paquete desde VpnService (llamado desde Tauri)"""
        if not self.running:
            await self.start()
        packet = CapturedPacket(
            packet_id=f"pkt_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            timestamp=datetime.datetime.now().isoformat(),
            src_ip=packet_data.get("src_ip", "0.0.0.0"),
            dst_ip=packet_data.get("dst_ip", "0.0.0.0"),
            src_port=packet_data.get("src_port", 0),
            dst_port=packet_data.get("dst_port", 0),
            protocol=TrafficType(packet_data.get("protocol", "unknown")),
            payload=packet_data.get("payload", b""),
            length=packet_data.get("length", 0)
        )
        await self.packet_queue.put(packet)
        self._update_stats(packet)
    
    async def _process_packets(self):
        """Procesa paquetes de la cola"""
        while self.running:
            try:
                packet = await asyncio.wait_for(self.packet_queue.get(), timeout=1.0)
                self.captured_packets.append(packet)
                if len(self.captured_packets) > 10000:
                    self.captured_packets = self.captured_packets[-10000:]
                analysis = await self._analyze_packet(packet)
                if analysis:
                    if analysis.get("type") == "threat" and self.threat_detected_callback:
                        await self.threat_detected_callback(analysis)
                    elif analysis.get("type") == "anomaly" and self.anomaly_detected_callback:
                        await self.anomaly_detected_callback(analysis)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"⚠️ Error procesando paquete: {e}")
                continue
    
    def _update_stats(self, packet: CapturedPacket):
        """Actualiza estadísticas"""
        self.traffic_stats["total_packets"] += 1
        self.traffic_stats["total_bytes"] += packet.length
        protocol = packet.protocol.value
        if protocol in self.traffic_stats["packets_by_protocol"]:
            self.traffic_stats["packets_by_protocol"][protocol] += 1
        conn_key = f"{packet.src_ip}:{packet.src_port}->{packet.dst_ip}:{packet.dst_port}"
        if conn_key not in self.traffic_stats["connections"]:
            self.traffic_stats["connections"][conn_key] = {
                "count": 0, "bytes": 0,
                "first_seen": packet.timestamp, "last_seen": packet.timestamp
            }
        self.traffic_stats["connections"][conn_key]["count"] += 1
        self.traffic_stats["connections"][conn_key]["bytes"] += packet.length
        self.traffic_stats["connections"][conn_key]["last_seen"] = packet.timestamp
    
    async def _analyze_packet(self, packet: CapturedPacket) -> Optional[Dict]:
        """Analiza un paquete usando reglas"""
        for rule in self.analysis_rules:
            try:
                result = rule["condition"](packet)
                if result:
                    return {
                        "type": rule["type"],
                        "rule_id": rule["id"],
                        "name": rule["name"],
                        "severity": rule["severity"].value,
                        "description": rule["description"],
                        "packet": packet.to_dict(),
                        "details": result,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
            except Exception as e:
                print(f"⚠️ Error en regla {rule['id']}: {e}")
                continue
        return None
    
    def _detect_port_scan(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta escaneo de puertos"""
        conn_key = packet.dst_ip
        if conn_key not in self.connection_tracker:
            self.connection_tracker[conn_key] = {"ports": set(), "timestamps": [], "first_seen": packet.timestamp}
        tracker = self.connection_tracker[conn_key]
        tracker["ports"].add(packet.dst_port)
        tracker["timestamps"].append(packet.timestamp)
        cutoff = datetime.datetime.fromisoformat(packet.timestamp) - datetime.timedelta(seconds=5)
        tracker["timestamps"] = [t for t in tracker["timestamps"] if datetime.datetime.fromisoformat(t) >= cutoff]
        if len(tracker["ports"]) > 5 and len(tracker["timestamps"]) > 5:
            return {"ports_scanned": list(tracker["ports"]), "count": len(tracker["ports"]), "time_window": "5s"}
        return None
    
    def _detect_brute_force(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta fuerza bruta"""
        conn_key = f"{packet.dst_ip}:{packet.dst_port}"
        if conn_key not in self.connection_tracker:
            self.connection_tracker[conn_key] = {"attempts": 0, "timestamps": [], "first_seen": packet.timestamp}
        tracker = self.connection_tracker[conn_key]
        tracker["attempts"] += 1
        tracker["timestamps"].append(packet.timestamp)
        cutoff = datetime.datetime.fromisoformat(packet.timestamp) - datetime.timedelta(seconds=10)
        tracker["timestamps"] = [t for t in tracker["timestamps"] if datetime.datetime.fromisoformat(t) >= cutoff]
        if tracker["attempts"] > 10 and len(tracker["timestamps"]) > 10:
            return {"target": f"{packet.dst_ip}:{packet.dst_port}", "attempts": tracker["attempts"], "time_window": "10s"}
        return None
    
    def _detect_data_exfiltration(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta exfiltración de datos"""
        conn_key = f"{packet.src_ip}->{packet.dst_ip}"
        if conn_key not in self.connection_tracker:
            self.connection_tracker[conn_key] = {"bytes_sent": 0, "packets": 0, "first_seen": packet.timestamp}
        tracker = self.connection_tracker[conn_key]
        tracker["bytes_sent"] += packet.length
        tracker["packets"] += 1
        if tracker["bytes_sent"] > 10 * 1024 * 1024:
            return {"source": packet.src_ip, "destination": packet.dst_ip, "bytes": tracker["bytes_sent"], "packets": tracker["packets"]}
        return None
    
    def _detect_c2_communication(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta comunicación con servidores C2"""
        c2_indicators = ["1.1.1.1", "malicious-domain.com"]
        if packet.dst_ip in c2_indicators:
            return {"c2_server": packet.dst_ip, "protocol": packet.protocol.value}
        return None
    
    def _detect_dns_tunneling(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta DNS tunneling"""
        if packet.protocol != TrafficType.DNS:
            return None
        payload_str = packet.payload.decode('utf-8', errors='ignore')
        if len(payload_str) > 100:
            return {"query": payload_str[:100], "length": len(payload_str)}
        return None
    
    def _detect_beaconing(self, packet: CapturedPacket) -> Optional[Dict]:
        """Detecta beaconing"""
        conn_key = f"{packet.src_ip}->{packet.dst_ip}:{packet.dst_port}"
        if conn_key not in self.connection_tracker:
            self.connection_tracker[conn_key] = {"intervals": [], "last_seen": packet.timestamp}
        tracker = self.connection_tracker[conn_key]
        if tracker["last_seen"]:
            last = datetime.datetime.fromisoformat(tracker["last_seen"])
            current = datetime.datetime.fromisoformat(packet.timestamp)
            interval = (current - last).total_seconds()
            tracker["intervals"].append(interval)
        tracker["last_seen"] = packet.timestamp
        if len(tracker["intervals"]) > 5:
            avg_interval = sum(tracker["intervals"]) / len(tracker["intervals"])
            similar = sum(1 for i in tracker["intervals"] if abs(i - avg_interval) / avg_interval < 0.1)
            if similar >= 5:
                return {"target": f"{packet.dst_ip}:{packet.dst_port}", "interval": avg_interval, "count": similar}
        return None
    
    def _resolve_domain(self, domain: str) -> str:
        try:
            return socket.gethostbyname(domain)
        except:
            return ""
    
    async def get_stats(self) -> Dict:
        return {
            **self.traffic_stats,
            "uptime": (datetime.datetime.now() - datetime.datetime.fromisoformat(self.traffic_stats["start_time"])).total_seconds()
        }
    
    async def get_captured_packets(self, limit: int = 100) -> List[Dict]:
        return [p.to_dict() for p in self.captured_packets[-limit:]]
    
    async def get_top_connections(self, limit: int = 10) -> List[Dict]:
        connections = list(self.traffic_stats["connections"].values())
        connections.sort(key=lambda x: x["bytes"], reverse=True)
        return connections[:limit]
    
    async def get_threats(self) -> List[Dict]:
        return []
    
    async def get_analysis(self) -> TrafficAnalysis:
        threats = await self.get_threats()
        anomalies = []
        top_connections = await self.get_top_connections()
        return TrafficAnalysis(
            analysis_id=f"analysis_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            timestamp=datetime.datetime.now().isoformat(),
            packet_count=self.traffic_stats["total_packets"],
            threats=threats,
            anomalies=anomalies,
            statistics=await self.get_stats(),
            top_connections=top_connections
        )
    
    def on_threat_detected(self, callback: Callable):
        self.threat_detected_callback = callback
    
    def on_anomaly_detected(self, callback: Callable):
        self.anomaly_detected_callback = callback
    
    async def clear_stats(self):
        self.traffic_stats = self._init_stats()
        self.connection_tracker = {}
        self.captured_packets = []


vpn_interceptor = VpnInterceptor()
