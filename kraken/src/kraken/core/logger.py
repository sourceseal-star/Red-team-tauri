"""
Logging estructurado para KRAKEN v3.0.
Soporta formato JSON (para ELK) y texto (para consola/Termux).
"""
import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from pythonjsonlogger import jsonlogger


class KrakenFormatter(logging.Formatter):
    """Formatter personalizado que soporta JSON y texto."""
    
    def __init__(self, fmt="text", **kwargs):
        self.fmt = fmt
        if fmt == "json":
            self._json_formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                json_ensure_ascii=False
            )
        else:
            super().__init__(
                "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
    
    def format(self, record):
        if self.fmt == "json":
            return self._json_formatter.format(record)
        return super().format(record)


# Singleton logger
_logger = None


def logger(name: str = "kraken", log_level: str = "INFO", 
           log_format: str = "text", log_dir: str = None):
    """
    Devuelve un logger configurado.
    
    Args:
        name: Nombre del logger
        log_level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_format: 'json' o 'text'
        log_dir: Directorio de logs (default: ~/.kraken/logs o /var/log/kraken)
    """
    global _logger
    if _logger is not None:
        return _logger
    
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Determinar directorio de logs
    if log_dir is None:
        # En Termux, usar el home del usuario
        if os.path.exists("/data/data/com.termux/files/home"):
            log_dir = os.path.expanduser("~/.kraken/logs")
        else:
            log_dir = "/var/log/kraken"
    
    os.makedirs(log_dir, exist_ok=True)
    
    formatter = KrakenFormatter(fmt=log_format)
    
    # Handler de archivo con rotación
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "kraken.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger_instance.addHandler(file_handler)
    
    # Handler de consola (siempre texto para Termux)
    console_formatter = KrakenFormatter(fmt="text")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger_instance.addHandler(console_handler)
    
    _logger = logger_instance
    return logger_instance


def get_logger():
    """Devuelve el logger actual o crea uno por defecto."""
    global _logger
    if _logger is None:
        return logger()
    return _logger
