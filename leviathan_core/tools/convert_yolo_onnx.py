#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONVERTIR YOLOv8 a ONNX — Script para PC (NO Termux)
====================================================
Corre esto en una PC con Python + pip install ultralytics onnx.
Genera yolov8n.onnx listo para copiar a Termux.

Uso:
  pip install ultralytics onnx
  python3 convert_yolo_onnx.py
  # Copia yolov8n.onnx a Termux:
  # scp yolov8n.onnx termux:~/Red-team-tauri/redteam/models/

Autor: Harold Paredes / SourceSeal Red Team
"""

import sys
import os

def main():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ ultralytics no instalado. Ejecuta: pip install ultralytics onnx")
        sys.exit(1)

    # Descargar y cargar yolov8n (nano — más ligero para ARM)
    print("[1/4] Descargando yolov8n.pt...")
    model = YOLO("yolov8n.pt")

    # Exportar a ONNX con opset 12 (compatible con onnxruntime)
    print("[2/4] Exportando a ONNX...")
    onnx_path = model.export(format="onnx", opset=12, simplify=True)

    if os.path.exists(onnx_path):
        size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        print(f"[3/4] ✅ Modelo ONNX generado: {onnx_path} ({size_mb:.1f} MB)")
    else:
        print(f"[3/4] ❌ No se encontró el archivo: {onnx_path}")
        sys.exit(1)

    print("[4/4] Instrucciones para Termux:")
    print()
    print("  1. Copia el archivo a tu teléfono:")
    print(f"     scp {onnx_path} termux:~/Red-team-tauri/redteam/models/yolov8n.onnx")
    print()
    print("  2. En Termux instala dependencias:")
    print("     pip install onnxruntime numpy pillow")
    print()
    print("  3. Verifica que funciona:")
    print("     python3 -c \"")
    print("       import onnxruntime as ort")
    print(f"       s = ort.InferenceSession('{os.path.expanduser('~/Red-team-tauri/redteam/models/yolov8n.onnx')}')")
    print("       print('OK:', s.get_inputs()[0].shape)")
    print("     \"")
    print()
    print("  El módulo object_detection detectará el modelo .onnx automáticamente.")
    print()
    print("✅ Listo!")

if __name__ == "__main__":
    main()
