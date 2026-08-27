"""
ARTO - Automated Red Team Operations
=====================================
Sistema de operaciones autónomas de red team con inteligencia artificial.

Integración con Red-Team-Tauri:
    - Usa enhanced_recon.py para OSINT local
    - Usa interceptor.py para análisis de tráfico
    
Uso:
    from arto import arto
    
    # Iniciar el sistema
    await arto.start()
    
    # Ejecutar operación autónoma
    result = await arto.autonomous_operation("example.com", "scan")
    
    # Predecir ataques
    predictions = await arto.predict_attacks(24)
    
    # Simular ataque
    simulation = await arto.simulate_attack("sql_injection", "192.168.1.100")
    
    # Responder a amenaza
    response = await arto.respond_to_threat(threat_data)
"""

from .core.decision_engine import DecisionEngine
from .core.learning_engine import LearningEngine
from .core.prediction_engine import PredictionEngine
from .core.action_engine import ActionEngine
from .core.behavior_analyzer import BehaviorAnalyzer
from .modules.attack_simulator import AttackSimulator
from .modules.vpn_interceptor import VpnInterceptor, vpn_interceptor
from .modules.defense_orchestrator import DefenseOrchestrator
from .modules.report_generator import ReportGenerator
from .memory.memory_storage import MemoryStorage
from .memory.knowledge_base import KnowledgeBase
from .utils.threat_intelligence import ThreatIntelligence
from .utils.risk_assessor import RiskAssessor
from .utils.pattern_recognizer import PatternRecognizer
from .utils.anomaly_detector import AnomalyDetector
from .utils.temporal_analyzer import TemporalAnalyzer

import asyncio
import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum


