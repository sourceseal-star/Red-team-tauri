# -*- coding: utf-8 -*-
"""
=== FILE: ndr/ml_detector.py ===
Módulo de Detección NDR basado en Aprendizaje Automático (ML) y Análisis de Comportamiento.
Este módulo implementa algoritmos heurísticos, estadísticos y de Machine Learning para identificar
anomalías en flujos de red que indiquen actividades maliciosas como C2, exfiltración de datos,
tunneling DNS e ICMP.
"""

import math
from datetime import datetime
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Intentamos importar numpy y sklearn. Si no estuvieran instalados, se asumen disponibles
# en producción o se proveen fallbacks básicos.
try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class TrafficFlow:
    """
    Representa un flujo de tráfico de red unificado para análisis.
    """
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # 'TCP', 'UDP', 'ICMP', etc.
    bytes_sent: int
    bytes_recv: int
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    dns_query: Optional[str] = None
    dns_answers: List[str] = field(default_factory=list)
    icmp_type: Optional[int] = None
    icmp_code: Optional[int] = None
    icmp_payload_len: Optional[int] = None


@dataclass
class AnomalyAlert:
    """
    Representa una alerta de anomalía generada por los detectores de NDR.
    """
    detector_name: str
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description: str
    flow: TrafficFlow
    timestamp: datetime = field(default_factory=datetime.utcnow)
    extra_data: Dict[str, Any] = field(default_factory=dict)


def calculate_entropy(s: str) -> float:
    """
    Calcula la entropía de Shannon para una cadena de caracteres dada.
    Útil para medir la aleatoriedad en nombres de subdominios de consultas DNS.
    """
    if not s:
        return 0.0
    entropy = 0.0
    length = len(s)
    counts = collections_counter = {}
    for char in s:
        collections_counter[char] = collections_counter.get(char, 0) + 1
    
    for count in collections_counter.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


