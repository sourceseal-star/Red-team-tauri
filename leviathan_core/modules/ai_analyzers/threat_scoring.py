#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THREAT SCORING - Puntuación de Amenazas
========================================
Calcula puntuación de amenazas basada en múltiples factores.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ThreatFactor:
    """Factor de amenaza."""
    name: str
    value: float = 0.0
    weight: float = 1.0
    description: str = ""


@dataclass
class ThreatScore:
    """Puntuación de amenaza."""
    target: str
    score: float = 0.0
    risk_level: str = "low"
    factors: List[ThreatFactor] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = ""


class ThreatScoringAnalyzer:
    """Analizador de puntuación de amenazas."""
    
    def __init__(self):
        self.name = "threat_scoring"
        self.category = "ai_analyzer"
        self.description = "Puntuación de amenazas basada en IA"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Pesos de factores
        self.factor_weights = {
            "vulnerabilities": 0.30,
            "exploitability": 0.25,
            "accessibility": 0.20,
            "sensitivity": 0.15,
            "anomalies": 0.10
        }
        
        # Puntuación por severidad de vulnerabilidad
        self.vulnerability_scores = {
            "critical": 10.0,
            "high": 7.0,
            "medium": 4.0,
            "low": 2.0,
            "info": 0.5
        }
        
        # Puntuación por tipo de dispositivo
        self.device_scores = {
            "camera": 8.0,
            "router": 9.0,
            "server": 10.0,
            "iot": 6.0,
            "workstation": 7.0,
            "switch": 5.0,
            "printer": 3.0
        }
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el analizador es aplicable."""
        return True
    
    async def analyze(self, target: str, context: Dict = None) -> Dict:
        """
        Calcula la puntuación de amenaza para un objetivo.
        
        Args:
            target: IP o dispositivo a analizar
            context: Contexto con información del objetivo
        """
        context = context or {}
        
        results = {
            "target": target,
            "score": 0.0,
            "risk_level": "low",
            "factors": [],
            "recommendations": [],
            "success": False,
            "error": None
        }
        
        try:
            # Calcular puntuación
            score_result = await self._calculate_score(target, context)
            
            results["score"] = score_result.score
            results["risk_level"] = score_result.risk_level
            results["factors"] = [
                {
                    "name": f.name,
                    "value": f.value,
                    "weight": f.weight,
                    "description": f.description
                }
                for f in score_result.factors
            ]
            results["recommendations"] = score_result.recommendations
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _calculate_score(self, target: str, context: Dict) -> ThreatScore:
        """Calcula la puntuación de amenaza."""
        result = ThreatScore(
            target=target,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Calcular factores
        vulnerability_factor = await self._calculate_vulnerability_factor(target, context)
        exploitability_factor = await self._calculate_exploitability_factor(target, context)
        accessibility_factor = await self._calculate_accessibility_factor(target, context)
        sensitivity_factor = await self._calculate_sensitivity_factor(target, context)
        anomalies_factor = await self._calculate_anomalies_factor(target, context)
        
        # Agregar factores
        result.factors.extend([
            vulnerability_factor,
            exploitability_factor,
            accessibility_factor,
            sensitivity_factor,
            anomalies_factor
        ])
        
        # Calcular puntuación total (0-100)
        total_weight = sum(f.weight for f in result.factors)
        if total_weight > 0:
            result.score = sum(f.value * f.weight for f in result.factors) / total_weight * 100
        
        # Determinar nivel de riesgo
        if result.score >= 80:
            result.risk_level = "critical"
        elif result.score >= 60:
            result.risk_level = "high"
        elif result.score >= 40:
            result.risk_level = "medium"
        elif result.score >= 20:
            result.risk_level = "low"
        else:
            result.risk_level = "info"
        
        # Generar recomendaciones
        result.recommendations = self._generate_recommendations(result)
        
        return result
    
    async def _calculate_vulnerability_factor(self, target: str, context: Dict) -> ThreatFactor:
        """Calcula el factor de vulnerabilidades."""
        vulnerabilities = context.get("vulnerabilities", [])
        
        if not vulnerabilities:
            return ThreatFactor(
                name="vulnerabilities",
                value=0.0,
                weight=self.factor_weights["vulnerabilities"],
                description="No se encontraron vulnerabilidades"
            )
        
        # Calcular puntuación basada en severidad
        total_score = sum(
            self.vulnerability_scores.get(v.get("severity", "info"), 0.5)
            for v in vulnerabilities
        )
        avg_score = total_score / len(vulnerabilities)
        
        # Normalizar a 0-10
        normalized_score = min(avg_score, 10.0)
        
        return ThreatFactor(
            name="vulnerabilities",
            value=normalized_score,
            weight=self.factor_weights["vulnerabilities"],
            description=f"{len(vulnerabilities)} vulnerabilidades encontradas, puntuación promedio: {avg_score:.1f}"
        )
    
    async def _calculate_exploitability_factor(self, target: str, context: Dict) -> ThreatFactor:
        """Calcula el factor de explotabilidad."""
        exploits_available = context.get("exploits_available", 0)
        exploits_successful = context.get("exploits_successful", 0)
        
        # Puntuación basada en exploits disponibles y exitosos
        score = exploits_available * 2 + exploits_successful * 5
        normalized_score = min(score, 10.0)
        
        return ThreatFactor(
            name="exploitability",
            value=normalized_score,
            weight=self.factor_weights["exploitability"],
            description=f"{exploits_available} exploits disponibles, {exploits_successful} exitosos"
        )
    
    async def _calculate_accessibility_factor(self, target: str, context: Dict) -> ThreatFactor:
        """Calcula el factor de accesibilidad."""
        is_accessible = context.get("is_accessible", False)
        open_ports = context.get("open_ports", 0)
        services = context.get("services", [])
        
        # Puntuación basada en accesibilidad
        score = 0.0
        
        if is_accessible:
            score += 5.0
        
        # Más puertos abiertos = más accesible
        score += min(open_ports * 0.5, 5.0)
        
        # Servicios vulnerables
        vulnerable_services = sum(1 for s in services if s.get("is_vulnerable", False))
        score += vulnerable_services * 1.0
        
        normalized_score = min(score, 10.0)
        
        return ThreatFactor(
            name="accessibility",
            value=normalized_score,
            weight=self.factor_weights["accessibility"],
            description=f"Accesible: {is_accessible}, Puertos abiertos: {open_ports}, Servicios vulnerables: {vulnerable_services}"
        )
    
    async def _calculate_sensitivity_factor(self, target: str, context: Dict) -> ThreatFactor:
        """Calcula el factor de sensibilidad."""
        device_type = context.get("device_type", "unknown").lower()
        has_sensitive_data = context.get("has_sensitive_data", False)
        
        # Puntuación basada en tipo de dispositivo
        score = self.device_scores.get(device_type, 5.0)
        
        if has_sensitive_data:
            score += 3.0
        
        normalized_score = min(score, 10.0)
        
        return ThreatFactor(
            name="sensitivity",
            value=normalized_score,
            weight=self.factor_weights["sensitivity"],
            description=f"Tipo de dispositivo: {device_type}, Datos sensibles: {has_sensitive_data}"
        )
    
    async def _calculate_anomalies_factor(self, target: str, context: Dict) -> ThreatFactor:
        """Calcula el factor de anomalías."""
        anomalies = context.get("anomalies", [])
        
        if not anomalies:
            return ThreatFactor(
                name="anomalies",
                value=0.0,
                weight=self.factor_weights["anomalies"],
                description="No se detectaron anomalías"
            )
        
        # Puntuación basada en número y severidad de anomalías
        severity_scores = {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
        total_score = sum(
            severity_scores.get(a.get("severity", "low"), 0.5)
            for a in anomalies
        )
        
        normalized_score = min(total_score, 10.0)
        
        return ThreatFactor(
            name="anomalies",
            value=normalized_score,
            weight=self.factor_weights["anomalies"],
            description=f"{len(anomalies)} anomalías detectadas"
        )
    
    def _generate_recommendations(self, score_result: ThreatScore) -> List[str]:
        """Genera recomendaciones basadas en la puntuación."""
        recommendations = []
        
        # Recomendaciones basadas en nivel de riesgo
        if score_result.risk_level == "critical":
            recommendations.extend([
                "🔴 AISLAR INMEDIATAMENTE: Este dispositivo representa un riesgo crítico",
                "Desconectar de la red hasta que se mitiguen las vulnerabilidades",
                "Realizar análisis forense completo",
                "Implementar controles de acceso más estrictos"
            ])
        elif score_result.risk_level == "high":
            recommendations.extend([
                "🟠 ALTO RIESGO: Revisar y parchear inmediatamente",
                "Aplicar parches de seguridad para todas las vulnerabilidades críticas",
                "Implementar monitoreo continuo",
                "Restringir acceso desde redes externas"
            ])
        elif score_result.risk_level == "medium":
            recommendations.extend([
                "🟡 RIESGO MODERADO: Revisar en las próximas 24 horas",
                "Aplicar parches de seguridad",
                "Revisar configuración de seguridad",
                "Implementar autenticación multifactor"
            ])
        
        # Recomendaciones basadas en factores específicos
        for factor in score_result.factors:
            if factor.name == "vulnerabilities" and factor.value > 7:
                recommendations.append("⚠️ Vulnerabilidades críticas detectadas - Parchear inmediatamente")
            elif factor.name == "exploitability" and factor.value > 7:
                recommendations.append("⚠️ Dispositivo altamente explotable - Restringir acceso")
            elif factor.name == "accessibility" and factor.value > 7:
                recommendations.append("⚠️ Dispositivo muy accesible - Implementar firewall")
        
        return recommendations
    
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
    return ThreatScoringAnalyzer()
