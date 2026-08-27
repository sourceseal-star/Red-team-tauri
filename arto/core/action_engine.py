"""
Action Engine - Motor de Acción
===============================
Ejecuta acciones autónomas basadas en decisiones.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class ActionType(Enum):
    """Tipos de acciones"""
    SCAN = "scan"
    ATTACK = "attack"
    DEFEND = "defend"
    MONITOR = "monitor"
    INVESTIGATE = "investigate"
    BLOCK = "block"
    ALERT = "alert"
    LOG = "log"
    NOTIFY = "notify"


@dataclass
class ActionResult:
    """Resultado de una acción"""
    action_id: str
    action_type: ActionType
    target: str
    status: str  # success, failed, partial
    message: str
    data: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }


class ActionEngine:
    """Motor de Acción Autónomo"""
    
    def __init__(self):
        self.attack_simulator = None
        self.defense_orchestrator = None
        self.threat_intel = None
        self.memory = None
        self.knowledge_base = None
        self.action_history: List[ActionResult] = []
        self.action_handlers = {
            ActionType.SCAN.value: self._handle_scan,
            ActionType.ATTACK.value: self._handle_attack,
            ActionType.DEFEND.value: self._handle_defend,
            ActionType.MONITOR.value: self._handle_monitor,
            ActionType.INVESTIGATE.value: self._handle_investigate,
            ActionType.BLOCK.value: self._handle_block,
            ActionType.ALERT.value: self._handle_alert,
            ActionType.LOG.value: self._handle_log,
            ActionType.NOTIFY.value: self._handle_notify
        }
    
    async def execute(self, decision: Any, context: Dict) -> Dict:
        """
        Ejecuta una acción basada en una decisión.
        
        Args:
            decision: Decisión a ejecutar
            context: Contexto adicional
            
        Returns:
            Resultado de la acción
        """
        action_type = decision.action
        target = context.get("target", "unknown")
        action_id = f"act_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Obtener handler
        handler = self.action_handlers.get(action_type)
        if handler is None:
            result = ActionResult(
                action_id=action_id,
                action_type=ActionType.LOG,
                target=target,
                status="failed",
                message=f"Acción no soportada: {action_type}"
            )
            self.action_history.append(result)
            return result.to_dict()
        
        # Ejecutar acción
        try:
            result = await handler(decision, context, action_id)
            self.action_history.append(result)
            
            # Guardar en memoria
            if self.memory:
                await self.memory.store_action(result.to_dict())
            
            return result.to_dict()
            
        except Exception as e:
            result = ActionResult(
                action_id=action_id,
                action_type=ActionType(action_type),
                target=target,
                status="failed",
                message=str(e),
                data={"error": str(e), "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None}
            )
            self.action_history.append(result)
            return result.to_dict()
    
    async def _handle_scan(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de escaneo"""
        target = context.get("target", "unknown")
        scan_type = context.get("scan_type", "full")
        
        if self.attack_simulator:
            if scan_type == "full":
                result = await self.attack_simulator.osint_module.full_scan(target)
            elif scan_type == "quick":
                result = await self.attack_simulator.osint_module.quick_scan(target)
            elif scan_type == "deep":
                result = await self.attack_simulator.osint_module.deep_scan(target)
            else:
                result = await self.attack_simulator.osint_module.full_scan(target)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.SCAN,
                target=target,
                status="success",
                message=f"Escaneo {scan_type} completado en {target}",
                data={"scan_result": result}
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.SCAN,
                target=target,
                status="failed",
                message="AttackSimulator no está inicializado"
            )
    
    async def _handle_attack(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de ataque (simulación)"""
        target = context.get("target", "unknown")
        template_name = decision.metadata.get("template", "default")
        
        if self.attack_simulator:
            simulation = await self.attack_simulator.simulate_attack(template_name, target)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.ATTACK,
                target=target,
                status="success",
                message=f"Simulación de ataque {template_name} completada en {target}",
                data={"simulation": simulation.to_dict()}
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.ATTACK,
                target=target,
                status="failed",
                message="AttackSimulator no está inicializado"
            )
    
    async def _handle_defend(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de defensa"""
        target = context.get("target", "unknown")
        threat_data = context.get("threat_data", {})
        
        if self.defense_orchestrator:
            if threat_data:
                response = await self.defense_orchestrator.respond_to_threat(threat_data)
            else:
                response = await self.defense_orchestrator.execute_defense(target)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.DEFEND,
                target=target,
                status="success",
                message=f"Defensa ejecutada en {target}",
                data={"defense_result": response.to_dict()}
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.DEFEND,
                target=target,
                status="failed",
                message="DefenseOrchestrator no está inicializado"
            )
    
    async def _handle_monitor(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de monitoreo"""
        target = context.get("target", "unknown")
        
        if self.attack_simulator:
            monitor_result = await self.attack_simulator.start_monitoring(target)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.MONITOR,
                target=target,
                status="success",
                message=f"Monitoreo iniciado en {target}",
                data={"monitor_result": monitor_result}
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.MONITOR,
                target=target,
                status="failed",
                message="AttackSimulator no está inicializado"
            )
    
    async def _handle_investigate(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de investigación"""
        target = context.get("target", "unknown")
        
        if self.attack_simulator:
            deep_scan = await self.attack_simulator.osint_module.deep_scan(target)
            traffic_analysis = await self.attack_simulator.interceptor.analyze_traffic(target)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.INVESTIGATE,
                target=target,
                status="success",
                message=f"Investigación completada en {target}",
                data={
                    "deep_scan": deep_scan,
                    "traffic_analysis": traffic_analysis
                }
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.INVESTIGATE,
                target=target,
                status="failed",
                message="AttackSimulator no está inicializado"
            )
    
    async def _handle_block(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de bloqueo"""
        target = context.get("target", "unknown")
        reason = context.get("reason", "Amenaza detectada")
        
        if self.defense_orchestrator:
            block_result = await self.defense_orchestrator.block_target(target, reason)
            
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.BLOCK,
                target=target,
                status="success",
                message=f"Bloqueado {target}: {reason}",
                data={"block_result": block_result}
            )
        else:
            return ActionResult(
                action_id=action_id,
                action_type=ActionType.BLOCK,
                target=target,
                status="partial",
                message=f"Bloqueo registrado para {target}: {reason}",
                data={"status": "pending", "target": target, "reason": reason}
            )
    
    async def _handle_alert(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de alerta"""
        target = context.get("target", "unknown")
        message = context.get("message", "Alerta de seguridad")
        severity = context.get("severity", "medium")
        
        # Crear alerta
        alert = {
            "id": action_id,
            "target": target,
            "message": message,
            "severity": severity,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "security_alert"
        }
        
        # Guardar en memoria
        if self.memory:
            await self.memory.store_alert(alert)
        
        return ActionResult(
            action_id=action_id,
            action_type=ActionType.ALERT,
            target=target,
            status="success",
            message=f"Alerta generada: {message}",
            data={"alert": alert}
        )
    
    async def _handle_log(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de registro"""
        target = context.get("target", "unknown")
        message = context.get("message", "Evento registrado")
        
        # Crear registro
        log_entry = {
            "id": action_id,
            "target": target,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "log"
        }
        
        # Guardar en memoria
        if self.memory:
            await self.memory.store_log(log_entry)
        
        return ActionResult(
            action_id=action_id,
            action_type=ActionType.LOG,
            target=target,
            status="success",
            message=f"Registro: {message}",
            data={"log": log_entry}
        )
    
    async def _handle_notify(self, decision: Any, context: Dict, action_id: str) -> ActionResult:
        """Maneja acción de notificación"""
        target = context.get("target", "unknown")
        message = context.get("message", "Notificación")
        
        # Crear notificación
        notification = {
            "id": action_id,
            "target": target,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "notification"
        }
        
        return ActionResult(
            action_id=action_id,
            action_type=ActionType.NOTIFY,
            target=target,
            status="success",
            message=f"Notificación: {message}",
            data={"notification": notification}
        )
    
    async def get_action_stats(self) -> Dict:
        """Obtiene estadísticas de acciones"""
        type_counts = {}
        status_counts = {}
        
        for action in self.action_history:
            atype = action.action_type.value
            type_counts[atype] = type_counts.get(atype, 0) + 1
            
            status = action.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_actions": len(self.action_history),
            "type_counts": type_counts,
            "status_counts": status_counts,
            "success_rate": status_counts.get("success", 0) / len(self.action_history) if self.action_history else 0
        }
