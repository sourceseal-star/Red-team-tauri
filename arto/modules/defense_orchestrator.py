"""
Defense Orchestrator - Orquestador de Defensa
=============================================
Orquestra respuestas de defensa a amenazas detectadas.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class DefenseAction(Enum):
    """Acciones de defensa"""
    BLOCK = "block"
    ISOLATE = "isolate"
    MONITOR = "monitor"
    ALERT = "alert"
    PATCH = "patch"
    INVESTIGATE = "investigate"
    QUARANTINE = "quarantine"
    SHUTDOWN = "shutdown"


class ThreatSeverity(Enum):
    """Severidad de amenazas"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class DefenseResponse:
    """Respuesta de defensa"""
    response_id: str
    threat_id: str
    action: DefenseAction
    target: str
    status: str  # success, failed, partial
    message: str
    severity: ThreatSeverity
    timestamp: str
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "response_id": self.response_id,
            "threat_id": self.threat_id,
            "action": self.action.value,
            "target": self.target,
            "status": self.status,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "details": self.details
        }


@dataclass
class Vulnerability:
    """Vulnerabilidad detectada"""
    id: str
    name: str
    severity: str
    description: str
    affected_systems: List[str]
    cvss_score: float
    recommendation: str
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity,
            "description": self.description,
            "affected_systems": self.affected_systems,
            "cvss_score": self.cvss_score,
            "recommendation": self.recommendation
        }


