"""
Report Generator - Generador de Informes
========================================
Genera informes detallados de operaciones, simulaciones y amenazas.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class ReportType(Enum):
    """Tipos de informes"""
    SCAN = "scan"
    SIMULATION = "simulation"
    MONITORING = "monitoring"
    INVESTIGATION = "investigation"
    DEFENSE = "defense"
    THREAT = "threat"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class Report:
    """Informe generado"""
    report_id: str
    type: ReportType
    title: str
    target: str
    summary: str
    findings: List[Dict]
    recommendations: List[str]
    risk_score: float
    severity: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "type": self.type.value,
            "title": self.title,
            "target": self.target,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class ReportGenerator:
    """Generador de Informes Autónomo"""
    
    def __init__(self):
        self.memory = None
        self.report_history: List[Report] = []
        self.report_templates: Dict[str, Dict] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Carga plantillas de informes"""
        self.report_templates = {
            "scan": {
                "title": "Informe de Escaneo OSINT",
                "sections": ["summary", "findings", "vulnerabilities", "threats", "recommendations"]
            },
            "simulation": {
                "title": "Informe de Simulación de Ataque",
                "sections": ["summary", "execution", "results", "findings", "recommendations"]
            },
            "monitoring": {
                "title": "Informe de Monitoreo",
                "sections": ["summary", "behavior", "anomalies", "recommendations"]
            },
            "investigation": {
                "title": "Informe de Investigación",
                "sections": ["summary", "deep_scan", "traffic", "behavior", "patterns", "recommendations"]
            },
            "defense": {
                "title": "Informe de Defensa",
                "sections": ["summary", "threats", "vulnerabilities", "actions", "recommendations"]
            },
            "threat": {
                "title": "Informe de Amenaza",
                "sections": ["summary", "threat_details", "impact", "recommendations"]
            }
        }
    
    async def generate_report(self, data: Dict) -> Report:
        """
        Genera un informe basado en los datos proporcionados.
        
        Args:
            data: Datos para el informe
            
        Returns:
            Report: Informe generado
        """
        report_type = data.get("type", "scan")
        template = self.report_templates.get(report_type, self.report_templates["scan"])
        
        report_id = f"rep_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        target = data.get("target", "unknown")
        
        # Generar contenido según el tipo
        if report_type == "scan":
            return await self._generate_scan_report(data, report_id, template, target)
        elif report_type == "simulation":
            return await self._generate_simulation_report(data, report_id, template, target)
        elif report_type == "monitoring":
            return await self._generate_monitoring_report(data, report_id, template, target)
        elif report_type == "investigation":
            return await self._generate_investigation_report(data, report_id, template, target)
        elif report_type == "defense":
            return await self._generate_defense_report(data, report_id, template, target)
        elif report_type == "threat":
            return await self._generate_threat_report(data, report_id, template, target)
        else:
            return await self._generate_generic_report(data, report_id, template, target)
    
    async def _generate_scan_report(self, data: Dict, report_id: str, 
                                     template: Dict, target: str) -> Report:
        """Genera informe de escaneo"""
        scan_result = data.get("scan_result", {})
        threat_analysis = data.get("threat_analysis", {})
        risk_assessment = data.get("risk_assessment", {})
        
        # Resumen
        summary = self._generate_scan_summary(scan_result, threat_analysis, risk_assessment)
        
        # Hallazgos
        findings = self._extract_findings_from_scan(scan_result, threat_analysis)
        
        # Recomendaciones
        recommendations = self._generate_scan_recommendations(scan_result, threat_analysis)
        
        # Score de riesgo
        risk_score = risk_assessment.get("score", 0.5)
        severity = risk_assessment.get("severity", "medium")
        
        report = Report(
            report_id=report_id,
            type=ReportType.SCAN,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "scan_type": scan_result.get("type", "full"),
                "duration": scan_result.get("duration", 0),
                "sources": list(scan_result.get("sources", {}).keys())
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_simulation_report(self, data: Dict, report_id: str,
                                         template: Dict, target: str) -> Report:
        """Genera informe de simulación"""
        simulation = data.get("simulation", {})
        analysis = data.get("analysis", {})
        impact = data.get("impact", {})
        
        # Resumen
        summary = self._generate_simulation_summary(simulation, analysis, impact)
        
        # Hallazgos
        findings = analysis.get("findings", [])
        
        # Recomendaciones
        recommendations = simulation.get("recommendations", [])
        
        # Score de riesgo
        risk_score = analysis.get("risk_score", 0.7)
        severity = "critical" if risk_score >= 0.9 else "high" if risk_score >= 0.7 else "medium"
        
        report = Report(
            report_id=report_id,
            type=ReportType.SIMULATION,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "template": simulation.get("template_name", "unknown"),
                "success": simulation.get("success", False),
                "impact": impact
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_monitoring_report(self, data: Dict, report_id: str,
                                          template: Dict, target: str) -> Report:
        """Genera informe de monitoreo"""
        monitor_result = data.get("monitor_result", {})
        behavior_analysis = data.get("behavior_analysis", {})
        anomalies = data.get("anomalies", [])
        
        # Resumen
        summary = self._generate_monitoring_summary(monitor_result, behavior_analysis, anomalies)
        
        # Hallazgos
        findings = self._extract_findings_from_monitoring(monitor_result, behavior_analysis, anomalies)
        
        # Recomendaciones
        recommendations = self._generate_monitoring_recommendations(behavior_analysis, anomalies)
        
        # Score de riesgo
        risk_score = self._calculate_monitoring_risk_score(behavior_analysis, anomalies)
        severity = "critical" if risk_score >= 0.9 else "high" if risk_score >= 0.7 else "medium"
        
        report = Report(
            report_id=report_id,
            type=ReportType.MONITORING,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "duration": monitor_result.get("duration", 0),
                "behavior_score": behavior_analysis.get("score", 0),
                "anomaly_count": len(anomalies)
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_investigation_report(self, data: Dict, report_id: str,
                                             template: Dict, target: str) -> Report:
        """Genera informe de investigación"""
        deep_scan = data.get("deep_scan", {})
        traffic_analysis = data.get("traffic_analysis", {})
        behavior_analysis = data.get("behavior_analysis", {})
        patterns = data.get("patterns", [])
        temporal_analysis = data.get("temporal_analysis", {})
        
        # Resumen
        summary = self._generate_investigation_summary(
            deep_scan, traffic_analysis, behavior_analysis, patterns, temporal_analysis
        )
        
        # Hallazgos
        findings = self._extract_findings_from_investigation(
            deep_scan, traffic_analysis, behavior_analysis, patterns
        )
        
        # Recomendaciones
        recommendations = self._generate_investigation_recommendations(
            deep_scan, traffic_analysis, behavior_analysis
        )
        
        # Score de riesgo
        risk_score = self._calculate_investigation_risk_score(
            deep_scan, traffic_analysis, behavior_analysis
        )
        severity = "critical" if risk_score >= 0.9 else "high" if risk_score >= 0.7 else "medium"
        
        report = Report(
            report_id=report_id,
            type=ReportType.INVESTIGATION,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "scan_duration": deep_scan.get("duration", 0),
                "behavior_score": behavior_analysis.get("score", 0) if isinstance(behavior_analysis, dict) else 0,
                "pattern_count": len(patterns)
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_defense_report(self, data: Dict, report_id: str,
                                      template: Dict, target: str) -> Report:
        """Genera informe de defensa"""
        threat_scan = data.get("threat_scan", {})
        vulnerabilities = data.get("vulnerabilities", [])
        defense_result = data.get("defense_result", {})
        
        # Resumen
        summary = self._generate_defense_summary(threat_scan, vulnerabilities, defense_result)
        
        # Hallazgos
        findings = self._extract_findings_from_defense(threat_scan, vulnerabilities, defense_result)
        
        # Recomendaciones
        recommendations = self._generate_defense_recommendations(vulnerabilities, defense_result)
        
        # Score de riesgo
        risk_score = self._calculate_defense_risk_score(threat_scan, vulnerabilities)
        severity = "critical" if risk_score >= 0.9 else "high" if risk_score >= 0.7 else "medium"
        
        report = Report(
            report_id=report_id,
            type=ReportType.DEFENSE,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "threat_count": len(threat_scan.get("threats", [])),
                "vulnerability_count": len(vulnerabilities),
                "action_count": len(defense_result.get("actions", []))
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_threat_report(self, data: Dict, report_id: str,
                                     template: Dict, target: str) -> Report:
        """Genera informe de amenaza"""
        threat = data.get("threat", {})
        
        # Resumen
        summary = self._generate_threat_summary(threat)
        
        # Hallazgos
        findings = [{
            "type": "threat",
            "description": threat.get("description", ""),
            "severity": threat.get("severity", "medium"),
            "target": threat.get("target", target)
        }]
        
        # Recomendaciones
        recommendations = self._generate_threat_recommendations(threat)
        
        # Score de riesgo
        risk_score = threat.get("risk_score", 0.8)
        severity = threat.get("severity", "high")
        
        report = Report(
            report_id=report_id,
            type=ReportType.THREAT,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={
                "threat_type": threat.get("type", "unknown"),
                "threat_id": threat.get("id", "unknown")
            }
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    async def _generate_generic_report(self, data: Dict, report_id: str,
                                       template: Dict, target: str) -> Report:
        """Genera informe genérico"""
        summary = data.get("summary", f"Informe generado para {target}")
        findings = data.get("findings", [])
        recommendations = data.get("recommendations", [])
        risk_score = data.get("risk_score", 0.5)
        severity = data.get("severity", "medium")
        
        report = Report(
            report_id=report_id,
            type=ReportType.SCAN,
            title=template["title"].replace("{target}", target),
            target=target,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            risk_score=risk_score,
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            metadata=data.get("metadata", {})
        )
        
        self.report_history.append(report)
        if self.memory:
            await self.memory.store_report(report.to_dict())
        
        return report
    
    def _generate_scan_summary(self, scan_result: Dict, threat_analysis: Dict,
                              risk_assessment: Dict) -> str:
        """Genera resumen de escaneo"""
        total_findings = len(scan_result.get("findings", []))
        total_vulnerabilities = len(scan_result.get("vulnerabilities", []))
        total_threats = len(threat_analysis.get("threats", []))
        risk_score = risk_assessment.get("score", 0.5)
        
        summary = f"Escaneo completado en {scan_result.get('target', 'objetivo desconocido')}. "
        summary += f"Se encontraron {total_findings} hallazgos, {total_vulnerabilities} vulnerabilidades, "
        summary += f"y {total_threats} amenazas. "
        summary += f"Puntuación de riesgo: {risk_score:.2f}/1.0. "
        summary += f"Nivel de severidad: {risk_assessment.get('severity', 'medio')}."
        
        return summary
    
    def _generate_simulation_summary(self, simulation: Dict, analysis: Dict,
                                     impact: Dict) -> str:
        """Genera resumen de simulación"""
        success = simulation.get("success", False)
        template = simulation.get("template_name", "desconocido")
        impact_level = impact.get("level", "medio")
        
        summary = f"Simulación de ataque {template} completada en {simulation.get('target', 'objetivo desconocido')}. "
        summary += f"Resultado: {'Éxito' if success else 'Fracaso'}. "
        summary += f"Impacto: {impact_level}. "
        summary += f"Vulnerabilidades explotadas: {len(analysis.get('vulnerabilities', []))}."
        
        return summary
    
    def _generate_monitoring_summary(self, monitor_result: Dict, 
                                    behavior_analysis: Dict, anomalies: List[Dict]) -> str:
        """Genera resumen de monitoreo"""
        target = monitor_result.get("target", "objetivo desconocido")
        behavior_score = behavior_analysis.get("score", 0) if isinstance(behavior_analysis, dict) else 0
        
        summary = f"Monitoreo completado en {target}. "
        summary += f"Puntuación de comportamiento: {behavior_score:.2f}/1.0. "
        summary += f"Anomalías detectadas: {len(anomalies)}."
        
        return summary
    
    def _generate_investigation_summary(self, deep_scan: Dict, traffic_analysis: Dict,
                                        behavior_analysis: Dict, patterns: List[Dict],
                                        temporal_analysis: Dict) -> str:
        """Genera resumen de investigación"""
        target = deep_scan.get("target", "objetivo desconocido")
        behavior_score = behavior_analysis.get("score", 0) if isinstance(behavior_analysis, dict) else 0
        
        summary = f"Investigación completada en {target}. "
        summary += f"Escaneo profundo: {len(deep_scan.get('sources', {}))} fuentes analizadas. "
        summary += f"Puntuación de comportamiento: {behavior_score:.2f}/1.0. "
        summary += f"Patrones detectados: {len(patterns)}."
        
        return summary
    
    def _generate_defense_summary(self, threat_scan: Dict, vulnerabilities: List[Dict],
                                  defense_result: Dict) -> str:
        """Genera resumen de defensa"""
        target = threat_scan.get("target", "objetivo desconocido")
        threat_count = len(threat_scan.get("threats", []))
        vuln_count = len(vulnerabilities)
        action_count = len(defense_result.get("actions", []))
        
        summary = f"Defensa ejecutada en {target}. "
        summary += f"Amenazas detectadas: {threat_count}. "
        summary += f"Vulnerabilidades: {vuln_count}. "
        summary += f"Acciones de defensa: {action_count}."
        
        return summary
    
    def _generate_threat_summary(self, threat: Dict) -> str:
        """Genera resumen de amenaza"""
        threat_type = threat.get("type", "desconocido")
        severity = threat.get("severity", "media")
        target = threat.get("target", "objetivo desconocido")
        
        summary = f"Amenaza de tipo {threat_type} detectada en {target}. "
        summary += f"Nivel de severidad: {severity}. "
        summary += f"Descripción: {threat.get('description', 'sin descripción')}."
        
        return summary
    
    def _extract_findings_from_scan(self, scan_result: Dict, threat_analysis: Dict) -> List[Dict]:
        """Extrae hallazgos de un escaneo"""
        findings = []
        
        # Hallazgos de escaneo
        for finding in scan_result.get("findings", []):
            findings.append({
                "type": "scan_finding",
                "category": finding.get("category", "unknown"),
                "title": finding.get("title", "Sin título"),
                "count": finding.get("count", 0),
                "severity": finding.get("severity", "medium")
            })
        
        # Hallazgos de amenazas
        for threat in threat_analysis.get("threats", []):
            findings.append({
                "type": "threat",
                "threat_type": threat.get("type", "unknown"),
                "severity": threat.get("severity", "medium"),
                "description": threat.get("description", "")
            })
        
        return findings
    
    def _extract_findings_from_monitoring(self, monitor_result: Dict,
                                         behavior_analysis: Dict, anomalies: List[Dict]) -> List[Dict]:
        """Extrae hallazgos de monitoreo"""
        findings = []
        
        # Hallazgos de comportamiento
        if isinstance(behavior_analysis, dict):
            findings.append({
                "type": "behavior_analysis",
                "behavior_type": behavior_analysis.get("behavior_type", "normal").value,
                "score": behavior_analysis.get("score", 0),
                "severity": "high" if behavior_analysis.get("score", 0) >= 0.7 else "medium"
            })
        
        # Hallazgos de anomalías
        for anomaly in anomalies:
            findings.append({
                "type": "anomaly",
                "anomaly_type": anomaly.get("type", "unknown"),
                "severity": anomaly.get("severity", "medium"),
                "description": anomaly.get("description", "")
            })
        
        return findings
    
    def _extract_findings_from_investigation(self, deep_scan: Dict, traffic_analysis: Dict,
                                            behavior_analysis: Dict, patterns: List[Dict]) -> List[Dict]:
        """Extrae hallazgos de investigación"""
        findings = []
        
        # Hallazgos de escaneo profundo
        for source, data in deep_scan.get("sources", {}).items():
            if isinstance(data, dict):
                findings.append({
                    "type": "deep_scan",
                    "source": source,
                    "data": str(data)[:200],
                    "severity": "medium"
                })
        
        # Hallazgos de análisis de tráfico
        if isinstance(traffic_analysis, dict):
            findings.append({
                "type": "traffic_analysis",
                "requests": len(traffic_analysis.get("requests", [])),
                "injections": len(traffic_analysis.get("injections", [])),
                "severity": "high" if traffic_analysis.get("injections", []) else "medium"
            })
        
        # Hallazgos de patrones
        for pattern in patterns:
            findings.append({
                "type": "pattern",
                "pattern_type": pattern.get("type", "unknown"),
                "severity": pattern.get("severity", "medium"),
                "description": pattern.get("description", "")
            })
        
        return findings
    
    def _extract_findings_from_defense(self, threat_scan: Dict, vulnerabilities: List[Dict],
                                       defense_result: Dict) -> List[Dict]:
        """Extrae hallazgos de defensa"""
        findings = []
        
        # Hallazgos de amenazas
        for threat in threat_scan.get("threats", []):
            findings.append({
                "type": "threat",
                "threat_type": threat.get("type", "unknown"),
                "severity": threat.get("severity", "medium"),
                "description": threat.get("description", "")
            })
        
        # Hallazgos de vulnerabilidades
        for vuln in vulnerabilities:
            findings.append({
                "type": "vulnerability",
                "name": vuln.get("name", "unknown"),
                "severity": vuln.get("severity", "medium"),
                "cvss_score": vuln.get("cvss_score", 0)
            })
        
        # Hallazgos de acciones de defensa
        for action in defense_result.get("actions", []):
            findings.append({
                "type": "defense_action",
                "action": action.get("action", "unknown"),
                "status": action.get("status", "unknown"),
                "target": action.get("target", "unknown")
            })
        
        return findings
    
    def _generate_scan_recommendations(self, scan_result: Dict, threat_analysis: Dict) -> List[str]:
        """Genera recomendaciones de escaneo"""
        recommendations = []
        
        # Recomendaciones de escaneo
        for finding in scan_result.get("findings", []):
            if finding.get("severity") == "critical":
                recommendations.append(f"🚨 ACCIÓN INMEDIATA: {finding.get('title', 'Hallazgo crítico')}")
            elif finding.get("severity") == "high":
                recommendations.append(f"⚠️ INVESTIGAR: {finding.get('title', 'Hallazgo importante')}")
        
        # Recomendaciones de amenazas
        for threat in threat_analysis.get("threats", []):
            if threat.get("severity") == "critical":
                recommendations.append(f"🚨 BLOQUEAR: {threat.get('description', 'Amenaza crítica')}")
        
        # Recomendaciones generales
        recommendations.append("✅ Realizar escaneos periódicos")
        recommendations.append("✅ Mantener sistemas actualizados")
        
        return list(set(recommendations))
    
    def _generate_monitoring_recommendations(self, behavior_analysis: Dict, 
                                             anomalies: List[Dict]) -> List[str]:
        """Genera recomendaciones de monitoreo"""
        recommendations = []
        
        # Recomendaciones de comportamiento
        if isinstance(behavior_analysis, dict):
            score = behavior_analysis.get("score", 0)
            if score >= 0.9:
                recommendations.append("🚨 BLOQUEAR INMEDIATAMENTE: Comportamiento malicioso detectado")
            elif score >= 0.7:
                recommendations.append("⚠️ INVESTIGAR: Comportamiento sospechoso")
        
        # Recomendaciones de anomalías
        for anomaly in anomalies:
            if anomaly.get("severity") == "critical":
                recommendations.append(f"🚨 ACCIÓN INMEDIATA: {anomaly.get('description', 'Anomalía crítica')}")
        
        # Recomendaciones generales
        recommendations.append("✅ Aumentar nivel de monitoreo")
        recommendations.append("✅ Revisar logs de actividad")
        
        return list(set(recommendations))
    
    def _generate_investigation_recommendations(self, deep_scan: Dict,
                                               traffic_analysis: Dict, behavior_analysis: Dict) -> List[str]:
        """Genera recomendaciones de investigación"""
        recommendations = []
        
        # Recomendaciones de escaneo
        for source, data in deep_scan.get("sources", {}).items():
            if isinstance(data, dict) and data.get("vulnerabilities"):
                recommendations.append(f"🚨 PARCHEAR: Vulnerabilidades encontradas en {source}")
        
        # Recomendaciones de tráfico
        if isinstance(traffic_analysis, dict):
            if traffic_analysis.get("injections"):
                recommendations.append("⚠️ INVESTIGAR: Inyecciones detectadas en tráfico")
        
        # Recomendaciones de comportamiento
        if isinstance(behavior_analysis, dict):
            score = behavior_analysis.get("score", 0)
            if score >= 0.7:
                recommendations.append("🔍 PROFUNDIZAR: Análisis de comportamiento anómalo")
        
        # Recomendaciones generales
        recommendations.append("✅ Implementar controles de seguridad adicionales")
        recommendations.append("✅ Revisar configuraciones de red")
        
        return list(set(recommendations))
    
    def _generate_defense_recommendations(self, vulnerabilities: List[Dict],
                                          defense_result: Dict) -> List[str]:
        """Genera recomendaciones de defensa"""
        recommendations = []
        
        # Recomendaciones de vulnerabilidades
        for vuln in vulnerabilities:
            if vuln.get("severity") == "critical":
                recommendations.append(f"🚨 PARCHE CRÍTICO: {vuln.get('name', 'Vulnerabilidad crítica')}")
            elif vuln.get("severity") == "high":
                recommendations.append(f"⚠️ PARCHEAR: {vuln.get('name', 'Vulnerabilidad importante')}")
        
        # Recomendaciones de acciones de defensa
        for action in defense_result.get("actions", []):
            if action.get("status") == "failed":
                recommendations.append(f"⚠️ REINTENTAR: {action.get('action', 'Acción fallida')}")
        
        # Recomendaciones generales
        recommendations.append("✅ Realizar auditorías de seguridad periódicas")
        recommendations.append("✅ Capacitar al personal en ciberseguridad")
        
        return list(set(recommendations))
    
    def _generate_threat_recommendations(self, threat: Dict) -> List[str]:
        """Genera recomendaciones de amenaza"""
        recommendations = []
        
        severity = threat.get("severity", "medium")
        threat_type = threat.get("type", "unknown")
        
        if severity == "critical":
            recommendations.append("🚨 BLOQUEAR INMEDIATAMENTE: Amenaza crítica detectada")
            recommendations.append("🚨 NOTIFICAR A EQUIPO DE SEGURIDAD")
        elif severity == "high":
            recommendations.append("⚠️ INVESTIGAR Y CONTENER: Amenaza importante")
        
        # Recomendaciones específicas por tipo
        if threat_type == "malicious_domain":
            recommendations.append("🔒 Bloquear dominio en DNS y firewalls")
        elif threat_type == "brute_force":
            recommendations.append("🔒 Implementar bloqueo de cuentas")
            recommendations.append("🔒 Configurar autenticación multifactor")
        
        # Recomendaciones generales
        recommendations.append("✅ Monitorear actividad sospechosa")
        recommendations.append("✅ Revisar logs de seguridad")
        
        return list(set(recommendations))
    
    def _calculate_monitoring_risk_score(self, behavior_analysis: Dict, 
                                         anomalies: List[Dict]) -> float:
        """Calcula score de riesgo de monitoreo"""
        score = 0.0
        
        if isinstance(behavior_analysis, dict):
            score += behavior_analysis.get("score", 0) * 0.6
        
        score += len(anomalies) * 0.1
        
        return max(0.0, min(1.0, score))
    
    def _calculate_investigation_risk_score(self, deep_scan: Dict, traffic_analysis: Dict,
                                           behavior_analysis: Dict) -> float:
        """Calcula score de riesgo de investigación"""
        score = 0.0
        
        # Score de escaneo
        scan_sources = deep_scan.get("sources", {})
        vuln_count = sum(
            len(s.get("vulnerabilities", [])) for s in scan_sources.values() 
            if isinstance(s, dict)
        )
        score += min(0.4, vuln_count * 0.1)
        
        # Score de tráfico
        if isinstance(traffic_analysis, dict):
            injection_count = len(traffic_analysis.get("injections", []))
            score += min(0.3, injection_count * 0.15)
        
        # Score de comportamiento
        if isinstance(behavior_analysis, dict):
            score += behavior_analysis.get("score", 0) * 0.3
        
        return max(0.0, min(1.0, score))
    
    def _calculate_defense_risk_score(self, threat_scan: Dict, vulnerabilities: List[Dict]) -> float:
        """Calcula score de riesgo de defensa"""
        score = 0.0
        
        # Score de amenazas
        threat_count = len(threat_scan.get("threats", []))
        score += min(0.4, threat_count * 0.15)
        
        # Score de vulnerabilidades
        vuln_count = len(vulnerabilities)
        score += min(0.4, vuln_count * 0.1)
        
        # Score por severidad
        for threat in threat_scan.get("threats", []):
            if threat.get("severity") == "critical":
                score += 0.2
            elif threat.get("severity") == "high":
                score += 0.1
        
        for vuln in vulnerabilities:
            if vuln.get("severity") == "critical":
                score += 0.15
            elif vuln.get("severity") == "high":
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def get_report_history(self, limit: int = 100) -> List[Dict]:
        """Obtiene el historial de informes"""
        return [r.to_dict() for r in self.report_history[-limit:]]
    
    async def get_report_stats(self) -> Dict:
        """Obtiene estadísticas de informes"""
        type_counts = {}
        for report in self.report_history:
            rtype = report.type.value
            type_counts[rtype] = type_counts.get(rtype, 0) + 1
        
        severity_counts = {}
        for report in self.report_history:
            severity = report.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "total_reports": len(self.report_history),
            "type_counts": type_counts,
            "severity_counts": severity_counts,
            "avg_risk_score": sum(r.risk_score for r in self.report_history) / len(self.report_history) if self.report_history else 0
        }