class ARTO:
    """Sistema ARTO principal - Operaciones Autónomas de Red Team"""
    
    def __init__(self):
        """Inicializa todos los componentes de ARTO"""
        print("🔧 Inicializando ARTO...")
        
        # Motores principales
        self.decision_engine = DecisionEngine()
        self.learning_engine = LearningEngine()
        self.prediction_engine = PredictionEngine()
        self.action_engine = ActionEngine()
        self.behavior_analyzer = BehaviorAnalyzer()
        
        # Módulos
        self.attack_simulator = AttackSimulator()
        self.defense_orchestrator = DefenseOrchestrator()
        self.report_generator = ReportGenerator()
        self.vpn_interceptor = vpn_interceptor
        
        # Utilidades
        self.memory = MemoryStorage()
        self.knowledge_base = KnowledgeBase()
        self.threat_intel = ThreatIntelligence()
        self.risk_assessor = RiskAssessor()
        self.pattern_recognizer = PatternRecognizer()
        self.anomaly_detector = AnomalyDetector()
        self.temporal_analyzer = TemporalAnalyzer()
        
        # Conectar componentes
        self._connect_components()
        
        # Estado
        self.running = False
        self.operations: List[Dict] = []
        self.predictions: List[Dict] = []
        self.threats: List[Dict] = []
        
        print("✅ ARTO inicializado")
    
    def _connect_components(self):
        """Conecta todos los componentes entre sí"""
        # Conectar motores con módulos
        self.action_engine.attack_simulator = self.attack_simulator
        self.action_engine.defense_orchestrator = self.defense_orchestrator
        self.action_engine.threat_intel = self.threat_intel
        self.action_engine.memory = self.memory
        self.action_engine.knowledge_base = self.knowledge_base
        
        # Conectar learning con prediction
        self.prediction_engine.learning_engine = self.learning_engine
        self.prediction_engine.memory = self.memory
        self.prediction_engine.knowledge_base = self.knowledge_base
        
        # Conectar decision con learning y threat intel
        self.decision_engine.learning_engine = self.learning_engine
        self.decision_engine.threat_intel = self.threat_intel
        self.decision_engine.memory = self.memory
        
        # Conectar módulos con utilidades
        self.attack_simulator.threat_intel = self.threat_intel
        self.attack_simulator.memory = self.memory
        self.defense_orchestrator.threat_intel = self.threat_intel
        self.defense_orchestrator.memory = self.memory
        self.defense_orchestrator.knowledge_base = self.knowledge_base
        
        # Conectar behavior analyzer
        self.behavior_analyzer.pattern_recognizer = self.pattern_recognizer
        self.behavior_analyzer.anomaly_detector = self.anomaly_detector
        self.behavior_analyzer.temporal_analyzer = self.temporal_analyzer
        
        print("🔗 Componentes conectados")
    
    async def start(self):
        """Inicia el sistema ARTO"""
        print("🚀 Iniciando ARTO...")
        
        # Inicializar componentes con recovery individual
        _init_errors = []
        
        try:
            await self.memory.initialize()
            print("[ARTO] Memory: OK")
        except Exception as e:
            print(f"[ARTO] Memory init FAILED: {e}")
            _init_errors.append(f"memory: {e}")
            # Intentar recrear desde cero
            try:
                import os
                if hasattr(self.memory, 'db_path') and os.path.exists(self.memory.db_path):
                    os.remove(self.memory.db_path)
                    print(f"[ARTO] Removed corrupt {self.memory.db_path}")
                self.memory.conn = None
                self.memory.initialized = False
                await self.memory.initialize()
                print("[ARTO] Memory: OK (after recovery)")
            except Exception as e2:
                print(f"[ARTO] Memory recovery FAILED: {e2}")
                _init_errors.append(f"memory_recovery: {e2}")
        
        try:
            await self.knowledge_base.initialize()
            print("[ARTO] KnowledgeBase: OK")
        except Exception as e:
            print(f"[ARTO] KnowledgeBase init FAILED: {e}")
            _init_errors.append(f"knowledge_base: {e}")
            # Intentar recrear desde cero
            try:
                import os
                if hasattr(self.knowledge_base, 'db_path') and os.path.exists(self.knowledge_base.db_path):
                    os.remove(self.knowledge_base.db_path)
                    print(f"[ARTO] Removed corrupt {self.knowledge_base.db_path}")
                self.knowledge_base.initialized = False
                await self.knowledge_base.initialize()
                print("[ARTO] KnowledgeBase: OK (after recovery)")
            except Exception as e2:
                print(f"[ARTO] KnowledgeBase recovery FAILED: {e2}")
                _init_errors.append(f"knowledge_base_recovery: {e2}")
        
        try:
            await self.threat_intel.initialize()
            print("[ARTO] ThreatIntel: OK")
        except Exception as e:
            print(f"[ARTO] ThreatIntel init FAILED: {e}")
            _init_errors.append(f"threat_intel: {e}")
        
        try:
            await self.learning_engine.load_memory()
            print("[ARTO] LearningEngine: OK")
        except Exception as e:
            print(f"[ARTO] LearningEngine load FAILED: {e}")
            _init_errors.append(f"learning_engine: {e}")
        
        try:
            await self.prediction_engine.load_models()
            print("[ARTO] PredictionEngine: OK")
        except Exception as e:
            print(f"[ARTO] PredictionEngine load FAILED: {e}")
            _init_errors.append(f"prediction_engine: {e}")
        
        try:
            await self.attack_simulator.initialize()
            print("[ARTO] AttackSimulator: OK")
        except Exception as e:
            print(f"[ARTO] AttackSimulator init FAILED: {e}")
            _init_errors.append(f"attack_simulator: {e}")
        
        try:
            await self.defense_orchestrator.initialize()
            print("[ARTO] DefenseOrchestrator: OK")
        except Exception as e:
            print(f"[ARTO] DefenseOrchestrator init FAILED: {e}")
            _init_errors.append(f"defense_orchestrator: {e}")
        
        if _init_errors:
            print(f"[ARTO] ⚠ Inicializado con {len(_init_errors)} errores: {_init_errors}")
            print("[ARTO] ⚡ Operando en modo degradado — funciones limitadas")
        else:
            print("[ARTO] ✅ Todos los componentes inicializados correctamente")
        
        self.running = True
        print("✅ ARTO listo para operar")
    
    async def stop(self):
        """Detiene el sistema ARTO"""
        print("🛑 Deteniendo ARTO...")
        self.running = False
        try:
            await self.memory.save()
        except Exception as e:
            print(f"[ARTO] Warning: memory.save() failed: {e}")
        try:
            await self.knowledge_base.save()
        except Exception as e:
            print(f"[ARTO] Warning: knowledge_base.save() failed: {e}")
        print("✅ ARTO detenido")
    
    async def autonomous_operation(self, target: str, operation_type: str = "scan") -> Dict:
        """
        Ejecuta una operación autónoma completa.
        
        Args:
            target: Objetivo (IP, dominio, email, URL)
            operation_type: Tipo de operación (scan, simulate, monitor, investigate, defend)
            
        Returns:
            Diccionario con resultados completos
        """
        if not self.running:
            await self.start()
        
        operation = {
            "id": f"op_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "type": operation_type,
            "target": target,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "running"
        }
        self.operations.append(operation)
        
        try:
            if operation_type == "scan":
                result = await self._autonomous_scan(target)
            elif operation_type == "simulate":
                result = await self._autonomous_simulation(target)
            elif operation_type == "monitor":
                result = await self._autonomous_monitoring(target)
            elif operation_type == "investigate":
                result = await self._autonomous_investigation(target)
            elif operation_type == "defend":
                result = await self._autonomous_defense(target)
            else:
                raise ValueError(f"Tipo de operación no soportado: {operation_type}")
            
            operation["status"] = "completed"
            operation["result"] = result
            return result
            
        except Exception as e:
            operation["status"] = "failed"
            operation["error"] = str(e)
            operation["traceback"] = str(e.__traceback__) if hasattr(e, '__traceback__') else None
            raise
    
    async def _autonomous_scan(self, target: str) -> Dict:
        """Operación autónoma de escaneo"""
        print(f"🔍 Iniciando escaneo autónomo de {target}")
        
        # 1. Escaneo OSINT completo
        scan_result = await self.attack_simulator.osint_module.full_scan(target)
        
        # 2. Análisis de amenaza
        threat_analysis = await self.threat_intel.analyze_target(target, scan_result)
        
        # 3. Evaluación de riesgo
        risk_assessment = await self.risk_assessor.assess_risk(scan_result, threat_analysis)
        risk_assessment = risk_assessment.to_dict()
        
        # 4. Decidir acción basada en resultados
        decision = await self.decision_engine.decide_action({
            "type": "scan_result",
            "target": target,
            "scan_result": scan_result,
            "threat_analysis": threat_analysis,
            "risk_assessment": risk_assessment
        })
        
        # 5. Ejecutar acción
        action_result = await self.action_engine.execute(decision, {
            "target": target,
            "scan_result": scan_result,
            "threat_analysis": threat_analysis,
            "risk_assessment": risk_assessment
        })
        
        # 6. Aprender de la operación
        await self.learning_engine.learn_from_observation({
            "target": target,
            "action": decision.action,
            "result": action_result,
            "scan_result": scan_result,
            "threat_analysis": threat_analysis,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 7. Almacenar en memoria
        await self.memory.store_operation({
            "type": "scan",
            "target": target,
            "result": scan_result,
            "threat_analysis": threat_analysis,
            "risk_assessment": risk_assessment,
            "decision": decision.to_dict(),
            "action": action_result,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 8. Generar informe
        report = await self.report_generator.generate_report({
            "type": "autonomous_scan",
            "target": target,
            "scan_result": scan_result,
            "threat_analysis": threat_analysis,
            "risk_assessment": risk_assessment,
            "decision": decision.to_dict(),
            "action_result": action_result
        })
        
        return {
            "operation_type": "scan",
            "target": target,
            "scan_result": scan_result,
            "threat_analysis": threat_analysis,
            "risk_assessment": risk_assessment,
            "decision": decision.to_dict(),
            "action_result": action_result,
            "report": report.to_dict()
        }
    
    async def _autonomous_simulation(self, target: str) -> Dict:
        """Operación autónoma de simulación"""
        print(f"🎭 Iniciando simulación autónoma en {target}")
        
        # 1. Analizar objetivo
        target_info = await self.attack_simulator.osint_module.quick_scan(target)
        
        # 2. Seleccionar plantilla de ataque
        template = await self._select_attack_template(target, target_info)
        
        # 3. Simular ataque
        simulation = await self.attack_simulator.simulate_attack(template.name, target)
        
        # 4. Analizar resultados
        analysis = await self.attack_simulator.analyze_results(simulation)
        
        # 5. Evaluar impacto
        impact = await self.risk_assessor.assess_impact(simulation, target)
        
        # 6. Aprender de la simulación
        await self.learning_engine.learn_from_observation({
            "type": "attack_simulation",
            "target": target,
            "template": template.name,
            "result": simulation.execution,
            "analysis": analysis,
            "impact": impact,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 7. Almacenar en memoria
        await self.memory.store_simulation({
            "target": target,
            "template": template.name,
            "simulation": simulation.to_dict(),
            "analysis": analysis,
            "impact": impact,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 8. Generar informe
        report = await self.report_generator.generate_report({
            "type": "attack_simulation",
            "target": target,
            "template": template.name,
            "simulation": simulation,
            "analysis": analysis,
            "impact": impact
        })
        
        return {
            "operation_type": "simulation",
            "target": target,
            "template": template.name,
            "target_info": target_info,
            "simulation": simulation.to_dict(),
            "analysis": analysis,
            "impact": impact,
            "report": report.to_dict()
        }
    
    async def _autonomous_monitoring(self, target: str) -> Dict:
        """Operación autónoma de monitoreo"""
        print(f"👁️ Iniciando monitoreo autónomo de {target}")
        
        # 1. Iniciar monitoreo
        monitor_result = await self.attack_simulator.start_monitoring(target)
        
        # 2. Analizar comportamiento
        behavior_analysis = await self.behavior_analyzer.analyze_behavior(
            target, monitor_result.behavior_data
        )
        
        # 3. Detectar anomalías
        anomalies = await self.anomaly_detector.detect_anomalies(
            monitor_result.behavior_data
        )
        
        # 4. Decidir acción basada en el monitoreo
        decision = await self.decision_engine.decide_action({
            "type": "monitoring_result",
            "target": target,
            "data": monitor_result,
            "behavior_analysis": behavior_analysis.to_dict(),
            "anomalies": anomalies
        })
        
        # 5. Ejecutar acción si es necesario
        if decision.action != "LOG_AND_CONTINUE":
            action_result = await self.action_engine.execute(decision, {
                "target": target,
                "monitor_result": monitor_result,
                "behavior_analysis": behavior_analysis,
                "anomalies": anomalies
            })
        else:
            action_result = {"status": "skipped", "reason": "No action required"}
        
        # 6. Aprender del monitoreo
        await self.learning_engine.learn_from_observation({
            "type": "monitoring",
            "target": target,
            "behavior_analysis": behavior_analysis.to_dict(),
            "anomalies": anomalies,
            "decision": decision.to_dict(),
            "action": action_result,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 7. Almacenar en memoria
        await self.memory.store_monitoring({
            "target": target,
            "monitor_result": monitor_result,
            "behavior_analysis": behavior_analysis.to_dict(),
            "anomalies": anomalies,
            "decision": decision.to_dict(),
            "action": action_result,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {
            "operation_type": "monitoring",
            "target": target,
            "monitor_result": monitor_result,
            "behavior_analysis": behavior_analysis.to_dict(),
            "anomalies": anomalies,
            "decision": decision.to_dict(),
            "action_result": action_result
        }
    
    async def _autonomous_investigation(self, target: str) -> Dict:
        """Operación autónoma de investigación"""
        print(f"🔍 Iniciando investigación autónoma de {target}")
        
        # 1. Escaneo profundo
        deep_scan = await self.attack_simulator.osint_module.deep_scan(target)
        
        # 2. Análisis de tráfico
        traffic_analysis = await self.attack_simulator.interceptor.analyze_traffic(target)
        
        # 3. Análisis de comportamiento
        behavior_analysis = await self.behavior_analyzer.analyze_behavior(
            target, traffic_analysis.behavior_data
        )
        
        # 4. Análisis de patrones
        patterns = await self.pattern_recognizer.recognize_patterns(
            deep_scan, traffic_analysis
        )
        
        # 5. Análisis temporal
        temporal_analysis = await self.temporal_analyzer.analyze_temporal(
            target, deep_scan, traffic_analysis
        )
        
        # 6. Generar informe de investigación
        report = await self.report_generator.generate_report({
            "type": "investigation",
            "target": target,
            "deep_scan": deep_scan,
            "traffic_analysis": traffic_analysis,
            "behavior_analysis": behavior_analysis,
            "patterns": patterns,
            "temporal_analysis": temporal_analysis
        })
        
        # 7. Aprender de la investigación
        await self.learning_engine.learn_from_observation({
            "type": "investigation",
            "target": target,
            "deep_scan": deep_scan,
            "traffic_analysis": traffic_analysis,
            "behavior_analysis": behavior_analysis.to_dict(),
            "patterns": patterns,
            "temporal_analysis": temporal_analysis,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 8. Almacenar en memoria
        await self.memory.store_investigation({
            "target": target,
            "deep_scan": deep_scan,
            "traffic_analysis": traffic_analysis,
            "behavior_analysis": behavior_analysis.to_dict(),
            "patterns": patterns,
            "temporal_analysis": temporal_analysis,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {
            "operation_type": "investigation",
            "target": target,
            "deep_scan": deep_scan,
            "traffic_analysis": traffic_analysis,
            "behavior_analysis": behavior_analysis.to_dict(),
            "patterns": patterns,
            "temporal_analysis": temporal_analysis,
            "report": report.to_dict()
        }
    
    async def _autonomous_defense(self, target: str) -> Dict:
        """Operación autónoma de defensa"""
        print(f"🛡️ Iniciando defensa autónoma para {target}")
        
        # 1. Escaneo de amenaza
        threat_scan = await self.defense_orchestrator.scan_for_threats(target)
        
        # 2. Análisis de vulnerabilidades
        vulnerabilities = await self.defense_orchestrator.analyze_vulnerabilities(target)
        
        # 3. Evaluación de riesgo
        risk_assessment = await self.risk_assessor.assess_risk(threat_scan, vulnerabilities)
        risk_assessment = risk_assessment.to_dict()
        
        # 4. Decidir estrategia de defensa
        decision = await self.decision_engine.decide_action({
            "type": "defense",
            "target": target,
            "threat_scan": threat_scan,
            "vulnerabilities": vulnerabilities,
            "risk_assessment": risk_assessment
        })
        
        # 5. Ejecutar defensa
        defense_result = await self.defense_orchestrator.execute_defense(
            target, decision, threat_scan, vulnerabilities
        )
        
        # 6. Aprender de la defensa
        await self.learning_engine.learn_from_observation({
            "type": "defense",
            "target": target,
            "threat_scan": threat_scan,
            "vulnerabilities": vulnerabilities,
            "defense_result": defense_result,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # 7. Generar informe
        report = await self.report_generator.generate_report({
            "type": "defense",
            "target": target,
            "threat_scan": threat_scan,
            "vulnerabilities": vulnerabilities,
            "defense_result": defense_result
        })
        
        return {
            "operation_type": "defense",
            "target": target,
            "threat_scan": threat_scan,
            "vulnerabilities": vulnerabilities,
            "risk_assessment": risk_assessment,
            "decision": decision.to_dict(),
            "defense_result": defense_result,
            "report": report.to_dict()
        }
    
    async def _select_attack_template(self, target: str, target_info: Optional[Dict] = None) -> Any:
        """Selecciona la plantilla de ataque adecuada"""
        templates = await self.attack_simulator.get_templates()
        
        # Si no hay información del objetivo, usar escaneo rápido
        if target_info is None:
            target_info = await self.attack_simulator.osint_module.quick_scan(target)
        
        # Lógica de selección inteligente
        if target.startswith("http"):
            if "/api/" in target or "/graphql" in target:
                return templates.get("api_attack", templates["web_attack"])
            elif "/admin" in target or "/login" in target:
                return templates.get("auth_attack", templates["web_attack"])
            else:
                return templates.get("web_attack", templates["default"])
        elif "." in target and not target.replace(".", "").isdigit():
            return templates.get("domain_attack", templates["default"])
        elif target.count(".") == 3:
            return templates.get("ip_attack", templates["network_attack"])
        else:
            return templates.get("network_attack", templates["default"])
    
    async def predict_attacks(self, time_horizon: int = 24) -> List[Dict]:
        """
        Predice posibles ataques en las próximas horas.
        
        Args:
            time_horizon: Horas hacia adelante para predecir
            
        Returns:
            Lista de predicciones
        """
        if not self.running:
            await self.start()
        
        context = await self._get_current_context()
        predictions = await self.prediction_engine.predict_attacks(context, time_horizon)
        self.predictions = [p.to_dict() for p in predictions]
        return self.predictions
    
    async def _get_current_context(self) -> Dict:
        """Obtiene el contexto actual para predicciones"""
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "operations": self.operations[-10:] if len(self.operations) > 10 else self.operations,
            "predictions": self.predictions[-5:] if len(self.predictions) > 5 else self.predictions,
            "threats": self.threats[-10:] if len(self.threats) > 10 else self.threats,
            "memory_stats": await self.memory.get_stats()
        }
    
    async def analyze_behavior(self, entity: str, behavior_data: Dict) -> Dict:
        """
        Analiza el comportamiento de una entidad.
        
        Args:
            entity: Entidad a analizar (IP, usuario, etc.)
            behavior_data: Datos de comportamiento
            
        Returns:
            Análisis de comportamiento
        """
        analysis = await self.behavior_analyzer.analyze_behavior(entity, behavior_data)
        return analysis.to_dict()
    
    async def simulate_attack(self, template_name: str, target: str) -> Dict:
        """
        Simula un ataque usando una plantilla.
        
        Args:
            template_name: Nombre de la plantilla de ataque
            target: Objetivo del ataque
            
        Returns:
            Resultados de la simulación
        """
        simulation = await self.attack_simulator.simulate_attack(template_name, target)
        return simulation.to_dict()
    
    async def respond_to_threat(self, threat: Dict) -> Dict:
        """
        Responde a una amenaza detectada.
        
        Args:
            threat: Datos de la amenaza
            
        Returns:
            Resultados de la respuesta
        """
        response = await self.defense_orchestrator.respond_to_threat(threat)
        self.threats.append(threat)
        return response.to_dict()
    
    async def get_operations(self) -> List[Dict]:
        """Obtiene todas las operaciones ejecutadas"""
        return self.operations
    
    async def get_predictions(self) -> List[Dict]:
        """Obtiene todas las predicciones"""
        return self.predictions
    
    async def get_threats(self) -> List[Dict]:
        """Obtiene todas las amenazas detectadas"""
        return self.threats
    
    async def get_memory_stats(self) -> Dict:
        """Obtiene estadísticas de la memoria"""
        return await self.memory.get_stats()
    
    async def get_knowledge_stats(self) -> Dict:
        """Obtiene estadísticas de la base de conocimiento"""
        return await self.knowledge_base.get_knowledge_stats()
    
    async def event_stream(self):
        """Generador de eventos en tiempo real"""
        # Eventos de operaciones
        for operation in self.operations:
            yield {
                "type": "operation",
                "data": operation
            }
        
        # Eventos de predicciones
        for prediction in self.predictions:
            yield {
                "type": "prediction",
                "data": prediction
            }
        
        # Eventos de amenazas
        for threat in self.threats:
            yield {
                "type": "threat",
                "data": threat
            }
    
    async def get_status(self) -> Dict:
        """Obtiene el estado actual del sistema"""
        try:
            memory_stats = await self.memory.get_stats()
        except Exception as e:
            print(f"[ARTO] Warning: memory.get_stats() failed: {e}")
            memory_stats = {"error": str(e)}
        try:
            knowledge_stats = await self.knowledge_base.get_knowledge_stats()
        except Exception as e:
            print(f"[ARTO] Warning: knowledge_base.get_knowledge_stats() failed: {e}")
            knowledge_stats = {"error": str(e)}
        return {
            "running": self.running,
            "operations_count": len(self.operations),
            "predictions_count": len(self.predictions),
            "threats_count": len(self.threats),
            "memory_stats": memory_stats,
            "knowledge_stats": knowledge_stats
        }


# Instancia global
arto = ARTO()

# Función para iniciar ARTO
async def start_arto():
    """Inicia el sistema ARTO"""
    await arto.start()
    return arto

# Función para detener ARTO
async def stop_arto():
    """Detiene el sistema ARTO"""
    await arto.stop()
