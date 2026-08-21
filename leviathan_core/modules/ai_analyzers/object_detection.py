#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OBJECT DETECTION - Detección de Objetos con YOLOv8
=================================================
Detección de objetos en imágenes y streams de video usando YOLOv8.

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import cv2
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from PIL import Image
import io


@dataclass
class DetectedObject:
    """Objeto detectado."""
    class_name: str
    confidence: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    class_id: int


@dataclass
class DetectionResult:
    """Resultado de detección."""
    image_path: Optional[str] = None
    objects: List[DetectedObject] = field(default_factory=list)
    total_objects: int = 0
    classes_found: List[str] = field(default_factory=list)
    alert_objects: List[DetectedObject] = field(default_factory=list)


class ObjectDetectionAnalyzer:
    """Analizador de detección de objetos con YOLOv8."""
    
    def __init__(self):
        self.name = "object_detection"
        self.category = "ai_analyzer"
        self.description = "Detección de objetos con YOLOv8"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
        # Configuración de YOLOv8
        self.model_path = "yolov8n.pt"
        self.confidence_threshold = 0.5
        self.alert_classes = ["person", "car", "truck", "motorcycle", "bus", "bicycle"]
        
        # Modelo cargado
        self.model = None
        
    async def initialize(self):
        """Inicializa el modelo."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            return True
        except ImportError:
            print("⚠️ ultralytics no está instalado. Usa: pip install ultralytics")
            return False
        except Exception as e:
            print(f"❌ Error al cargar modelo: {e}")
            return False
    
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Verifica si el analizador es aplicable."""
        context = context or {}
        
        # Aplicable si hay imágenes o streams de video
        if context.get("image_data") or context.get("image_path") or context.get("stream_url"):
            return True
        
        return False
    
    async def analyze(self, target: str, context: Dict = None) -> Dict:
        """
        Analiza una imagen o stream de video.
        
        Args:
            target: Path a imagen o URL de stream
            context: Contexto adicional
        """
        context = context or {}
        
        results = {
            "target": target,
            "detections": [],
            "statistics": {
                "total_objects": 0,
                "classes_found": [],
                "alerts": 0
            },
            "success": False,
            "error": None
        }
        
        try:
            # Inicializar modelo si no está cargado
            if not self.model:
                await self.initialize()
            
            if not self.model:
                results["error"] = "Modelo YOLOv8 no disponible"
                return results
            
            # Obtener imagen
            image = await self._get_image(target, context)
            if image is None:
                results["error"] = "No se pudo obtener la imagen"
                return results
            
            # Realizar detección
            detection_result = await self._detect_objects(image)
            
            results["detections"] = [
                {
                    "class_name": obj.class_name,
                    "confidence": obj.confidence,
                    "bbox": [obj.x_min, obj.y_min, obj.x_max, obj.y_max]
                }
                for obj in detection_result.objects
            ]
            results["statistics"]["total_objects"] = detection_result.total_objects
            results["statistics"]["classes_found"] = detection_result.classes_found
            results["statistics"]["alerts"] = len(detection_result.alert_objects)
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _get_image(self, target: str, context: Dict) -> Optional[np.ndarray]:
        """Obtiene una imagen desde el target o contexto."""
        # Verificar si hay datos de imagen en contexto
        if context.get("image_data"):
            # Convertir bytes a numpy array
            image_bytes = context["image_data"]
            image = Image.open(io.BytesIO(image_bytes))
            return np.array(image)
        
        # Verificar si hay path a imagen
        if context.get("image_path"):
            try:
                image = cv2.imread(context["image_path"])
                return image
            except:
                pass
        
        # Verificar si es una URL de stream
        if target.startswith(("http://", "https://", "rtsp://")):
            return await self._capture_stream_frame(target)
        
        # Intentar leer como path
        try:
            image = cv2.imread(target)
            return image
        except:
            pass
        
        return None
    
    async def _capture_stream_frame(self, stream_url: str) -> Optional[np.ndarray]:
        """Captura un frame de un stream de video."""
        try:
            # Para RTSP
            if stream_url.startswith("rtsp://"):
                cap = cv2.VideoCapture(stream_url)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        return frame
            
            # Para HTTP (MJPEG, etc.)
            else:
                import aiohttp
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(stream_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            image = Image.open(io.BytesIO(data))
                            return np.array(image)
        except:
            pass
        
        return None
    
    async def _detect_objects(self, image: np.ndarray) -> DetectionResult:
        """Realiza detección de objetos en una imagen."""
        result = DetectionResult()
        
        try:
            # Convertir a RGB si es BGR
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Realizar detección con YOLOv8
            predictions = self.model.predict(image, conf=self.confidence_threshold)
            
            # Procesar resultados
            for pred in predictions:
                for box in pred.boxes:
                    class_id = int(box.cls)
                    class_name = self.model.names[class_id]
                    confidence = float(box.conf)
                    x_min, y_min, x_max, y_max = map(int, box.xyxy[0])
                    
                    obj = DetectedObject(
                        class_name=class_name,
                        confidence=confidence,
                        x_min=x_min,
                        y_min=y_min,
                        x_max=x_max,
                        y_max=y_max,
                        class_id=class_id
                    )
                    result.objects.append(obj)
                    
                    # Agregar a clases encontradas
                    if class_name not in result.classes_found:
                        result.classes_found.append(class_name)
                    
                    # Verificar si es un objeto de alerta
                    if class_name in self.alert_classes:
                        result.alert_objects.append(obj)
            
            result.total_objects = len(result.objects)
            
        except Exception as e:
            print(f"❌ Error en detección: {e}")
        
        return result
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "model": self.model_path,
            "confidence_threshold": self.confidence_threshold
        }


def register():
    """Función de registro para el sistema de plugins."""
    return ObjectDetectionAnalyzer()
