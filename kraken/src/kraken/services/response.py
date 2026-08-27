import subprocess
import requests
from typing import Dict, List, Optional
import json

from kraken.config.settings import settings
from kraken.core.logger import logger

class ResponseAutomation:
    """Automatización de respuestas a amenazas."""

    def __init__(self):
        self.siem_webhook_url = settings.SIEM_WEBHOOK_URL
        self.siem_api_key = settings.SIEM_API_KEY

    def block_ip_firewall(self, ip: str, reason: str = "Vulnerabilidad detectada") -> bool:
        """Bloquea una IP en el firewall local (iptables)."""
        if not self._is_valid_ip(ip):
            return False

        try:
            # Verificar si ya está bloqueada
            check_cmd = ["iptables", "-L", "INPUT", "-n", "-v"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            if f" {ip} " in result.stdout:
                logger.info(f"IP {ip} ya está bloqueada")
                return True

            # Bloquear IP
            cmd = [
                "iptables", "-A", "INPUT",
                "-s", ip,
                "-j", "DROP",
                "-m", "comment",
                "--comment", f"KRAKEN: {reason}"
            ]
            subprocess.run(cmd, check=True)

            # Guardar regla persistente (para iptables-persistent)
            if subprocess.run(["which", "iptables-persistent"], capture_output=True).returncode == 0:
                subprocess.run(["netfilter-persistent", "save"])

            logger.warning(f"🚫 IP bloqueada en firewall: {ip} (Razón: {reason})")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error bloqueando IP {ip}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado bloqueando IP {ip}: {e}")
            return False

    def unblock_ip_firewall(self, ip: str) -> bool:
        """Desbloquea una IP en el firewall local."""
        if not self._is_valid_ip(ip):
            return False

        try:
            cmd = ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"]
            subprocess.run(cmd, check=True)

            # Guardar regla persistente
            if subprocess.run(["which", "iptables-persistent"], capture_output=True).returncode == 0:
                subprocess.run(["netfilter-persistent", "save"])

            logger.info(f"✅ IP desbloqueada: {ip}")
            return True
        except Exception as e:
            logger.error(f"Error desbloqueando IP {ip}: {e}")
            return False

    def send_to_siem(self, event: Dict) -> bool:
        """Envía un evento a un SIEM (Elasticsearch, Splunk, etc.)."""
        if not self.siem_webhook_url:
            logger.warning("No se ha configurado SIEM_WEBHOOK_URL")
            return False

        headers = {"Content-Type": "application/json"}
        if self.siem_api_key:
            headers["Authorization"] = f"Bearer {self.siem_api_key}"

        try:
            response = requests.post(
                self.siem_webhook_url,
                headers=headers,
                json=event,
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"📤 Evento enviado a SIEM: {event.get('event_type', 'unknown')}")
                return True
            else:
                logger.error(f"Error enviando a SIEM: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error enviando a SIEM: {e}")
            return False

    def trigger_response(self, event_type: str, data: Dict) -> bool:
        """Dispara una respuesta automática basada en el tipo de evento."""
        actions = {
            "critical_vulnerability": self._handle_critical_vulnerability,
            "successful_exploit": self._handle_successful_exploit,
            "new_host": self._handle_new_host,
            "malicious_ip": self._handle_malicious_ip
        }

        if event_type in actions:
            return actions[event_type](data)
        return False

    def _handle_critical_vulnerability(self, data: Dict) -> bool:
        """Maneja una vulnerabilidad crítica."""
        ip = data.get("ip")
        vulnerability = data.get("vulnerability")
        cvss = data.get("cvss", 0)

        if cvss >= 9.0:
            # Bloquear IP
            self.block_ip_firewall(ip, f"Vulnerabilidad crítica: {vulnerability}")

            # Enviar a SIEM
            event = {
                "event_type": "critical_vulnerability",
                "timestamp": data.get("timestamp", ""),
                "ip": ip,
                "vulnerability": vulnerability,
                "cvss": cvss,
                "action": "blocked",
                "source": "kraken"
            }
            self.send_to_siem(event)

            # Notificar
            logger.warning(f"⚠️ Vulnerabilidad crítica en {ip}: {vulnerability} (CVSS: {cvss})")
            return True
        return False

    def _handle_successful_exploit(self, data: Dict) -> bool:
        """Maneja un exploit exitoso."""
        ip = data.get("ip")
        port = data.get("port")
        plugin = data.get("plugin")
        vulnerability = data.get("vulnerability")

        # Bloquear IP
        self.block_ip_firewall(ip, f"Exploit exitoso: {plugin} - {vulnerability}")

        # Enviar a SIEM
        event = {
            "event_type": "successful_exploit",
            "timestamp": data.get("timestamp", ""),
            "ip": ip,
            "port": port,
            "plugin": plugin,
            "vulnerability": vulnerability,
            "action": "blocked",
            "source": "kraken"
        }
        self.send_to_siem(event)

        logger.warning(f"💀 Exploit exitoso en {ip}:{port} ({plugin}) - {vulnerability}")
        return True

    def _handle_new_host(self, data: Dict) -> bool:
        """Maneja un nuevo host detectado."""
        ip = data.get("ip")
        os_name = data.get("os")

        # Enviar a SIEM
        event = {
            "event_type": "new_host",
            "timestamp": data.get("timestamp", ""),
            "ip": ip,
            "os": os_name,
            "action": "detected",
            "source": "kraken"
        }
        self.send_to_siem(event)

        logger.info(f"🆕 Nuevo host detectado: {ip} ({os_name})")
        return True

    def _handle_malicious_ip(self, data: Dict) -> bool:
        """Maneja una IP maliciosa detectada por inteligencia de amenazas."""
        ip = data.get("ip")
        reputation = data.get("reputation")
        source = data.get("source")

        if reputation == "malicious":
            # Bloquear IP
            self.block_ip_firewall(ip, f"IP maliciosa ({source})")

            # Enviar a SIEM
            event = {
                "event_type": "malicious_ip",
                "timestamp": data.get("timestamp", ""),
                "ip": ip,
                "reputation": reputation,
                "source": source,
                "action": "blocked",
                "source": "kraken"
            }
            self.send_to_siem(event)

            logger.warning(f"🚨 IP maliciosa detectada: {ip} (Fuente: {source})")
            return True
        return False

    def _is_valid_ip(self, ip: str) -> bool:
        """Valida una dirección IP."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except:
            return False
