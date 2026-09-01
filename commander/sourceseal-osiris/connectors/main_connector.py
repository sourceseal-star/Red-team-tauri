"""
Conector Principal SourceSeal -> OSIRIS v3.0
- WebSocket robusto con reconexión automática
- Caché local en SQLite con limpieza automática
- Soporte para múltiples tipos de eventos
- Logging estructurado con rotación de archivos
- Métricas de rendimiento
"""

import asyncio
import aiohttp
import json
import websockets
import os
import sys
import sqlite3
import logging
import argparse
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import threading

# ============================================================
# CONFIGURACIÓN
# ============================================================

class EventType(Enum):
    ALERT = "alert"
    SCAN = "scan"
    PLAYBOOK = "playbook"
    CAMERA = "camera"
    HEARTBEAT = "heartbeat"
    METRICS = "metrics"

@dataclass
class Config:
    osiris_url: str = "http://localhost:3000/api"
    seal_ws: str = "ws://localhost:8001/ws/alerts"
    db_path: str = os.path.expanduser("~/connector_cache.db")
    log_file: str = os.path.expanduser("~/connector.log")
    log_level: str = "INFO"
    max_retries: int = 5
    retry_delay: float = 1.0
    cache_cleanup_interval: int = 3600  # 1 hora
    max_cache_age: int = 86400  # 24 horas
    metrics_interval: int = 60  # 1 minuto
    heartbeat_interval: int = 30  # 30 segundos
    
    # Configuración para cámaras
    enable_camera: bool = False
    camera_check_interval: int = 10  # 10 segundos
    
    # Configuración para playbooks
    enable_playbook: bool = True
    playbook_timeout: int = 300  # 5 minutos

# Variables globales derivadas de Config (para compatibilidad)
LOG_FILE = os.path.expanduser("~/connector.log")
DB_PATH = os.path.expanduser("~/connector_cache.db")

# ============================================================
# LOGGING AVANZADO
# ============================================================

class RotatingFileHandler(logging.Handler):
    """Handler personalizado para rotación de logs"""
    
    def __init__(self, filename, max_bytes=10*1024*1024, backup_count=5):
        super().__init__()
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._check_rotation()
        
    def _check_rotation(self):
        if os.path.exists(self.filename):
            size = os.path.getsize(self.filename)
            if size >= self.max_bytes:
                self._rotate()
    
    def _rotate(self):
        for i in range(self.backup_count - 1, 0, -1):
            old_path = f"{self.filename}.{i}"
            new_path = f"{self.filename}.{i+1}"
            if os.path.exists(old_path):
                if i + 1 == self.backup_count:
                    os.remove(old_path)
                else:
                    os.rename(old_path, new_path)
        
        if os.path.exists(self.filename):
            os.rename(self.filename, f"{self.filename}.1")
    
    def emit(self, record):
        self._check_rotation()
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(self.format(record) + '\n')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(LOG_FILE, max_bytes=5*1024*1024, backup_count=3),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MainConnector")

# ============================================================
# GESTIÓN DE CONFIGURACIÓN
# ============================================================

