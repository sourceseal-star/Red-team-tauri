#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OBJECT DETECTION - Detección de Objetos con YOLOv8 (ONNX)
=========================================================
Funciona en Termux/Android usando onnxruntime en vez de ultralytics.
El modelo yolov8n.pt se convierte a .onnx una vez en una PC.

Flujo:
  1. En PC:  python3 convert_yolo_onnx.py  → genera yolov8n.onnx
  2. Copias yolov8n.onnx a Termux: ~/Red-team-tauri/redteam/models/
  3. En Termux: pip install onnxruntime numpy pillow
  4. El módulo detecta automáticamente si usar ONNX o ultralytics

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import os
import io
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

# Imports opcionales — el módulo funciona sin todos
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import onnxruntime as ort
    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False

# Clases COCO (80) que YOLOv8 detecta por defecto
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush"
]


@dataclass
class DetectedObject:
    class_name: str
    confidence: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    class_id: int


@dataclass
class DetectionResult:
    image_path: Optional[str] = None
    objects: List[DetectedObject] = field(default_factory=list)
    total_objects: int = 0
    classes_found: List[str] = field(default_factory=list)
    alert_objects: List[DetectedObject] = field(default_factory=list)


class ObjectDetectionAnalyzer:
    """Detector de objetos — ONNX (Termux) o ultralytics (PC)."""

    def __init__(self):
        self.name = "object_detection"
        self.category = "ai_analyzer"
        self.description = "Detección de objetos (ONNX/ultralytics)"
        self.author = "Harold Paredes"
        self.version = "3.1.0"

        # Buscar modelo en múltiples ubicaciones
        self.model_dir = os.environ.get("LEVIATHAN_MODELS", "")
        possible_paths = []
        if self.model_dir:
            possible_paths.append(os.path.join(self.model_dir, "yolov8n.onnx"))
        possible_paths.extend([
            os.path.expanduser("~/Red-team-tauri/redteam/models/yolov8n.onnx"),
            os.path.expanduser("~/redteam/models/yolov8n.onnx"),
            "yolov8n.onnx",
            "/data/data/com.termux/files/home/redteam/models/yolov8n.onnx",
        ])
        self.model_path = next((p for p in possible_paths if os.path.exists(p)), possible_paths[0])

        self.confidence_threshold = 0.5
        self.alert_classes = ["person", "car", "truck", "motorcycle", "bus", "bicycle"]

        # Estado del modelo
        self.model = None
        self._backend = None  # "onnx", "ultralytics", o None

    def _detect_backend(self) -> Optional[str]:
        """Detecta qué backend usar: ONNX o ultralytics."""
        if _HAS_ONNX and os.path.exists(self.model_path):
            return "onnx"
        try:
            import ultralytics  # noqa
            return "ultralytics"
        except ImportError:
            pass
        return None

    async def initialize(self) -> bool:
        """Inicializa el modelo con el backend disponible."""
        self._backend = self._detect_backend()

        if self._backend == "onnx":
            try:
                providers = ["CPUExecutionProvider"]
                # En GPU real: agregar ["CUDAExecutionProvider"] si disponible
                self.model = ort.InferenceSession(self.model_path, providers=providers)
                print(f"[OBJECT-DETECTION] ONNX cargado: {self.model_path}")
                return True
            except Exception as e:
                print(f"[OBJECT-DETECTION] Error ONNX: {e}")
                return False

        elif self._backend == "ultralytics":
            try:
                from ultralytics import YOLO
                pt_path = self.model_path.replace(".onnx", ".pt")
                self.model = YOLO(pt_path)
                print(f"[OBJECT-DETECTION] ultralytics cargado: {pt_path}")
                return True
            except Exception as e:
                print(f"[OBJECT-DETECTION] Error ultralytics: {e}")
                return False

        else:
            print("[OBJECT-DETECTION] Sin backend disponible")
            print("  Opción 1 (Termux): pip install onnxruntime numpy pillow")
            print("  Opción 2 (PC):     pip install ultralytics")
            print("  Modelo ONNX: copia yolov8n.onnx a redteam/models/")
            return False

    def is_applicable(self, target: str, context: Dict = None) -> bool:
        context = context or {}
        return bool(
            context.get("image_data") or
            context.get("image_path") or
            context.get("stream_url") or
            os.path.exists(target) if target else False
        )

    async def analyze(self, target: str, context: Dict = None) -> Dict:
        """Analiza una imagen o stream."""
        context = context or {}

        results = {
            "target": target,
            "detections": [],
            "statistics": {"total_objects": 0, "classes_found": [], "alerts": 0},
            "success": False,
            "error": None,
            "backend": self._backend,
        }

        try:
            if not self.model:
                await self.initialize()
            if not self.model:
                results["error"] = "No hay modelo disponible"
                return results

            image = await self._get_image(target, context)
            if image is None:
                results["error"] = "No se pudo obtener la imagen"
                return results

            if self._backend == "onnx":
                det_result = await self._detect_onnx(image)
            else:
                det_result = await self._detect_ultralytics(image)

            results["detections"] = [
                {
                    "class_name": o.class_name,
                    "confidence": round(o.confidence, 3),
                    "bbox": [o.x_min, o.y_min, o.x_max, o.y_max],
                }
                for o in det_result.objects
            ]
            results["statistics"]["total_objects"] = det_result.total_objects
            results["statistics"]["classes_found"] = det_result.classes_found
            results["statistics"]["alerts"] = len(det_result.alert_objects)
            results["success"] = True
            return results

        except Exception as e:
            results["error"] = str(e)[:200]
            return results

    # ── Obtener imagen ──

    async def _get_image(self, target: str, context: Dict):
        # image_data: bytes crudos
        if context.get("image_data"):
            if _HAS_PIL:
                return np.array(Image.open(io.BytesIO(context["image_data"])))
            if _HAS_CV2:
                arr = np.frombuffer(context["image_data"], np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)

        # image_path: archivo local
        if context.get("image_path"):
            if _HAS_CV2:
                return cv2.imread(context["image_path"])
            if _HAS_PIL:
                return np.array(Image.open(context["image_path"]))

        # Stream URL
        if target and target.startswith(("http://", "https://", "rtsp://")):
            return await self._capture_stream_frame(target)

        # Path directo
        if target and os.path.exists(target):
            if _HAS_CV2:
                return cv2.imread(target)
            if _HAS_PIL:
                return np.array(Image.open(target))

        return None

    async def _capture_stream_frame(self, stream_url: str):
        """Captura un frame de RTSP o HTTP MJPEG."""
        if _HAS_CV2 and stream_url.startswith("rtsp://"):
            cap = cv2.VideoCapture(stream_url)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    return frame

        if _HAS_AIOHTTP and stream_url.startswith(("http://", "https://")):
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if _HAS_PIL:
                            return np.array(Image.open(io.BytesIO(data)))
        return None

    # ── Inferencia ONNX ──

    async def _detect_onnx(self, image) -> DetectionResult:
        """Detección usando onnxruntime — preprocesa, infiere, postprocesa."""
        result = DetectionResult()

        if not _HAS_NUMPY:
            return result

        # Preprocesar: resize a 640x640, normalizar, NCHW
        input_h, input_w = 640, 640
        orig_h, orig_w = image.shape[:2]

        if _HAS_CV2:
            resized = cv2.resize(image, (input_w, input_h))
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        elif _HAS_PIL:
            img_pil = Image.fromarray(image).resize((input_w, input_h))
            resized = np.array(img_pil)
        else:
            return result

        # Normalizar 0-1, NCHW
        input_tensor = resized.astype(np.float32) / 255.0
        input_tensor = input_tensor.transpose(2, 0, 1)  # HWC → CHW
        input_tensor = np.expand_dims(input_tensor, 0)  # batch

        # Inferencia (to_thread para no bloquear el event loop)
        input_name = self.model.get_inputs()[0].name
        outputs = await asyncio.to_thread(
            self.model.run, None, {input_name: input_tensor}
        )

        # YOLOv8 ONNX output: [1, 84, 8400] — 80 classes + 4 box coords
        # Formato: [cx, cy, w, h, conf_class_0, conf_class_1, ...]
        pred = outputs[0]  # shape: (1, 84, 8400)

        # Transponer a (8400, 84)
        if pred.shape[1] == 84 or pred.shape[2] == 8400:
            pred = pred[0].T  # (8400, 84)
        elif pred.shape[0] == 8400:
            pred = pred[0]
        else:
            # Otro formato — intentar adaptar
            pred = pred[0].T if pred.ndim == 3 else pred

        # Filtrar por confianza
        scores = pred[:, 4:]  # solo classes (80)
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)

        # Filtrar por threshold
        mask = confidences >= self.confidence_threshold
        filtered = pred[mask]
        filtered_classes = class_ids[mask]
        filtered_confs = confidences[mask]

        # NMS simple (greedy)
        boxes = []
        for i in range(len(filtered)):
            cx, cy, w, h = filtered[i, :4]
            # Escalar al tamaño original
            x_min = int((cx - w / 2) * orig_w / input_w)
            y_min = int((cy - h / 2) * orig_h / input_h)
            x_max = int((cx + w / 2) * orig_w / input_w)
            y_max = int((cy + h / 2) * orig_h / input_h)

            cls_id = int(filtered_classes[i])
            cls_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"
            conf = float(filtered_confs[i])

            obj = DetectedObject(
                class_name=cls_name, confidence=conf,
                x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                class_id=cls_id,
            )
            result.objects.append(obj)

            if cls_name not in result.classes_found:
                result.classes_found.append(cls_name)
            if cls_name in self.alert_classes:
                result.alert_objects.append(obj)

        # NMS greedy por clase
        result.objects = self._nms(result.objects)
        result.total_objects = len(result.objects)
        return result

    def _nms(self, objects: List[DetectedObject], iou_threshold: float = 0.5) -> List[DetectedObject]:
        """Non-Maximum Suppression simple."""
        if len(objects) <= 1:
            return objects

        # Ordenar por confianza descendente
        objects.sort(key=lambda o: o.confidence, reverse=True)
        keep = []

        while objects:
            best = objects.pop(0)
            keep.append(best)
            objects = [
                o for o in objects
                if o.class_id != best.class_id or
                self._iou(best, o) < iou_threshold
            ]

        return keep

    @staticmethod
    def _iou(a: DetectedObject, b: DetectedObject) -> float:
        """Intersection over Union."""
        ix1 = max(a.x_min, b.x_min)
        iy1 = max(a.y_min, b.y_min)
        ix2 = min(a.x_max, b.x_max)
        iy2 = min(a.y_max, b.y_max)

        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = (a.x_max - a.x_min) * (a.y_max - a.y_min)
        area_b = (b.x_max - b.x_min) * (b.y_max - b.y_min)
        union = area_a + area_b - inter

        return inter / union if union > 0 else 0.0

    # ── Inferencia ultralytics (PC) ──

    async def _detect_ultralytics(self, image) -> DetectionResult:
        """Detección usando ultralytics YOLO (fallback en PC)."""
        result = DetectionResult()
        try:
            predictions = await asyncio.to_thread(
                self.model.predict, image, conf=self.confidence_threshold
            )
            for pred in predictions:
                for box in pred.boxes:
                    cls_id = int(box.cls)
                    cls_name = self.model.names.get(cls_id, f"class_{cls_id}")
                    conf = float(box.conf)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    obj = DetectedObject(
                        class_name=cls_name, confidence=conf,
                        x_min=x1, y_min=y1, x_max=x2, y_max=y2, class_id=cls_id,
                    )
                    result.objects.append(obj)
                    if cls_name not in result.classes_found:
                        result.classes_found.append(cls_name)
                    if cls_name in self.alert_classes:
                        result.alert_objects.append(obj)
            result.total_objects = len(result.objects)
        except Exception as e:
            print(f"[OBJECT-DETECTION] Error: {e}")
        return result

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "model": self.model_path,
            "backend": self._backend or "none",
            "confidence_threshold": self.confidence_threshold,
        }


def register():
    return ObjectDetectionAnalyzer()
