#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARTO INTEGRATION - Integración con ARTO (Automated Red Team Operations)
====================================================================
Conecta el SEAL SUPER PACK con el sistema ARTO para operaciones autónomas.

Capacidades:
- Envío de resultados de escaneo a ARTO
- Ejecución de operaciones autónomas basadas en hallazgos
- Recepción de predicciones y decisiones de ARTO
- Integración con el orquestador para automatización

Autor: Harold Paredes / SourceSeal Red Team
Uso: from seal.ai.arto_integration import ARTOIntegration
"""

import asyncio
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging


# ============================================================
# CONFIGURACIÓN
# ============================================================

class ARTOConfig:
    # URL base de ARTO (local)
    ARTO_BASE_URL = "http://localhost:8001/arto"
    
    # Timeouts
    TIMEOUT = 10.0
    
    # Archivo de configuración
    CONFIG_FILE = "./arto_integration.json"


# ============================================================
# CLIENTE ARTO
# ============================================================

class ARTOClient:
    """Cliente para comunicarse con ARTO."""
    
    def __init__(self, base_url: str = ARTOConfig.ARTO_BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=ARTOConfig.TIMEOUT))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def send_scan_results(self, scan_data: Dict) -> Dict:
        """Envía resultados de escaneo a ARTO."""
        url = f"{self.base_url}/scan"
        
        async with self.session.post(url, json=scan_data) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def request_autonomous_operation(self, target: str, operation_type: str, 
                                           data: Dict = None) -> Dict:
        """Solicita una operación autónoma a ARTO."""
        url = f"{self.base_url}/operations"
        
        payload = {
            "target": target,
            "operation_type": operation_type,
            "data": data or {}
        }
        
        async with self.session.post(url, json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_predictions(self, timeframe: int = 24) -> Dict:
        """Obtiene predicciones de ARTO."""
        url = f"{self.base_url}/predictions?timeframe={timeframe}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_decision(self, context: Dict) -> Dict:
        """Obtiene una decisión de ARTO para un contexto específico."""
        url = f"{self.base_url}/decision"
        
        async with self.session.post(url, json=context) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_threat_intel(self, target: str) -> Dict:
        """Obtiene inteligencia de amenazas de ARTO."""
        url = f"{self.base_url}/threat-intel?target={target}"
        
        async with self.session.get(url) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_risk_assessment(self, target: str, scan_data: Dict = None) -> Dict:
        """Obtiene evaluación de riesgo de ARTO."""
        url = f"{self.base_url}/risk-assessment"
        
        payload = {
            "target": target,
            "scan_data": scan_data or {}
        }
        
        async with self.session.post(url, json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_attack_simulation(self, attack_type: str, target: str) -> Dict:
        """Solicita una simulación de ataque a ARTO."""
        url = f"{self.base_url}/simulate"
        
        payload = {
            "attack_type": attack_type,
            "target": target
        }
        
        async with self.session.post(url, json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}
    
    async def get_report(self, report_type: str, data: Dict = None) -> Dict:
        """Solicita un informe a ARTO."""
        url = f"{self.base_url}/report"
        
        payload = {
            "report_type": report_type,
            "data": data or {}
        }
        
        async with self.session.post(url, json=payload) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return {"error": f"ARTO error: {resp.status}", "status": resp.status}


# ============================================================
# INTEGRACIÓN PRINCIPAL
# ============================================================

class ARTOIntegration:
    """Integración principal con ARTO."""
    
    def __init__(self, base_url: str = ARTOConfig.ARTO_BASE_URL):
        self.client = ARTOClient(base_url)
        self.connected = False
    
    async def connect(self) -> bool:
        """Conecta con ARTO."""
        try:
            async with self.client as client:
                # Probar conexión
                result = await client.get_predictions(timeframe=1)
                if "error" not in result:
                    self.connected = True
                    return True
                else:
                    self.connected = False
                    return False
        except Exception as e:
            self.connected = False
            return False
    
    async def process_scan_results(self, scan_data: Dict) -> Dict:
        """
        Procesa resultados de escaneo con ARTO.
        
        Args:
            scan_data: Resultados del escaneo (de network_sweep_ultimate.py)
            
        Returns:
            Diccionario con análisis completo de ARTO
        """
        result = {
            "original_scan": scan_data,
            "arto_analysis": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with self.client as client:
                # 1. Enviar resultados a ARTO
                scan_response = await client.send_scan_results(scan_data)
                result["arto_analysis"]["scan_response"] = scan_response
                
                # 2. Obtener evaluación de riesgo para cada objetivo
                for target in scan_data.get("targets", []):
                    target_ip = target.get("ip")
                    risk_assessment = await client.get_risk_assessment(target_ip, target)
                    result["arto_analysis"][f"risk_{target_ip}"] = risk_assessment
                    
                    # 3. Obtener inteligencia de amenazas
                    threat_intel = await client.get_threat_intel(target_ip)
                    result["arto_analysis"][f"threat_{target_ip}"] = threat_intel
                    
                    # 4. Obtener decisión
                    decision_context = {
                        "target": target_ip,
                        "scan_data": target,
                        "risk_assessment": risk_assessment,
                        "threat_intel": threat_intel
                    }
                    decision = await client.get_decision(decision_context)
                    result["arto_analysis"][f"decision_{target_ip}"] = decision
                    
                    # 5. Solicitar operación autónoma si es necesario
                    if decision.get("action") == "exploit":
                        operation = await client.request_autonomous_operation(
                            target_ip, "exploit", decision
                        )
                        result["arto_analysis"][f"operation_{target_ip}"] = operation
                
                # 6. Obtener predicciones
                predictions = await client.get_predictions(24)
                result["arto_analysis"]["predictions"] = predictions
                
                # 7. Generar informe
                report = await client.get_report("scan_analysis", scan_data)
                result["arto_analysis"]["report"] = report
                
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result
    
    async def process_single_target(self, target: str, scan_data: Dict = None) -> Dict:
        """
        Procesa un objetivo específico con ARTO.
        
        Args:
            target: IP o dominio del objetivo
            scan_data: Datos de escaneo (opcional)
            
        Returns:
            Diccionario con análisis de ARTO
        """
        result = {
            "target": target,
            "arto_analysis": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with self.client as client:
                # 1. Obtener evaluación de riesgo
                risk_assessment = await client.get_risk_assessment(target, scan_data)
                result["arto_analysis"]["risk_assessment"] = risk_assessment
                
                # 2. Obtener inteligencia de amenazas
                threat_intel = await client.get_threat_intel(target)
                result["arto_analysis"]["threat_intel"] = threat_intel
                
                # 3. Obtener decisión
                decision_context = {
                    "target": target,
                    "risk_assessment": risk_assessment,
                    "threat_intel": threat_intel
                }
                decision = await client.get_decision(decision_context)
                result["arto_analysis"]["decision"] = decision
                
                # 4. Ejecutar acción basada en decisión
                if decision.get("action"):
                    operation = await client.request_autonomous_operation(
                        target, decision.get("action"), decision
                    )
                    result["arto_analysis"]["operation"] = operation
                
                # 5. Obtener predicciones
                predictions = await client.get_predictions(24)
                result["arto_analysis"]["predictions"] = predictions
                
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result
    
    async def get_autonomous_recommendations(self, scan_data: Dict = None) -> Dict:
        """
        Obtiene recomendaciones autónomas de ARTO.
        
        Args:
            scan_data: Datos de escaneo (opcional)
            
        Returns:
            Diccionario con recomendaciones
        """
        result = {
            "recommendations": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with self.client as client:
                # Obtener predicciones
                predictions = await client.get_predictions(24)
                result["predictions"] = predictions
                
                # Obtener decisiones para cada objetivo
                if scan_data and "targets" in scan_data:
                    for target in scan_data["targets"]:
                        decision_context = {
                            "target": target.get("ip"),
                            "scan_data": target
                        }
                        decision = await client.get_decision(decision_context)
                        
                        if decision.get("recommendation"):
                            result["recommendations"].append({
                                "target": target.get("ip"),
                                "recommendation": decision["recommendation"],
                                "priority": decision.get("priority", "medium"),
                                "reason": decision.get("reason", "")
                            })
                
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result


# ============================================================
# INTEGRACIÓN CON ORQUESTADOR
# ============================================================

class ARTOOrchestratorIntegration:
    """Integración entre ARTO y el SEAL Orchestrator."""
    
    def __init__(self):
        self.arto = ARTOIntegration()
        self.connected = False
    
    async def connect(self) -> bool:
        """Conecta con ARTO."""
        self.connected = await self.arto.connect()
        return self.connected
    
    async def process_orchestrator_data(self, devices: List[Dict], alerts: List[Dict]) -> Dict:
        """
        Procesa datos del orquestador con ARTO.
        
        Args:
            devices: Lista de dispositivos del orquestador
            alerts: Lista de alertas del orquestador
            
        Returns:
            Diccionario con análisis completo
        """
        result = {
            "devices": devices,
            "alerts": alerts,
            "arto_analysis": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with self.arto.client as client:
                # Procesar cada dispositivo
                for device in devices:
                    device_ip = device.get("ip")
                    
                    # Obtener evaluación de riesgo
                    risk_assessment = await client.get_risk_assessment(device_ip, device)
                    result["arto_analysis"][f"risk_{device_ip}"] = risk_assessment
                    
                    # Obtener inteligencia de amenazas
                    threat_intel = await client.get_threat_intel(device_ip)
                    result["arto_analysis"][f"threat_{device_ip}"] = threat_intel
                    
                    # Obtener decisión
                    decision_context = {
                        "target": device_ip,
                        "device_info": device,
                        "risk_assessment": risk_assessment,
                        "threat_intel": threat_intel
                    }
                    decision = await client.get_decision(decision_context)
                    result["arto_analysis"][f"decision_{device_ip}"] = decision
                
                # Procesar alertas
                for alert in alerts:
                    alert_context = {
                        "alert": alert,
                        "device_info": next((d for d in devices if d.get("ip") == alert.get("device_ip")), None)
                    }
                    decision = await client.get_decision(alert_context)
                    result["arto_analysis"][f"alert_decision_{alert.get('id')}"] = decision
                
                # Obtener predicciones
                predictions = await client.get_predictions(24)
                result["arto_analysis"]["predictions"] = predictions
                
                return result
                
        except Exception as e:
            result["error"] = str(e)
            return result
    
    async def get_autonomous_actions(self, devices: List[Dict]) -> List[Dict]:
        """
        Obtiene acciones autónomas recomendadas para los dispositivos.
        
        Args:
            devices: Lista de dispositivos
            
        Returns:
            Lista de acciones recomendadas
        """
        actions = []
        
        try:
            async with self.arto.client as client:
                for device in devices:
                    device_ip = device.get("ip")
                    
                    # Obtener decisión
                    decision_context = {
                        "target": device_ip,
                        "device_info": device
                    }
                    decision = await client.get_decision(decision_context)
                    
                    if decision.get("action"):
                        actions.append({
                            "device_ip": device_ip,
                            "action": decision["action"],
                            "priority": decision.get("priority", "medium"),
                            "reason": decision.get("reason", ""),
                            "timestamp": datetime.now().isoformat()
                        })
                
                return actions
                
        except Exception as e:
            return [{"error": str(e)}]


# ============================================================
# INSTANCIA GLOBAL
# ============================================================

arto_integration = None


def get_arto_integration() -> ARTOIntegration:
    """Obtiene la instancia de integración con ARTO."""
    global arto_integration
    if arto_integration is None:
        arto_integration = ARTOIntegration()
    return arto_integration


async def process_with_arto(scan_data: Dict) -> Dict:
    """Procesa datos de escaneo con ARTO."""
    integration = get_arto_integration()
    return await integration.process_scan_results(scan_data)


# ============================================================
# PRUEBA
# ============================================================

async def main():
    """Función principal de prueba."""
    print("🔗 Probando integración con ARTO...")
    
    # Crear integración
    integration = ARTOIntegration()
    
    # Conectar
    connected = await integration.connect()
    if not connected:
        print("❌ No se pudo conectar con ARTO. Asegúrate de que ARTO esté en ejecución.")
        return
    
    print("✅ Conectado con ARTO")
    
    # Probar con datos de ejemplo
    example_scan = {
        "scan": {
            "timestamp": datetime.now().isoformat(),
            "network": "192.168.1.0/24",
            "total_devices": 3,
            "camera_count": 2,
            "router_count": 1,
            "vulnerable_count": 1
        },
        "targets": [
            {
                "ip": "192.168.1.100",
                "services": [
                    {
                        "port": 80,
                        "service": "http",
                        "banner": "Server: Hikvision Web Server",
                        "device_info": {
                            "vendor": "Hikvision",
                            "type": "Camera",
                            "model": "DS-2CD2043G2-IU",
                            "risk": "high"
                        }
                    }
                ]
            }
        ]
    }
    
    # Procesar con ARTO
    result = await integration.process_scan_results(example_scan)
    
    print("\n" + "="*70)
    print("  📊 RESULTADOS DE ARTO")
    print("="*70)
    
    print(f"\nAnálisis completado: {datetime.now().isoformat()}")
    print(f"Número de objetivos analizados: {len(example_scan.get('targets', []))}")
    
    if "error" in result:
        print(f"\n❌ Error: {result['error']}")
    else:
        print("\n✅ Análisis exitoso")
        for key, value in result.get("arto_analysis", {}).items():
            if key.startswith("risk_"):
                print(f"\n  Riesgo para {key[5:]}:")
                print(f"    {json.dumps(value, indent=4)}")


if __name__ == "__main__":
    asyncio.run(main())
