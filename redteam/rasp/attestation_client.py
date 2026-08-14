import requests
import logging
from typing import Dict, Any, Optional

# Configuración del registrador de eventos
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AttestationClient")

class SourceSealAttestationClient:
    """
    Cliente de atestación en Python de SourceSeal.
    Se utiliza para realizar pruebas de integración y simular flujos de atestación móvil RASP.
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")
        # Almacenamiento local del estado del último reto para facilitar la firma simétrica
        self.last_signature: Optional[str] = None
        self.last_expires_at: Optional[float] = None
        self.last_device_id: Optional[str] = None

    def request_challenge(self, device_id: str) -> str:
        """
        Solicita un reto de atestación (Challenge / Nonce) al servidor de SourceSeal.
        Retorna el nonce generado y guarda internamente la firma asociada para la posterior verificación.
        """
        url = f"{self.server_url}/v1/attestation/challenge"
        payload = {"device_id": device_id}
        
        try:
            logger.info(f"Solicitando reto de atestación al servidor para el dispositivo: {device_id}")
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 201:
                data = response.json()
                challenge = data["challenge"]
                
                # Almacenar el estado de la firma simétrica recibida
                self.last_signature = data["signature"]
                self.last_expires_at = data["expires_at"]
                self.last_device_id = device_id
                
                logger.info(f"Reto recibido con éxito: {challenge[:8]}... Expira en el timestamp: {self.last_expires_at}")
                return challenge
            else:
                logger.error(f"Error del servidor al generar reto. Código: {response.status_code}. Respuesta: {response.text}")
                raise RuntimeError(f"No se pudo obtener el reto del servidor: {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Fallo de conexión HTTP al solicitar reto: {str(e)}")
            raise ConnectionError(f"Error de red al conectar con {url}: {str(e)}")

    def submit_attestation(self, challenge: str, token: str, platform: str) -> Dict[str, Any]:
        """
        Envía las evidencias de atestación del hardware y firmas del reto al servidor central para verificación definitiva.
        Retorna el diccionario con la evaluación final del dispositivo.
        """
        url = f"{self.server_url}/v1/attestation/verify"
        
        # Si no hay firma almacenada que coincida con este flujo, se genera un log de advertencia
        signature = self.last_signature if self.last_signature else ""
        if not signature:
            logger.warning("No se cuenta con una firma local registrada para este reto. Se enviará una firma vacía para testing.")

        payload = {
            "challenge": challenge,
            "token": token,
            "platform": platform,
            "signature": signature
        }
        
        try:
            logger.info(f"Enviando atestación de {platform.upper()} para verificación en el servidor...")
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Verificación completada. Veredicto: {result['device_integrity']}, Risk Score: {result['risk_score']}")
                return result
            elif response.status_code in [400, 403, 408]:
                logger.warning(f"El servidor rechazó la atestación: {response.status_code} - {response.text}")
                return response.json()
            else:
                logger.error(f"Fallo crítico en el servidor. Código: {response.status_code}. Detalle: {response.text}")
                raise RuntimeError(f"Error inesperado del servidor de atestación: {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Fallo de comunicación HTTP al validar atestación: {str(e)}")
            raise ConnectionError(f"Error de red al conectar con {url}: {str(e)}")

    def verify_local(self, rasp_report: Dict[str, Any]) -> bool:
        """
        Realiza una validación puramente local y offline a partir de un reporte RASP provisto por el agente móvil.
        Retorna True si el dispositivo se considera seguro, o False si se detectaron anomalías severas de integridad.
        """
        logger.info("Iniciando análisis y auditoría local del reporte de seguridad RASP.")
        
        # 1. Comprobación directa de la bandera de compromiso
        is_compromised = rasp_report.get("isDeviceCompromised", False)
        if is_compromised:
            logger.error("[Local Check] DISPOSITIVO COMPROMETIDO: El agente móvil reportó compromiso general activo.")
            return False
            
        # 2. Análisis granular de cada uno de los hallazgos reportados
        findings = rasp_report.get("findings", [])
        for finding in findings:
            check_name = finding.get("checkName", "Check Desconocido")
            detected = finding.get("isDetected", False)
            severity = finding.get("severity", "INFO").upper()
            details = finding.get("details", "")
            
            if detected:
                # Alertas de alta severidad causan un rechazo local inmediato
                if severity in ["CRITICAL", "HIGH"]:
                    logger.error(
                        f"[Local Check] AMENAZA DE ALTA SEVERIDAD DETECTADA: {check_name} "
                        f"[{severity}]. Detalles: {details}"
                    )
                    return False
                else:
                    logger.warning(
                        f"[Local Check] Advertencia menor detectada: {check_name} "
                        f"[{severity}]. Detalles: {details}"
                    )
                    
        logger.info("[Local Check] Análisis local finalizado con éxito. El dispositivo se encuentra dentro del rango seguro.")
        return True


# Código ejecutable para demostración o testing manual autónomo
if __name__ == "__main__":
    # Inicialización del cliente apuntando al servidor local por defecto
    client = SourceSealAttestationClient()
    device_mock_id = "device_test_android_secure"
    
    print("\n--- PASO 1: SOLICITAR RETO CRIPTOGRÁFICO ---")
    try:
        # Se simula el llamado del dispositivo móvil pidiendo el nonce
        nonce = client.request_challenge(device_id=device_mock_id)
        print(f"Reto obtenido de forma exitosa: {nonce}")
        
        print("\n--- PASO 2: VERIFICACIÓN LOCAL SIMULADA DE REPORTES RASP ---")
        # Simulación de un reporte RASP seguro del agente móvil
        mock_secure_report = {
            "timestamp": 1782043600000,
            "isDeviceCompromised": False,
            "findings": [
                {"checkName": "Anti-Frida Maps Scan", "isDetected": False, "severity": "CRITICAL", "details": "Limpio"},
                {"checkName": "Anti-Emulator Build Properties", "isDetected": False, "severity": "HIGH", "details": "Limpio"}
            ]
        }
        is_safe = client.verify_local(mock_secure_report)
        print(f"¿Reporte local seguro? {is_safe}")
        
        # Simulación de un reporte RASP comprometido del agente móvil
        mock_compromised_report = {
            "timestamp": 1782043600000,
            "isDeviceCompromised": True,
            "findings": [
                {"checkName": "Anti-Frida Maps Scan", "isDetected": True, "severity": "CRITICAL", "details": "Frida memory match found"}
            ]
        }
        is_safe_compromised = client.verify_local(mock_compromised_report)
        print(f"¿Reporte comprometido local seguro? {is_safe_compromised}")

        print("\n--- PASO 3: ENVIAR ATESTACIÓN DE HARDWARE AL SERVIDOR (SIMULACIÓN DE MODO SEGURO) ---")
        # El dispositivo móvil envía el token obtenido por su API de atestación
        result_secure = client.submit_attestation(
            challenge=nonce,
            token="mock-secure-token-abc-123",
            platform="android"
        )
        print("Resultado del Servidor:", result_secure)
        
    except Exception as ex:
        print(f"Ocurrió un error durante la simulación de integración: {ex}")
        print("Asegúrate de que el servidor 'attestation_server.py' esté activo en http://localhost:8000")
