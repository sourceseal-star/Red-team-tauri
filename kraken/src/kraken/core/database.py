from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.pool import QueuePool
from datetime import datetime
import os

from kraken.config.settings import settings

# Base para modelos
Base = declarative_base()

# ============================================================
# MODELOS
# ============================================================

class HostDB(Base):
    """Modelo de Host en la base de datos."""
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True)
    ip = Column(String(45), unique=True, nullable=False, index=True)
    hostname = Column(String(255))
    os = Column(String(255))
    os_family = Column(String(100))
    os_accuracy = Column(Integer, default=0)
    mac = Column(String(17))
    vendor = Column(String(255))
    uptime = Column(Integer)  # segundos
    last_seen = Column(DateTime, default=datetime.utcnow)
    total_vulns = Column(Integer, default=0)
    cvss_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

    # Relaciones
    ports = relationship("PortDB", back_populates="host", cascade="all, delete-orphan")
    vulnerabilities = relationship("VulnerabilityDB", back_populates="host")
    exploits = relationship("ExploitDB", back_populates="host")
    scan_logs = relationship("ScanLogDB", back_populates="host")

    def __repr__(self):
        return f"<HostDB(ip={self.ip}, os={self.os}, vulns={self.total_vulns})>"

class PortDB(Base):
    """Modelo de Puerto en la base de datos."""
    __tablename__ = "ports"

    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String(10), default="tcp")  # tcp | udp
    service = Column(String(100))
    version = Column(String(100))
    product = Column(String(255))
    cpe = Column(String(255))

    # Relaciones
    host = relationship("HostDB", back_populates="ports")
    vulnerabilities = relationship("VulnerabilityDB", back_populates="port")

    __table_args__ = (
        UniqueConstraint("host_id", "port", "protocol", name="uq_host_port_protocol"),
    )

class VulnerabilityDB(Base):
    """Modelo de Vulnerabilidad en la base de datos."""
    __tablename__ = "vulnerabilities"

    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False)
    port_id = Column(Integer, ForeignKey("ports.id", ondelete="CASCADE"))
    port = Column(Integer, nullable=False)
    service = Column(String(100))
    script = Column(String(100))  # Nombre del script NSE
    output = Column(Text)
    cve = Column(String(50), index=True)
    cvss_score = Column(Float, default=0.0)
    severity = Column(String(20), default="unknown")  # critical, high, medium, low
    detected_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    host = relationship("HostDB", back_populates="vulnerabilities")
    port = relationship("PortDB", back_populates="vulnerabilities")

    def __repr__(self):
        return f"<VulnerabilityDB(host={self.host_id}, port={self.port}, cve={self.cve}, cvss={self.cvss_score})>"

class ExploitDB(Base):
    """Modelo de Exploit en la base de datos."""
    __tablename__ = "exploits"

    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False)
    port = Column(Integer, nullable=False)
    service = Column(String(100))
    plugin = Column(String(100))  # Nombre del plugin
    vulnerability = Column(String(255), nullable=False)
    cve = Column(String(50), index=True)
    cvss_score = Column(Float, default=0.0)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=False)
    output = Column(Text)

    # Relaciones
    host = relationship("HostDB", back_populates="exploits")

    def __repr__(self):
        return f"<ExploitDB(host={self.host_id}, port={self.port}, success={self.success})>"

