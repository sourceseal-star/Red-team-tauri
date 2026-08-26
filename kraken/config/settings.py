import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

class Settings:
    """Configuración centralizada de KRAKEN v3.0."""

    # ============================================================
    # RUTAS
    # ============================================================
    KRAKEN_HOME: Path = Path(os.getenv("KRAKEN_HOME", "/opt/kraken"))
    LOG_DIR: Path = Path(os.getenv("KRAKEN_LOG_DIR", "/var/log/kraken"))
    DATA_DIR: Path = Path(os.getenv("KRAKEN_DATA_DIR", "/var/lib/kraken"))
    CONFIG_DIR: Path = Path(os.getenv("KRAKEN_CONFIG_DIR", str(KRAKEN_HOME / "config")))
    PLUGINS_DIR: Path = Path(os.getenv("KRAKEN_PLUGINS_DIR", str(KRAKEN_HOME / "src" / "kraken" / "plugins")))
    REPORTS_DIR: Path = Path(os.getenv("KRAKEN_REPORTS_DIR", str(DATA_DIR / "reports")))

    # ============================================================
    # ESCANEO
    # ============================================================
    TARGETS: List[str] = os.getenv("KRAKEN_TARGETS", "192.168.1.0/24").split(",")
    SCAN_INTERVAL: int = int(os.getenv("KRAKEN_INTERVAL", "7200"))  # segundos
    MAX_WORKERS: int = int(os.getenv("KRAKEN_WORKERS", "20"))
    SCAN_TIMEOUT: int = int(os.getenv("KRAKEN_SCAN_TIMEOUT", "120"))  # segundos por IP
    DEFAULT_PORTS: str = os.getenv("KRAKEN_PORTS", "21-23,25,53,80,110,135,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017")
    MASSCAN_RATE: int = int(os.getenv("KRAKEN_MASSCAN_RATE", "1000"))  # paquetes por segundo
    NMAP_SCRIPTS: str = os.getenv("KRAKEN_NMAP_SCRIPTS", "vuln,ssh-brute,ftp-anon,smb-enum-shares,http-auth-finder,rtsp-url-brute,mysql-empty-password,pgsql-brute,redis-info,rdp-vuln-ms12-020,snmp-info,http-vuln-*,smb-vuln-*")

    # ============================================================
    # EXPLOTACIÓN
    # ============================================================
    DEFAULT_PASSWORDS: List[tuple] = [
        ("root", "root"), ("admin", "admin"), ("admin", "123456"),
        ("admin", "password"), ("user", "user"), ("root", ""),
        ("admin", "Admin123"), ("support", "support"), ("guest", "guest"),
        ("ubnt", "ubnt"), ("cisco", "cisco"), ("pi", "raspberry"),
        ("administrator", "password"), ("oracle", "oracle"),
        ("test", "test"), ("backup", "backup"), ("db2admin", "db2admin"),
        ("postgres", "postgres"), ("mysql", "mysql"), ("redis", ""),
        ("mongodb", ""), ("elastic", "changeme")
    ]
    EXPLOIT_TIMEOUT: int = int(os.getenv("KRAKEN_EXPLOIT_TIMEOUT", "5"))  # segundos
    MAX_EXPLOIT_ATTEMPTS: int = int(os.getenv("KRAKEN_MAX_EXPLOIT_ATTEMPTS", "3"))

    # ============================================================
    # BASE DE DATOS
    # ============================================================
    DB_TYPE: str = os.getenv("KRAKEN_DB_TYPE", "sqlite")  # sqlite | postgresql
    DB_PATH: str = os.getenv("KRAKEN_DB_PATH", str(DATA_DIR / "kraken.db"))
    DB_KEY: str = os.getenv("KRAKEN_DB_KEY", "cambia_esta_clave_urgente")
    DB_HOST: str = os.getenv("KRAKEN_DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("KRAKEN_DB_PORT", "5432"))
    DB_NAME: str = os.getenv("KRAKEN_DB_NAME", "kraken")
    DB_USER: str = os.getenv("KRAKEN_DB_USER", "kraken")
    DB_PASSWORD: str = os.getenv("KRAKEN_DB_PASSWORD", "kraken123")
    DB_POOL_SIZE: int = int(os.getenv("KRAKEN_DB_POOL_SIZE", "10"))
    DB_ECHO: bool = os.getenv("KRAKEN_DB_ECHO", "False").lower() == "true"

    # ============================================================
    # CACHE
    # ============================================================
    CACHE_TYPE: str = os.getenv("KRAKEN_CACHE_TYPE", "memory")  # memory | redis
    CACHE_EXPIRY: int = int(os.getenv("KRAKEN_CACHE_EXPIRY", "3600"))  # segundos
    REDIS_URL: str = os.getenv("KRAKEN_REDIS_URL", "redis://localhost:6379/0")

    # ============================================================
    # LOGGING
    # ============================================================
    LOG_LEVEL: str = os.getenv("KRAKEN_LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("KRAKEN_LOG_FORMAT", "json")  # json | text
    LOG_MAX_SIZE: int = int(os.getenv("KRAKEN_LOG_MAX_SIZE", "10485760"))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv("KRAKEN_LOG_BACKUP_COUNT", "5"))

    # ============================================================
    # NOTIFICACIONES
    # ============================================================
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    EMAIL_SMTP_SERVER: Optional[str] = os.getenv("EMAIL_SMTP_SERVER")
    EMAIL_SMTP_PORT: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    EMAIL_USERNAME: Optional[str] = os.getenv("EMAIL_USERNAME")
    EMAIL_PASSWORD: Optional[str] = os.getenv("EMAIL_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")
    EMAIL_TO: List[str] = os.getenv("EMAIL_TO", "").split(",")
    WEBHOOK_URLS: List[str] = os.getenv("KRAKEN_WEBHOOK_URLS", "").split(",")

    # ============================================================
    # INTEGRACIONES
    # ============================================================
    SHODAN_API_KEY: Optional[str] = os.getenv("SHODAN_API_KEY")
    CENSYS_API_ID: Optional[str] = os.getenv("CENSYS_API_ID")
    CENSYS_API_SECRET: Optional[str] = os.getenv("CENSYS_API_SECRET")
    VIRUSTOTAL_API_KEY: Optional[str] = os.getenv("VIRUSTOTAL_API_KEY")
    SIEM_WEBHOOK_URL: Optional[str] = os.getenv("SIEM_WEBHOOK_URL")
    SIEM_API_KEY: Optional[str] = os.getenv("SIEM_API_KEY")

    # ============================================================
    # API
    # ============================================================
    API_HOST: str = os.getenv("KRAKEN_API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("KRAKEN_API_PORT", "8000"))
    API_DEBUG: bool = os.getenv("KRAKEN_API_DEBUG", "False").lower() == "true"
    API_AUTH_ENABLED: bool = os.getenv("KRAKEN_API_AUTH_ENABLED", "True").lower() == "true"
    API_USERNAME: str = os.getenv("KRAKEN_API_USERNAME", "admin")
    API_PASSWORD: str = os.getenv("KRAKEN_API_PASSWORD", "kraken123")
    API_SECRET_KEY: str = os.getenv("KRAKEN_API_SECRET_KEY", "super-secret-key-123")

    # ============================================================
    # WEB
    # ============================================================
    WEB_HOST: str = os.getenv("KRAKEN_WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("KRAKEN_WEB_PORT", "8501"))
    WEB_DEBUG: bool = os.getenv("KRAKEN_WEB_DEBUG", "False").lower() == "true"

    # ============================================================
    # SEGURIDAD
    # ============================================================
    ALLOWED_NETWORKS: List[str] = os.getenv("KRAKEN_ALLOWED_NETWORKS", "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12").split(",")
    BLOCKED_IPS: List[str] = os.getenv("KRAKEN_BLOCKED_IPS", "").split(",")
    RATE_LIMIT: int = int(os.getenv("KRAKEN_RATE_LIMIT", "100"))  # peticiones por minuto
    JWT_EXPIRY: int = int(os.getenv("KRAKEN_JWT_EXPIRY", "3600"))  # segundos

    # ============================================================
    # IA / ML
    # ============================================================
    ML_ENABLED: bool = os.getenv("KRAKEN_ML_ENABLED", "True").lower() == "true"
    ML_MODEL_PATH: str = os.getenv("KRAKEN_ML_MODEL_PATH", str(DATA_DIR / "models" / "anomaly_detector.pkl"))
    ML_TRAINING_INTERVAL: int = int(os.getenv("KRAKEN_ML_TRAINING_INTERVAL", "86400"))  # 24 horas

    # ============================================================
    # DOCKER
    # ============================================================
    DOCKER_IMAGE: str = os.getenv("KRAKEN_DOCKER_IMAGE", "kraken:3.0")
    DOCKER_REGISTRY: str = os.getenv("KRAKEN_DOCKER_REGISTRY", "ghcr.io")

    # ============================================================
    # Cargar configuración de YAML (si existe)
    # ============================================================
    def __init__(self):
        config_file = self.CONFIG_DIR / "kraken.yaml"
        if config_file.exists():
            with open(config_file, "r") as f:
                yaml_config = yaml.safe_load(f)
                for key, value in yaml_config.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

    # ============================================================
    # Obtener configuración como singleton
    # ============================================================
    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

# Inicializar
settings = Settings.get_instance()
