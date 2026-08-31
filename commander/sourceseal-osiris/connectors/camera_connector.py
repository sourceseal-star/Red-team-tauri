#!/usr/bin/env python3
"""
Conector de Cámaras -> OSIRIS v1.0
Captura imágenes de cámaras IP y envía eventos a OSIRIS
"""

import asyncio
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
import os
import json
import time
import logging
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aiohttp
import requests

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [CameraConnector] %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser('~/camera_connector.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CameraConnector")

@dataclass
class CameraConfig:
    id: str
    name: str
    url: str
    type: str = "rtsp"
    motion_detection: bool = False
    motion_threshold: float = 0.1
    capture_interval: int = 5
    osiris_event_type: str = "camera_motion"
    location: Optional[Dict] = None

@dataclass
class CameraImage:
    camera_id: str
    camera_name: str
    timestamp: str
    image_data: bytes
    event_type: str
    confidence: float = 0.0
    location: Optional[Dict] = None

class CameraConnector:
    """Conector para cámaras IP"""
    
    def __init__(self, config_path: str = "configs/cameras_config.json", 
                 osiris_url: str = "http://localhost:3000/api"):
        self.config_path = config_path
        self.osiris_url = osiris_url
        self.cameras: Dict[str, CameraConfig] = {}
        self._running = False
        self._load_config()
        
        # Crear directorio de almacenamiento
        os.makedirs(
            self.config.get("image_storage", {}).get("local_path", "/tmp/camera_captures"),
            exist_ok=True
        )
    
    def _load_config(self):
        """Cargar configuración de cámaras"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if not config.get("enabled", False):
                logger.warning("⚠️  Integración de cámaras deshabilitada")
                return
            
            for cam_config in config.get("cameras", []):
                camera = CameraConfig(
                    id=cam_config["id"],
                    name=cam_config["name"],
                    url=cam_config["url"],
                    type=cam_config.get("type", "rtsp"),
                    motion_detection=cam_config.get("motion_detection", False),
                    motion_threshold=cam_config.get("motion_threshold", 0.1),
                    capture_interval=cam_config.get("capture_interval", 5),
                    osiris_event_type=cam_config.get("osiris_event_type", "camera_motion"),
                    location=cam_config.get("location")
                )
                self.cameras[camera.id] = camera
                logger.info(f"📹 Cámara configurada: {camera.name} ({camera.id})")
                
            self.config = config
            
        except FileNotFoundError:
            logger.error(f"❌ Configuración no encontrada: {self.config_path}")
        except json.JSONDecodeError:
            logger.error(f"❌ Configuración inválida: {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Error cargando configuración: {e}")
    
    async def start(self):
        """Iniciar captura de cámaras"""
        if not self.cameras:
            logger.warning("⚠️  No hay cámaras configuradas")
            return
        
        self._running = True
        logger.info("🚀 Iniciando conector de cámaras")
        
        tasks = []
        for cam_id, camera in self.cameras.items():
            task = asyncio.create_task(self._capture_loop(camera))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def _capture_loop(self, camera: CameraConfig):
        """Bucle de captura para una cámara"""
        logger.info(f"🎬 Iniciando captura para {camera.name}")
        
        last_frame = None
        motion_detected = False
        
        while self._running:
            try:
                # Capturar frame
                frame = self._capture_frame(camera)
                
                if frame is None:
                    logger.warning(f"⚠️  No se pudo capturar frame de {camera.name}")
                    await asyncio.sleep(camera.capture_interval)
                    continue
                
                # Detectar movimiento si está habilitado
                if camera.motion_detection and last_frame is not None:
                    motion = self._detect_motion(last_frame, frame, camera.motion_threshold)
                    if motion > camera.motion_threshold:
                        if not motion_detected:
                            logger.info(f"🚨 Movimiento detectado en {camera.name} ({motion:.2f})")
                            motion_detected = True
                            # Enviar evento de movimiento
                            await self._send_camera_event(camera, frame, "motion")
                    else:
                        motion_detected = False
                else:
                    # Enviar captura periódica
                    await self._send_camera_event(camera, frame, "snapshot")
                
                last_frame = frame
                await asyncio.sleep(camera.capture_interval)
                
            except Exception as e:
                logger.error(f"❌ Error en captura de {camera.name}: {e}")
                await asyncio.sleep(5)
    
    def _capture_frame(self, camera: CameraConfig) -> Any:
        """Capturar un frame de la cámara"""
        try:
            if camera.type == "rtsp":
                return self._capture_rtsp(camera.url)
            elif camera.type == "http":
                return self._capture_http(camera.url)
            else:
                logger.warning(f"⚠️  Tipo de cámara no soportado: {camera.type}")
                return None
        except Exception as e:
            logger.error(f"Error capturando de {camera.url}: {e}")
            return None
    
    def _capture_rtsp(self, url: str) -> Any:
        """Capturar frame de RTSP"""
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            logger.warning(f"⚠️  No se pudo abrir RTSP: {url}")
            return None
        
        try:
            ret, frame = cap.read()
            if ret:
                return frame
            return None
        finally:
            cap.release()
    
    def _capture_http(self, url: str) -> Any:
        """Capturar frame de HTTP (MJPEG o imagen estática)"""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # Decodificar imagen
                img_array = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                return frame
            return None
        except Exception as e:
            logger.error(f"Error capturando HTTP: {e}")
            return None
    
    def _detect_motion(self, frame1: Any, frame2: Any, threshold: float = 0.1) -> float:
        """Detectar movimiento entre dos frames"""
        try:
            # Convertir a escala de grises
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            
            # Aplicar blur para reducir ruido
            gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
            gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
            
            # Calcular diferencia absoluta
            frame_delta = cv2.absdiff(gray1, gray2)
            
            # Aplicar umbral
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            
            # Dilatar para llenar huecos
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # Calcular porcentaje de píxeles blancos
            white_pixels = cv2.countNonZero(thresh)
            total_pixels = thresh.size
            motion_score = white_pixels / total_pixels
            
            return motion_score
        except Exception as e:
            logger.error(f"Error en detección de movimiento: {e}")
            return 0.0
    
    async def _send_camera_event(self, camera: CameraConfig, frame: Any, event_type: str):
        """Enviar evento de cámara a OSIRIS"""
        try:
            # Guardar imagen localmente
            image_path = self._save_image(camera, frame, event_type)
            
            # Convertir a base64 si es pequeño
            config = self.config.get("osiris", {})
            if config.get("send_images", True):
                if config.get("image_format") == "base64":
                    image_data = self._frame_to_base64(frame, config.get("max_image_size", 1024))
                else:
                    image_data = ""
            else:
                image_data = ""
            
            # Preparar payload
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "camera_id": camera.id,
                "camera_name": camera.name,
                "event_type": event_type,
                "image_url": image_path if image_path else "",
                "image_data": image_data,
                "confidence": 0.0,
                "location": camera.location or {}
            }
            
            # Enviar a OSIRIS
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.osiris_url}/events/visual"
                
                async with session.post(endpoint, json=payload, timeout=10) as resp:
                    if resp.status in [200, 201]:
                        logger.info(f"✅ Imagen de {camera.name} enviada a OSIRIS ({event_type})")
                    else:
                        logger.warning(f"⚠️  Error enviando imagen: {resp.status}")
                        # Guardar en caché local
                        self._save_to_cache(camera, frame, event_type)
                        
        except Exception as e:
            logger.error(f"❌ Error enviando evento de cámara: {e}")
            # Guardar en caché local
            self._save_to_cache(camera, frame, event_type)
    
    def _save_image(self, camera: CameraConfig, frame: Any, event_type: str) -> str:
        """Guardar imagen localmente"""
        try:
            storage_config = self.config.get("image_storage", {})
            local_path = storage_config.get("local_path", "/tmp/camera_captures")
            quality = storage_config.get("quality", 85)
            
            os.makedirs(local_path, exist_ok=True)
            
            # Generar nombre de archivo
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{camera.id}_{event_type}_{timestamp}.jpg"
            filepath = os.path.join(local_path, filename)
            
            # Guardar imagen
            cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            
            logger.debug(f"💾 Imagen guardada: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error guardando imagen: {e}")
            return ""
    
    def _frame_to_base64(self, frame: Any, max_size: int = 1024) -> str:
        """Convertir frame a base64, redimensionando si es necesario"""
        try:
            # Redimensionar si es muy grande
            height, width = frame.shape[:2]
            if max(height, width) > max_size:
                scale = max_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # Convertir a base64
            _, buffer = cv2.imencode('.jpg', frame)
            return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Error convirtiendo a base64: {e}")
            return ""
    
    def _save_to_cache(self, camera: CameraConfig, frame: Any, event_type: str):
        """Guardar evento en caché local"""
        try:
            cache_path = "/home/user/camera_cache.db"
            conn = sqlite3.connect(cache_path)
            c = conn.cursor()
            
            # Crear tabla si no existe
            c.execute('''
                CREATE TABLE IF NOT EXISTS camera_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    image_path TEXT,
                    timestamp TEXT NOT NULL,
                    sent INTEGER DEFAULT 0
                )
            ''')
            
            # Guardar imagen temporalmente
            image_path = self._save_image(camera, frame, event_type)
            
            c.execute(
                "INSERT INTO camera_events (camera_id, event_type, image_path, timestamp) VALUES (?, ?, ?, ?)",
                (camera.id, event_type, image_path, datetime.utcnow().isoformat())
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"💾 Evento de cámara guardado en caché: {camera.id}")
            
        except Exception as e:
            logger.error(f"Error guardando en caché: {e}")
    
    def stop(self):
        """Detener el conector"""
        self._running = False
        logger.info("✅ Conector de cámaras detenido")

# ============================================================
# PUNTO DE ENTRADA
# ============================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Conector de Cámaras -> OSIRIS")
    parser.add_argument("--config", default="configs/cameras_config.json", help="Archivo de configuración")
    parser.add_argument("--osiris-url", default="http://localhost:3000/api", help="URL de OSIRIS")
    args = parser.parse_args()
    
    connector = CameraConnector(args.config, args.osiris_url)
    
    try:
        await connector.start()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
    finally:
        connector.stop()


    
    # ── Integración con Red-team-tauri Dashboard (v6.0) ──────────────────
    
    def audit_cameras_batch(self, cidr: str = "192.168.1.0/24") -> dict:
        """Escanea una red CIDR y audita todas las cámaras encontradas.
        Usa el endpoint /api/iot/auto-access-batch del dashboard Red-team-tauri.
        
        Returns:
            dict: {cameras_found, summary, cameras[]}
        """
        import requests
        dashboard_url = self.config.get("dashboard_url", "http://localhost:8001")
        try:
            r = requests.post(
                f"{dashboard_url}/api/iot/auto-access-batch",
                json={"cidr": cidr},
                timeout=120
            )
            if r.status_code == 200:
                return r.json()
            else:
                return {"error": f"HTTP {r.status_code}", "detail": r.text[:200]}
        except Exception as e:
            return {"error": str(e)}
    
    def audit_single_camera(self, ip: str, port: int = 80) -> dict:
        """Audita una cámara individual: vendor + CVEs + creds + snapshot.
        Usa el endpoint /api/iot/auto-access del dashboard.
        """
        import requests
        dashboard_url = self.config.get("dashboard_url", "http://localhost:8001")
        try:
            r = requests.get(
                f"{dashboard_url}/api/iot/auto-access",
                params={"ip": ip, "port": port},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()
            else:
                return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_camera_vulns(self, ip: str, port: int = 80) -> dict:
        """Obtiene CVEs conocidos y credenciales por defecto de una cámara.
        Usa el endpoint /api/iot/vulns del dashboard.
        """
        import requests
        dashboard_url = self.config.get("dashboard_url", "http://localhost:8001")
        try:
            r = requests.get(
                f"{dashboard_url}/api/iot/vulns",
                params={"ip": ip, "port": port},
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
            else:
                return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_snapshot_url(self, ip: str, port: int = 80, user: str = None, pwd: str = None) -> str:
        """Construye la URL de snapshot del dashboard para una cámara."""
        dashboard_url = self.config.get("dashboard_url", "http://localhost:8001")
        url = f"{dashboard_url}/api/iot/snapshot?ip={ip}&port={port}"
        if user and pwd:
            url += f"&user={user}&pwd={pwd}"
        return url
    
    def get_stream_url(self, ip: str, port: int = 80, path: str = "/mjpg/video.mjpg", 
                       user: str = None, pwd: str = None) -> str:
        """Construye la URL de stream MJPEG del dashboard."""
        dashboard_url = self.config.get("dashboard_url", "http://localhost:8001")
        from urllib.parse import quote
        url = f"{dashboard_url}/api/iot/stream?ip={ip}&port={port}&path={quote(path, safe='')}"
        if user and pwd:
            url += f"&user={user}&pwd={pwd}"
        return url

if __name__ == "__main__":
    asyncio.run(main())
