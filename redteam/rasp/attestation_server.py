import os
import time
import hmac
import hashlib
import uuid
import logging
import threading
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status, Depends

# Configuración de registro/logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AttestationServer")

app = FastAPI(
    title="SourceSeal RASP Attestation Server",
    description="Servidor de atestación de seguridad móvil y verificación para Android (Play Integrity API) e iOS (DeviceCheck)",
    version="1.0.0"
)

# Llave secreta del servidor para firmas HMAC de retos (Challenge).
# En producción, esto DEBE cargarse desde variables de entorno seguras o un almacén de secretos.
SERVER_SECRET_KEY = os.getenv("SOURCESEAL_SECRET_KEY", "super-secret-sourceseal-key-2026").encode("utf-8")

# El paquete del APK y el Bundle ID de la aplicación para validaciones de integridad de plataforma
EXPECTED_ANDROID_PACKAGE = os.getenv("ANDROID_PACKAGE_NAME", "com.sourceseal.redteam")
EXPECTED_IOS_BUNDLE_ID = os.getenv("IOS_BUNDLE_ID", "com.sourceseal.redteam")

# Almacenamiento en memoria para desafíos activos (Retos / Challenges) con TTL.
# Estructura: { nonce: { "device_id": str, "expires_at": float } }
ACTIVE_CHALLENGES: Dict[str, Dict[str, Any]] = {}
challenges_lock = threading.Lock()

# ==========================================
# MODELOS DE PETICIÓN Y RESPUESTA (PYDANTIC)
# ==========================================

class ChallengeRequest(BaseModel):
    device_id: str = Field(..., description="Identificador único del dispositivo cliente")

class ChallengeResponse(BaseModel):
    challenge: str = Field(..., description="Nonce criptográfico generado para la atestación")
    signature: str = Field(..., description="Firma HMAC del reto realizada por el servidor para verificar su autenticidad")
    expires_at: float = Field(..., description="Timestamp Unix de expiración (TTL de 5 minutos)")

class VerificationRequest(BaseModel):
    challenge: str = Field(..., description="El reto original recibido del servidor")
    token: str = Field(..., description="Token de atestación generado por la plataforma móvil (Play Integrity o DeviceCheck)")
    platform: str = Field(..., description="Plataforma del dispositivo: 'android' o 'ios'")
    signature: str = Field(..., description="Firma HMAC del reto enviada por el cliente")

class VerificationResponse(BaseModel):
    attestation_valid: bool = Field(..., description="True si la atestación y las firmas son válidas y seguras")
    device_integrity: str = Field(..., description="Nivel de integridad detectado (Ej: MEETS_STRONG_INTEGRITY, SECURE, COMPROMISED)")
    risk_score: float = Field(..., description="Nivel de riesgo de 0.0 (seguro) a 10.0 (máximo riesgo)")
    details: str = Field(..., description="Detalles adicionales sobre el estado de verificación")

# ==========================================
# SERVICIOS DE TERCEROS MOCK/PRODUCCIÓN
# ==========================================

def verify_google_play_integrity(token: str, expected_challenge_hash: str) -> Dict[str, Any]:
    """
    Se conecta con la API oficial de Google Play Integrity para descifrar y validar el token.
    Soporta credenciales reales cargadas de un archivo de cuentas de servicio, con fallback seguro para simulaciones.
    """
    google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not google_creds_path:
        logger.warning("GOOGLE_APPLICATION_CREDENTIALS no configurado. Corriendo verificación local de simulación.")
        # Simulación de verificación para desarrollo/test
        # Un token que comience con "mock-compromised" se considerará alterado
        if token.startswith("mock-compromised"):
            return {
                "valid": False,
                "verdict": "FAILED",
                "risk_score": 9.0,
                "details": "Fallo simulado: Dispositivo con Root o Hooking detectado en emulador."
            }
        return {
            "valid": True,
            "verdict": "MEETS_DEVICE_INTEGRITY",
            "risk_score": 0.0,
            "details": "Verificación simulada exitosa (Play Integrity Mock mode)."
        }

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Crear credenciales y el cliente de Play Integrity
        credentials = service_account.Credentials.from_service_account_file(google_creds_path)
        service = build("playintegrity", "v1", credentials=credentials)

        # Decodificar el token enviando la petición a Google
        # El requestHash debe enviarse en Base64 seguro para URL sin relleno
        response = service.integrityToken().decode(
            packageName=EXPECTED_ANDROID_PACKAGE,
            body={"integrityToken": token}
        ).execute()

        payload = response.get("tokenPayloadExternal", {})
        
        # 1. Validar coincidencia de paquete
        app_integrity = payload.get("appIntegrity", {})
        pkg_name = app_integrity.get("packageName")
        if pkg_name != EXPECTED_ANDROID_PACKAGE:
            return {
                "valid": False,
                "verdict": "FAILED_PACKAGE_MISMATCH",
                "risk_score": 10.0,
                "details": f"Diferencia en paquete APK. Esperado: {EXPECTED_ANDROID_PACKAGE}, Recibido: {pkg_name}"
            }

        # 2. Validar coincidencia de Nonce / Challenge
        request_details = payload.get("requestDetails", {})
        received_hash = request_details.get("requestHash")
        # Google Play Integrity retorna el hash del request. Comparamos con el esperado.
        if received_hash != expected_challenge_hash:
            return {
                "valid": False,
                "verdict": "FAILED_CHALLENGE_MISMATCH",
                "risk_score": 10.0,
                "details": f"Firma o reto manipulado. Hash esperado: {expected_challenge_hash}, Recibido: {received_hash}"
            }

        # 3. Evaluar los veredictos de integridad del dispositivo
        device_integrity = payload.get("deviceIntegrity", {})
        verdict_list = device_integrity.get("deviceRecognitionVerdict", [])

        # Clasificación del nivel de riesgo según niveles de Play Integrity
        if "MEETS_STRONG_INTEGRITY" in verdict_list:
            return {"valid": True, "verdict": "MEETS_STRONG_INTEGRITY", "risk_score": 0.0, "details": "Cumple integridad fuerte por hardware (Keystore)."}
        elif "MEETS_DEVICE_INTEGRITY" in verdict_list:
            return {"valid": True, "verdict": "MEETS_DEVICE_INTEGRITY", "risk_score": 1.0, "details": "Dispositivo con ROM de fábrica y cargador de arranque bloqueado."}
        elif "MEETS_BASIC_INTEGRITY" in verdict_list:
            return {"valid": True, "verdict": "MEETS_BASIC_INTEGRITY", "risk_score": 4.0, "details": "El dispositivo cumple integridad básica (posible root ocultado o ROM personalizada básica)."}
        else:
            return {"valid": False, "verdict": "FAILED_HARDWARE_ATTESTATION", "risk_score": 9.5, "details": "El dispositivo falló todos los controles de integridad de Google."}

    except Exception as e:
        logger.error(f"Excepción llamando a Google Play Integrity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fallo en comunicación con servidor de atestación de Google: {str(e)}"
        )


