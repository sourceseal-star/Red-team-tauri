#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BEHAVIOR ANALYZER - Análisis de Comportamiento
==============================================
Análisis de comportamiento de dispositivos y usuarios.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class BehaviorPattern:
    """Patrón de comportamiento."""
    pattern_type: str
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    severity: str = "low"
    confidence: float = 0.0


@dataclass
class BehaviorAnalysisResult:
    """Resultado de análisis de comportamiento."""
    target: str
    patterns: List[BehaviorPattern] = field(default_factory=list)
    suspicious_patterns: List[BehaviorPattern] = field(default_factory=list)
    threat_level: str = "low"
    confidence: float = 0.0


class BehaviorAnalyzer:
    """Analizador de comportamiento."""
    
    def __init__(self):
        self.name = "behavior_analyzer"
        self.category = "ai_analyzer"
        self.description = "Análisis de comportamiento de dispositivos"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Configuración
        self.analysis_window = timedelta(hours=24)
        self.suspicious_threshold = 0.7
        
        # Base de conocimiento
        self.behavior_db: Dict[str, List[Dict]] = defaultdict(list)
        
        # Patrones conocidos
        self.known_patterns = {
            "scanning": {
                "description": "Escaneo de red",
                "severity": "high",
                "indicators": [
                    lambda data: data.get("port_scan_count", 0) > 10,
                    lambda data: data.get("unique_ports_scanned", 0) > 20
                ]
            },
            "brute_force": {
                "description": "Ataque de fuerza bruta",
                "severity": "critical",
                "indicators": [
                    lambda data: data.get("failed_logins", 0) > 20,
                    lambda data: data.get("login_attempts", 0) > 50
                ]
            },
            "data_exfiltration": {
                "description": "Posible exfiltración de datos",
                "severity": "critical",
                "indicators": [
                    lambda data: data.get("outbound_traffic_mb", 0) > 100,
                    lambda data: data.get("large_file_transfers", 0) > 5
                ]
            },
            "lateral_movement": {
                "description": "Movimiento lateral en la red",
                "severity": "high",
                "indicators": [
                    lambda data: data.get("internal_connections", 0) > 10,
                    lambda data: data.get("new_devices_contacted", 0) > 5
                ]
            },
            "c2_communication": {
                "description": "Comunicación con servidor C2",
                "severity": "critical",
                "indicators": [
                    lambda data: data.get("known_c2_ips", 0) > 0,
                    lambda data: data.get("beaconing_detected", False)
                ]
            }
        }
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el analizador es aplicable."""
        return True
    
    async def analyze(self, target: str, context: Dict = None) -> Dict:
        """
        Analiza el comportamiento de un objetivo.
        
        Args:
            target: IP o dispositivo a analizar
            context: Contexto con datos de comportamiento
        """
        context = context or {}
        
        results = {
            "target": target,
            "patterns": [],
            "suspicious_patterns": [],
            "threat_level": "low",
            "confidence": 0.0,
            "success": False,
            "error": None
        }
        
        try:
            # Obtener datos de comportamiento
            behavior_data = context.get("behavior_data", {})
            historical_data = context.get("historical_data", [])
            
            # Almacenar datos
            self._store_behavior_data(target, behavior_data)
            
            # Analizar patrones
            analysis_result = await self._analyze_patterns(target, behavior_data, historical_data)
            
            results["patterns"] = [
                {
                    "type": p.pattern_type,
                    "count": p.count,
                    "first_seen": p.first_seen,
                    "last_seen": p.last_seen,
                    "severity": p.severity,
                    "confidence": p.confidence
                }
                for p in analysis_result.patterns
            ]
            
            results["suspicious_patterns"] = [
                {
                    "type": p.pattern_type,
                    "count": p.count,
                    "description": self._get_pattern_description(p.pattern_type),
                    "severity": p.severity,
                    "confidence": p.confidence
                }
                for p in analysis_result.suspicious_patterns
            ]
            
            results["threat_level"] = analysis_result.threat_level
            results["confidence"] = analysis_result.confidence
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    def _store_behavior_data(self, target: str, data: Dict):
        """Almacena datos de comportamiento."""
        if target not in self.behavior_db:
            self.behavior_db[target] = []
        
        self.behavior_db[target].append({
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        })
        
        # Limitar tamaño de la base de datos
        if len(self.behavior_db[target]) > 1000:
            self.behavior_db[target] = self.behavior_db[target][-1000:]
    
    async def _analyze_patterns(self, target: str, data: Dict, historical_data: List[Dict]) -> BehaviorAnalysisResult:
        """Analiza patrones de comportamiento."""
        result = BehaviorAnalysisResult(target=target)
        
        # Verificar patrones conocidos
        for pattern_name, pattern_info in self.known_patterns.items():
            for indicator in pattern_info["indicators"]:
                try:
                    if indicator(data):
                        pattern = BehaviorPattern(
                            pattern_type=pattern_name,
                            count=1,
                            first_seen=datetime.utcnow().isoformat(),
                            last_seen=datetime.utcnow().isoformat(),
                            severity=pattern_info["severity"],
                            confidence=0.9
                        )
                        result.patterns.append(pattern)
                        
                        # Verificar si es sospechoso
                        if pattern.confidence >= self.suspicious_threshold:
                            result.suspicious_patterns.append(pattern)
                        
                        break
                except:
                    continue
        
        # Análisis de patrones históricos
        await self._analyze_historical_patterns(target, result)
        
        # Calcular nivel de amenaza
        self._calculate_threat_level(result)
        
        return result
    
    async def _analyze_historical_patterns(self, target: str, result: BehaviorAnalysisResult):
        """Analiza patrones históricos."""
        if target not in self.behavior_db:
            return
        
        historical_data = self.behavior_db[target]
        
        # Contar ocurrencias de cada patrón
        pattern_counts: Dict[str, int] = defaultdict(int)
        
        for entry in historical_data:
            data = entry.get("data", {})
            for pattern_name, pattern_info in self.known_patterns.items():
                for indicator in pattern_info["indicators"]:
                    try:
                        if indicator(data):
                            pattern_counts[pattern_name] += 1
                            break
                    except:
                        continue
        
        # Crear patrones con conteos
        for pattern_name, count in pattern_counts.items():
            pattern_info = self.known_patterns.get(pattern_name, {})
            
            # Verificar si ya existe este patrón
            existing = next((p for p in result.patterns if p.pattern_type == pattern_name), None)
            
            if existing:
                existing.count += count
            else:
                pattern = BehaviorPattern(
                    pattern_type=pattern_name,
                    count=count,
                    severity=pattern_info.get("severity", "low"),
                    confidence=min(0.9 + (count * 0.05), 1.0)
                )
                result.patterns.append(pattern)
                
                if pattern.confidence >= self.suspicious_threshold:
                    result.suspicious_patterns.append(pattern)
    
    def _calculate_threat_level(self, result: BehaviorAnalysisResult):
        """Calcula el nivel de amenaza."""
        if not result.suspicious_patterns:
            result.threat_level = "low"
            result.confidence = 0.0
            return
        
        # Calcular severidad promedio
        severity_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        total_score = sum(severity_scores.get(p.severity, 1) for p in result.suspicious_patterns)
        avg_score = total_score / len(result.suspicious_patterns)
        
        # Calcular confianza promedio
        avg_confidence = sum(p.confidence for p in result.suspicious_patterns) / len(result.suspicious_patterns)
        
        # Determinar nivel de amenaza
        if avg_score >= 3.5:
            result.threat_level = "critical"
        elif avg_score >= 2.5:
            result.threat_level = "high"
        elif avg_score >= 1.5:
            result.threat_level = "medium"
        else:
            result.threat_level = "low"
        
        result.confidence = avg_confidence
    
    def _get_pattern_description(self, pattern_type: str) -> str:
        """Obtiene la descripción de un patrón."""
        pattern_info = self.known_patterns.get(pattern_type, {})
        return pattern_info.get("description", pattern_type)
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version
        }


def register():
    """Función de registro para el sistema de plugins."""
    return BehaviorAnalyzer()
