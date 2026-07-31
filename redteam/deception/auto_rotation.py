# -*- coding: utf-8 -*-
"""
=== FILE: deception/auto_rotation.py ===
Módulo de Deception para la Generación y Auto-Rotación Dinámica de Honeytokens.
Provee capacidades automatizadas para crear y rotar cebos (lures) realistas como
JWTs, API Keys, credenciales de AWS y cadenas de conexión de bases de datos, con soporte
para alertas basadas en eventos mediante llamadas a callbacks programables.
"""

import hmac
import hashlib
import base64
import json
import time
import random
import string
import secrets
import threading
from typing import List, Dict, Any, Optional, Callable


class HoneyTokenGenerator:
    """
    Generador de cebos y tokens ficticios (Honeytokens) de alta fidelidad.
    Produce strings realistas para engañar a atacantes que inspeccionan el entorno.
    """
    
    @staticmethod
    def _base64url_encode(payload_bytes: bytes) -> str:
        """
        Codifica bytes en formato Base64URL sin relleno (=), compatible con el estándar JWT.
        """
        return base64.urlsafe_b64encode(payload_bytes).decode('utf-8').rstrip('=')

    def generate_jwt(self, user_id: str = 'attacker_lure') -> str:
        """
        Genera un token JWT sintáctico y semánticamente correcto, firmado de forma simulada.
        """
        secret_key = "sourceseal_deception_hmac_secret_key"
        header = {"alg": "HS256", "typ": "JWT"}
        
        now = int(time.time())
        payload = {
            "sub": user_id,
            "name": "Administrador de Sistemas",
            "role": "SuperAdmin",
            "iss": "sourceseal-internal-iam",
            "aud": "sourceseal-prod-api",
            "iat": now,
            "exp": now + 86400 * 30,  # Vence en 30 días
            "scope": "root system:read system:write admin:all db:backup",
            "cluster_access": "prod-k8s-main"
        }
        
        # Serialización compacta sin espacios innecesarios
        header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
        payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        
        header_b64 = self._base64url_encode(header_json)
        payload_b64 = self._base64url_encode(payload_json)
        
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        signature = hmac.new(secret_key.encode('utf-8'), signing_input, hashlib.sha256).digest()
        signature_b64 = self._base64url_encode(signature)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def generate_api_key(prefix: str = 'sk-') -> str:
        """
        Genera un token API-Key con un formato común (ej. OpenAI, Stripe) altamente codiciado.
        """
        # Prefijo en vivo seguido de 32 o 40 caracteres criptográficamente seguros
        secure_rand = secrets.token_hex(20)
        return f"{prefix}live-{secure_rand}"

    @staticmethod
    def generate_aws_credentials() -> Dict[str, str]:
        """
        Genera un par de credenciales de AWS ficticias (Access Key ID y Secret Access Key).
        Cumple con el formato de expresiones regulares estándar de AWS.
        """
        # AWS Access Key ID: 'AKIA' + 16 caracteres alfanuméricos en mayúsculas
        aws_access_key_id = "AKIA" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
        
        # AWS Secret Access Key: 40 caracteres base64 aleatorios (mayúsculas, minúsculas, números, +, /)
        aws_secret_chars = string.ascii_letters + string.digits + "+/"
        aws_secret_access_key = "".join(random.choices(aws_secret_chars, k=40))
        
        return {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key
        }

    @staticmethod
    def generate_db_connection_string() -> str:
        """
        Genera un connection string realista para bases de datos relacionales y no relacionales.
        Elige de forma aleatoria entre plantillas de PostgreSQL, MongoDB, MySQL y SQL Server.
        """
        db_templates = [
            "postgresql://db_master_admin:{password}@db-prod-primary.sourceseal-internal.net:5432/sourceseal_prod?sslmode=require",
            "mongodb+srv://dba_superuser:{password}@cluster0.private.sourceseal-internal.net/admin?retryWrites=true&w=majority",
            "mysql://deploy_agent:{password}@sql-replica.sourceseal-internal.net:3306/production_billing_db",
            "mssql+pyodbc://sa:{password}@mssql-server-db.sourceseal-internal.net:1433/sensitive_customers?driver=ODBC+Driver+17+for+SQL+Server"
        ]
        
        # Generar una contraseña fuerte simulada para atraer al atacante
        password_chars = string.ascii_letters + string.digits + "@#_-"
        password = "".join(random.choices(password_chars, k=14)) + "!"
        
        template = random.choice(db_templates)
        return template.format(password=password)


