import subprocess
from typing import Optional
from kraken.core.exploiter import ExploitPlugin
from kraken.models.exploit import ExploitResult

class SMBExploitPlugin(ExploitPlugin):
    """Plugin para explotación SMB (Null Session, Credenciales por defecto)."""

    def __init__(self):
        super().__init__(
            name="smb_exploit",
            description="Explotación SMB (Null Session, fuerza bruta)",
            author="Sealclient",
            targets=["smb", "netbios-ssn", "microsoft-ds"],
            default_ports=[139, 445]
        )

    def exploit(self, ip: str, port: int, service: str, **kwargs) -> Optional[ExploitResult]:
        settings = kwargs.get("settings")
        if not settings:
            return None

        # 1. Probar Null Session
        cmd = ["smbclient", "-L", f"//{ip}", "-N", "-p", str(port)]
        try:
            result = subprocess.run(
                cmd,
                timeout=settings.EXPLOIT_TIMEOUT,
                capture_output=True,
                text=True
            )
            if "session setup failed" not in result.stderr:
                return ExploitResult(
                    ip=ip,
                    port=port,
                    service=service,
                    plugin=self.name,
                    vulnerability="SMB Null Session (Acceso sin autenticación)",
                    cve="CVE-2000-1200",
                    cvss=8.1,
                    success=True,
                    output="Acceso SMB sin credenciales"
                )
        except: pass

        # 2. Probar credenciales por defecto
        for user, password in settings.DEFAULT_PASSWORDS:
            cmd = [
                "smbclient", "-L", f"//{ip}",
                "-U", f"{user}%{password}",
                "-p", str(port)
            ]
            try:
                result = subprocess.run(
                    cmd,
                    timeout=settings.EXPLOIT_TIMEOUT,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and "session setup ok" in result.stderr:
                    return ExploitResult(
                        ip=ip,
                        port=port,
                        service=service,
                        plugin=self.name,
                        vulnerability=f"SMB Credenciales: {user}/{password}",
                        cve=None,
                        cvss=9.0,
                        success=True,
                        output=f"Acceso SMB con {user}/{password}"
                    )
            except: pass

        return None
