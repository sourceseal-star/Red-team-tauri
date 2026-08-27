"""
LEVIATHAN CORE ENGINE — Module Manager
=======================================
Stub: el doc LEVIATHAN v3.0 referencia este archivo pero no incluye su
codigo completo. Esto es un esqueleto funcional que carga los modulos
disponibles y permite ejecutarlos. Cuando se tenga el codigo completo
del engine, reemplazar este archivo.

Uso:
    from leviathan_core.core.engine import LeviathanEngine
    engine = LeviathanEngine()
    engine.scan("192.168.1.0/24")
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("leviathan.engine")


class ModuleManager:
    """Carga y registra todos los módulos disponibles."""

    def __init__(self):
        self.scanners = {}
        self.exploiters = {}
        self.analyzers = {}
        self.reporters = {}

    def register_all(self):
        try:
            from leviathan_core.modules.scanners import register_all as register_scanners
            register_scanners(self.scanners)
            logger.info(f"Scanners registrados: {list(self.scanners.keys())}")
        except Exception as e:
            logger.warning(f"No se pudieron cargar scanners: {e}")

        try:
            from leviathan_core.modules.exploiters import register_all as register_exploiters
            register_exploiters(self.exploiters)
            logger.info(f"Exploiters registrados: {list(self.exploiters.keys())}")
        except Exception as e:
            logger.warning(f"No se pudieron cargar exploiters: {e}")

        try:
            from leviathan_core.modules.ai_analyzers import register_all as register_analyzers
            register_analyzers(self.analyzers)
            logger.info(f"AI Analyzers registrados: {list(self.analyzers.keys())}")
        except Exception as e:
            logger.warning(f"No se pudieron cargar AI analyzers: {e}")

        try:
            from leviathan_core.modules.reporters import register_all as register_reporters
            register_reporters(self.reporters)
            logger.info(f"Reporters registrados: {list(self.reporters.keys())}")
        except Exception as e:
            logger.warning(f"No se pudieron cargar reporters: {e}")


class LeviathanEngine:
    """Motor principal del sistema LEVIATHAN."""

    def __init__(self):
        self.manager = ModuleManager()
        self.manager.register_all()

    async def scan(self, target: str, modules: Optional[List[str]] = None) -> Dict[str, Any]:
        results = {}
        scanners = self.manager.scanners
        if modules:
            scanners = {k: v for k, v in scanners.items() if k in modules}

        for name, scanner_class in scanners.items():
            try:
                scanner = scanner_class()
                result = await scanner.scan(target) if asyncio.iscoroutinefunction(scanner.scan) else scanner.scan(target)
                results[name] = result
            except Exception as e:
                logger.error(f"Error en scanner {name}: {e}")
                results[name] = {"error": str(e)}

        return results

    async def generate_report(self, target: str, format: str = "json", context: Optional[Dict] = None) -> Dict[str, Any]:
        reporter_key = f"{format}_reporter"
        if reporter_key not in self.manager.reporters:
            raise ValueError(f"Reporter '{format}' no disponible. Disponibles: {list(self.manager.reporters.keys())}")

        reporter = self.manager.reporters[reporter_key]()
        return reporter.generate(target, context or {})
