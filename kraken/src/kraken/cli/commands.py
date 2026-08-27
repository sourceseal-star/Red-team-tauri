import click
import sys
import time
from datetime import datetime
from typing import Optional, List

from kraken.config.settings import settings
from kraken.core.scanner import Scanner
from kraken.core.exploiter import Exploiter
from kraken.core.database import db
from kraken.core.logger import logger
from kraken.services.report import ReportGenerator
from kraken.services.notification import NotificationService
from kraken.services.threat_intel import ThreatIntelligence
from kraken.services.response import ResponseAutomation

# ============================================================
# COMANDOS PRINCIPALES
# ============================================================

@click.group()
@click.option("--config", "-c", type=click.Path(), help="Archivo de configuración YAML")
@click.option("--debug", is_flag=True, help="Modo debug")
@click.pass_context
def cli(ctx, config, debug):
    """KRAKEN v3.0 - Motor de Explotación Autónomo."""
    if debug:
        settings.LOG_LEVEL = "DEBUG"
    if config:
        settings.CONFIG_DIR = config.parent
        settings.__init__()  # Recargar configuración

@cli.command()
@click.option("--target", "-t", multiple=True, required=True, help="Rango(s) de IP a escanear")
@click.option("--workers", "-w", type=int, default=settings.MAX_WORKERS, help="Número de workers")
@click.option("--interval", "-i", type=int, default=settings.SCAN_INTERVAL, help="Intervalo en segundos")
@click.option("--test", is_flag=True, help="Modo prueba (1 escaneo y sale)")
@click.option("--no-cache", is_flag=True, help="Deshabilitar cache")
def scan(target, workers, interval, test, no_cache):
    """Ejecuta un escaneo manual."""
    if no_cache:
        settings.CACHE_EXPIRY = 0

    scanner = Scanner()
    exploiter = Exploiter()
    notification = NotificationService()

    # Actualizar configuración
    settings.MAX_WORKERS = workers
    settings.SCAN_INTERVAL = interval

    logger.info(f"🎯 Iniciando escaneo manual sobre {target}")
    logger.info(f"⚙️  Workers: {workers}, Intervalo: {interval}s")

    start_time = datetime.utcnow()

    for t in target:
        logger.info(f"🔍 Escaneando {t}...")
        hosts = scanner.scan_network(t)

        if hosts:
            logger.info(f"✅ Encontrados {len(hosts)} hosts activos en {t}")

            for host in hosts:
                # Enriquecer con inteligencia de amenazas
                threat_intel = ThreatIntelligence()
                host_data = {
                    "ip": host.ip,
                    "os": host.os,
                    "hostname": host.hostname
                }
                enriched_host = threat_intel.enrich_host_data(host_data)
                if enriched_host.get("reputation") == "malicious":
                    logger.warning(f"🚨 IP maliciosa detectada: {host.ip} (Reputación: {enriched_host.get('reputation')})")
                    # Bloquear automáticamente
                    response = ResponseAutomation()
                    response.block_ip_firewall(host.ip, f"Reputación maliciosa: {enriched_host.get('reputation')}")

                # Guardar host en DB
                host_dict = {
                    "ip": host.ip,
                    "hostname": host.hostname,
                    "os": host.os,
                    "os_family": host.os_family,
                    "os_accuracy": host.os_accuracy,
                    "mac": host.mac,
                    "vendor": host.vendor,
                    "uptime": host.uptime,
                    "total_vulns": len(host.vulnerabilities),
                    "cvss_score": max([v.cvss for v in host.vulnerabilities], default=0.0)
                }
                host_db = db.add_host(host_dict)

                # Guardar puertos
                for port in host.tcp_ports + host.udp_ports:
                    port_dict = {
                        "host_id": host_db.id,
                        "port": port.port,
                        "protocol": port.protocol,
                        "service": port.name,
                        "version": port.version,
                        "product": port.product,
                        "cpe": port.cpe
                    }
                    db.add_port(host_db.id, port_dict)

                # Guardar vulnerabilidades
                for vuln in host.vulnerabilities:
                    vuln_dict = {
                        "host_id": host_db.id,
                        "port_id": None,  # Se actualizará después
                        "port": vuln.port,
                        "service": vuln.service,
                        "script": vuln.script,
                        "output": vuln.output,
                        "cve": vuln.cve,
                        "cvss_score": vuln.cvss,
                        "severity": vuln.severity
                    }
                    db.add_vulnerability(host_db.id, None, vuln_dict)

                # Ejecutar exploits
                exploits = exploiter.exploit_host(host)
                critical_count = 0
                for exploit in exploits:
                    exploit_dict = {
                        "host_id": host_db.id,
                        "port": exploit.port,
                        "service": exploit.service,
                        "plugin": exploit.plugin,
                        "vulnerability": exploit.vulnerability,
                        "cve": exploit.cve,
                        "cvss_score": exploit.cvss,
                        "success": exploit.success,
                        "output": exploit.output
                    }
                    db.add_exploit(host_db.id, exploit_dict)
                    if exploit.success and exploit.cvss >= 8.0:
                        critical_count += 1

                    # Notificar exploits críticos
                    if exploit.success and exploit.cvss >= 9.0:
                        notification.send_critical_alert(
                            f"💀 Exploit exitoso en {host.ip}:{exploit.port}",
                            f"Servicio: {exploit.service}\nVulnerabilidad: {exploit.vulnerability}\nCVSS: {exploit.cvss}"
                        )

                # Guardar log de escaneo
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                db.add_scan_log({
                    "host_id": host_db.id,
                    "target_range": t,
                    "started_at": start_time,
                    "finished_at": end_time,
                    "hosts_found": 1,
                    "exploits_found": len([e for e in exploits if e.success]),
                    "critical_vulns": critical_count,
                    "duration": duration
                })

                logger.info(f"✅ Procesado {host.ip}: {len(host.vulnerabilities)} vulns, {len(exploits)} exploits")
        else:
            logger.warning(f"ℹ️ No se encontraron hosts activos en {t}")

    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"✅ Escaneo completado en {duration:.2f} segundos")

    if test:
        sys.exit(0)

