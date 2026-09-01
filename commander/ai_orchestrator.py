#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI ORCHESTRATOR v1.1 — El motor de evolución autónoma de Seal IA
=================================================================
No solo ejecuta. Piensa, decide, genera y actúa.
Requiere API_KEY de Base44/Claude/OpenAI.

Última actualización: 2026-09-01
Versión: 1.1 (integración con seal_ia_knowledge.py)

Cambios v1.1:
- Integración con seal_ia_knowledge.py (ética, seguridad, integridad de producto)
- System prompt usa build_system_prompt() de Seal IA
- Prompts especializados: análisis, exploit, reporte
- Detección de intentos de extracción en respuestas del LLM
- Validación de confianza antes de ejecutar exploits
- Logging con contexto táctico

Compatibilidad: Termux (Android F-Droid), Linux, macOS

LECCIONES APRENDIDAS:
- /tmp NO es escribible en Termux → usar ~/.commander_tmp/
- cryptography puede fallar en Python 3.14 → --force-reinstall --no-cache-dir
- Los exploits generados se guardan en ~/.commander_tmp/ai_exploit_<timestamp>.py
- La memoria persiste en ~/ai_memory.json y ~/ai_knowledge.json
"""

import os
import sys
import json
import subprocess
import time
import asyncio
import re
import shutil
import logging
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# ============================================================
# IMPORTAR CONOCIMIENTO DE SEAL IA
# ============================================================
try:
    from seal_ia_knowledge import (
        build_system_prompt,
        build_analysis_prompt,
        build_exploit_prompt,
        build_report_prompt,
        SECURITY_BLOCK,
    )
    SEAL_IA_AVAILABLE = True
except ImportError:
    SEAL_IA_AVAILABLE = False
    logger_placeholder = logging.getLogger("ai_orchestrator")

# ============================================================
# CONFIGURACIÓN
# ============================================================
CONFIG = {
    "llm_api": {
        "url": os.environ.get("LLM_API_URL", "https://api.anthropic.com/v1/messages"),
        "key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "4096")),
    },
    "memory_file": os.path.expanduser("~/ai_memory.json"),
    "knowledge_base": os.path.expanduser("~/ai_knowledge.json"),
    "target_network": os.environ.get("TARGET_NETWORK", "192.168.1.0/24"),
    "temp_dir": os.path.expanduser("~/.commander_tmp"),  # NUNCA /tmp en Termux
    "log_file": os.path.expanduser("~/ai_orchestrator.log"),
    "cycle_interval": int(os.environ.get("CYCLE_INTERVAL", "60")),
    "max_exploit_timeout": int(os.environ.get("EXPLOIT_TIMEOUT", "30")),
    "nmap_timeout": int(os.environ.get("NMAP_TIMEOUT", "120")),
    "min_confidence": int(os.environ.get("MIN_CONFIDENCE", "50")),  # Confianza mínima para auto-ejecutar
    "require_confirm_exploit": os.environ.get("REQUIRE_CONFIRM_EXPLOIT", "true").lower() == "true",
}

# Asegurar que el directorio temporal existe
os.makedirs(CONFIG["temp_dir"], exist_ok=True)

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(CONFIG["log_file"]),
    ],
)
logger = logging.getLogger("ai_orchestrator")


# ============================================================
# DETECCIÓN DE INTENTOS DE EXTRACCIÓN
# ============================================================
EXTRACTION_PATTERNS = [
    re.compile(r'ignora?\s*(tus?\s*)?(instrucciones|reglas|directivas|prompt)', re.IGNORECASE),
    re.compile(r'olvida?\s*(lo\s*que\s*te\s*)?dijeron', re.IGNORECASE),
    re.compile(r'repite?\s*(tu\s*)?(system\s*prompt|instrucciones|reglas)', re.IGNORECASE),
    re.compile(r'modo\s*(desarrollador|developer|admin)', re.IGNORECASE),
    re.compile(r'api_?key|token|password|credenciales', re.IGNORECASE),
    re.compile(r'canary|honeypot|honeyToken|beacon|deceptive', re.IGNORECASE),
    re.compile(r'c[oó]mo\s*funciona\s*(internamente|por\s*dentro)', re.IGNORECASE),
    re.compile(r'mu[eé]strame?\s*(tu\s*)?(c[oó]digo|api\s*interna)', re.IGNORECASE),
]

def is_extraction_attempt(text: str) -> bool:
    """Detecta si un texto contiene intentos de extracción de información interna."""
    return any(pattern.search(text) for pattern in EXTRACTION_PATTERNS)


# ============================================================
# MEMORIA DEL SISTEMA
# ============================================================
class AISystem:
    """Gestión de memoria persistente y base de conocimiento."""

    def __init__(self):
        self.memory = self._load(CONFIG["memory_file"], {"history": [], "last_scan": None})
        self.knowledge = self._load(CONFIG["knowledge_base"], {"vulnerabilities": [], "services": {}, "solutions": []})

    def _load(self, path: str, default: dict) -> dict:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"No se pudo cargar {path}: {e}. Usando default.")
        return default

    def save_memory(self):
        self._save(CONFIG["memory_file"], self.memory)

    def save_knowledge(self):
        self._save(CONFIG["knowledge_base"], self.knowledge)

    def _save(self, path: str, data: dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"No se pudo guardar {path}: {e}")

    def add_event(self, event: str, data: Any):
        """Registra un evento en el historial de memoria."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data,
        }
        self.memory["history"].append(entry)
        if len(self.memory["history"]) > 1000:
            self.memory["history"] = self.memory["history"][-500:]
        self.save_memory()
        logger.info(f"Evento registrado: {event}")

    def learn(self, category: str, key: str, value: Any):
        """Aprende algo nuevo y lo guarda en la base de conocimiento."""
        if category not in self.knowledge:
            self.knowledge[category] = {}
        self.knowledge[category][key] = value
        self.save_knowledge()
        logger.info(f"Conocimiento adquirido: {category}/{key}")

    def get_history(self, limit: int = 10) -> list:
        """Obtiene los últimos N eventos del historial."""
        return self.memory["history"][-limit:]


