#!/usr/bin/env python3
"""
Punto de entrada para Replit
Inicia OSIRIS (si está configurado) y los conectores
"""

import os
import sys
import subprocess
import asyncio
import time
import logging
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [Replit] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ReplitMain")

def check_osiris_installed():
    """Verificar si OSIRIS está instalado"""
    return os.path.exists("osiris/package.json")

def start_osiris():
    """Iniciar OSIRIS en Replit"""
    logger.info("🚀 Iniciando OSIRIS...")
    
    # Cambiar a directorio de OSIRIS
    os.chdir("osiris")
    
    # Instalar dependencias si es necesario
    if not os.path.exists("node_modules"):
        logger.info("📦 Instalando dependencias de OSIRIS...")
        subprocess.run(["npm", "install"], check=True)
    
    # Iniciar OSIRIS en background
    # En Replit, usamos un proceso en segundo plano
    os.environ["PORT"] = "8000"  # Usar puerto 8000 para OSIRIS en Replit
    os.environ["NEXT_PUBLIC_MAPBOX_TOKEN"] = ""
    os.environ["ALLOW_CORS"] = "true"
    
    # Construir OSIRIS
    subprocess.run(["npm", "run", "build"], check=False)
    
    # Iniciar servidor
    osiris_process = subprocess.Popen(
        ["npm", "start"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Esperar a que OSIRIS inicie
    time.sleep(10)
    
    # Verificar si está funcionando
    try:
        import requests
        response = requests.get("http://localhost:8000/api/status", timeout=5)
        if response.status_code == 200:
            logger.info("✅ OSIRIS iniciado correctamente en puerto 8000")
            return osiris_process
        else:
            logger.warning("⚠️  OSIRIS no respondió correctamente")
    except Exception as e:
        logger.error(f"❌ Error verificando OSIRIS: {e}")
    
    return osiris_process

def start_connectors():
    """Iniciar los conectores"""
    logger.info("🔌 Iniciando conectores...")
    
    # Configurar variables de entorno para los conectores
    os.environ["OSIRIS_URL"] = "http://localhost:8000/api"
    os.environ["SEAL_WS"] = "ws://localhost:8001/ws/alerts"
    
    # Iniciar conector principal en un hilo separado
    import threading
    
    def run_connector():
        import connectors.main_connector
        asyncio.run(connectors.main_connector.main())
    
    connector_thread = threading.Thread(target=run_connector, daemon=True)
    connector_thread.start()
    
    # Iniciar conector de playbooks
    def run_playbook_connector():
        import connectors.playbook_connector
        asyncio.run(connectors.playbook_connector.main())
    
    playbook_thread = threading.Thread(target=run_playbook_connector, daemon=True)
    playbook_thread.start()
    
    # En Replit, las cámaras pueden no funcionar bien
    # Pero intentamos iniciarlo
    def run_camera_connector():
        try:
            import connectors.camera_connector
            asyncio.run(connectors.camera_connector.main())
        except Exception as e:
            logger.warning(f"⚠️  Conector de cámaras no disponible en Replit: {e}")
    
    camera_thread = threading.Thread(target=run_camera_connector, daemon=True)
    camera_thread.start()
    
    logger.info("✅ Conectores iniciados")
    
    return [connector_thread, playbook_thread, camera_thread]

def main():
    """Función principal"""
    logger.info("="*50)
    logger.info("🚀 INICIANDO SOURCESEAL + OSIRIS EN REPLIT")
    logger.info("="*50)
    
    # Verificar e instalar dependencias
    logger.info("📦 Verificando dependencias...")
    
    try:
        import aiohttp
        import websockets
        import opencv
        logger.info("✅ Dependencias Python instaladas")
    except ImportError as e:
        logger.error(f"❌ Falta dependencia: {e}")
        logger.info("Instalando dependencias...")
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
        logger.info("✅ Dependencias instaladas")
    
    # Iniciar OSIRIS
    osiris_process = None
    if check_osiris_installed():
        osiris_process = start_osiris()
    else:
        logger.warning("⚠️  OSIRIS no está instalado. Clona el repositorio primero.")
        logger.info("Para instalar OSIRIS en Replit:")
        logger.info("  1. git clone https://github.com/osiris-org/osiris.git")
        logger.info("  2. cd osiris")
        logger.info("  3. npm install")
        logger.info("  4. Reinicia el Repl")
    
    # Iniciar conectores
    connector_threads = start_connectors()
    
    # Mantener vivo
    try:
        while True:
            time.sleep(60)
            logger.info("💤 Manteniendo vivo...")
    except KeyboardInterrupt:
        logger.info("🛑 Deteniendo servicios...")
        if osiris_process:
            osiris_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
