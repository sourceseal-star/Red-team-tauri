"""Gestión de credenciales - NUNCA versionar con claves reales."""
import os
from cryptography.fernet import Fernet

def generate_key() -> bytes:
    return Fernet.generate_key()

def encrypt_value(value: str, key: bytes = None) -> str:
    key = key or os.getenv("KRAKEN_DB_KEY", "").encode() or generate_key()
    f = Fernet(key if isinstance(key, bytes) else key.encode())
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted: str, key: str = None) -> str:
    key = key or os.getenv("KRAKEN_DB_KEY", "")
    f = Fernet(key.encode() if isinstance(key, str) else key)
    return f.decrypt(encrypted.encode()).decode()