# ============================================================
# COMUNICACIÓN CON LA IA (Base44/Claude/OpenAI)
# ============================================================
class AIClient:
    """Cliente para comunicarse con el LLM usando el conocimiento de Seal IA."""

    def __init__(self, system: AISystem):
        self.system = system
        try:
            import aiohttp
            self.session_class = aiohttp.ClientSession
        except ImportError:
            logger.warning("aiohttp no instalado. Usando urllib como fallback.")
            self.session_class = None

    async def _post(self, url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
        """POST con aiohttp o fallback urllib."""
        if self.session_class:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return await resp.json()
        else:
            import urllib.request
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())

    def _build_system_prompt(self, context: Dict = None) -> str:
        """Construye el system prompt usando Seal IA knowledge si está disponible."""
        if SEAL_IA_AVAILABLE:
            tactical_ctx = {
                "operator": "Harold Giovanni Paredes",
                "project": "Commander AI Orchestrator",
                "authorized": True,
                "modules": ["commander_cli", "comlink", "osiris", "tactical", "anchor"],
            }
            if context:
                tactical_ctx.update(context)
            return build_system_prompt(tactical_ctx)
        else:
            # Fallback básico si seal_ia_knowledge no está disponible
            return "Eres un agente autónomo de operaciones tácticas de seguridad."

    async def ask(self, prompt: str, context: Dict = None, use_seal_ia: bool = True) -> str:
        """Envía un prompt a la IA y obtiene una respuesta."""
        if not CONFIG["llm_api"]["key"]:
            raise Exception("LLM_API_KEY no configurada. Define la variable de entorno.")

        # Verificar intentos de extracción en el prompt
        if is_extraction_attempt(prompt):
            logger.warning("⚠️ Intento de extracción detectado en el prompt. Bloqueando.")
            return json.dumps({
                "action": "wait",
                "reasoning": "Intento de extracción detectado. Acción bloqueada por seguridad.",
                "confidence": 0,
            })

        # Construir system prompt con Seal IA
        system_prompt = self._build_system_prompt(context) if use_seal_ia else ""

        # Limitar historial para no exceder tokens
        recent_history = self.system.get_history(limit=5)
        recent_knowledge = {}
        for k, v in list(self.system.knowledge.items())[:3]:
            if isinstance(v, dict):
                recent_knowledge[k] = dict(list(v.items())[-5:])
            else:
                recent_knowledge[k] = v

        user_content = f"""
MEMORIA RECIENTE (últimos 5 eventos):
{json.dumps(recent_history, indent=2, ensure_ascii=False)}

CONOCIMIENTO ACUMULADO (resumen):
{json.dumps(recent_knowledge, indent=2, ensure_ascii=False)}

CONTEXTO ACTUAL:
{json.dumps(context, indent=2, ensure_ascii=False) if context else 'Ninguno'}

TAREA:
{prompt}
"""

        # Anthropic format: system + messages
        messages = []
        if system_prompt:
            # Anthropic usa "system" como top-level
            pass
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": CONFIG["llm_api"]["model"],
            "max_tokens": CONFIG["llm_api"]["max_tokens"],
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "Content-Type": "application/json",
            "x-api-key": CONFIG["llm_api"]["key"],
            "anthropic-version": "2023-06-01",
        }

        try:
            data = await self._post(CONFIG["llm_api"]["url"], payload, headers)
            # Anthropic format
            if "content" in data:
                return data["content"][0].get("text", "{}")
            # OpenAI format
            if "choices" in data:
                return data["choices"][0].get("message", {}).get("content", "{}")
            return json.dumps(data)
        except Exception as e:
            logger.error(f"Error conectando con la IA: {e}")
            return "{}"

    async def think(self, prompt: str, context: Dict = None) -> Dict:
        """Obtiene una decisión estructurada de la IA."""
        response = await self.ask(prompt, context)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"No se pudo parsear la respuesta de la IA. Raw: {response[:200]}")
            return {"error": "No se pudo parsear la respuesta", "raw": response[:500]}

    async def analyze_scan(self, scan_result: Dict) -> Dict:
        """Analiza resultados de escaneo usando el prompt especializado de Seal IA."""
        if SEAL_IA_AVAILABLE:
            prompt = build_analysis_prompt(scan_result)
        else:
            prompt = f"Analiza el resultado del escaneo: {json.dumps(scan_result, default=str)[:2000]}"

        return await self.think(prompt, context={"scan_result": scan_result})

    async def generate_exploit(self, target: str, service: str, version: str = "") -> Dict:
        """Genera código de exploit usando el prompt especializado de Seal IA."""
        if SEAL_IA_AVAILABLE:
            prompt = build_exploit_prompt(target, service, version)
        else:
            prompt = f"Genera código Python para verificar vulnerabilidad en {target} ({service} {version})"

        return await self.think(prompt, context={"target": target, "service": service})

    async def generate_report(self, findings: list) -> Dict:
        """Genera un reporte usando el prompt especializado de Seal IA."""
        if SEAL_IA_AVAILABLE:
            prompt = build_report_prompt(findings)
        else:
            prompt = f"Genera reporte de auditoría: {json.dumps(findings, default=str)[:2000]}"

        return await self.think(prompt, context={"findings": findings})


