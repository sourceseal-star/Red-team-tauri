#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON REPORTER - Generación de Informes JSON
============================================
Genera informes detallados en formato JSON.

Autor: Harold Paredes / SourceSeal Red Team
"""

import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JSONReport:
    """Informe JSON."""
    title: str = "LEVIATHAN Scan Report"
    target: str = ""
    scan_type: str = "comprehensive"
    timestamp: str = ""
    duration: float = 0.0
    summary: Dict = field(default_factory=dict)
    findings: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convierte a diccionario para serializacion JSON."""
        return {
            "title": self.title,
            "target": self.target,
            "scan_type": self.scan_type,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "summary": self.summary,
            "findings": self.findings,
            "recommendations": self.recommendations
        }


class JSONReporter:
    """Generador de informes JSON."""
    
    def __init__(self):
        self.name = "json_reporter"
        self.category = "reporter"
        self.description = "Generación de informes JSON"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Siempre aplicable."""
        return True
    
    async def generate(self, target: str, context: Dict = None) -> Dict:
        """
        Genera un informe JSON.
        
        Args:
            target: Objetivo del informe
            context: Contexto con datos del escaneo
        """
        context = context or {}
        
        results = {
            "target": target,
            "report": None,
            "file_path": None,
            "success": False,
            "error": None
        }
        
        try:
            # Crear informe
            report = await self._create_report(target, context)
            
            # Convertir a JSON
            report_json = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
            
            results["report"] = report_json
            results["success"] = True
            
            # Guardar en archivo
            filename = self._generate_filename(target, context)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_json)
            
            results["file_path"] = filename
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _create_report(self, target: str, context: Dict) -> JSONReport:
        """Crea un informe JSON."""
        report = JSONReport(
            target=target,
            timestamp=datetime.utcnow().isoformat(),
            duration=context.get("scan_duration", 0.0)
        )
        
        # Determinar tipo de escaneo
        report.scan_type = context.get("scan_type", "comprehensive")
        
        # Crear resumen
        report.summary = await self._create_summary(context)
        
        # Crear hallazgos
        report.findings = await self._create_findings(context)
        
        # Crear recomendaciones
        report.recommendations = await self._create_recommendations(context)
        
        return report
    
    async def _create_summary(self, context: Dict) -> Dict:
        """Crea el resumen del informe."""
        summary = {
            "total_targets": context.get("total_targets", 0),
            "active_targets": context.get("active_targets", 0),
            "cameras_detected": context.get("cameras_detected", 0),
            "vulnerabilities_found": context.get("vulnerabilities_found", 0),
            "exploits_successful": context.get("exploits_successful", 0),
            "anomalies_detected": context.get("anomalies_detected", 0),
            "threat_level": context.get("threat_level", "low"),
            "threat_score": context.get("threat_score", 0.0)
        }
        
        return summary
    
    async def _create_findings(self, context: Dict) -> Dict:
        """Crea la sección de hallazgos."""
        findings = {}
        
        # Cámaras detectadas
        if context.get("cameras"):
            findings["cameras"] = context["cameras"]
        
        # Vulnerabilidades
        if context.get("vulnerabilities"):
            findings["vulnerabilities"] = context["vulnerabilities"]
        
        # Exploits
        if context.get("exploits"):
            findings["exploits"] = context["exploits"]
        
        # Anomalías
        if context.get("anomalies"):
            findings["anomalies"] = context["anomalies"]
        
        # Servicios
        if context.get("services"):
            findings["services"] = context["services"]
        
        return findings
    
    async def _create_recommendations(self, context: Dict) -> List[str]:
        """Crea la sección de recomendaciones."""
        recommendations = []
        
        # Recomendaciones basadas en nivel de amenaza
        threat_level = context.get("threat_level", "low")
        
        if threat_level == "critical":
            recommendations.extend([
                "🔴 AISLAR INMEDIATAMENTE: Este sistema representa un riesgo crítico",
                "Desconectar dispositivos vulnerables de la red",
                "Realizar análisis forense completo",
                "Implementar controles de acceso más estrictos"
            ])
        elif threat_level == "high":
            recommendations.extend([
                "🟠 ALTO RIESGO: Revisar y parchear inmediatamente",
                "Aplicar parches de seguridad para todas las vulnerabilidades críticas",
                "Implementar monitoreo continuo",
                "Restringir acceso desde redes externas"
            ])
        elif threat_level == "medium":
            recommendations.extend([
                "🟡 RIESGO MODERADO: Revisar en las próximas 24 horas",
                "Aplicar parches de seguridad",
                "Revisar configuración de seguridad"
            ])
        
        # Recomendaciones específicas
        if context.get("cameras_detected", 0) > 0:
            recommendations.append("⚠️ Cámaras IP detectadas - Verificar credenciales y actualizar firmware")
        
        if context.get("vulnerabilities_found", 0) > 0:
            recommendations.append("⚠️ Vulnerabilidades detectadas - Aplicar parches de seguridad")
        
        return recommendations
    
    def _generate_filename(self, target: str, context: Dict) -> str:
        """Genera un nombre de archivo único."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scan_type = context.get("scan_type", "scan")
        
        # Limpiar target para usar en nombre de archivo
        clean_target = target.replace("/", "_").replace(":", "_").replace(".", "_")
        
        return f"leviathan_{scan_type}_{clean_target}_{timestamp}.json"
    
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
    return JSONReporter()


# Extensión para JSONReport
class JSONReportExtension:
    """Extensión para convertir JSONReport a diccionario."""
    
    @staticmethod
    def to_dict(report: JSONReport) -> Dict:
        """Convierte JSONReport a diccionario."""
        return {
            "title": report.title,
            "target": report.target,
            "scan_type": report.scan_type,
            "timestamp": report.timestamp,
            "duration": report.duration,
            "summary": report.summary,
            "findings": report.findings,
            "recommendations": report.recommendations
        }
