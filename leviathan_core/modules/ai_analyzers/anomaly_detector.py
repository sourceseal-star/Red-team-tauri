#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANOMALY DETECTOR - Detección de Anomalías con IA
================================================
Detección de comportamientos anómalos en dispositivos y redes.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Anomaly:
    """Anomalía detectada."""
    anomaly_type: str
    severity: str
    description: str
    confidence: float
    timestamp: str
    data: Dict = field(default_factory=dict)


@dataclass
class AnomalyDetectionResult:
    """Resultado de detección de anomalías."""
    target: str
    anomalies: List[Anomaly] = field(default_factory=list)
    total_anomalies: int = 0
    critical_anomalies: int = 0
    high_anomalies: int = 0
    baseline: Dict = field(default_factory=dict)


class AnomalyDetectorAnalyzer:
    """Analizador de detección de anomalías."""
    
    def __init__(self):
        self.name = "anomaly_detector"
        self.category = "ai_analyzer"
        self.description = "Detección de anomalías con IA"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Configuración
        self.sensitivity = 0.85  # Sensibilidad (0-1)
        self.window_size = 10  # Tamaño de ventana para análisis
        self.learning_rate = 0.1  # Tasa de aprendizaje
        
        # Base de conocimiento
        self.baselines: Dict[str, Dict] = {}
        self.history: Dict[str, List[Dict]] = {}
        
        # Reglas de anomalías
        self.anomaly_rules = [
            {
                "name": "port_scan_detected",
                "type": "behavioral",
                "condition": lambda data: data.get("port_scan_count", 0) > 5,
                "severity": "high",
                "description": "Posible escaneo de puertos detectado"
            },
            {
                "name": "brute_force_detected",
                "type": "behavioral", 
                "condition": lambda data: data.get("failed_logins", 0) > 10,
                "severity": "critical",
                "description": "Posible ataque de fuerza bruta detectado"
            },
            {
                "name": "unusual_service",
                "type": "service",
                "condition": lambda data: data.get("service", "") in ["unknown", "suspicious"],
                "severity": "medium",
                "description": "Servicio desconocido o sospechoso detectado"
            },
            {
                "name": "high_bandwidth",
                "type": "network",
                "condition": lambda data: data.get("bandwidth_mbps", 0) > 100,
                "severity": "medium",
                "description": "Consumo de ancho de banda inusualmente alto"
            },
            {
                "name": "rapid_requests",
                "type": "network",
                "condition": lambda data: data.get("requests_per_second", 0) > 50,
                "severity": "high",
                "description": "Tasa de peticiones inusualmente alta"
            }
        ]
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el analizador es aplicable."""
        return True
    
    async def analyze(self, target: str, context: Dict = None) -> Dict:
        """
        Analiza un objetivo en busca de anomalías.
        
        Args:
            target: IP o dispositivo a analizar
            context: Contexto con datos históricos
        """
        context = context or {}
        
        results = {
            "target": target,
            "anomalies": [],
            "statistics": {
                "total_anomalies": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "success": False,
            "error": None
        }
        
        try:
            # Obtener datos del objetivo
            target_data = context.get("target_data", {})
            historical_data = context.get("historical_data", [])
            
            # Actualizar línea base
            self._update_baseline(target, target_data)
            
            # Detectar anomalías
            detection_result = await self._detect_anomalies(target, target_data, historical_data)
            
            results["anomalies"] = [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "description": a.description,
                    "confidence": a.confidence,
                    "timestamp": a.timestamp,
                    "data": a.data
                }
                for a in detection_result.anomalies
            ]
            
            results["statistics"]["total_anomalies"] = detection_result.total_anomalies
            results["statistics"]["critical"] = detection_result.critical_anomalies
            results["statistics"]["high"] = detection_result.high_anomalies
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    def _update_baseline(self, target: str, data: Dict):
        """Actualiza la línea base para un objetivo."""
        if target not in self.baselines:
            self.baselines[target] = {
                "services": {},
                "behavior": {},
                "network": {},
                "last_updated": datetime.utcnow().isoformat()
            }
        
        baseline = self.baselines[target]
        
        # Actualizar servicios
        if "services" in data:
            for service in data["services"]:
                port = service.get("port")
                baseline["services"][str(port)] = {
                    "service": service.get("service"),
                    "banner": service.get("banner", ""),
                    "last_seen": datetime.utcnow().isoformat()
                }
        
        # Actualizar comportamiento
        if "behavior" in data:
            for key, value in data["behavior"].items():
                if key not in baseline["behavior"]:
                    baseline["behavior"][key] = []
                baseline["behavior"][key].append(value)
                
                # Limitar tamaño de historia
                if len(baseline["behavior"][key]) > self.window_size:
                    baseline["behavior"][key] = baseline["behavior"][key][-self.window_size:]
        
        baseline["last_updated"] = datetime.utcnow().isoformat()
        
        # Guardar en historia
        if target not in self.history:
            self.history[target] = []
        self.history[target].append(data)
        if len(self.history[target]) > self.window_size * 10:
            self.history[target] = self.history[target][-self.window_size * 10:]
    
    async def _detect_anomalies(self, target: str, data: Dict, historical_data: List[Dict]) -> AnomalyDetectionResult:
        """Detecta anomalías en los datos."""
        result = AnomalyDetectionResult(target=target)
        
        # Aplicar reglas de anomalías
        for rule in self.anomaly_rules:
            try:
                if rule["condition"](data):
                    anomaly = Anomaly(
                        anomaly_type=rule["name"],
                        severity=rule["severity"],
                        description=rule["description"],
                        confidence=self.sensitivity,
                        timestamp=datetime.utcnow().isoformat(),
                        data=data
                    )
                    result.anomalies.append(anomaly)
            except:
                continue
        
        # Análisis estadístico
        await self._statistical_analysis(target, data, result)
        
        # Contar anomalías por severidad
        for anomaly in result.anomalies:
            result.total_anomalies += 1
            if anomaly.severity == "critical":
                result.critical_anomalies += 1
            elif anomaly.severity == "high":
                result.high_anomalies += 1
        
        return result
    
    async def _statistical_analysis(self, target: str, data: Dict, result: AnomalyDetectionResult):
        """Análisis estadístico para detección de anomalías."""
        if target not in self.baselines:
            return
        
        baseline = self.baselines[target]
        
        # Verificar servicios nuevos
        current_services = {str(s.get("port")): s.get("service") for s in data.get("services", [])}
        for port, service in current_services.items():
            if port not in baseline["services"]:
                anomaly = Anomaly(
                    anomaly_type="new_service",
                    severity="medium",
                    description=f"Nuevo servicio detectado en puerto {port}: {service}",
                    confidence=0.9,
                    timestamp=datetime.utcnow().isoformat(),
                    data={"port": port, "service": service}
                )
                result.anomalies.append(anomaly)
        
        # Verificar servicios desaparecidos
        for port in baseline["services"]:
            if port not in current_services:
                anomaly = Anomaly(
                    anomaly_type="service_disappeared",
                    severity="low",
                    description=f"Servicio en puerto {port} ya no está disponible",
                    confidence=0.7,
                    timestamp=datetime.utcnow().isoformat(),
                    data={"port": port}
                )
                result.anomalies.append(anomaly)
        
        # Verificar cambios de banner
        for port, service_info in baseline["services"].items():
            if port in current_services:
                current_banner = next((s.get("banner") for s in data.get("services", []) if str(s.get("port")) == port), None)
                if current_banner and current_banner != service_info.get("banner"):
                    anomaly = Anomaly(
                        anomaly_type="banner_changed",
                        severity="medium",
                        description=f"Banner cambiado en puerto {port}",
                        confidence=0.8,
                        timestamp=datetime.utcnow().isoformat(),
                        data={"port": port, "old_banner": service_info.get("banner"), "new_banner": current_banner}
                    )
                    result.anomalies.append(anomaly)
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "sensitivity": self.sensitivity
        }


def register():
    """Función de registro para el sistema de plugins."""
    return AnomalyDetectorAnalyzer()