class DefenseOrchestrator:
    """Orquestador de Defensa Autónomo"""
    
    def __init__(self):
        self.threat_intel = None
        self.memory = None
        self.knowledge_base = None
        self.defense_rules: Dict[str, Dict] = {}
        self.response_history: List[DefenseResponse] = []
        self.blocked_targets: Dict[str, Dict] = {}
        self.quarantined_systems: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Inicializa el orquestador de defensa"""
        print("🛡️ Inicializando Defense Orchestrator...")
        self._load_defense_rules()
        print("✅ Defense Orchestrator listo")
    
    def _load_defense_rules(self):
        """Carga las reglas de defensa"""
        self.defense_rules = {
            "critical_threat": {
                "condition": lambda t: t.get("severity") == "critical",
                "action": DefenseAction.BLOCK,
                "priority": 10
            },
            "high_threat": {
                "condition": lambda t: t.get("severity") == "high",
                "action": DefenseAction.ISOLATE,
                "priority": 8
            },
            "malicious_domain": {
                "condition": lambda t: t.get("type") == "malicious_domain",
                "action": DefenseAction.BLOCK,
                "priority": 9
            },
            "vulnerability_critical": {
                "condition": lambda t: t.get("type") == "vulnerability" and t.get("severity") == "critical",
                "action": DefenseAction.PATCH,
                "priority": 7
            },
            "brute_force": {
                "condition": lambda t: t.get("type") == "brute_force",
                "action": DefenseAction.BLOCK,
                "priority": 9
            },
            "suspicious_behavior": {
                "condition": lambda t: t.get("type") == "suspicious_behavior",
                "action": DefenseAction.MONITOR,
                "priority": 5
            },
            "default": {
                "condition": lambda t: True,
                "action": DefenseAction.ALERT,
                "priority": 1
            }
        }
    
    async def respond_to_threat(self, threat: Dict) -> DefenseResponse:
        """
        Responde a una amenaza detectada.
        
        Args:
            threat: Datos de la amenaza
            
        Returns:
            DefenseResponse: Respuesta de defensa
        """
        threat_id = threat.get("id", f"threat_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}")
        target = threat.get("target", "unknown")
        severity = threat.get("severity", "medium")
        
        # Determinar mejor acción
        best_action = await self._determine_best_action(threat)
        
        # Ejecutar acción
        response = await self._execute_defense_action(
            threat_id, target, best_action, threat, severity
        )
        
        # Guardar en historial
        self.response_history.append(response)
        if self.memory:
            await self.memory.store_defense_response(response.to_dict())
        
        return response
    
    async def _determine_best_action(self, threat: Dict) -> DefenseAction:
        """Determina la mejor acción de defensa"""
        best_action = DefenseAction.ALERT
        best_priority = -1
        
        for rule_name, rule in self.defense_rules.items():
            try:
                if rule["condition"](threat):
                    priority = rule["priority"]
                    if priority > best_priority:
                        best_priority = priority
                        best_action = rule["action"]
            except Exception:
                continue
        
        return best_action
    
    async def _execute_defense_action(self, threat_id: str, target: str,
                                        action: DefenseAction, threat: Dict,
                                        severity: str) -> DefenseResponse:
        """Ejecuta una acción de defensa"""
        response_id = f"resp_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        severity_enum = ThreatSeverity(severity) if severity in [s.value for s in ThreatSeverity] else ThreatSeverity.MEDIUM
        
        if action == DefenseAction.BLOCK:
            return await self._execute_block(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.ISOLATE:
            return await self._execute_isolate(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.MONITOR:
            return await self._execute_monitor(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.ALERT:
            return await self._execute_alert(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.PATCH:
            return await self._execute_patch(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.INVESTIGATE:
            return await self._execute_investigate(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.QUARANTINE:
            return await self._execute_quarantine(response_id, threat_id, target, threat, severity_enum)
        elif action == DefenseAction.SHUTDOWN:
            return await self._execute_shutdown(response_id, threat_id, target, threat, severity_enum)
        else:
            return DefenseResponse(
                response_id=response_id,
                threat_id=threat_id,
                action=action,
                target=target,
                status="failed",
                message=f"Acción no implementada: {action.value}",
                severity=severity_enum,
                timestamp=datetime.datetime.now().isoformat()
            )
    
    async def _execute_block(self, response_id: str, threat_id: str, target: str,
                              threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de bloqueo"""
        self.blocked_targets[target] = {
            "threat_id": threat_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "reason": threat.get("description", "Amenaza detectada"),
            "severity": severity.value
        }
        
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.BLOCK,
            target=target,
            status="success",
            message=f"Bloqueado {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "blocked": True,
                "reason": threat.get("description", "Amenaza detectada")
            }
        )
    
    async def _execute_isolate(self, response_id: str, threat_id: str, target: str,
                               threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de aislamiento"""
        self.quarantined_systems[target] = {
            "threat_id": threat_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "reason": threat.get("description", "Amenaza detectada"),
            "severity": severity.value
        }
        
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.ISOLATE,
            target=target,
            status="success",
            message=f"Aislamiento iniciado para {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "isolated": True,
                "reason": threat.get("description", "Amenaza detectada")
            }
        )
    
    async def _execute_monitor(self, response_id: str, threat_id: str, target: str,
                               threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de monitoreo"""
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.MONITOR,
            target=target,
            status="success",
            message=f"Monitoreo intensivo iniciado para {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "monitoring": True,
                "threat_type": threat.get("type", "unknown")
            }
        )
    
    async def _execute_alert(self, response_id: str, threat_id: str, target: str,
                            threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de alerta"""
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.ALERT,
            target=target,
            status="success",
            message=f"Alerta generada para {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "alert": True,
                "threat": threat
            }
        )
    
    async def _execute_patch(self, response_id: str, threat_id: str, target: str,
                             threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de parcheo"""
        vulnerability = threat.get("vulnerability", "unknown")
        
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.PATCH,
            target=target,
            status="partial",
            message=f"Parche recomendado para {vulnerability} en {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "vulnerability": vulnerability,
                "action": "apply_patch",
                "status": "recommended"
            }
        )
    
    async def _execute_investigate(self, response_id: str, threat_id: str, target: str,
                                   threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de investigación"""
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.INVESTIGATE,
            target=target,
            status="success",
            message=f"Investigación iniciada para {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "investigation": True,
                "threat_type": threat.get("type", "unknown")
            }
        )
    
    async def _execute_quarantine(self, response_id: str, threat_id: str, target: str,
                                  threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de cuarentena"""
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.QUARANTINE,
            target=target,
            status="success",
            message=f"Cuarentena aplicada a {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "quarantined": True,
                "reason": threat.get("description", "Amenaza crítica")
            }
        )
    
    async def _execute_shutdown(self, response_id: str, threat_id: str, target: str,
                                 threat: Dict, severity: ThreatSeverity) -> DefenseResponse:
        """Ejecuta acción de apagado"""
        return DefenseResponse(
            response_id=response_id,
            threat_id=threat_id,
            action=DefenseAction.SHUTDOWN,
            target=target,
            status="partial",
            message=f"Apagado de emergencia recomendado para {target}",
            severity=severity,
            timestamp=datetime.datetime.now().isoformat(),
            details={
                "action": "emergency_shutdown",
                "status": "recommended",
                "reason": threat.get("description", "Amenaza crítica")
            }
        )
    
    async def scan_for_threats(self, target: str) -> Dict:
        """Escanea un objetivo en busca de amenazas"""
        result = {
            "target": target,
            "timestamp": datetime.datetime.now().isoformat(),
            "threats": [],
            "vulnerabilities": []
        }
        
        # Usar inteligencia de amenazas si está disponible
        if self.threat_intel:
            threat_data = await self.threat_intel.scan_target(target)
            result["threats"] = threat_data.get("threats", [])
        
        # Analizar vulnerabilidades
        result["vulnerabilities"] = await self.analyze_vulnerabilities(target)
        
        return result
    
    async def analyze_vulnerabilities(self, target: str) -> List[Dict]:
        """Analiza vulnerabilidades en un objetivo"""
        vulnerabilities = []
        
        # Simulación de análisis de vulnerabilidades
        common_vulnerabilities = [
            {
                "id": "VULN-001",
                "name": "Outdated Software",
                "severity": "high",
                "description": "Software desactualizado detectado",
                "affected_systems": [target],
                "cvss_score": 7.5,
                "recommendation": "Actualizar a la última versión"
            },
            {
                "id": "VULN-002",
                "name": "Weak Password Policy",
                "severity": "medium",
                "description": "Política de contraseñas débil",
                "affected_systems": [target],
                "cvss_score": 5.0,
                "recommendation": "Implementar política de contraseñas fuertes"
            },
            {
                "id": "VULN-003",
                "name": "Open Ports",
                "severity": "medium",
                "description": "Puertos innecesarios abiertos",
                "affected_systems": [target],
                "cvss_score": 6.0,
                "recommendation": "Cerrar puertos no utilizados"
            }
        ]
        
        # Filtrar por objetivo
        for vuln in common_vulnerabilities:
            if target in vuln["affected_systems"]:
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    async def execute_defense(self, target: str, decision: Any = None, 
                             threat_scan: Optional[Dict] = None,
                             vulnerabilities: Optional[List[Dict]] = None) -> Dict:
        """
        Ejecuta defensa completa en un objetivo.
        
        Args:
            target: Objetivo a defender
            decision: Decisión de defensa (opcional)
            threat_scan: Resultados de escaneo de amenazas (opcional)
            vulnerabilities: Vulnerabilidades detectadas (opcional)
            
        Returns:
            Resultado de la defensa
        """
        result = {
            "target": target,
            "timestamp": datetime.datetime.now().isoformat(),
            "actions": [],
            "threats": [],
            "vulnerabilities": []
        }
        
        # Escanear amenazas si no se proporcionan
        if threat_scan is None:
            threat_scan = await self.scan_for_threats(target)
        
        result["threats"] = threat_scan.get("threats", [])
        
        # Analizar vulnerabilidades si no se proporcionan
        if vulnerabilities is None:
            vulnerabilities = await self.analyze_vulnerabilities(target)
        
        result["vulnerabilities"] = vulnerabilities
        
        # Ejecutar acciones de defensa para cada amenaza
        for threat in threat_scan.get("threats", []):
            response = await self.respond_to_threat(threat)
            result["actions"].append(response.to_dict())
        
        # Ejecutar acciones de defensa para cada vulnerabilidad
        for vuln in vulnerabilities:
            threat_data = {
                "id": vuln.get("id"),
                "type": "vulnerability",
                "severity": vuln.get("severity", "medium"),
                "target": target,
                "description": vuln.get("description", ""),
                "vulnerability": vuln.get("name", "")
            }
            response = await self.respond_to_threat(threat_data)
            result["actions"].append(response.to_dict())
        
        return result
    
    async def block_target(self, target: str, reason: str = "Amenaza detectada") -> Dict:
        """Bloquea un objetivo específico"""
        self.blocked_targets[target] = {
            "timestamp": datetime.datetime.now().isoformat(),
            "reason": reason,
            "severity": "high"
        }
        
        return {
            "status": "success",
            "target": target,
            "action": "block",
            "reason": reason,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    async def unblock_target(self, target: str) -> Dict:
        """Desbloquea un objetivo"""
        if target in self.blocked_targets:
            del self.blocked_targets[target]
            return {
                "status": "success",
                "target": target,
                "action": "unblock",
                "timestamp": datetime.datetime.now().isoformat()
            }
        return {
            "status": "failed",
            "target": target,
            "message": "Objetivo no estaba bloqueado",
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    async def get_defense_stats(self) -> Dict:
        """Obtiene estadísticas de defensa"""
        action_counts = {}
        for response in self.response_history:
            action = response.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "total_responses": len(self.response_history),
            "action_counts": action_counts,
            "blocked_targets": len(self.blocked_targets),
            "quarantined_systems": len(self.quarantined_systems)
        }
