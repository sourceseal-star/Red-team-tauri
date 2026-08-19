"""
ARTO API Router - Router FastAPI
===============================
Proporciona endpoints REST para el sistema ARTO.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi import Depends, status
from typing import Dict, List, Optional, Any
import asyncio
import datetime
import json
from dataclasses import asdict

# Importar ARTO
from arto import arto, start_arto, stop_arto

# Crear router
router = APIRouter(prefix="/api/arto", tags=["ARTO"])


# 📡 WebSocket para streaming en tiempo real
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para eventos en tiempo real"""
    await manager.connect(websocket)
    
    try:
        while True:
            # En implementación completa, esto manejaría mensajes entrantes
            data = await websocket.receive_text()
            
            # Procesar mensaje
            message = json.loads(data)
            action = message.get("action")
            
            if action == "subscribe":
                await websocket.send_text(json.dumps({
                    "status": "subscribed",
                    "message": "Suscripción a eventos ARTO exitosa"
                }))
            elif action == "unsubscribe":
                await websocket.send_text(json.dumps({
                    "status": "unsubscribed",
                    "message": "Suscripción cancelada"
                }))
            
            # Enviar eventos actuales
            async for event in arto.event_stream():
                await manager.send_personal_message(json.dumps(event), websocket)
                await asyncio.sleep(0.1)  # Evitar saturar
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"🔌 Cliente desconectado")


# 🎯 Endpoints de Sistema