@cli.command()
@click.option("--interval", "-i", type=int, default=settings.SCAN_INTERVAL, help="Intervalo en segundos")
@click.option("--workers", "-w", type=int, default=settings.MAX_WORKERS, help="Número de workers")
def daemon(interval, workers):
    """Ejecuta KRAKEN en modo daemon (persistente)."""
    import signal
    import threading

    # Configuración
    settings.SCAN_INTERVAL = interval
    settings.MAX_WORKERS = workers

    logger.info("🦈 KRAKEN v3.0 Daemon iniciado")
    logger.info(f"📡 Targets: {settings.TARGETS}")
    logger.info(f"⏳ Intervalo: {interval//60} min")
    logger.info(f"⚙️  Workers: {workers}")

    # Manejo de señales
    shutdown_event = threading.Event()

    def signal_handler(sig, frame):
        logger.info(f"🛑 Señal {sig} recibida. Cerrando graceful...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Bucle principal
    scanner = Scanner()
    exploiter = Exploiter()
    notification = NotificationService()
    threat_intel = ThreatIntelligence()
    response = ResponseAutomation()

    while not shutdown_event.is_set():
        start_time = datetime.utcnow()
        logger.info(f"⚡ Iniciando ciclo de escaneo ({start_time.isoformat()})")

        for target in settings.TARGETS:
            if shutdown_event.is_set():
                break

            logger.info(f"🔍 Escaneando {target}...")
            hosts = scanner.scan_network(target)

            if hosts:
                logger.info(f"✅ Encontrados {len(hosts)} hosts activos en {target}")

                for host in hosts:
                    if shutdown_event.is_set():
                        break

                    # Enriquecer con inteligencia de amenazas
                    host_data = {
                        "ip": host.ip,
                        "os": host.os,
                        "hostname": host.hostname
                    }
                    enriched_host = threat_intel.enrich_host_data(host_data)

                    # Automatización de respuestas para IPs maliciosas
                    if enriched_host.get("reputation") == "malicious":
                        response.trigger_response("malicious_ip", {
                            "ip": host.ip,
                            "reputation": enriched_host.get("reputation"),
                            "source": list(enriched_host.get("sources", {}).keys())[0] if enriched_host.get("sources") else "unknown",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                    # Guardar host en DB
                    host_dict = {
                        "ip": host.ip,
                        "hostname": host.hostname,
                        "os": host.os,
                        "os_family": host.os_family,
                        "os_accuracy": host.os_accuracy,
                        "mac": host.mac,
                        "vendor": host.vendor,
                        "uptime": host.uptime,
                        "total_vulns": len(host.vulnerabilities),
                        "cvss_score": max([v.cvss for v in host.vulnerabilities], default=0.0)
                    }
                    host_db = db.add_host(host_dict)

                    # Guardar puertos
                    for port in host.tcp_ports + host.udp_ports:
                        port_dict = {
                            "host_id": host_db.id,
                            "port": port.port,
                            "protocol": port.protocol,
                            "service": port.name,
                            "version": port.version,
                            "product": port.product,
                            "cpe": port.cpe
                        }
                        db.add_port(host_db.id, port_dict)

                    # Guardar vulnerabilidades
                    for vuln in host.vulnerabilities:
                        vuln_dict = {
                            "host_id": host_db.id,
                            "port_id": None,
                            "port": vuln.port,
                            "service": vuln.service,
                            "script": vuln.script,
                            "output": vuln.output,
                            "cve": vuln.cve,
                            "cvss_score": vuln.cvss,
                            "severity": vuln.severity
                        }
                        db.add_vulnerability(host_db.id, None, vuln_dict)

                        # Automatización de respuestas para vulnerabilidades críticas
                        if vuln.cvss >= 9.0:
                            response.trigger_response("critical_vulnerability", {
                                "ip": host.ip,
                                "port": vuln.port,
                                "service": vuln.service,
                                "vulnerability": vuln.script,
                                "cve": vuln.cve,
                                "cvss": vuln.cvss,
                                "timestamp": datetime.utcnow().isoformat()
                            })

                    # Ejecutar exploits
                    exploits = exploiter.exploit_host(host)
                    critical_count = 0
                    for exploit in exploits:
                        exploit_dict = {
                            "host_id": host_db.id,
                            "port": exploit.port,
                            "service": exploit.service,
                            "plugin": exploit.plugin,
                            "vulnerability": exploit.vulnerability,
                            "cve": exploit.cve,
                            "cvss_score": exploit.cvss,
                            "success": exploit.success,
                            "output": exploit.output
                        }
                        db.add_exploit(host_db.id, exploit_dict)

                        if exploit.success:
                            # Automatización de respuestas para exploits exitosos
                            response.trigger_response("successful_exploit", {
                                "ip": host.ip,
                                "port": exploit.port,
                                "service": exploit.service,
                                "plugin": exploit.plugin,
                                "vulnerability": exploit.vulnerability,
                                "cve": exploit.cve,
                                "cvss": exploit.cvss,
                                "timestamp": datetime.utcnow().isoformat()
                            })

                            # Notificar
                            if exploit.cvss >= 7.0:
                                notification.send_exploit_alert(
                                    f"💀 Exploit exitoso en {host.ip}:{exploit.port}",
                                    f"Servicio: {exploit.service}\nVulnerabilidad: {exploit.vulnerability}\nCVSS: {exploit.cvss}\nPlugin: {exploit.plugin}"
                                )

                        if exploit.success and exploit.cvss >= 8.0:
                            critical_count += 1

                    # Guardar log de escaneo
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    db.add_scan_log({
                        "host_id": host_db.id,
                        "target_range": target,
                        "started_at": start_time,
                        "finished_at": end_time,
                        "hosts_found": 1,
                        "exploits_found": len([e for e in exploits if e.success]),
                        "critical_vulns": critical_count,
                        "duration": duration
                    })

                    logger.info(f"✅ Procesado {host.ip}: {len(host.vulnerabilities)} vulns, {len(exploits)} exploits")

            else:
                logger.warning(f"ℹ️ No se encontraron hosts activos en {target}")

        # Limpieza de datos antiguos
        db.cleanup_old_data(days=30)

        # Tiempo restante
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        remaining = max(0, interval - duration)
        logger.info(f"✅ Ciclo completado en {duration:.2f}s. Esperando {remaining:.2f}s...")

        # Esperar (con checks cada 10 segundos)
        for _ in range(int(remaining // 10)):
            if shutdown_event.is_set():
                break
            time.sleep(10)

    logger.info("👋 KRAKEN Daemon detenido")

@cli.command()
@click.option("--days", "-d", type=int, default=7, help="Días de datos a incluir")
@click.option("--format", "-f", type=click.Choice(["pdf", "html", "json"]), default="pdf", help="Formato del informe")
@click.option("--output", "-o", type=click.Path(), help="Ruta de salida (opcional)")
def report(days, format, output):
    """Genera un informe de seguridad."""
    generator = ReportGenerator()

    if format == "json":
        filepath = generator.generate_json_report(days)
    else:
        filepath = generator.generate_report(days, format)

    if filepath:
        if output:
            import shutil
            shutil.copy(filepath, output)
            click.echo(f"✅ Informe generado: {output}")
        else:
            click.echo(f"✅ Informe generado: {filepath}")
    else:
        click.echo("❌ Error generando el informe", err=True)

@cli.command()
def priorities():
    """Muestra los hosts más prioritarios."""
    priorities = db.get_priorities(limit=10)
    click.echo("\n📊 TOP 10 HOSTS PRIORITARIOS (por CVSS):")
    click.echo("-" * 60)
    click.echo(f"{'#':<3} {'IP':<18} {'CVSS':<8} {'Vulns':<8}")
    click.echo("-" * 60)
    for i, (ip, cvss, vulns) in enumerate(priorities, 1):
        click.echo(f"{i:<3} {ip:<18} {cvss:<8.1f} {vulns:<8}")
    click.echo("-" * 60)

@cli.command()
@click.option("--limit", "-l", type=int, default=20, help="Número de exploits a mostrar")
@click.option("--success", "-s", is_flag=True, default=True, help="Solo exploits exitosos")
def exploits(limit, success):
    """Muestra los últimos exploits."""
    exploits = db.get_exploits(limit=limit, success=success)
    if not exploits:
        click.echo("No se encontraron exploits.")
        return

    click.echo(f"\n💀 ÚLTIMOS {limit} EXPLOITS ({'EXITOSOS' if success else 'TODOS'}):")
    click.echo("-" * 80)
    click.echo(f"{'IP':<18} {'Puerto':<8} {'Servicio':<12} {'Vulnerabilidad':<30} {'CVSS':<6} {'Plugin':<15}")
    click.echo("-" * 80)
    for e in exploits:
        severity = "🔴" if e["cvss"] >= 9 else "🟠" if e["cvss"] >= 7 else "🟡" if e["cvss"] >= 4 else "🟢"
        click.echo(f"{e['ip']:<18} {e['port']:<8} {e['service']:<12} {e['vuln'][:28]:<30} {e['cvss']:<6.1f} {e['plugin']:<15} {severity}")
    click.echo("-" * 80)

@cli.command()
@click.option("--days", "-d", type=int, default=7, help="Días de datos")
def stats(days):
    """Muestra estadísticas de escaneos."""
    stats = db.get_scan_stats(days)
    click.echo("\n📈 ESTADÍSTICAS DE ESCANEOS:")
    click.echo("-" * 50)
    click.echo(f"{'Total de Hosts:':<25} {stats.get('total_hosts', 0)}")
    click.echo(f"{'Vulnerabilidades Críticas:':<25} {stats.get('vulnerabilities', {}).get('critical', 0)}")
    click.echo(f"{'Vulnerabilidades Altas:':<25} {stats.get('vulnerabilities', {}).get('high', 0)}")
    click.echo(f"{'Vulnerabilidades Medias:':<25} {stats.get('vulnerabilities', {}).get('medium', 0)}")
    click.echo(f"{'Vulnerabilidades Bajas:':<25} {stats.get('vulnerabilities', {}).get('low', 0)}")
    click.echo(f"{'Exploits Exitosos:':<25} {stats.get('total_exploits', 0)}")
    click.echo(f"{'Período:':<25} {days} días")
    click.echo("-" * 50)

@cli.command()
@click.argument("ip")
@click.option("--reason", "-r", default="Vulnerabilidad detectada", help="Razón del bloqueo")
def block(ip, reason):
    """Bloquea una IP en el firewall."""
    response = ResponseAutomation()
    if response.block_ip_firewall(ip, reason):
        click.echo(f"✅ IP bloqueada: {ip} (Razón: {reason})")
    else:
        click.echo(f"❌ Error bloqueando IP: {ip}", err=True)

@cli.command()
@click.argument("ip")
def unblock(ip):
    """Desbloquea una IP en el firewall."""
    response = ResponseAutomation()
    if response.unblock_ip_firewall(ip):
        click.echo(f"✅ IP desbloqueada: {ip}")
    else:
        click.echo(f"❌ Error desbloqueando IP: {ip}", err=True)

@cli.command()
@click.option("--ip", "-i", help="IP a consultar")
@click.option("--all", "-a", is_flag=True, help="Consultar todas las IPs escaneadas")
def threat_intel(ip, all):
    """Consulta inteligencia de amenazas para una IP."""
    intel = ThreatIntelligence()

    if all:
        session = db.get_session()
        try:
            hosts = session.query(HostDB).all()
            click.echo("\n🔍 CONSULTANDO INTELIGENCIA DE AMENAZAS PARA TODOS LOS HOSTS:")
            click.echo("-" * 60)
            for host in hosts:
                info = intel.get_threat_info(host.ip)
                if info.get("sources"):
                    click.echo(f"\n📌 {host.ip}:")
                    click.echo(f"   Reputación: {info.get('reputation', 'unknown')}")
                    click.echo(f"   Fuentes: {list(info.get('sources', {}).keys())}")
                    if info.get("threats"):
                        click.echo(f"   Amenazas: {len(info.get('threats'))}")
        finally:
            session.close()
    elif ip:
        info = intel.get_threat_info(ip)
        if info.get("sources"):
            click.echo("\n🔍 INFORMACIÓN DE AMENAZAS PARA " + ip)
            click.echo("-" * 60)
            click.echo(f"{'Reputación:':<15} {info.get('reputation', 'unknown')}")
            click.echo(f"{'Fuentes:':<15} {list(info.get('sources', {}).keys())}")
            if info.get("threats"):
                click.echo(f"{'Amenazas:':<15} {len(info.get('threats'))}")
                for threat in info.get("threats", []):
                    click.echo(f"   - {threat.get('type')}: {threat.get('id', threat.get('source', 'unknown'))}")
        else:
            click.echo(f"❌ No se encontró información de amenazas para {ip}")
    else:
        click.echo("❌ Debes especificar --ip o --all")

@cli.command()
def clean():
    """Limpia datos antiguos de la base de datos."""
    click.confirm("¿Estás seguro de que quieres limpiar datos antiguos (más de 30 días)?", abort=True)
    db.cleanup_old_data(days=30)
    click.echo("✅ Datos antiguos limpiados")

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def main():
    """Punto de entrada principal."""
    cli()

if __name__ == "__main__":
    main()