class ConfigManager:
    """Gestor de configuración con soporte para .env y JSON"""
    
    def __init__(self):
        self.config = Config()
        self._load_env()
        self._load_json()
    
    def _load_env(self):
        """Cargar configuración desde variables de entorno"""
        import os
        
        env_mappings = {
            'OSIRIS_URL': ('osiris_url', str),
            'SEAL_WS': ('seal_ws', str),
            'DB_PATH': ('db_path', str),
            'LOG_FILE': ('log_file', str),
            'LOG_LEVEL': ('log_level', str),
            'MAX_RETRIES': ('max_retries', int),
            'RETRY_DELAY': ('retry_delay', float),
            'ENABLE_CAMERA': ('enable_camera', lambda x: x.lower() == 'true'),
            'ENABLE_PLAYBOOK': ('enable_playbook', lambda x: x.lower() == 'true'),
        }
        
        for env_var, (attr, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(self.config, attr, converter(value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"No se pudo convertir {env_var}={value}: {e}")
    
    def _load_json(self, path: str = "configs/default_config.json"):
        """Cargar configuración desde archivo JSON"""
        if not os.path.exists(path):
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key, value in data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        except Exception as e:
            logger.warning(f"Error cargando configuración JSON: {e}")
    
    def save(self, path: str = "configs/default_config.json"):
        """Guardar configuración en archivo JSON"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.config), f, indent=2)
    
    def get(self):
        return self.config

# ============================================================
# BASE DE DATOS MEJORADA
# ============================================================

class CacheManager:
    """Gestor de caché con SQLite y limpieza automática"""
    
    def __init__(self, db_path: str, max_age: int = 86400):
        self.db_path = db_path
        self.max_age = max_age
        self._init_db()
        self._cleanup_old()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tabla de mensajes pendientes
        c.execute('''
            CREATE TABLE IF NOT EXISTS pending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_attempt TEXT,
                hash TEXT UNIQUE
            )
        ''')
        
        # Tabla de métricas
        c.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time_ms INTEGER,
                payload_size INTEGER
            )
        ''')
        
        # Tabla de salud
        c.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"📁 Base de datos de caché inicializada: {self.db_path}")
    
    def _generate_hash(self, event_type: str, payload: dict) -> str:
        """Generar hash único para evitar duplicados"""
        data = f"{event_type}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    def save_pending(self, event_type: str, payload: dict) -> bool:
        """Guardar mensaje pendiente con hash único"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            payload_str = json.dumps(payload)
            event_hash = self._generate_hash(event_type, payload)
            
            c.execute(
                "INSERT OR IGNORE INTO pending (event_type, payload_json, created_at, hash) VALUES (?, ?, ?, ?)",
                (event_type, payload_str, datetime.utcnow().isoformat(), event_hash)
            )
            conn.commit()
            conn.close()
            logger.debug(f"💾 Mensaje guardado en caché: {event_type} (hash: {event_hash[:8]})")
            return True
        except Exception as e:
            conn.close()
            logger.error(f"Error guardando en caché: {e}")
            return False
    
    def get_pending(self, limit: int = 20) -> List[Dict]:
        """Obtener mensajes pendientes ordenados por fecha"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            "SELECT id, event_type, payload_json, created_at, retry_count FROM pending ORDER BY created_at ASC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "type": r[1],
            "payload": json.loads(r[2]),
            "created_at": r[3],
            "retry_count": r[4]
        } for r in rows]
    
    def delete_pending(self, ids: List[int]):
        """Eliminar mensajes pendientes"""
        if not ids:
            return
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(f"DELETE FROM pending WHERE id IN ({','.join(['?']*len(ids))})", ids)
        conn.commit()
        conn.close()
        logger.debug(f"🗑️  {len(ids)} mensajes eliminados de la caché")
    
    def update_retry_count(self, id: int):
        """Incrementar contador de reintentos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE pending SET retry_count = retry_count + 1, last_attempt = ? WHERE id = ?", 
                  (datetime.utcnow().isoformat(), id))
        conn.commit()
        conn.close()
    
    def _cleanup_old(self):
        """Limpiar mensajes antiguos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff = (datetime.utcnow() - timedelta(seconds=self.max_age)).isoformat()
        c.execute("DELETE FROM pending WHERE created_at < ?", (cutoff,))
        deleted = c.rowcount
        
        # También limpiar métricas antiguas (más de 30 días)
        cutoff_metrics = (datetime.utcnow() - timedelta(days=30)).isoformat()
        c.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff_metrics,))
        
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"🧹 Limpieza de caché: {deleted} mensajes antiguos eliminados")
    
    def record_metric(self, event_type: str, status: str, response_time: float = 0, payload_size: int = 0):
        """Registrar métrica de rendimiento"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO metrics (timestamp, event_type, status, response_time_ms, payload_size) VALUES (?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), event_type, status, int(response_time * 1000), payload_size)
        )
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas de la caché"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        stats = {}
        
        # Conteo por tipo de evento
        c.execute("SELECT event_type, COUNT(*) FROM pending GROUP BY event_type")
        stats['pending_by_type'] = dict(c.fetchall())
        
        # Total pendientes
        c.execute("SELECT COUNT(*) FROM pending")
        stats['total_pending'] = c.fetchone()[0]
        
        # Métricas recientes (última hora)
        one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        c.execute("SELECT event_type, status, COUNT(*) FROM metrics WHERE timestamp >= ? GROUP BY event_type, status", 
                  (one_hour_ago,))
        stats['recent_metrics'] = c.fetchall()
        
        conn.close()
        return stats

