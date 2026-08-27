"""
Risk Assessor - Evaluador de Riesgos
===================================
Evalúa el nivel de riesgo de diferentes situaciones.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class RiskAssessment:
    """Evaluación de riesgo"""
    score: float  # 0.0 - 1.0
    severity: str  # critical, high, medium, low, info
    factors: Dict[str, float]
    recommendations: List[str]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "severity": self.severity,
            "factors": self.factors,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp
        }


class RiskAssessor:
    """Evaluador de Riesgos Autónomo"""
    
    def __init__(self):
        self.weights = {
            "threat_score": 0.4,
            "vulnerability_score": 0.3,
            "anomaly_score": 0.2,
            "impact_score": 0.1
        }
    
    async def assess_risk(self, scan_result: Dict, threat_analysis: Dict) -> RiskAssessment:
        """
        Evalúa el riesgo basado en resultados de escaneo y análisis de amenaza.
        
        Args:
            scan_result: Resultados del escaneo
            threat_analysis: Análisis de amenazas
            
        Returns:
            RiskAssessment: Evaluación de riesgo
        """
        factors = {}
        
        # Factor de amenaza
        threat_score = threat_analysis.get("threat_score", 0.0)
        factors["threat_score"] = threat_score
        
        # Factor de vulnerabilidad
        vulnerability_score = self._calculate_vulnerability_score(scan_result)
        factors["vulnerability_score"] = vulnerability_score
        
        # Factor de anomalía (si está disponible)
        anomaly_score = 0.0
        if "behavior_analysis" in scan_result:
            anomaly_score = scan_result["behavior_analysis"].get("score", 0.0) * 0.5
        factors["anomaly_score"] = anomaly_score
        
        # Calcular score total
        score = sum(
            factors.get(key, 0.0) * weight 
            for key, weight in self.weights.items()
        )
        
        # Determinar severidad
        severity = self._determine_severity(score)
        
        # Generar recomendaciones
        recommendations = self._generate_recommendations(
            scan_result, threat_analysis, score, severity
        )
        
        return RiskAssessment(
            score=score,
            severity=severity,
            factors=factors,
            recommendations=recommendations,
            timestamp=datetime.datetime.now().isoformat()
        )
    
    async def assess_impact(self, simulation: Any, target: str) -> Dict:
        """
        Evalúa el impacto de una simulación.
        
        Args:
            simulation: Resultados de la simulación
            target: Objetivo
            
        Returns:
            Evaluación de impacto
        """
        impact_score = 0.0
        factors = {}
        
        # Factor de éxito
        if simulation.success:
            impact_score += 0.4
            factors["success"] = 0.4
        
        # Factor de impacto
        impact_level = simulation.results.get("impact", "none")
        impact_weights = {"none": 0.0, "low": 0.1, "medium": 0.3, "high": 0.6, "critical": 0.9}
        impact_score += impact_weights.get(impact_level, 0.0)
        factors["impact_level"] = impact_weights.get(impact_level, 0.0)
        
        # Factor de vulnerabilidades explotadas
        vuln_count = len(simulation.results.get("vulnerabilities_exploited", []))
        vuln_score = min(0.3, vuln_count * 0.1)
        impact_score += vuln_score
        factors["vulnerabilities"] = vuln_score
        
        # Factor de datos accedidos
        data_count = len(simulation.results.get("data_accessed", []))
        data_score = min(0.2, data_count * 0.1)
        impact_score += data_score
        factors["data_accessed"] = data_score
        
        # Determinar nivel de impacto
        if impact_score >= 0.9:
            impact = "critical"
        elif impact_score >= 0.7:
            impact = "high"
        elif impact_score >= 0.4:
            impact = "medium"
        elif impact_score >= 0.1:
            impact = "low"
        else:
            impact = "none"
        
        return {
            "score": impact_score,
            "level": impact,
            "factors": factors,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def _calculate_vulnerability_score(self, scan_result: Dict) -> float:
        """Calcula el score de vulnerabilidad"""
        vulnerabilities = scan_result.get("vulnerabilities", [])
        if not vulnerabilities:
            return 0.0
        
        score = 0.0
        severity_weights = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
        
        for vuln in vulnerabilities:
            severity = vuln.get("severity", "low")
            score += severity_weights.get(severity, 0.0)
        
        # Normalizar
        score = score / len(vulnerabilities)
        
        return max(0.0, min(1.0, score))
    
    def _determine_severity(self, score: float) -> str:
        """Determina la severidad basada en el score"""
        if score >= 0.9:
            return "critical"
        elif score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.1:
            return "low"
        else:
            return "info"
    
    def _generate_recommendations(self, scan_result: Dict, threat_analysis: Dict,
                                  score: float, severity: str) -> List[str]:
        """Genera recomendaciones basadas en la evaluación"""
        recommendations = []
        
        # Recomendaciones por severidad
        if severity == "critical":
            recommendations.append("🚨 ACCIÓN INMEDIATA REQUERIDA: Riesgo crítico detectado")
            recommendations.append("🚨 NOTIFICAR A EQUIPO DE SEGURIDAD")
        elif severity == "high":
            recommendations.append("⚠️ INVESTIGAR Y CONTENER: Riesgo alto detectado")
        
        # Recomendaciones por vulnerabilidades
        vulnerabilities = scan_result.get("vulnerabilities", [])
        for vuln in vulnerabilities:
            if vuln.get("severity") == "critical":
                recommendations.append(f"🚨 PARCHE CRÍTICO: {vuln.get('name', 'Vulnerabilidad crítica')}")
        
        # Recomendaciones por amenazas
        threats = threat_analysis.get("threats", [])
        for threat in threats:
            if threat.get("severity") == "critical":
                recommendations.append(f"🚨 BLOQUEAR: {threat.get('description', 'Amenaza crítica')}")
        
        # Recomendaciones generales
        recommendations.append("✅ Realizar auditoría de seguridad completa")
        recommendations.append("✅ Revisar configuraciones de firewall")
        recommendations.append("✅ Implementar monitoreo continuo")
        
        return list(set(recommendations))