class TokenRotationManager:
    """
    Administrador central de Honeytokens. Se encarga de programar la generación,
    invalidación por TTL, rotación masiva programada e integración con callbacks de alerta.
    """
    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        # Diccionario para almacenar tokens activos controlados: { token_value: token_data_dict }
        self.active_tokens: Dict[str, Dict[str, Any]] = {}
        # Callbacks para disparar alertas cuando se consumen/acceden
        self.callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []
        
        self.generator = HoneyTokenGenerator()
        self.lock = threading.Lock()
        
        # Hilo del temporizador de auto-rotación
        self.rotation_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

    def rotate_all(self) -> Dict[str, Any]:
        """
        Invalida todos los tokens actuales (los elimina del mapa activo) y genera
        un conjunto nuevo y fresco de cebos (JWT, API Key, AWS creds, base de datos).
        Retorna los nuevos tokens generados.
        """
        now = time.time()
        expires_at = now + self.default_ttl
        
        with self.lock:
            # Limpiamos el mapa de tokens activos anteriores (invalidación instantánea)
            self.active_tokens.clear()
            
            # Generar nuevos observables de engaño
            jwt_token = self.generator.generate_jwt()
            api_key = self.generator.generate_api_key()
            aws_creds = self.generator.generate_aws_credentials()
            db_conn = self.generator.generate_db_connection_string()
            
            # Registro: JWT
            self.active_tokens[jwt_token] = {
                "type": "JWT",
                "value": jwt_token,
                "created_at": now,
                "expires_at": expires_at,
                "active": True,
                "metadata": {"subject": "attacker_lure", "role": "SuperAdmin"}
            }
            
            # Registro: API-Key
            self.active_tokens[api_key] = {
                "type": "API_KEY",
                "value": api_key,
                "created_at": now,
                "expires_at": expires_at,
                "active": True,
                "metadata": {"prefix": "sk-live-"}
            }
            
            # Registro: AWS ID (almacena relación de secreto para validación)
            aws_id = aws_creds["aws_access_key_id"]
            aws_secret = aws_creds["aws_secret_access_key"]
            self.active_tokens[aws_id] = {
                "type": "AWS_ACCESS_KEY_ID",
                "value": aws_id,
                "associated_secret": aws_secret,
                "created_at": now,
                "expires_at": expires_at,
                "active": True,
                "metadata": {"provider": "AWS"}
            }
            
            # Registro: Connection string
            self.active_tokens[db_conn] = {
                "type": "DB_CONNECTION_STRING",
                "value": db_conn,
                "created_at": now,
                "expires_at": expires_at,
                "active": True,
                "metadata": {"critical": "PII"}
            }
            
            print(f"[TOKEN-ROTATION] Rotación de tokens completada con éxito. TTL: {self.default_ttl}s")
            
            return {
                "jwt": jwt_token,
                "api_key": api_key,
                "aws": aws_creds,
                "db_connection": db_conn
            }

    def schedule_rotation(self, interval_seconds: int = 3600):
        """
        Planifica y arranca el hilo de segundo plano para rotar automáticamente los
        tokens en base a un intervalo de segundos recurrente.
        """
        with self.lock:
            if self.rotation_thread is not None:
                print("[TOKEN-ROTATION] El planificador ya está en ejecución.")
                return
                
            self.stop_event.clear()
            self.rotation_thread = threading.Thread(
                target=self._rotation_worker_loop,
                args=(interval_seconds,),
                name="SourceSeal-TokenRotator",
                daemon=True
            )
            self.rotation_thread.start()

    def stop_rotation(self):
        """
        Apaga y detiene el hilo de auto-rotación de manera segura.
        """
        self.stop_event.set()
        if self.rotation_thread:
            self.rotation_thread.join(timeout=1.5)
            self.rotation_thread = None
        print("[TOKEN-ROTATION] Planificador de rotación detenido de forma segura.")

    def on_token_consumed(self, callback: Callable[[str, str, Dict[str, Any]], None]):
        """
        Permite registrar un callback personalizado para recibir eventos cuando un
        honeytoken sea utilizado, leído o consumido.
        El callback debe admitir parámetros: callback(token_valor, tipo_token, metadatos).
        """
        with self.lock:
            self.callbacks.append(callback)

    def consume_token(self, token_value: str) -> bool:
        """
        Invocado por el sensor del honeypot o analizador de logs cuando detecta el uso de un token.
        Valida si corresponde a un token (activo o expirado) controlado y activa la alerta.
        Retorna True si el token coincidió con la base de cebos registrados.
        """
        now = time.time()
        matched_token = None
        
        with self.lock:
            # 1. Búsqueda por correspondencia exacta de token directo
            if token_value in self.active_tokens:
                matched_token = self.active_tokens[token_value]
            else:
                # 2. Búsqueda por correspondencia interna (ejemplo: si el atacante usó el secret key de AWS)
                for val, token_data in self.active_tokens.items():
                    if token_value == val or token_data.get("associated_secret") == token_value:
                        matched_token = token_data
                        break
                        
            if matched_token:
                is_expired = now > matched_token["expires_at"]
                token_type = matched_token["type"]
                metadata = dict(matched_token["metadata"])
                metadata["expired_use"] = is_expired
                metadata["creation_time"] = matched_token["created_at"]
                
                # Ejecutamos todos los callbacks de alerta registrados
                for callback in self.callbacks:
                    try:
                        callback(token_value, token_type, metadata)
                    except Exception as e:
                        # Prevenimos fallos causados por el manejo externo de alertas
                        print(f"[TOKEN-ROTATION] Error ejecutando callback de consumo de token: {e}")
                return True
                
        return False

    def _rotation_worker_loop(self, interval: int):
        """
        Bucle interno ejecutado por el hilo secundario para realizar la rotación recurrente.
        """
        print(f"[TOKEN-ROTATION] Planificador iniciado. Rotaciones cada {interval}s.")
        # Ejecuta la rotación inicial de inmediato
        try:
            self.rotate_all()
        except Exception as e:
            print(f"[TOKEN-ROTATION] Error en rotación inicial: {e}")
            
        # Espera el intervalo especificado de forma interrumpible usando el event
        while not self.stop_event.wait(interval):
            print("[TOKEN-ROTATION] Ejecutando rotación automática planificada...")
            try:
                self.rotate_all()
            except Exception as e:
                print(f"[TOKEN-ROTATION] Error durante la rotación automática periódica: {e}")