def verify_apple_device_check(token: str) -> Dict[str, Any]:
    """
    Se comunica con el servicio de validación DeviceCheck de Apple utilizando credenciales JWT nativas.
    https://api.devicecheck.apple.com/v1/validate_device_token
    """
    apple_key_id = os.getenv("APPLE_KEY_ID")
    apple_team_id = os.getenv("APPLE_TEAM_ID")
    apple_p8_content = os.getenv("APPLE_P8_KEY_CONTENT") # Contenido de la llave privada .p8
    
    use_sandbox = os.getenv("APPLE_DEVICECHECK_SANDBOX", "true").lower() == "true"
    api_url = (
        "https://api.development.devicecheck.apple.com/v1/validate_device_token"
        if use_sandbox
        else "https://api.devicecheck.apple.com/v1/validate_device_token"
    )

    if not (apple_key_id and apple_team_id and apple_p8_content):
        logger.warning("Credenciales de Apple DeviceCheck incompletas. Corriendo verificación local de simulación.")
        if token.startswith("mock-compromised"):
            return {
                "valid": False,
                "verdict": "FAILED_JAILBREAK",
                "risk_score": 9.5,
                "details": "Simulación: Dispositivo iOS con Jailbreak/Frida o firma modificada."
            }
        return {
            "valid": True,
            "verdict": "SECURE_IOS",
            "risk_score": 0.0,
            "details": "Atestación simulada de DeviceCheck Apple exitosa."
        }

    try:
        import jwt  # PyJWT
        import requests

        # 1. Generar JWT para autenticarse con Apple
        now = int(time.time())
        headers = {
            "alg": "ES256",
            "kid": apple_key_id
        }
        payload = {
            "iss": apple_team_id,
            "iat": now
        }
        
        # Encriptación el token JWT usando la llave privada p8 (curva elíptica)
        client_jwt = jwt.encode(payload, apple_p8_content, algorithm="ES256", headers=headers)

        # 2. Construir cuerpo de petición a Apple
        transaction_id = str(uuid.uuid4())
        request_body = {
            "device_token": token,
            "transaction_id": transaction_id,
            "timestamp": int(now * 1000) # Requerido en milisegundos por Apple
        }

        # 3. Consumir endpoint de validación
        http_headers = {
            "Authorization": f"Bearer {client_jwt}",
            "Content-Type": "application/json"
        }

        response = requests.post(api_url, json=request_body, headers=http_headers, timeout=10)

        if response.status_code == 200:
            # Apple retorna un 200 sin cuerpo de error cuando el token es legítimo
            return {
                "valid": True,
                "verdict": "MEETS_APPLE_INTEGRITY",
                "risk_score": 0.0,
                "details": "Dispositivo iOS verificado formalmente mediante hardware de Apple."
            }
        elif response.status_code == 400:
            return {
                "valid": False,
                "verdict": "BAD_DEVICE_TOKEN",
                "risk_score": 10.0,
                "details": "El token enviado es inválido, expiró o no pertenece al equipo emisor de la app."
            }
        else:
            return {
                "valid": False,
                "verdict": "APPLE_SERVICE_ERROR",
                "risk_score": 5.0,
                "details": f"Respuesta inesperada del servidor de Apple. Código: {response.status_code} - {response.text}"
            }

    except Exception as e:
        logger.error(f"Excepción verificando DeviceCheck de Apple: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fallo de interconexión con Apple DeviceCheck: {str(e)}"
        )


