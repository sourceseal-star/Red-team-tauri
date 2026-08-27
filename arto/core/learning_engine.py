"""
Learning Engine - Motor de Aprendizaje
======================================
Aprende de cada interacción y mejora las decisiones futuras.
"""

import asyncio
import datetime
import json
import pickle
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import os


@dataclass
class LearningObservation:
    """Observación para aprendizaje"""
    observation_id: str
    type: str  # scan, simulation, monitoring, investigation, defense
    target: str
    data: Dict
    action: str
    result: Dict
    timestamp: str
    metadata: Dict = field(default_factory=dict)


class LearningEngine:
    """Motor de Aprendizaje Autónomo"""
    
    def __init__(self):
        self.memory = None
        self.knowledge_base = None
        self.observations: List[LearningObservation] = []
        self.patterns: Dict[str, Dict] = {}
        self.decision_feedback: Dict[str, List[Dict]] = defaultdict(list)
        self.learning_rate = 0.1
        self.observation_limit = 1000
        
    async def load_memory(self):
        """Carga datos de memoria para aprendizaje"""
        if self.memory:
            self.observations = await self.memory.load_observations()
            self.patterns = await self.memory.load_patterns()
            self.decision_feedback = await self.memory.load_decision_feedback()
    
    async def save_memory(self):
        """Guarda datos de aprendizaje en memoria"""
        if self.memory:
            await self.memory.save_observations(self.observations)
            await self.memory.save_patterns(self.patterns)
            await self.memory.save_decision_feedback(self.decision_feedback)
    
    async def learn_from_observation(self, observation_data: Dict):
        """
        Aprende de una observación.
        
        Args:
            observation_data: Datos de la observación
        """
        # Crear ID único
        obs_id = f"obs_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Crear observación
        observation = LearningObservation(
            observation_id=obs_id,
            type=observation_data.get("type", "unknown"),
            target=observation_data.get("target", "unknown"),
            data=observation_data.get("data", {}),
            action=observation_data.get("action", "none"),
            result=observation_data.get("result", {}),
            timestamp=datetime.datetime.now().isoformat(),
            metadata=observation_data.get("metadata", {})
        )
        
        # Almacenar observación
        self.observations.append(observation)
        if len(self.observations) > self.observation_limit:
            self.observations = self.observations[-self.observation_limit:]
        
        # Extraer patrones
        await self._extract_patterns(observation)
        
        # Actualizar feedback de decisiones
        await self._update_decision_feedback(observation)
        
        # Guardar en memoria
        if self.memory:
            await self.memory.store_observation(observation.to_dict())
        
        # Guardar en base de conocimiento
        if self.knowledge_base:
            await self.knowledge_base.add_observation(observation.to_dict())
    
    async def _extract_patterns(self, observation: LearningObservation):
        """Extrae patrones de la observación"""
        obs_type = observation.type
        target = observation.target
        data = observation.data
        result = observation.result
        
        # Patrones por tipo de observación
        if obs_type not in self.patterns:
            self.patterns[obs_type] = {
                "count": 0,
                "targets": defaultdict(int),
                "actions": defaultdict(int),
                "common_data": defaultdict(int),
                "common_results": defaultdict(int)
            }
        
        pattern = self.patterns[obs_type]
        pattern["count"] += 1
        pattern["targets"][target] += 1
        pattern["actions"][observation.action] += 1
        
        # Extraer datos comunes
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                pattern["common_data"][key] += 1
        
        # Extraer resultados comunes
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)):
                pattern["common_results"][key] += 1
    
    async def _update_decision_feedback(self, observation: LearningObservation):
        """Actualiza el feedback de decisiones"""
        action = observation.action
        result = observation.result
        
        # Determinar si el resultado fue positivo
        is_positive = self._evaluate_result_quality(result)
        
        self.decision_feedback[action].append({
            "observation_id": observation.observation_id,
            "target": observation.target,
            "type": observation.type,
            "positive": is_positive,
            "timestamp": observation.timestamp,
            "result": result
        })
        
        # Limitar feedback
        for action in self.decision_feedback:
            if len(self.decision_feedback[action]) > 100:
                self.decision_feedback[action] = self.decision_feedback[action][-100:]
    
    def _evaluate_result_quality(self, result: Dict) -> bool:
        """Evalúa la calidad del resultado"""
        # Lógica simplificada - en implementación completa se analiza el resultado
        if result.get("status") == "success":
            return True
        if result.get("status") == "completed":
            return True
        if result.get("vulnerabilities_found", 0) > 0:
            return True
        if result.get("threats_detected", 0) > 0:
            return True
        return False
    
    async def get_decision_confidence(self, rule_name: str, context: Dict) -> float:
        """
        Obtiene la confianza ajustada basada en aprendizaje.
        
        Args:
            rule_name: Nombre de la regla
            context: Contexto actual
            
        Returns:
            Confianza ajustada (0.0 - 1.0)
        """
        base_confidence = 0.5
        
        # Buscar feedback para la acción de la regla
        action = self._get_action_from_rule(rule_name)
        if action and action in self.decision_feedback:
            feedback = self.decision_feedback[action]
            if feedback:
                # Calcular tasa de éxito
                positive_count = sum(1 for f in feedback if f["positive"])
                total = len(feedback)
                success_rate = positive_count / total
                
                # Ajustar confianza
                base_confidence = 0.5 + (success_rate - 0.5) * self.learning_rate
        
        # Ajustar basado en patrones
        obs_type = context.get("type", "unknown")
        if obs_type in self.patterns:
            pattern = self.patterns[obs_type]
            action_count = pattern["actions"].get(action, 0)
            total_actions = sum(pattern["actions"].values())
            
            if total_actions > 0:
                action_frequency = action_count / total_actions
                base_confidence = base_confidence * 0.7 + action_frequency * 0.3
        
        return max(0.0, min(1.0, base_confidence))
    
    def _get_action_from_rule(self, rule_name: str) -> Optional[str]:
        """Obtiene la acción de una regla"""
        # Esto debería estar conectado al DecisionEngine
        # Por ahora, devolver acción por defecto
        return "investigate"
    
    async def get_learning_stats(self) -> Dict:
        """Obtiene estadísticas de aprendizaje"""
        action_stats = {}
        for action, feedback in self.decision_feedback.items():
            positive = sum(1 for f in feedback if f["positive"])
            total = len(feedback)
            action_stats[action] = {
                "total": total,
                "positive": positive,
                "success_rate": positive / total if total > 0 else 0
            }
        
        pattern_stats = {}
        for obs_type, pattern in self.patterns.items():
            pattern_stats[obs_type] = {
                "count": pattern["count"],
                "targets": len(pattern["targets"]),
                "actions": dict(pattern["actions"])
            }
        
        return {
            "total_observations": len(self.observations),
            "action_stats": action_stats,
            "pattern_stats": pattern_stats,
            "learning_rate": self.learning_rate
        }
    
    async def get_patterns(self, obs_type: Optional[str] = None) -> Dict:
        """Obtiene patrones de aprendizaje"""
        if obs_type:
            return self.patterns.get(obs_type, {})
        return self.patterns
    
    async def predict_best_action(self, context: Dict) -> str:
        """
        Predice la mejor acción basada en aprendizaje.
        
        Args:
            context: Contexto actual
            
        Returns:
            Mejor acción
        """
        obs_type = context.get("type", "unknown")
        
        if obs_type in self.patterns:
            pattern = self.patterns[obs_type]
            # Devolver la acción más común
            if pattern["actions"]:
                return max(pattern["actions"].items(), key=lambda x: x[1])[0]
        
        return "log_and_continue"