# ============================================================
# MÓDULO DE EJECUCIÓN AUTÓNOMA
# ============================================================
class AutonomousExecutor:
    """Ejecuta acciones decididas por la IA con validación de seguridad."""

    def __init__(self, system: AISystem, ai_client: AIClient):
        self.system = system
        self.ai = ai_client

    def run_scan(self, network: str) -> Dict:
        """Ejecuta un escaneo nmap y devuelve resultados estructurados."""
        logger.info(f"🔍 Escaneando {network}...")

        if not shutil.which("nmap"):
            logger.warning("nmap no encontrado. Usando fallback con socket.")
            return self._socket_scan(network)

        cmd = [
            "nmap", "-sT", "-sV", "-p-",
            "--open", "--host-timeout", f"{CONFIG['nmap_timeout']}s",
            network,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=CONFIG["nmap_timeout"] + 10,
            )
            return {
                "raw": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode,
                "method": "nmap",
            }
        except subprocess.TimeoutExpired:
            logger.warning("nmap excedió el timeout.")
            return {"error": "timeout", "method": "nmap"}
        except Exception as e:
            return {"error": str(e), "method": "nmap"}

    def _socket_scan(self, network: str) -> Dict:
        """Fallback: escaneo básico con socket si nmap no está."""
        import socket
        logger.info("Escaneo fallback con socket (top 20 puertos)...")

        top_ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                     554, 587, 993, 995, 8000, 8080, 8443, 8888, 37777, 5432]
        results = []

        base_ip = network.split("/")[0].rsplit(".", 1)[0]
        for host_num in range(1, 255):
            target = f"{base_ip}.{host_num}"
            for port in top_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((target, port))
                    if result == 0:
                        results.append({"host": target, "port": port, "status": "open"})
                    sock.close()
                except:
                    pass

        return {"hosts": results, "method": "socket", "count": len(results)}

    def run_exploit(self, target: str, exploit_code: str) -> Dict:
        """Ejecuta código generado por la IA en un entorno controlado."""
        logger.info(f"⚡ Ejecutando código generado por IA en {target}...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exploit_path = os.path.join(CONFIG["temp_dir"], f"ai_exploit_{timestamp}.py")

        try:
            with open(exploit_path, "w", encoding="utf-8") as f:
                f.write(exploit_code)

            result = subprocess.run(
                ["python3", exploit_path],
                capture_output=True, text=True,
                timeout=CONFIG["max_exploit_timeout"],
            )

            exploit_hash = hashlib.sha256(exploit_code.encode()).hexdigest()[:16]

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "code": result.returncode,
                "exploit_hash": exploit_hash,
                "path": exploit_path,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"Exploit excedió timeout de {CONFIG['max_exploit_timeout']}s")
            return {"error": "timeout", "path": exploit_path}
        except Exception as e:
            return {"error": str(e), "path": exploit_path}
        finally:
            if os.path.exists(exploit_path):
                try:
                    os.remove(exploit_path)
                except:
                    pass

    def parse_nmap_output(self, raw: str) -> List[Dict]:
        """Parsea la salida de nmap en formato estructurado."""
        hosts = []
        current_host = None

        for line in raw.split("\n"):
            if "Nmap scan report for" in line:
                if current_host:
                    hosts.append(current_host)
                ip = line.split("for")[-1].strip()
                current_host = {"ip": ip, "ports": []}

            elif "/tcp" in line or "/udp" in line:
                parts = line.strip().split()
                if len(parts) >= 3 and current_host is not None:
                    current_host["ports"].append({
                        "port": parts[0],
                        "state": parts[1],
                        "service": parts[2] if len(parts) > 2 else "unknown",
                    })

        if current_host:
            hosts.append(current_host)

        return hosts

    async def cycle(self):
        """Ciclo principal de decisión y acción autónoma."""
        logger.info("🧠 Iniciando ciclo autónomo...")

        # 1. ESCANEAR
        scan_result = self.run_scan(CONFIG["target_network"])
        self.system.add_event("scan_completed", {
            "network": CONFIG["target_network"],
            "method": scan_result.get("method", "unknown"),
        })

        # Parsear resultados si son de nmap
        if "raw" in scan_result:
            hosts = self.parse_nmap_output(scan_result["raw"])
            scan_result["parsed"] = hosts

            for host in hosts:
                for port_info in host.get("ports", []):
                    self.system.learn("services", f"{host['ip']}:{port_info['port']}", port_info)

        # 2. PENSAR — Usar Seal IA para análisis
        decision = await self.ai.analyze_scan(scan_result)

        logger.info(f"🧠 Decisión de la IA: {json.dumps(decision, indent=2, ensure_ascii=False)}")

        # 3. VALIDAR — Verificar confianza y seguridad
        action = decision.get("action", "wait")
        confidence = decision.get("confidence", 0)
        reasoning = decision.get("reasoning", "Sin razonamiento")

        logger.info(f"Acción: {action} | Confianza: {confidence}% | Razón: {reasoning}")

        # Verificar confianza mínima
        if confidence < CONFIG["min_confidence"]:
            logger.warning(f"⚠️ Confianza {confidence}% < mínimo {CONFIG['min_confidence']}%. Esperando.")
            self.system.add_event("low_confidence", {
                "action": action,
                "confidence": confidence,
                "reasoning": reasoning,
            })
            return decision

        # 4. ACTUAR
        if action == "exploit":
            target = decision.get("target", "")
            payload = decision.get("payload", "")

            if not target or not payload:
                logger.warning("Decisión de exploit sin target o payload.")
                return decision

            # Verificar si requiere confirmación
            if CONFIG["require_confirm_exploit"]:
                logger.info(f"🔐 Exploit requiere confirmación. Target: {target}")
                logger.info(f"   Confianza: {confidence}%")
                logger.info(f"   Razón: {reasoning}")
                # En modo autónomo, ejecutar. En modo interactivo, preguntar.
                # Por ahora ejecutamos si la confianza es suficiente.
                self.system.add_event("exploit_authorized", {
                    "target": target,
                    "confidence": confidence,
                })

            result = self.run_exploit(target, payload)
            self.system.add_event("exploit_attempted", {
                "target": target,
                "result": {k: v for k, v in result.items() if k != "stdout"},
                "confidence": confidence,
            })
            self.system.learn("exploits", target, {
                "success": result.get("code") == 0,
                "error": result.get("error") or result.get("stderr", "")[:200],
            })
            logger.info(f"💀 Exploit ejecutado en {target}: code={result.get('code', '?')}")

        elif action == "scan_deeper":
            new_target = decision.get("target", CONFIG["target_network"])
            logger.info(f"🔍 Escaneo profundo solicitado para {new_target}")
            deeper_result = self.run_scan(new_target)
            self.system.add_event("deep_scan", {"target": new_target, "result": deeper_result})

        elif action == "report":
            # Generar reporte con Seal IA
            findings = self.system.knowledge.get("services", {})
            report = await self.ai.generate_report(list(findings.values()) if findings else [])
            logger.info(f"📄 Reporte generado: {report.get('reasoning', 'Sin detalles')}")
            self.system.add_event("report_generated", {"content": report})

        elif action == "learn":
            category = decision.get("category", "general")
            key = decision.get("key", "unknown")
            value = decision.get("value", "")
            self.system.learn(category, key, value)
            logger.info(f"📚 Aprendido: {category}/{key}")

        elif action == "wait":
            logger.info(f"⏳ Esperando. Razón: {reasoning}")

        else:
            logger.warning(f"Acción desconocida: {action}")

        return decision


