# backend/modules/__init__.py
# No importar submódulos aquí — permite que cada consumidor importe lo que necesita
# sin romper todo el paquete si una dependencia (fastapi, httpx) no está disponible.
# Los submódulos se importan explícitamente: from modules.osint_bridge import ...