class ZScoreAnomalyDetector:
    """
    Detector estadístico adaptativo que utiliza Z-Score basado en una ventana rodante
    de las últimas 100 muestras de tráfico por combinación de IP/Puerto destino.
    Alerta cuando el valor actual de bytes (enviados/recibidos) o duración se desvía Z > 3.0.
    """
    def __init__(self, min_samples: int = 15, z_threshold: float = 3.0):
        self.min_samples = min_samples
        self.z_threshold = z_threshold
        # Estructura: { (dst_ip, dst_port): { 'bytes_sent': deque, 'bytes_recv': deque, 'duration_ms': deque } }
        self.history = defaultdict(lambda: {
            'bytes_sent': deque(maxlen=100),
            'bytes_recv': deque(maxlen=100),
            'duration_ms': deque(maxlen=100)
        })

    def analyze(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        alerts = []
        key = (flow.dst_ip, flow.dst_port)
        metrics = {
            'bytes_sent': flow.bytes_sent,
            'bytes_recv': flow.bytes_recv,
            'duration_ms': flow.duration_ms
        }
        
        hist = self.history[key]
        
        for name, value in metrics.items():
            q = hist[name]
            if len(q) >= self.min_samples:
                # Calcular media
                mean = sum(q) / len(q)
                # Calcular desviación estándar
                variance = sum((x - mean) ** 2 for x in q) / len(q)
                std_dev = math.sqrt(variance)
                
                if std_dev > 0:
                    z = (value - mean) / std_dev
                else:
                    # Si la desviación estándar es 0, significa que todas las muestras previas eran idénticas.
                    # Si el nuevo valor es mayor, es anómalo con score infinito teórico.
                    z = float('inf') if value > mean else 0.0
                
                if z > self.z_threshold:
                    alerts.append(AnomalyAlert(
                        detector_name="ZScoreAnomalyDetector",
                        severity="MEDIUM",
                        description=(
                            f"Anomalía estadística detectada por Z-Score en '{name}'. "
                            f"Valor actual: {value:.2f}, Media: {mean:.2f}, Desv.Est: {std_dev:.2f} (Z = {z:.2f} > {self.z_threshold})"
                        ),
                        flow=flow,
                        extra_data={
                            "metric": name,
                            "current_value": value,
                            "z_score": z if z != float('inf') else 999.0,
                            "mean": mean,
                            "std_dev": std_dev,
                            "window_size": len(q)
                        }
                    ))
            
            # Actualizamos el historial adaptativo con el nuevo valor
            q.append(value)
            
        return alerts


class IsolationForestDetector:
    """
    Detector comportamental avanzado basado en el algoritmo Isolation Forest de Scikit-Learn.
    Analiza un conjunto de características multidimensionales de cada flujo de red:
    [bytes_sent, bytes_recv, duration_ms, dst_port, hour_of_day, day_of_week].
    Entrena el modelo en caliente (online/rolling retraining) con una ventana rodante
    de las últimas 1000 muestras globales de tráfico.
    """
    def __init__(self, window_size: int = 1000, retrain_interval: int = 50, contamination: float = 0.01):
        self.window_size = window_size
        self.retrain_interval = retrain_interval
        self.contamination = contamination
        self.buffer = []
        self.clf = None
        self.flows_since_retrain = 0

    def _extract_features(self, flow: TrafficFlow) -> List[float]:
        """
        Extrae el vector numérico de características requerido para el modelo.
        """
        hour = flow.timestamp.hour
        day = flow.timestamp.weekday()
        return [
            float(flow.bytes_sent),
            float(flow.bytes_recv),
            float(flow.duration_ms),
            float(flow.dst_port),
            float(hour),
            float(day)
        ]

    def analyze(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        alerts = []
        if not SKLEARN_AVAILABLE:
            # Fallback en caso de que sklearn no esté instalado en el entorno de ejecución
            return alerts

        feats = self._extract_features(flow)
        
        # Añadir al búfer rodante global
        self.buffer.append(feats)
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)
            
        # Si ya existe un modelo entrenado, evaluamos la anomalía
        if self.clf is not None:
            try:
                # Predict retorna -1 para anomalía y 1 para normal
                pred = self.clf.predict([feats])[0]
                if pred == -1:
                    score = self.clf.decision_function([feats])[0]
                    # Cuanto más negativo el score, más profunda es la anomalía
                    alerts.append(AnomalyAlert(
                        detector_name="IsolationForestDetector",
                        severity="HIGH",
                        description=(
                            f"Flujo identificado como anomalía comportamental por Isolation Forest "
                            f"(Anomaly Score: {score:.4f})"
                        ),
                        flow=flow,
                        extra_data={
                            "anomaly_score": float(score),
                            "features_evaluated": {
                                "bytes_sent": flow.bytes_sent,
                                "bytes_recv": flow.bytes_recv,
                                "duration_ms": flow.duration_ms,
                                "dst_port": flow.dst_port,
                                "hour_of_day": feats[4],
                                "day_of_week": feats[5]
                            }
                        }
                    ))
            except Exception as e:
                # Prevención de fallos en producción ante inconsistencias de predicción
                pass
                
        self.flows_since_retrain += 1
        
        # Re-entrenamiento periódico del bosque cuando acumulamos suficientes muestras
        # Requiere al menos un mínimo de 100 muestras iniciales para tener significancia estadística
        if len(self.buffer) >= 100 and (self.flows_since_retrain >= self.retrain_interval or self.clf is None):
            try:
                X = np.array(self.buffer)
                self.clf = IsolationForest(
                    contamination=self.contamination,
                    random_state=42,
                    n_estimators=100,
                    n_jobs=-1
                )
                self.clf.fit(X)
                self.flows_since_retrain = 0
            except Exception:
                pass
                
        return alerts


class DNSTunnelingDetector:
    """
    Detector especializado en DNS Tunneling. Monitorea consultas DNS buscando:
    1. Longitud del subdominio superior a 50 caracteres (típico de exfiltración encoded).
    2. Entropía de Shannon superior a 4.5 bits (indica datos codificados / cifrados, no legible).
    3. Frecuencia de consultas DNS > 100 por minuto al mismo dominio raíz.
    """
    def __init__(self, max_subdomain_len: int = 50, min_entropy: float = 4.5, max_queries_per_min: int = 100):
        self.max_subdomain_len = max_subdomain_len
        self.min_entropy = min_entropy
        self.max_queries_per_min = max_queries_per_min
        # Historial: { dominio_raiz: deque de timestamps (float) }
        self.domain_history = defaultdict(deque)

    def _parse_query(self, query: str) -> tuple[str, str]:
        """
        Divide una consulta DNS en subdominio y dominio base de segundo nivel.
        Ejemplo: 'abcdef123456.data.attacker-c2.com' -> ('abcdef123456.data', 'attacker-c2.com')
        """
        if not query:
            return "", ""
        query = query.strip().rstrip('.')
        parts = query.split('.')
        if len(parts) <= 2:
            return "", query
        # Dominio base (ej: attacker-c2.com)
        domain = ".".join(parts[-2:])
        # Subdominio (ej: abcdef123456.data)
        subdomain = ".".join(parts[:-2])
        return subdomain, domain

    def analyze(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        alerts = []
        
        # Filtrar si el flujo no contiene una query de DNS válida
        if not flow.dns_query:
            return alerts
            
        subdomain, domain = self._parse_query(flow.dns_query)
        if not domain:
            return alerts
            
        now_ts = flow.timestamp.timestamp()
        
        # Actualización de la frecuencia de consultas al mismo dominio en el último minuto
        q_history = self.domain_history[domain]
        while q_history and now_ts - q_history[0] > 60.0:
            q_history.popleft()
        q_history.append(now_ts)
        
        # 1. Alerta de Frecuencia de Queries
        if len(q_history) > self.max_queries_per_min:
            alerts.append(AnomalyAlert(
                detector_name="DNSTunnelingDetector",
                severity="HIGH",
                description=(
                    f"Tráfico DNS sospechoso: Frecuencia de consultas anómala para el dominio '{domain}' "
                    f"({len(q_history)} consultas en el último minuto, límite: {self.max_queries_per_min})"
                ),
                flow=flow,
                extra_data={
                    "domain": domain,
                    "queries_last_minute": len(q_history),
                    "threshold": self.max_queries_per_min
                }
            ))
            
        # 2. Alerta de longitud de subdominio
        if len(subdomain) > self.max_subdomain_len:
            alerts.append(AnomalyAlert(
                detector_name="DNSTunnelingDetector",
                severity="HIGH",
                description=(
                    f"Tráfico DNS sospechoso: Subdominio excesivamente largo ({len(subdomain)} caracteres, "
                    f"límite: {self.max_subdomain_len}). Posible exfiltración/túnel."
                ),
                flow=flow,
                extra_data={
                    "subdomain": subdomain,
                    "subdomain_length": len(subdomain),
                    "full_query": flow.dns_query
                }
            ))
            
        # 3. Alerta de Entropía de Shannon (solo si el subdominio tiene una longitud mínima para evitar falsos positivos)
        if len(subdomain) > 12:
            entropy = calculate_entropy(subdomain)
            if entropy > self.min_entropy:
                alerts.append(AnomalyAlert(
                    detector_name="DNSTunnelingDetector",
                    severity="HIGH",
                    description=(
                        f"Tráfico DNS sospechoso: Entropía de subdominio elevada ({entropy:.2f} bits, "
                        f"límite: {self.min_entropy}). Indica ofuscación o encripción de datos."
                    ),
                    flow=flow,
                    extra_data={
                        "subdomain": subdomain,
                        "entropy": entropy,
                        "full_query": flow.dns_query
                    }
                ))
                
        return alerts


class ICMPTunnelingDetector:
    """
    Detector especializado en ICMP Tunneling. Evalúa:
    1. Tamaño de payload ICMP anómalo superior a 100 bytes (las solicitudes de ping normales suelen ser pequeñas).
    2. Alta frecuencia de paquetes ICMP (> 60 paquetes por minuto) provenientes de la misma IP.
    """
    def __init__(self, max_payload_len: int = 100, max_freq_per_min: int = 60):
        self.max_payload_len = max_payload_len
        self.max_freq_per_min = max_freq_per_min
        # Historial de pings por origen: { src_ip: deque de timestamps (float) }
        self.icmp_history = defaultdict(deque)

    def analyze(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        alerts = []
        
        # Validar si el protocolo es ICMP
        if flow.protocol.upper() != 'ICMP':
            return alerts
            
        # 1. Validación de tamaño de payload
        # En flujos de red reales, usamos icmp_payload_len; como alternativa fallback se usan los bytes enviados
        payload_len = flow.icmp_payload_len if flow.icmp_payload_len is not None else flow.bytes_sent
        if payload_len > self.max_payload_len:
            alerts.append(AnomalyAlert(
                detector_name="ICMPTunnelingDetector",
                severity="MEDIUM",
                description=(
                    f"Túnel ICMP sospechoso: Tamaño de payload anómalo detectado ({payload_len} bytes, "
                    f"límite permitido: {self.max_payload_len} bytes)."
                ),
                flow=flow,
                extra_data={
                    "icmp_payload_len": payload_len,
                    "icmp_type": flow.icmp_type,
                    "icmp_code": flow.icmp_code
                }
            ))
            
        # 2. Validación de frecuencia/tasa de pings
        now_ts = flow.timestamp.timestamp()
        src_ip = flow.src_ip
        
        history = self.icmp_history[src_ip]
        while history and now_ts - history[0] > 60.0:
            history.popleft()
        history.append(now_ts)
        
        if len(history) > self.max_freq_per_min:
            alerts.append(AnomalyAlert(
                detector_name="ICMPTunnelingDetector",
                severity="HIGH",
                description=(
                    f"Túnel ICMP sospechoso: Tasa anormal de paquetes ICMP desde {src_ip} "
                    f"({len(history)} paquetes/minuto, límite: {self.max_freq_per_min})."
                ),
                flow=flow,
                extra_data={
                    "src_ip": src_ip,
                    "packets_last_minute": len(history),
                    "threshold": self.max_freq_per_min
                }
            ))
            
        return alerts


class MLNDREngine:
    """
    Engine NDR que consolida e integra todos los detectores de comportamiento
    y Machine Learning. Analiza flujos individuales ejecutándolos contra todos
    los detectores configurados y consolida las alertas detectadas.
    """
    def __init__(self):
        self.detectors = [
            ZScoreAnomalyDetector(),
            IsolationForestDetector(),
            DNSTunnelingDetector(),
            ICMPTunnelingDetector()
        ]

    def analyze(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        """
        Analiza un flujo de red a través de todos los detectores activos.
        Retorna una lista consolidada con todas las alertas disparadas.
        """
        all_alerts = []
        for detector in self.detectors:
            try:
                alerts = detector.analyze(flow)
                if alerts:
                    all_alerts.extend(alerts)
            except Exception as e:
                # Manejo robusto de errores para garantizar que un detector fallido
                # no interrumpa el procesamiento de todo el pipeline NDR
                # En producción se registraría en logs de telemetría del Red Team.
                pass
        return all_alerts