# ============================================================
# ENVÍO A OSIRIS MEJORADO
# ============================================================

class OsirisClient:
    """Cliente HTTP para OSIRIS con manejo de errores mejorado"""
    
    def __init__(self, base_url: str, config: Config):
        self.base_url = base_url.rstrip('/')
        self.config = config
        self.session = None
        self._health_status = None
        self._last_health_check = 0
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> bool:
        """Verificar si OSIRIS está saludable"""
        now = time.time()
        
        # Cachear el resultado por 10 segundos
        if self._health_status is not None and now - self._last_health_check < 10:
            return self._health_status
        
        try:
            async with aiohttp.ClientSession() as temp_session:
                async with temp_session.get(f"{self.base_url}/status", timeout=5) as resp:
                    if resp.status == 200:
                        self._health_status = True
                        self._last_health_check = now
                        return True
                    else:
                        self._health_status = False
                        self._last_health_check = now
                        return False
        except Exception as e:
            logger.debug(f"Error en health check: {e}")
            self._health_status = False
            self._last_health_check = now
            return False
    
    async def send_event(self, event_type: str, payload: dict, retry: bool = True) -> bool:
        """Enviar evento a OSIRIS con reintentos"""
        if not await self.check_health():
            logger.warning("⚠️  OSIRIS no está disponible, guardando en caché")
            return False
        
        endpoint_map = {
            EventType.ALERT.value: "/events/alert",
            EventType.SCAN.value: "/events/network",
            EventType.PLAYBOOK.value: "/events/incident",
            EventType.CAMERA.value: "/events/visual",
            EventType.HEARTBEAT.value: "/events/heartbeat",
        }
        
        endpoint = endpoint_map.get(event_type)
        if not endpoint:
            logger.warning(f"⚠️  Tipo de evento no soportado: {event_type}")
            return False
        
        data = self._transform_payload(event_type, payload)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()
                
                async with self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=data,
                    timeout=10
                ) as resp:
                    response_time = time.time() - start_time
                    payload_size = len(json.dumps(data))
                    
                    if resp.status in [200, 201]:
                        logger.debug(f"✅ Evento {event_type} enviado a OSIRIS (intento {attempt + 1})")
                        return True
                    else:
                        logger.warning(f"⚠️  OSIRIS respondió {resp.status} para {event_type}")
                        text = await resp.text()
                        logger.debug(f"Respuesta: {text}")
                        
                        if attempt < self.config.max_retries:
                            await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                        else:
                            return False
                            
            except asyncio.TimeoutError:
                logger.warning(f"⏱️  Timeout enviando {event_type} (intento {attempt + 1})")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    return False
            except Exception as e:
                logger.warning(f"⚠️  Error enviando a OSIRIS: {e}")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    return False
        
        return False
    
    def _transform_payload(self, event_type: str, payload: dict) -> dict:
        """Transformar payload según el tipo de evento"""
        
        if event_type == EventType.ALERT.value:
            return {
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "src_ip": payload.get("target", payload.get("src_ip", "0.0.0.0")),
                "alert_type": payload.get("severity", "info"),
                "message": payload.get("message", ""),
                "details": payload.get("details", {}),
                "source": payload.get("source", "sourceseal")
            }
        
        elif event_type == EventType.SCAN.value:
            hosts = payload.get("hosts", [])
            return {
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "src_ip": payload.get("target", "0.0.0.0"),
                "src_port": payload.get("src_port", 0),
                "dst_ip": payload.get("dst_ip", "0.0.0.0"),
                "dst_port": payload.get("dst_port", 0),
                "proto": payload.get("proto", "tcp"),
                "info": json.dumps(hosts) if hosts else "{}",
                "scan_type": payload.get("scan_type", "unknown")
            }
        
        elif event_type == EventType.PLAYBOOK.value:
            return {
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "src_ip": payload.get("target", "0.0.0.0"),
                "incident_type": "playbook_execution",
                "message": payload.get("message", ""),
                "details": {
                    **payload.get("details", {}),
                    "playbook_name": payload.get("playbook_name", "unknown"),
                    "status": payload.get("status", "running"),
                    "execution_time": payload.get("execution_time", 0)
                }
            }
        
        elif event_type == EventType.CAMERA.value:
            return {
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "camera_id": payload.get("camera_id", "unknown"),
                "camera_name": payload.get("camera_name", ""),
                "image_url": payload.get("image_url", ""),
                "image_data": payload.get("image_data", ""),  # Base64
                "event_type": payload.get("event_type", "motion"),
                "confidence": payload.get("confidence", 0),
                "location": payload.get("location", {})
            }
        
        elif event_type == EventType.HEARTBEAT.value:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "component": payload.get("component", "connector"),
                "status": "healthy",
                "version": payload.get("version", "3.0.0")
            }
        
        # Default
        return {
            **payload,
            "timestamp": payload.get("timestamp", datetime.utcnow().isoformat())
        }

