"""
Memory Storage - Almacenamiento en SQLite
=========================================
Almacena operaciones, decisiones, predicciones y otros datos.
"""

import asyncio
import datetime
import sqlite3
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import os


class MemoryStorage:
    """Almacenamiento persistente en SQLite"""
    
    def __init__(self, db_path: str = "arto_memory.db"):
        self.db_path = db_path
        self.conn = None
        self.initialized = False
        
    async def initialize(self):
        """Inicializa la base de datos"""
        print("💾 Inicializando almacenamiento de memoria...")
        
        # Crear directorio si no existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Conectar a la base de datos
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Crear tablas
        await self._create_tables()
        
        self.initialized = True
        print("✅ Almacenamiento de memoria listo")
    
    async def _create_tables(self):
        """Crea las tablas necesarias"""
        cursor = self.conn.cursor()
        
        # Tabla de operaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                target TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Tabla de decisiones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                confidence REAL NOT NULL,
                reason TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                context TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Tabla de predicciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                target TEXT NOT NULL,
                description TEXT NOT NULL,
                probability REAL NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                time_horizon INTEGER NOT NULL,
                confidence REAL NOT NULL,
                mitigation TEXT,
                metadata TEXT
            )
        """)
        
        # Tabla de acciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Tabla de observaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                target TEXT NOT NULL,
                data TEXT NOT NULL,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Tabla de simulaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                target TEXT NOT NULL,
                execution TEXT NOT NULL,
                results TEXT NOT NULL,
                findings TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration REAL NOT NULL,
                success INTEGER NOT NULL
            )
        """)
        
        # Tabla de respuestas de defensa
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defense_responses (
                response_id TEXT PRIMARY KEY,
                threat_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT
            )
        """)
        
        # Tabla de informes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                target TEXT NOT NULL,
                summary TEXT NOT NULL,
                findings TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                risk_score REAL NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # Tabla de alertas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                target TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL
            )
        """)
        
        # Tabla de logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                target TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL
            )
        """)
        
        # Tabla de patrones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                obs_type TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        
        # Tabla de feedback de decisiones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_feedback (
                action TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
    
    async def save(self):
        """Guarda todos los cambios"""
        if self.conn:
            self.conn.commit()
    
    async def close(self):
        """Cierra la conexión"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    # Métodos de almacenamiento
    
    async def store_operation(self, operation: Dict):
        """Almacena una operación"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO operations (id, type, target, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            operation.get("id"),
            operation.get("type"),
            operation.get("target"),
            json.dumps(operation),
            operation.get("timestamp")
        ))
        self.conn.commit()
    
    async def store_decision(self, decision: Dict):
        """Almacena una decisión"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO decisions 
            (decision_id, action, confidence, reason, risk_level, context, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.get("decision_id"),
            decision.get("action"),
            decision.get("confidence", 0.0),
            decision.get("reason", ""),
            decision.get("risk_level", "info"),
            json.dumps(decision.get("context", {})),
            decision.get("timestamp"),
            json.dumps(decision.get("metadata", {}))
        ))
        self.conn.commit()
    
    async def store_prediction(self, prediction: Dict):
        """Almacena una predicción"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO predictions 
            (prediction_id, type, target, description, probability, severity, 
             timestamp, time_horizon, confidence, mitigation, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction.get("prediction_id"),
            prediction.get("type"),
            prediction.get("target"),
            prediction.get("description", ""),
            prediction.get("probability", 0.0),
            prediction.get("severity", "medium"),
            prediction.get("timestamp"),
            prediction.get("time_horizon", 24),
            prediction.get("confidence", 0.0),
            json.dumps(prediction.get("mitigation", {})),
            json.dumps(prediction.get("metadata", {}))
        ))
        self.conn.commit()
    
    async def store_action(self, action: Dict):
        """Almacena una acción"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO actions 
            (action_id, action_type, target, status, message, data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            action.get("action_id"),
            action.get("action_type"),
            action.get("target"),
            action.get("status"),
            action.get("message", ""),
            json.dumps(action.get("data", {})),
            action.get("timestamp")
        ))
        self.conn.commit()
    
    async def store_observation(self, observation: Dict):
        """Almacena una observación"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO observations 
            (observation_id, type, target, data, action, result, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            observation.get("observation_id"),
            observation.get("type"),
            observation.get("target"),
            json.dumps(observation.get("data", {})),
            observation.get("action", ""),
            json.dumps(observation.get("result", {})),
            observation.get("timestamp"),
            json.dumps(observation.get("metadata", {}))
        ))
        self.conn.commit()
    
    async def store_simulation(self, simulation: Dict):
        """Almacena una simulación"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO simulations 
            (simulation_id, template_name, target, execution, results, findings, 
             recommendations, timestamp, duration, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            simulation.get("simulation_id"),
            simulation.get("template_name"),
            simulation.get("target"),
            json.dumps(simulation.get("execution", {})),
            json.dumps(simulation.get("results", {})),
            json.dumps(simulation.get("findings", [])),
            json.dumps(simulation.get("recommendations", [])),
            simulation.get("timestamp"),
            simulation.get("duration", 0.0),
            1 if simulation.get("success") else 0
        ))
        self.conn.commit()
    
    async def store_defense_response(self, response: Dict):
        """Almacena una respuesta de defensa"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO defense_responses 
            (response_id, threat_id, action, target, status, message, severity, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.get("response_id"),
            response.get("threat_id"),
            response.get("action"),
            response.get("target"),
            response.get("status"),
            response.get("message", ""),
            response.get("severity", "medium"),
            response.get("timestamp"),
            json.dumps(response.get("details", {}))
        ))
        self.conn.commit()
    
    async def store_report(self, report: Dict):
        """Almacena un informe"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO reports 
            (report_id, type, title, target, summary, findings, recommendations, 
             risk_score, severity, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.get("report_id"),
            report.get("type"),
            report.get("title"),
            report.get("target"),
            report.get("summary", ""),
            json.dumps(report.get("findings", [])),
            json.dumps(report.get("recommendations", [])),
            report.get("risk_score", 0.0),
            report.get("severity", "medium"),
            report.get("timestamp"),
            json.dumps(report.get("metadata", {}))
        ))
        self.conn.commit()
    
    async def store_alert(self, alert: Dict):
        """Almacena una alerta"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO alerts (id, target, message, severity, timestamp, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            alert.get("id"),
            alert.get("target"),
            alert.get("message"),
            alert.get("severity", "medium"),
            alert.get("timestamp"),
            alert.get("type", "alert")
        ))
        self.conn.commit()
    
    async def store_log(self, log: Dict):
        """Almacena un registro"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO logs (id, target, message, timestamp, type)
            VALUES (?, ?, ?, ?, ?)
        """, (
            log.get("id"),
            log.get("target"),
            log.get("message"),
            log.get("timestamp"),
            log.get("type", "log")
        ))
        self.conn.commit()
    
    # Métodos de carga
    
    async def load_operations(self, limit: int = 100) -> List[Dict]:
        """Carga operaciones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT data FROM operations 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        return [json.loads(row["data"]) for row in cursor.fetchall()]
    
    async def load_decisions(self, limit: int = 100) -> List[Dict]:
        """Carga decisiones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM decisions 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    async def load_predictions(self, limit: int = 100) -> List[Dict]:
        """Carga predicciones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM predictions 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    async def load_observations(self, limit: int = 100) -> List[Dict]:
        """Carga observaciones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM observations 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            obs = dict(row)
            obs["data"] = json.loads(obs["data"]) if obs["data"] else {}
            obs["result"] = json.loads(obs["result"]) if obs["result"] else {}
            obs["metadata"] = json.loads(obs["metadata"]) if obs["metadata"] else {}
            results.append(obs)
        
        return results
    
    async def load_patterns(self) -> Dict:
        """Carga patrones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM patterns")
        
        results = {}
        for row in cursor.fetchall():
            results[row["obs_type"]] = json.loads(row["data"])
        
        return results
    
    async def load_decision_feedback(self) -> Dict:
        """Carga feedback de decisiones"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM decision_feedback")
        
        results = {}
        for row in cursor.fetchall():
            results[row["action"]] = json.loads(row["data"])
        
        return results
    
    # Métodos de estadísticas
    
    async def get_stats(self) -> Dict:
        """Obtiene estadísticas de la memoria"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        
        # Contar registros en cada tabla
        tables = ["operations", "decisions", "predictions", "actions", "observations",
                  "simulations", "defense_responses", "reports", "alerts", "logs"]
        
        stats = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[f"{table}_count"] = cursor.fetchone()[0]
        
        # Tamaño de la base de datos
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        
        return {
            "database_size_bytes": db_size,
            "database_path": self.db_path,
            **stats
        }
    
    async def clear_all(self):
        """Borra todos los datos"""
        if not self.initialized:
            await self.initialize()
        
        cursor = self.conn.cursor()
        
        tables = ["operations", "decisions", "predictions", "actions", "observations",
                  "simulations", "defense_responses", "reports", "alerts", "logs",
                  "patterns", "decision_feedback"]
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
        
        self.conn.commit()
        
        return {"status": "success", "message": "Todos los datos borrados"}