# ==========================================
# ENDPOINTS DE LA API
# ==========================================

@app.post(
    "/v1/attestation/challenge",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Genera un nuevo reto de seguridad móvil (Challenge)",
    description="Genera un nonce criptográfico de un solo uso vinculándolo al ID del dispositivo con expiración estricta de 5 minutos."
)
def generate_challenge(request: ChallengeRequest):
    nonce = hashlib.sha256(f"{uuid.uuid4()}-{time.time()}".encode("utf-8")).hexdigest()
    expires_at = time.time() + 300.0  # TTL de 5 minutos exactos

    # Generación de firma digital simétrica HMAC
    # Firma compuesta por el formato estricto 'nonce:device_id:expires_at'
    message_to_sign = f"{nonce}:{request.device_id}:{expires_at}".encode("utf-8")
    signature = hmac.new(SERVER_SECRET_KEY, message_to_sign, hashlib.sha256).hexdigest()

    # Guardar en almacenamiento volátil
    with challenges_lock:
        # Limpieza rápida de retos viejos
        current_time = time.time()
        expired_keys = [k for k, v in ACTIVE_CHALLENGES.items() if v["expires_at"] < current_time]
        for ek in expired_keys:
            del ACTIVE_CHALLENGES[ek]

        ACTIVE_CHALLENGES[nonce] = {
            "device_id": request.device_id,
            "expires_at": expires_at
        }

    logger.info(f"Reto creado para dispositivo {request.device_id}. Nonce: {nonce[:8]}... Expira: {expires_at}")
    
    return ChallengeResponse(
        challenge=nonce,
        signature=signature,
        expires_at=expires_at
    )


@app.post(
    "/v1/attestation/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Valida la atestación de seguridad e integridad del cliente",
    description="Verifica las firmas HMAC de los retos y valida la autenticidad frente a Play Integrity o DeviceCheck."
)
def verify_attestation(request: VerificationRequest):
    # 1. Validar la procedencia y firma del challenge usando HMAC
    # Extraemos del almacén el reto para verificar contra qué dispositivo se había generado originalmente
    with challenges_lock:
        stored_challenge = ACTIVE_CHALLENGES.get(request.challenge)
        if not stored_challenge:
            logger.warning(f"Intento de verificación con reto no existente o rejugado: {request.challenge[:8]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reto inválido, expirado o ataque de repetición (Replay Attack) detectado."
            )
        
        # Eliminar inmediatamente para prevenir ataques de replay
        del ACTIVE_CHALLENGES[request.challenge]

    device_id = stored_challenge["device_id"]
    expires_at = stored_challenge["expires_at"]

    # Re-calcular y corroborar la firma HMAC enviada por el cliente
    expected_message = f"{request.challenge}:{device_id}:{expires_at}".encode("utf-8")
    recalculated_signature = hmac.new(SERVER_SECRET_KEY, expected_message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(recalculated_signature, request.signature):
        logger.error(f"Firma digital del reto inválida. Recibida: {request.signature}, Esperada: {recalculated_signature}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firma HMAC del reto no coincide. Manipulación en tránsito."
        )

    # 2. Validar ventana de tiempo (TTL)
    if time.time() > expires_at:
        logger.error(f"Reto expirado. Límite de tiempo: {expires_at}, Hora actual: {time.time()}")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="La ventana de tiempo para resolver el reto (5 min) ha expirado."
        )

    # 3. Atestación móvil específica por plataforma
    platform_cleaned = request.platform.lower().strip()
    
    if platform_cleaned == "android":
        # Para Android, Google espera el hash del reto (nonce)
        # El cliente envía el hash SHA256 del challenge al SDK de Play Integrity
        expected_hash = hashlib.sha256(request.challenge.encode("utf-8")).hexdigest()
        result = verify_google_play_integrity(request.token, expected_hash)
        
    elif platform_cleaned == "ios":
        # Para iOS, validamos el hardware token a través de DeviceCheck de Apple
        result = verify_apple_device_check(request.token)
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plataforma de dispositivo '{request.platform}' no soportada."
        )

    logger.info(f"Resultado de verificación [{platform_cleaned.upper()}]: Valido={result['valid']} Verdict={result['verdict']}")

    return VerificationResponse(
        attestation_valid=result["valid"],
        device_integrity=result["verdict"],
        risk_score=result["risk_score"],
        details=result["details"]
    )


# Inicio de servidor opcional si se ejecuta directamente
if __name__ == "__main__":
    import uvicorn
    # Se expone por defecto en puerto 8000
    uvicorn.run("attestation_server:app", host="0.0.0.0", port=8000, reload=True)