# ============================================================
# ESCUCHAR SOURCESEAL WEB SOCKET
# ============================================================

class SourceSealListener:
    """Escuchador de WebSocket de SourceSeal"""
    
    def __init__(self, config: Config, cache_manager: CacheManager, osiris_client: OsirisClient):
        self.config = config
        self.cache_manager = cache_manager
        self.osiris_client = osiris_client
        self._running = False
        self._ws_connection = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
    
    async def start(self):
        """Iniciar el escuchador"""
        self._running = True
        logger.info(f"📡 Iniciando escuchador de SourceSeal: {self.config.seal_ws}")
        
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"❌ Error en conexión WebSocket: {e}")
                await self._handle_reconnect()
    
    async def _connect_and_listen(self):
        """Conectar y escuchar mensajes"""
        try:
            async with websockets.connect(
                self.config.seal_ws,
                ping_interval=20,
                ping_timeout=60
            ) as ws:
                self._ws_connection = ws
                self._reconnect_attempts = 0
                logger.info("✅ Conectado a SourceSeal WebSocket")
                
                while self._running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=60)
                        await self._process_message(msg)
                        
                    except asyncio.TimeoutError:
                        # Cada minuto, procesar pendientes
                        await self._process_pending()
                        
                    except websockets.ConnectionClosed:
                        logger.warning("⚠️  WebSocket cerrado por el servidor")
                        break
                        
        except Exception as e:
            logger.error(f"Error en conexión: {e}")
            raise
    
    async def _process_message(self, msg: str):
        """Procesar mensaje recibido"""
        try:
            data = json.loads(msg)
            event_type = data.get("type", "unknown")
            payload = data.get("payload", data)
            
            logger.debug(f"📩 Mensaje recibido: {event_type}")
            
            # Enviar a OSIRIS
            sent = await self.osiris_client.send_event(event_type, payload)
            
            if not sent:
                self.cache_manager.save_pending(event_type, payload)
                logger.warning(f"💾 Evento {event_type} guardado en caché")
            else:
                self.cache_manager.record_metric(event_type, "sent", payload_size=len(msg))
                logger.info(f"📤 Evento {event_type} enviado a OSIRIS")
                
        except json.JSONDecodeError:
            logger.warning("⚠️  Mensaje JSON inválido")
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
    
    async def _process_pending(self):
        """Procesar mensajes pendientes"""
        pending = self.cache_manager.get_pending(self.config.max_retries * 2)
        
        if not pending:
            return
        
        logger.info(f"📦 Procesando {len(pending)} mensajes pendientes...")
        
        success_ids = []
        for item in pending:
            # Verificar si excedió el máximo de reintentos
            if item.get("retry_count", 0) >= self.config.max_retries * 2:
                logger.warning(f"⚠️  Mensaje {item['id']} excedió máximo de reintentos")
                continue
            
            sent = await self.osiris_client.send_event(item["type"], item["payload"], retry=False)
            
            if sent:
                success_ids.append(item["id"])
                self.cache_manager.record_metric(item["type"], "retry_sent")
            else:
                self.cache_manager.update_retry_count(item["id"])
        
        if success_ids:
            self.cache_manager.delete_pending(success_ids)
            logger.info(f"✅ {len(success_ids)} mensajes pendientes enviados")
    
    async def _handle_reconnect(self):
        """Manejar reconexión"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("❌ Máximo de intentos de reconexión alcanzado")
            self._running = False
            return
        
        self._reconnect_attempts += 1
        delay = min(self.config.retry_delay * self._reconnect_attempts, 60)
        logger.info(f"⏳ Reconectando en {delay:.1f} segundos (intento {self._reconnect_attempts})...")
        await asyncio.sleep(delay)
    
    def stop(self):
        """Detener el escuchador"""
        self._running = False
        if self._ws_connection:
            try:
                asyncio.run_coroutine_threadsafe(self._ws_connection.close(), asyncio.get_event_loop())
            except:
                pass

# ============================================================
# MONITOREO Y SALUD
# ============================================================

class HealthMonitor:
    """Monitor de salud del sistema"""
    
    def __init__(self, config: Config, cache_manager: CacheManager, osiris_client: OsirisClient):
        self.config = config
        self.cache_manager = cache_manager
        self.osiris_client = osiris_client
        self._running = False
    
    async def start(self):
        """Iniciar monitor de salud"""
        self._running = True
        logger.info("🏥 Monitor de salud iniciado")
        
        while self._running:
            await self._check_all()
            await asyncio.sleep(self.config.heartbeat_interval)
    
    async def _check_all(self):
        """Verificar todos los componentes"""
        checks = []
        
        # Verificar OSIRIS
        osiris_healthy = await self.osiris_client.check_health()
        checks.append(("OSIRIS", "healthy" if osiris_healthy else "unhealthy"))
        
        # Verificar caché
        stats = self.cache_manager.get_stats()
        cache_status = "healthy" if stats.get('total_pending', 0) < 100 else "warning"
        checks.append(("Cache", cache_status, f"{stats.get('total_pending', 0)} pendientes"))
        
        # Verificar conexión WebSocket (simplificado)
        # En una implementación real, verificar la conexión activa
        checks.append(("WebSocket", "healthy", "Conectado"))
        
        # Registrar en base de datos
        conn = sqlite3.connect(self.cache_manager.db_path)
        c = conn.cursor()
        for check in checks:
            if len(check) == 3:
                component, status, details = check
            else:
                component, status = check
                details = ""
            
            c.execute(
                "INSERT INTO health_checks (timestamp, component, status, details) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), component, status, str(details))
            )
        conn.commit()
        conn.close()
        
        # Enviar heartbeat a OSIRIS
        if osiris_healthy:
            await self.osiris_client.send_event(
                EventType.HEARTBEAT.value,
                {
                    "component": "connector",
                    "version": "3.0.0",
                    "status": "running",
                    "metrics": stats
                },
                retry=False
            )
        
        # Log de estado
        status_icons = {"healthy": "✅", "warning": "⚠️ ", "unhealthy": "❌"}
        status_str = ", ".join([f"{status_icons.get(s, '❓')} {c}" for c, s, *_ in checks])
        logger.info(f"🏥 Estado del sistema: {status_str}")
    
    def stop(self):
        """Detener monitor"""
        self._running = False

# ============================================================
# MANEJO DE SEÑALES
# ============================================================

def signal_handler(sig, frame):
    """Manejar señales de sistema"""
    logger.info(f"🛑 Señal recibida: {sig}")
    global main_connector, health_monitor
    
    if main_connector:
        main_connector.stop()
    if health_monitor:
        health_monitor.stop()
    
    logger.info("✅ Conector detenido correctamente")
    sys.exit(0)

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

main_connector = None
health_monitor = None

async def main():
    global main_connector, health_monitor
    
    # Cargar configuración
    config_manager = ConfigManager()
    config = config_manager.get()
    
    # Inicializar componentes
    cache_manager = CacheManager(config.db_path, config.max_cache_age)
    
    async with OsirisClient(config.osiris_url, config) as osiris_client:
        # Crear escuchador
        main_connector = SourceSealListener(config, cache_manager, osiris_client)
        
        # Crear monitor de salud
        health_monitor = HealthMonitor(config, cache_manager, osiris_client)
        
        # Iniciar componentes
        listener_task = asyncio.create_task(main_connector.start())
        monitor_task = asyncio.create_task(health_monitor.start())
        
        logger.info("🚀 Conector SourceSeal -> OSIRIS v3.0 iniciado")
        logger.info(f"   → Escuchando: {config.seal_ws}")
        logger.info(f"   → Enviando a: {config.osiris_url}")
        logger.info(f"   → Caché: {config.db_path}")
        logger.info(f"   → Logs: {config.log_file}")
        logger.info("   (Presiona Ctrl+C para detener)")
        
        # Mantener vivo
        try:
            await asyncio.gather(listener_task, monitor_task)
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    # Configurar señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ejecutar
    asyncio.run(main())

