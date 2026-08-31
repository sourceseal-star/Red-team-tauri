#!/usr/bin/env python3
"""
Conector de Playbooks -> OSIRIS v2.0
Ejecución y reporte de playbooks de seguridad
"""

import asyncio
import json
import os
import sys
import logging
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import sqlite3

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [PlaybookConnector] %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser('~/playbook_connector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PlaybookConnector")

class PlaybookStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class PlaybookConfig:
    id: str
    name: str
    description: str
    command: str
    args: List[str] = None
    timeout: int = 300  # 5 minutos
    working_directory: str = "/tmp"
    env: Dict[str, str] = None
    triggers: List[str] = None  # Tipos de eventos que activan este playbook
    
    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}
        if self.triggers is None:
            self.triggers = []

@dataclass
class PlaybookExecution:
    id: str
    playbook_id: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    output: str = ""
    error: str = ""
    exit_code: int = 0
    trigger_event: Optional[Dict] = None
    results: Dict = None

class PlaybookConnector:
    """Conector para ejecución de playbooks"""
    
    def __init__(self, config_path: str = "configs/playbooks_config.json",
                 osiris_url: str = "http://localhost:3000/api",
                 cache_path: str = "/home/user/playbook_cache.db"):
        self.config_path = config_path
        self.osiris_url = osiris_url
        self.cache_path = cache_path
        self.playbooks: Dict[str, PlaybookConfig] = {}
        self._running_executions: Dict[str, PlaybookExecution] = {}
        self._running = False
        self._load_config()
        self._init_cache()
    
    def _load_config(self):
        """Cargar configuración de playbooks"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for pb_config in config.get("playbooks", []):
                playbook = PlaybookConfig(
                    id=pb_config["id"],
                    name=pb_config["name"],
                    description=pb_config.get("description", ""),
                    command=pb_config["command"],
                    args=pb_config.get("args", []),
                    timeout=pb_config.get("timeout", 300),
                    working_directory=pb_config.get("working_directory", "/tmp"),
                    env=pb_config.get("env", {}),
                    triggers=pb_config.get("triggers", [])
                )
                self.playbooks[playbook.id] = playbook
                logger.info(f"📋 Playbook cargado: {playbook.name} ({playbook.id})")
                
        except FileNotFoundError:
            logger.error(f"❌ Configuración no encontrada: {self.config_path}")
        except json.JSONDecodeError:
            logger.error(f"❌ Configuración inválida: {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Error cargando configuración: {e}")
    
    def _init_cache(self):
        """Inicializar base de datos de caché"""
        conn = sqlite3.connect(self.cache_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS playbook_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT UNIQUE NOT NULL,
                playbook_id TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                output TEXT,
                error TEXT,
                exit_code INTEGER DEFAULT 0,
                trigger_event_json TEXT,
                results_json TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def start(self):
        """Iniciar el conector"""
        self._running = True
        logger.info("🚀 Conector de Playbooks iniciado")
        
        # Procesar ejecuciones pendientes
        await self._process_pending_executions()
        
        # Mantener vivo
        while self._running:
            await asyncio.sleep(60)
    
    async def handle_event(self, event: Dict) -> bool:
        """Manejar un evento y ejecutar playbooks correspondientes"""
        event_type = event.get("type", "")
        
        # Buscar playbooks que coincidan con el trigger
        matching_playbooks = []
        for pb_id, playbook in self.playbooks.items():
            if event_type in playbook.triggers or "*" in playbook.triggers:
                matching_playbooks.append(playbook)
        
        if not matching_playbooks:
            logger.debug(f"🔍 No hay playbooks para evento: {event_type}")
            return False
        
        logger.info(f"🎯 Evento {event_type} coincide con {len(matching_playbooks)} playbook(s)")
        
        # Ejecutar cada playbook coincidente
        for playbook in matching_playbooks:
            execution_id = f"{playbook.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await self._execute_playbook(playbook, event, execution_id)
        
        return True
    
    async def _execute_playbook(self, playbook: PlaybookConfig, 
                               trigger_event: Dict, execution_id: str):
        """Ejecutar un playbook"""
        logger.info(f"▶️  Ejecutando playbook: {playbook.name} ({execution_id})")
        
        # Crear objeto de ejecución
        execution = PlaybookExecution(
            id=execution_id,
            playbook_id=playbook.id,
            status=PlaybookStatus.RUNNING.value,
            start_time=datetime.utcnow().isoformat(),
            trigger_event=trigger_event
        )
        
        self._running_executions[execution_id] = execution
        
        # Guardar en caché
        self._save_execution(execution)
        
        # Enviar evento de inicio a OSIRIS
        await self._send_playbook_event(execution, "started")
        
        try:
            # Ejecutar comando
            cmd = [playbook.command] + playbook.args
            
            # Preparar entorno
            env = os.environ.copy()
            env.update(playbook.env)
            
            # Ejecutar en subprocess
            process = subprocess.Popen(
                cmd,
                cwd=playbook.working_directory,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Esperar con timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=playbook.timeout
                )
                
                execution.end_time = datetime.utcnow().isoformat()
                execution.output = stdout
                execution.error = stderr
                execution.exit_code = process.returncode
                execution.status = PlaybookStatus.COMPLETED.value if process.returncode == 0 else PlaybookStatus.FAILED.value
                
            except asyncio.TimeoutError:
                process.kill()
                execution.end_time = datetime.utcnow().isoformat()
                execution.status = PlaybookStatus.TIMEOUT.value
                execution.error = f"Timeout después de {playbook.timeout} segundos"
        
        except Exception as e:
            execution.end_time = datetime.utcnow().isoformat()
            execution.status = PlaybookStatus.FAILED.value
            execution.error = str(e)
        
        finally:
            # Actualizar ejecución
            self._update_execution(execution)
            
            # Enviar evento de finalización a OSIRIS
            await self._send_playbook_event(execution, "completed")
            
            # Remover de ejecuciones en curso
            self._running_executions.pop(execution_id, None)
            
            logger.info(f"✅ Playbook {playbook.name} finalizado: {execution.status}")
    
    async def _send_playbook_event(self, execution: PlaybookExecution, event_type: str):
        """Enviar evento de playbook a OSIRIS"""
        playbook = self.playbooks.get(execution.playbook_id)
        if not playbook:
            return
        
        # Preparar payload
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "playbook_id": execution.playbook_id,
            "playbook_name": playbook.name,
            "execution_id": execution.id,
            "status": execution.status,
            "message": f"Playbook {playbook.name} {event_type}",
            "details": {
                "start_time": execution.start_time,
                "end_time": execution.end_time or "",
                "exit_code": execution.exit_code,
                "output": execution.output[:500] + "..." if len(execution.output) > 500 else execution.output,
                "error": execution.error[:500] + "..." if len(execution.error) > 500 else execution.error,
                "trigger": execution.trigger_event or {}
            }
        }
        
        # Enviar a OSIRIS
        try:
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.osiris_url}/events/incident"
                
                async with session.post(endpoint, json=payload, timeout=10) as resp:
                    if resp.status in [200, 201]:
                        logger.debug(f"✅ Evento de playbook enviado: {execution.id}")
                    else:
                        logger.warning(f"⚠️  Error enviando playbook: {resp.status}")
                        # Guardar en caché
                        self._save_to_cache(execution)
        except Exception as e:
            logger.error(f"❌ Error enviando evento de playbook: {e}")
            self._save_to_cache(execution)
    
    def _save_execution(self, execution: PlaybookExecution):
        """Guardar ejecución en base de datos"""
        try:
            conn = sqlite3.connect(self.cache_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT OR REPLACE INTO playbook_executions 
                (execution_id, playbook_id, status, start_time, end_time, output, error, exit_code, trigger_event_json, results_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                execution.id,
                execution.playbook_id,
                execution.status,
                execution.start_time,
                execution.end_time,
                execution.output,
                execution.error,
                execution.exit_code,
                json.dumps(execution.trigger_event or {}),
                json.dumps(execution.results or {})
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando ejecución: {e}")
    
    def _update_execution(self, execution: PlaybookExecution):
        """Actualizar ejecución en base de datos"""
        self._save_execution(execution)
    
    def _save_to_cache(self, execution: PlaybookExecution):
        """Guardar ejecución en caché para reenvío"""
        # Marcar como pendiente
        try:
            conn = sqlite3.connect(self.cache_path)
            c = conn.cursor()
            
            c.execute('''
                UPDATE playbook_executions 
                SET status = ? 
                WHERE execution_id = ?
            ''', (f"{execution.status}_pending", execution.id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando en caché: {e}")
    
    async def _process_pending_executions(self):
        """Procesar ejecuciones pendientes"""
        try:
            conn = sqlite3.connect(self.cache_path)
            c = conn.cursor()
            
            c.execute("SELECT execution_id FROM playbook_executions WHERE status LIKE '%_pending'")
            rows = c.fetchall()
            conn.close()
            
            for row in rows:
                execution_id = row[0]
                # Recuperar ejecución
                execution = self._load_execution(execution_id)
                if execution:
                    # Reenviar evento
                    await self._send_playbook_event(execution, "retry")
                    
        except Exception as e:
            logger.error(f"Error procesando pendientes: {e}")
    
    def _load_execution(self, execution_id: str) -> Optional[PlaybookExecution]:
        """Cargar ejecución desde base de datos"""
        try:
            conn = sqlite3.connect(self.cache_path)
            c = conn.cursor()
            
            c.execute("SELECT * FROM playbook_executions WHERE execution_id = ?", (execution_id,))
            row = c.fetchone()
            conn.close()
            
            if row:
                return PlaybookExecution(
                    id=row[1],
                    playbook_id=row[2],
                    status=row[3],
                    start_time=row[4],
                    end_time=row[5],
                    output=row[6],
                    error=row[7],
                    exit_code=row[8],
                    trigger_event=json.loads(row[9]) if row[9] else None,
                    results=json.loads(row[10]) if row[10] else None
                )
            return None
        except Exception as e:
            logger.error(f"Error cargando ejecución: {e}")
            return None
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict]:
        """Obtener estado de una ejecución"""
        execution = self._load_execution(execution_id)
        if execution:
            return asdict(execution)
        return None
    
    def list_executions(self, limit: int = 100) -> List[Dict]:
        """Listar ejecuciones recientes"""
        try:
            conn = sqlite3.connect(self.cache_path)
            c = conn.cursor()
            
            c.execute("SELECT * FROM playbook_executions ORDER BY start_time DESC LIMIT ?", (limit,))
            rows = c.fetchall()
            conn.close()
            
            executions = []
            for row in rows:
                executions.append({
                    "id": row[1],
                    "playbook_id": row[2],
                    "status": row[3],
                    "start_time": row[4],
                    "end_time": row[5],
                    "output": row[6][:200] + "..." if len(row[6]) > 200 else row[6],
                    "error": row[7][:200] + "..." if len(row[7]) > 200 else row[7],
                    "exit_code": row[8]
                })
            
            return executions
        except Exception as e:
            logger.error(f"Error listando ejecuciones: {e}")
            return []
    
    def stop(self):
        """Detener el conector"""
        self._running = False
        logger.info("✅ Conector de Playbooks detenido")

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Conector de Playbooks -> OSIRIS")
    parser.add_argument("--config", default="configs/playbooks_config.json", help="Archivo de configuración")
    parser.add_argument("--osiris-url", default="http://localhost:3000/api", help="URL de OSIRIS")
    parser.add_argument("--cache", default="/home/user/playbook_cache.db", help="Ruta de la caché")
    args = parser.parse_args()
    
    connector = PlaybookConnector(args.config, args.osiris_url, args.cache)
    
    try:
        await connector.start()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
    finally:
        connector.stop()

if __name__ == "__main__":
    asyncio.run(main())
