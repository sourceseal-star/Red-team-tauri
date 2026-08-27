"""
Knowledge Base - Base de Conocimiento
======================================
Almacena conocimiento aprendido de operaciones anteriores.
"""

import asyncio
import datetime
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import os


class KnowledgeBase:
    """Base de Conocimiento Persistente"""
    
    def __init__(self, db_path: str = "arto_knowledge.json"):
        self.db_path = db_path
        self.knowledge: Dict = {
            "observations": [],
            "patterns": {},
            "threats": [],
            "vulnerabilities": [],
            "recommendations": [],
            "metadata": {
                "created": datetime.datetime.now().isoformat(),
                "updated": datetime.datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        
    async def initialize(self):
        """Inicializa la base de conocimiento"""
        print("📚 Inicializando base de conocimiento...")
        
        # Cargar conocimiento existente
        await self._load_knowledge()
        
        print("✅ Base de conocimiento lista")
    
    async def _load_knowledge(self):
        """Carga el conocimiento desde el archivo"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.knowledge = json.load(f)
                print(f"📖 Conocimiento cargado desde {self.db_path}")
            except Exception as e:
                print(f"⚠️ Error cargando conocimiento: {e}")
        else:
            print(f"📝 Creando nueva base de conocimiento en {self.db_path}")
    
    async def save(self):
        """Guarda el conocimiento en el archivo"""
        self.knowledge["metadata"]["updated"] = datetime.datetime.now().isoformat()
        
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge, f, indent=2, ensure_ascii=False)
            print(f"💾 Conocimiento guardado en {self.db_path}")
        except Exception as e:
            print(f"⚠️ Error guardando conocimiento: {e}")
    
    async def add_observation(self, observation: Dict):
        """Agrega una observación a la base de conocimiento"""
        self.knowledge["observations"].append(observation)
        
        # Limitar tamaño
        if len(self.knowledge["observations"]) > 1000:
            self.knowledge["observations"] = self.knowledge["observations"][-1000:]
        
        # Extraer patrones
        await self._extract_patterns_from_observation(observation)
        
        # Guardar
        await self.save()
    
    async def _extract_patterns_from_observation(self, observation: Dict):
        """Extrae patrones de una observación"""
        obs_type = observation.get("type", "unknown")
        target = observation.get("target", "unknown")
        data = observation.get("data", {})
        result = observation.get("result", {})
        action = observation.get("action", "none")
        
        # Patrones por tipo
        if obs_type not in self.knowledge["patterns"]:
            self.knowledge["patterns"][obs_type] = {
                "count": 0,
                "targets": {},
                "actions": {},
                "common_data": {},
                "common_results": {}
            }
        
        pattern = self.knowledge["patterns"][obs_type]
        pattern["count"] += 1
        pattern["targets"][target] = pattern["targets"].get(target, 0) + 1
        pattern["actions"][action] = pattern["actions"].get(action, 0) + 1
        
        # Datos comunes
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                pattern["common_data"][key] = pattern["common_data"].get(key, 0) + 1
        
        # Resultados comunes
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)):
                pattern["common_results"][key] = pattern["common_results"].get(key, 0) + 1
    
    async def add_threat(self, threat: Dict):
        """Agrega una amenaza a la base de conocimiento"""
        # Verificar si ya existe
        threat_id = threat.get("id", threat.get("threat_id"))
        if threat_id:
            existing = next((t for t in self.knowledge["threats"] if t.get("id") == threat_id), None)
            if existing:
                existing.update(threat)
                await self.save()
                return
        
        self.knowledge["threats"].append(threat)
        
        # Limitar tamaño
        if len(self.knowledge["threats"]) > 500:
            self.knowledge["threats"] = self.knowledge["threats"][-500:]
        
        await self.save()
    
    async def add_vulnerability(self, vulnerability: Dict):
        """Agrega una vulnerabilidad a la base de conocimiento"""
        vuln_id = vulnerability.get("id")
        if vuln_id:
            existing = next((v for v in self.knowledge["vulnerabilities"] if v.get("id") == vuln_id), None)
            if existing:
                existing.update(vulnerability)
                await self.save()
                return
        
        self.knowledge["vulnerabilities"].append(vulnerability)
        
        # Limitar tamaño
        if len(self.knowledge["vulnerabilities"]) > 500:
            self.knowledge["vulnerabilities"] = self.knowledge["vulnerabilities"][-500:]
        
        await self.save()
    
    async def add_recommendation(self, recommendation: str, context: Dict = None):
        """Agrega una recomendación a la base de conocimiento"""
        rec = {
            "recommendation": recommendation,
            "context": context or {},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Verificar si ya existe
        existing = next((r for r in self.knowledge["recommendations"] 
                        if r.get("recommendation") == recommendation), None)
        if existing:
            existing["context"] = rec["context"]
            existing["timestamp"] = rec["timestamp"]
        else:
            self.knowledge["recommendations"].append(rec)
        
        # Limitar tamaño
        if len(self.knowledge["recommendations"]) > 200:
            self.knowledge["recommendations"] = self.knowledge["recommendations"][-200:]
        
        await self.save()
    
    async def search_observations(self, query: Dict) -> List[Dict]:
        """Busca observaciones que coincidan con la consulta"""
        results = []
        
        for obs in self.knowledge["observations"]:
            match = True
            for key, value in query.items():
                if obs.get(key) != value:
                    match = False
                    break
            
            if match:
                results.append(obs)
        
        return results
    
    async def search_patterns(self, obs_type: Optional[str] = None) -> Dict:
        """Busca patrones por tipo"""
        if obs_type:
            return self.knowledge["patterns"].get(obs_type, {})
        return self.knowledge["patterns"]
    
    async def search_threats(self, query: Dict) -> List[Dict]:
        """Busca amenazas que coincidan con la consulta"""
        results = []
        
        for threat in self.knowledge["threats"]:
            match = True
            for key, value in query.items():
                if threat.get(key) != value:
                    match = False
                    break
            
            if match:
                results.append(threat)
        
        return results
    
    async def search_vulnerabilities(self, query: Dict) -> List[Dict]:
        """Busca vulnerabilidades que coincidan con la consulta"""
        results = []
        
        for vuln in self.knowledge["vulnerabilities"]:
            match = True
            for key, value in query.items():
                if vuln.get(key) != value:
                    match = False
                    break
            
            if match:
                results.append(vuln)
        
        return results
    
    async def get_knowledge_stats(self) -> Dict:
        """Obtiene estadísticas de la base de conocimiento"""
        return {
            "observation_count": len(self.knowledge["observations"]),
            "pattern_count": len(self.knowledge["patterns"]),
            "threat_count": len(self.knowledge["threats"]),
            "vulnerability_count": len(self.knowledge["vulnerabilities"]),
            "recommendation_count": len(self.knowledge["recommendations"]),
            "last_updated": self.knowledge["metadata"].get("updated", "Nunca"),
            "version": self.knowledge["metadata"].get("version", "1.0")
        }
    
    async def get_pattern_stats(self, obs_type: Optional[str] = None) -> Dict:
        """Obtiene estadísticas de patrones"""
        if obs_type:
            pattern = self.knowledge["patterns"].get(obs_type, {})
            return {
                "obs_type": obs_type,
                **pattern
            }
        
        stats = {}
        for obs_type, pattern in self.knowledge["patterns"].items():
            stats[obs_type] = {
                "count": pattern.get("count", 0),
                "target_count": len(pattern.get("targets", {})),
                "action_count": len(pattern.get("actions", {}))
            }
        
        return stats
    
    async def clear_all(self):
        """Borra todo el conocimiento"""
        self.knowledge = {
            "observations": [],
            "patterns": {},
            "threats": [],
            "vulnerabilities": [],
            "recommendations": [],
            "metadata": {
                "created": datetime.datetime.now().isoformat(),
                "updated": datetime.datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        
        await self.save()
        
        return {"status": "success", "message": "Base de conocimiento borrada"}