class ScanLogDB(Base):
    """Modelo de Log de Escaneo en la base de datos."""
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True)
    host_id = Column(Integer, ForeignKey("hosts.id", ondelete="SET NULL"))
    target_range = Column(String(100), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    hosts_found = Column(Integer, default=0)
    exploits_found = Column(Integer, default=0)
    critical_vulns = Column(Integer, default=0)
    duration = Column(Float, default=0.0)  # segundos

    # Relaciones
    host = relationship("HostDB", back_populates="scan_logs")

    def __repr__(self):
        return f"<ScanLogDB(target={self.target_range}, hosts={self.hosts_found}, exploits={self.exploits_found})>"

# ============================================================
# BASE DE DATOS
# ============================================================

class Database:
    """Gestor de base de datos con SQLAlchemy."""

    def __init__(self):
        self.engine = None
        self.Session = None
        self._initialize()

    def _initialize(self):
        """Inicializa la conexión a la base de datos."""
        if settings.DB_TYPE == "postgresql":
            db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        else:  # sqlite
            db_url = f"sqlite:///{settings.DB_PATH}"
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)

        self.engine = create_engine(
            db_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=10,
            pool_pre_ping=True,
            echo=settings.DB_ECHO,
            # Cifrado para SQLite (si sqlcipher está instalado)
            connect_args={"check_same_thread": False} if settings.DB_TYPE == "sqlite" else {}
        )

        # Crear tablas
        Base.metadata.create_all(self.engine)

        # Configurar sesión
        self.Session = scoped_session(
            sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        )

    def get_session(self):
        """Obtiene una sesión de base de datos."""
        return self.Session()

    def close(self):
        """Cierra la conexión."""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()

    def add_host(self, host_data: Dict) -> HostDB:
        """Añade o actualiza un host."""
        session = self.get_session()
        try:
            host = session.query(HostDB).filter_by(ip=host_data["ip"]).first()
            if host:
                # Actualizar
                host.os = host_data.get("os", host.os)
                host.hostname = host_data.get("hostname", host.hostname)
                host.os_family = host_data.get("os_family", host.os_family)
                host.os_accuracy = host_data.get("os_accuracy", host.os_accuracy)
                host.mac = host_data.get("mac", host.mac)
                host.vendor = host_data.get("vendor", host.vendor)
                host.uptime = host_data.get("uptime", host.uptime)
                host.last_seen = datetime.utcnow()
                host.total_vulns = host_data.get("total_vulns", host.total_vulns)
                host.cvss_score = host_data.get("cvss_score", host.cvss_score)
                host.is_active = True
            else:
                # Crear nuevo
                host = HostDB(
                    ip=host_data["ip"],
                    hostname=host_data.get("hostname"),
                    os=host_data.get("os"),
                    os_family=host_data.get("os_family"),
                    os_accuracy=host_data.get("os_accuracy", 0),
                    mac=host_data.get("mac"),
                    vendor=host_data.get("vendor"),
                    uptime=host_data.get("uptime"),
                    total_vulns=host_data.get("total_vulns", 0),
                    cvss_score=host_data.get("cvss_score", 0.0)
                )
                session.add(host)
            session.commit()
            return host
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_port(self, host_id: int, port_data: Dict) -> PortDB:
        """Añade un puerto a un host."""
        session = self.get_session()
        try:
            port = session.query(PortDB).filter_by(
                host_id=host_id,
                port=port_data["port"],
                protocol=port_data.get("protocol", "tcp")
            ).first()
            if port:
                # Actualizar
                port.service = port_data.get("service", port.service)
                port.version = port_data.get("version", port.version)
                port.product = port_data.get("product", port.product)
                port.cpe = port_data.get("cpe", port.cpe)
            else:
                # Crear nuevo
                port = PortDB(
                    host_id=host_id,
                    port=port_data["port"],
                    protocol=port_data.get("protocol", "tcp"),
                    service=port_data.get("service"),
                    version=port_data.get("version"),
                    product=port_data.get("product"),
                    cpe=port_data.get("cpe")
                )
                session.add(port)
            session.commit()
            return port
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_vulnerability(self, host_id: int, port_id: int, vuln_data: Dict) -> VulnerabilityDB:
        """Añade una vulnerabilidad."""
        session = self.get_session()
        try:
            vuln = VulnerabilityDB(
                host_id=host_id,
                port_id=port_id,
                port=vuln_data["port"],
                service=vuln_data.get("service"),
                script=vuln_data.get("script"),
                output=vuln_data.get("output"),
                cve=vuln_data.get("cve"),
                cvss_score=vuln_data.get("cvss_score", 0.0),
                severity=vuln_data.get("severity", "unknown")
            )
            session.add(vuln)
            session.commit()
            return vuln
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_exploit(self, host_id: int, exploit_data: Dict) -> ExploitDB:
        """Añade un intento de exploit."""
        session = self.get_session()
        try:
            exploit = ExploitDB(
                host_id=host_id,
                port=exploit_data["port"],
                service=exploit_data.get("service"),
                plugin=exploit_data.get("plugin"),
                vulnerability=exploit_data["vulnerability"],
                cve=exploit_data.get("cve"),
                cvss_score=exploit_data.get("cvss_score", 0.0),
                success=exploit_data.get("success", False),
                output=exploit_data.get("output")
            )
            session.add(exploit)
            session.commit()
            return exploit
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_scan_log(self, log_data: Dict) -> ScanLogDB:
        """Añade un log de escaneo."""
        session = self.get_session()
        try:
            log = ScanLogDB(
                host_id=log_data.get("host_id"),
                target_range=log_data["target_range"],
                started_at=log_data.get("started_at"),
                finished_at=log_data.get("finished_at"),
                hosts_found=log_data.get("hosts_found", 0),
                exploits_found=log_data.get("exploits_found", 0),
                critical_vulns=log_data.get("critical_vulns", 0),
                duration=log_data.get("duration", 0.0)
            )
            session.add(log)
            session.commit()
            return log
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_priorities(self, limit: int = 10) -> List[Dict]:
        """Obtiene los hosts más prioritarios (por CVSS)."""
        session = self.get_session()
        try:
            query = session.query(
                HostDB.ip,
                HostDB.cvss_score,
                HostDB.total_vulns
            ).filter(
                HostDB.is_active == True
            ).order_by(
                HostDB.cvss_score.desc(),
                HostDB.total_vulns.desc()
            ).limit(limit)
            return [{"ip": ip, "cvss": cvss, "vulns": vulns} for ip, cvss, vulns in query.all()]
        finally:
            session.close()

    def get_host(self, ip: str) -> Optional[HostDB]:
        """Obtiene un host por IP."""
        session = self.get_session()
        try:
            return session.query(HostDB).filter_by(ip=ip).first()
        finally:
            session.close()

    def get_exploits(self, limit: int = 50, success: bool = True) -> List[Dict]:
        """Obtiene los últimos exploits."""
        session = self.get_session()
        try:
            query = session.query(ExploitDB).filter_by(success=success)
            query = query.order_by(ExploitDB.attempted_at.desc()).limit(limit)
            return [{
                "ip": e.host.ip,
                "port": e.port,
                "service": e.service,
                "vuln": e.vulnerability,
                "cvss": e.cvss_score,
                "time": e.attempted_at.isoformat(),
                "plugin": e.plugin
            } for e in query.all()]
        finally:
            session.close()

    def get_vulnerabilities(self, limit: int = 50) -> List[Dict]:
        """Obtiene las últimas vulnerabilidades detectadas."""
        session = self.get_session()
        try:
            query = session.query(VulnerabilityDB)
            query = query.order_by(VulnerabilityDB.detected_at.desc()).limit(limit)
            return [{
                "ip": v.host.ip,
                "port": v.port,
                "service": v.service,
                "cve": v.cve,
                "cvss": v.cvss_score,
                "severity": v.severity,
                "time": v.detected_at.isoformat()
            } for v in query.all()]
        finally:
            session.close()

    def get_scan_stats(self, days: int = 7) -> Dict:
        """Obtiene estadísticas de escaneos."""
        session = self.get_session()
        try:
            from sqlalchemy import func
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Total de hosts
            total_hosts = session.query(HostDB).filter(HostDB.last_seen >= cutoff).count()

            # Total de vulnerabilidades por severidad
            vulns_by_severity = session.query(
                VulnerabilityDB.severity,
                func.count(VulnerabilityDB.id)
            ).filter(
                VulnerabilityDB.detected_at >= cutoff
            ).group_by(VulnerabilityDB.severity).all()

            # Total de exploits exitosos
            total_exploits = session.query(ExploitDB).filter(
                ExploitDB.success == True,
                ExploitDB.attempted_at >= cutoff
            ).count()

            return {
                "total_hosts": total_hosts,
                "vulnerabilities": {sev: count for sev, count in vulns_by_severity},
                "total_exploits": total_exploits,
                "days": days
            }
        finally:
            session.close()

    def cleanup_old_data(self, days: int = 30):
        """Elimina datos antiguos."""
        session = self.get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Eliminar exploits antiguos
            session.query(ExploitDB).filter(ExploitDB.attempted_at < cutoff).delete()

            # Eliminar vulnerabilidades antiguas
            session.query(VulnerabilityDB).filter(VulnerabilityDB.detected_at < cutoff).delete()

            # Eliminar logs de escaneo antiguos
            session.query(ScanLogDB).filter(ScanLogDB.started_at < cutoff).delete()

            # Marcar hosts inactivos
            session.query(HostDB).filter(HostDB.last_seen < cutoff).update(
                {"is_active": False}
            )

            session.commit()
            logger.info(f"🧹 Limpieza de datos: eliminados registros de más de {days} días")
        except Exception as e:
            session.rollback()
            logger.error(f"Error en limpieza de datos: {e}")
        finally:
            session.close()

# Singleton
db = Database()