@router.get("/status")
async def get_status():
    """Obtiene el estado actual del sistema ARTO"""
    status = await arto.get_status()
    return {
        "status": "success",
        "data": status,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.post("/start")
async def start_system():
    """Inicia el sistema ARTO"""
    try:
        await start_arto()
        return {
            "status": "success",
            "message": "ARTO iniciado",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/stop")
async def stop_system():
    """Detiene el sistema ARTO"""
    try:
        await stop_arto()
        return {
            "status": "success",
            "message": "ARTO detenido",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 🔍 Endpoints de Operaciones Autónomas

@router.post("/operation/{operation_type}")
async def autonomous_operation(
    operation_type: str,
    request: Dict
):
    """
    Ejecuta una operación autónoma.
    
    Tipos de operación: scan, simulate, monitor, investigate, defend
    """
    target = request.get("target")
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'target' es obligatorio"
        )
    
    try:
        result = await arto.autonomous_operation(target, operation_type)
        return {
            "status": "success",
            "operation_type": operation_type,
            "target": target,
            "result": result,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/operations")
async def get_operations():
    """Obtiene todas las operaciones ejecutadas"""
    operations = await arto.get_operations()
    return {
        "status": "success",
        "count": len(operations),
        "operations": operations,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.get("/operations/{operation_id}")
async def get_operation(operation_id: str):
    """Obtiene una operación específica"""
    operations = await arto.get_operations()
    
    for op in operations:
        if op.get("id") == operation_id:
            return {
                "status": "success",
                "operation": op,
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Operación {operation_id} no encontrada"
    )


# 🔮 Endpoints de Predicción

@router.get("/predictions")
async def get_predictions():
    """Obtiene todas las predicciones"""
    predictions = await arto.get_predictions()
    return {
        "status": "success",
        "count": len(predictions),
        "predictions": predictions,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.post("/predict")
async def predict_attacks(request: Dict):
    """Predice posibles ataques"""
    time_horizon = request.get("time_horizon", 24)
    
    try:
        predictions = await arto.predict_attacks(time_horizon)
        return {
            "status": "success",
            "time_horizon": time_horizon,
            "predictions": predictions,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 🛡️ Endpoints de Defensa

@router.post("/defend")
async def respond_to_threat(request: Dict):
    """Responde a una amenaza"""
    threat = request.get("threat")
    
    if not threat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'threat' es obligatorio"
        )
    
    try:
        response = await arto.respond_to_threat(threat)
        return {
            "status": "success",
            "response": response,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/threats")
async def get_threats():
    """Obtiene todas las amenazas detectadas"""
    threats = await arto.get_threats()
    return {
        "status": "success",
        "count": len(threats),
        "threats": threats,
        "timestamp": datetime.datetime.now().isoformat()
    }


# 🎭 Endpoints de Simulación

@router.post("/simulate")
async def simulate_attack(request: Dict):
    """Simula un ataque"""
    template_name = request.get("template_name")
    target = request.get("target")
    
    if not template_name or not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los parámetros 'template_name' y 'target' son obligatorios"
        )
    
    try:
        result = await arto.simulate_attack(template_name, target)
        return {
            "status": "success",
            "template_name": template_name,
            "target": target,
            "result": result,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/templates")
async def get_templates():
    """Obtiene todas las plantillas de ataque"""
    templates = await arto.attack_simulator.get_templates()
    return {
        "status": "success",
        "count": len(templates),
        "templates": {name: template.to_dict() for name, template in templates.items()},
        "timestamp": datetime.datetime.now().isoformat()
    }


# 📊 Endpoints de Análisis

@router.post("/analyze/behavior")
async def analyze_behavior(request: Dict):
    """Analiza comportamiento"""
    entity = request.get("entity")
    behavior_data = request.get("behavior_data", {})
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'entity' es obligatorio"
        )
    
    try:
        result = await arto.analyze_behavior(entity, behavior_data)
        return {
            "status": "success",
            "entity": entity,
            "result": result,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 💾 Endpoints de Memoria

@router.get("/memory/stats")
async def get_memory_stats():
    """Obtiene estadísticas de memoria"""
    stats = await arto.get_memory_stats()
    return {
        "status": "success",
        "stats": stats,
        "timestamp": datetime.datetime.now().isoformat()
    }


@router.get("/knowledge/stats")
async def get_knowledge_stats():
    """Obtiene estadísticas de la base de conocimiento"""
    stats = await arto.get_knowledge_stats()
    return {
        "status": "success",
        "stats": stats,
        "timestamp": datetime.datetime.now().isoformat()
    }


# 📈 Endpoints de Estadísticas

@router.get("/stats")
async def get_all_stats():
    """Obtiene todas las estadísticas del sistema"""
    try:
        status = await arto.get_status()
        memory_stats = await arto.get_memory_stats()
        knowledge_stats = await arto.get_knowledge_stats()
        
        return {
            "status": "success",
            "system": status,
            "memory": memory_stats,
            "knowledge": knowledge_stats,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# 🔌 Endpoints de Captura de Tráfico (VPN)
# ============================================

@router.post("/traffic/start")
async def start_traffic_capture():
    """Inicia la captura de tráfico"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        await vpn_interceptor.start()
        return {
            "status": "success",
            "message": "Captura de tráfico iniciada",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/traffic/stop")
async def stop_traffic_capture():
    """Detiene la captura de tráfico"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        await vpn_interceptor.stop()
        return {
            "status": "success",
            "message": "Captura de tráfico detenida",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/traffic/stats")
async def get_traffic_stats():
    """Obtiene estadísticas de tráfico"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        stats = await vpn_interceptor.get_stats()
        return {
            "status": "success",
            "stats": stats,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/traffic/packets")
async def get_captured_packets(limit: int = 100):
    """Obtiene paquetes capturados"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        packets = await vpn_interceptor.get_captured_packets(limit)
        return {
            "status": "success",
            "packets": packets,
            "count": len(packets),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/traffic/analysis")
async def get_traffic_analysis():
    """Obtiene análisis completo de tráfico"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        analysis = await vpn_interceptor.get_analysis()
        return {
            "status": "success",
            "analysis": analysis.to_dict(),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/traffic/clear")
async def clear_traffic_stats():
    """Limpia estadísticas de tráfico"""
    try:
        from arto.modules.vpn_interceptor import vpn_interceptor
        await vpn_interceptor.clear_stats()
        return {
            "status": "success",
            "message": "Estadísticas de tráfico limpias",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