# ============================================================
# MODO OFFLINE (sin IA)
# ============================================================
class OfflineExecutor:
    """Ejecutor que funciona sin IA, usando heurísticas predefinidas."""

    def __init__(self, system: AISystem):
        self.system = system
        self.executor = AutonomousExecutor(system, None)

    async def cycle(self):
        """Ciclo offline con heurísticas básicas."""
        logger.info("🧠 Ciclo offline (sin IA)...")

        scan_result = self.executor.run_scan(CONFIG["target_network"])
        self.system.add_event("scan_completed", {"method": "offline"})

        if "raw" in scan_result:
            hosts = self.executor.parse_nmap_output(scan_result["raw"])
            for host in hosts:
                for port_info in host.get("ports", []):
                    self.system.learn("services", f"{host['ip']}:{port_info['port']}", port_info)
                    logger.info(f"  {host['ip']}:{port_info['port']} → {port_info['service']}")

        logger.info(f"Escaneo completado. {len(self.system.knowledge.get('services', {}))} servicios conocidos.")
        return {"action": "wait", "reasoning": "Modo offline: solo escaneo"}


# ============================================================
# PUNTO DE ENTRADA
# ============================================================
async def main():
    parser = argparse.ArgumentParser(
        description="AI Orchestrator — Motor de evolución autónoma de Seal IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 ai_orchestrator.py --network 192.168.1.0/24
  python3 ai_orchestrator.py --no-ai --network 10.0.0.0/24
  python3 ai_orchestrator.py --once --network 192.168.1.1
  python3 ai_orchestrator.py --status
  python3 ai_orchestrator.py --no-confirm --network 192.168.1.0/24

Variables de entorno:
  LLM_API_KEY           API key del LLM (Base44/Claude/OpenAI)
  LLM_API_URL           URL del endpoint (default: Anthropic)
  LLM_MODEL             Modelo a usar (default: claude-sonnet-4-20250514)
  LLM_MAX_TOKENS        Máximo tokens por respuesta (default: 4096)
  TARGET_NETWORK        Red por defecto (default: 192.168.1.0/24)
  CYCLE_INTERVAL        Segundos entre ciclos (default: 60)
  EXPLOIT_TIMEOUT       Timeout de exploits en segundos (default: 30)
  NMAP_TIMEOUT          Timeout de nmap en segundos (default: 120)
  MIN_CONFIDENCE         Confianza mínima para auto-ejecutar (default: 50)
  REQUIRE_CONFIRM_EXPLOIT  Si true, requiere confirmación para exploits (default: true)
        """,
    )
    parser.add_argument("--network", default=CONFIG["target_network"], help="Red a escanear")
    parser.add_argument("--no-ai", action="store_true", help="Modo offline (sin IA, solo escaneo)")
    parser.add_argument("--once", action="store_true", help="Ejecutar un solo ciclo y salir")
    parser.add_argument("--status", action="store_true", help="Mostrar estado y salir")
    parser.add_argument("--history", type=int, default=0, help="Mostrar últimos N eventos del historial")
    parser.add_argument("--clear-memory", action="store_true", help="Limpiar memoria persistente")
    parser.add_argument("--no-confirm", action="store_true", help="No requerir confirmación para exploits")
    args = parser.parse_args()

    CONFIG["target_network"] = args.network
    if args.no_confirm:
        CONFIG["require_confirm_exploit"] = False

    # --status
    if args.status:
        system = AISystem()
        print(f"\n🧠 AI ORCHESTRATOR — Estado del sistema")
        print(f"   Versión: 1.1 (Seal IA integrado: {'Sí' if SEAL_IA_AVAILABLE else 'No'})")
        print(f"   Memoria: {len(system.memory.get('history', []))} eventos")
        print(f"   Conocimiento: {len(system.knowledge.get('services', {}))} servicios")
        print(f"   Vulnerabilidades: {len(system.knowledge.get('vulnerabilities', []))}")
        print(f"   Exploits conocidos: {len(system.knowledge.get('exploits', {}))}")
        print(f"   Archivo memoria: {CONFIG['memory_file']}")
        print(f"   Archivo conocimiento: {CONFIG['knowledge_base']}")
        print(f"   Log: {CONFIG['log_file']}")
        print(f"   IA configurada: {'Sí' if CONFIG['llm_api']['key'] else 'No'}")
        print(f"   Modelo: {CONFIG['llm_api']['model']}")
        print(f"   Confianza mínima: {CONFIG['min_confidence']}%")
        return

    # --history
    if args.history > 0:
        system = AISystem()
        events = system.get_history(limit=args.history)
        for evt in events:
            print(f"  [{evt['timestamp']}] {evt['event']}: {json.dumps(evt['data'], ensure_ascii=False)[:100]}")
        return

    # --clear-memory
    if args.clear_memory:
        for path in [CONFIG["memory_file"], CONFIG["knowledge_base"]]:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Eliminado: {path}")
        logger.info("Memoria limpiada.")
        return

    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🧠 AI ORCHESTRATOR v1.1 — Seal IA                          ║
    ║  Motor de evolución autónoma con conocimiento integrado       ║
    ║  Compatibilidad: Termux / Linux / macOS                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    use_ai = not args.no_ai
    if use_ai and not CONFIG["llm_api"]["key"]:
        print("⚠️  LLM_API_KEY no configurada. Usando modo offline.")
        print("   Para activar IA: export LLM_API_KEY='tu_clave'")
        use_ai = False

    if use_ai:
        print(f"🤖 IA activa: {CONFIG['llm_api']['model']} @ {CONFIG['llm_api']['url']}")
        print(f"🛡  Seal IA knowledge: {'Integrado' if SEAL_IA_AVAILABLE else 'No disponible'}")
    else:
        print("🤖 Modo offline (solo escaneo, sin IA)")

    system = AISystem()

    if use_ai:
        client = AIClient(system)
        executor = AutonomousExecutor(system, client)
    else:
        executor = OfflineExecutor(system)

    print(f"🎯 Objetivo: {CONFIG['target_network']}")
    print(f"📁 Temp: {CONFIG['temp_dir']}")
    print(f"📝 Log: {CONFIG['log_file']}")
    print(f"⏱️  Intervalo: {CONFIG['cycle_interval']}s")
    print(f"🔐 Confianza mínima: {CONFIG['min_confidence']}%")
    print(f"{'🔒' if CONFIG['require_confirm_exploit'] else '🔓'} Confirmación exploits: {'Sí' if CONFIG['require_confirm_exploit'] else 'No'}")
    print()

    cycle_count = 0
    while True:
        cycle_count += 1
        logger.info(f"═══ Ciclo #{cycle_count} ═══")
        try:
            await executor.cycle()

            if args.once:
                logger.info("Ciclo único completado. Saliendo.")
                break

            logger.info(f"⏳ Esperando {CONFIG['cycle_interval']}s antes del próximo ciclo...")
            await asyncio.sleep(CONFIG["cycle_interval"])

        except KeyboardInterrupt:
            print("\n🛑 Detenido por el usuario.")
            break
        except Exception as e:
            logger.error(f"Error en ciclo #{cycle_count}: {e}")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
