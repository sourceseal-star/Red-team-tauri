from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from typing import List, Dict, Optional
import uvicorn
import time
from datetime import datetime, timedelta
from pydantic import BaseModel
import secrets
import hashlib
from passlib.context import CryptContext

from kraken.config.settings import settings
from kraken.core.database import db
from kraken.core.logger import logger

# ============================================================
# MODELOS PYDANTIC
# ============================================================

class HostResponse(BaseModel):
    ip: str
    hostname: Optional[str]
    os: Optional[str]
    os_family: Optional[str]
    os_accuracy: int
    mac: Optional[str]
    vendor: Optional[str]
    uptime: Optional[int]
    last_seen: str
    total_vulns: int
    cvss_score: float
    is_active: bool

class VulnerabilityResponse(BaseModel):
    ip: str
    port: int
    service: str
    cve: Optional[str]
    cvss_score: float
    severity: str
    detected_at: str

class ExploitResponse(BaseModel):
    ip: str
    port: int
    service: str
    plugin: str
    vulnerability: str
    cve: Optional[str]
    cvss_score: float
    attempted_at: str
    success: bool
    output: Optional[str]

class ScanLogResponse(BaseModel):
    target_range: str
    started_at: str
    finished_at: Optional[str]
    hosts_found: int
    exploits_found: int
    critical_vulns: int
    duration: float

class StatsResponse(BaseModel):
    total_hosts: int
    vulnerabilities: Dict[str, int]
    total_exploits: int
    days: int

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

# ============================================================
# AUTENTICACIÓN
# ============================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBasic()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """Autenticación básica."""
    correct_username = secrets.compare_digest(
        credentials.username,
        settings.API_USERNAME
    )
    correct_password = verify_password(
        credentials.password,
        get_password_hash(settings.API_PASSWORD)  # En producción, guarda el hash en DB
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ============================================================
# WEB SOCKET
# ============================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# ============================================================
# APP FASTAPI
# ============================================================

app = FastAPI(
    title="KRAKEN API v3.0",
    description="API REST para el motor de explotación KRAKEN",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ============================================================
# RUTAS PÚBLICAS
# ============================================================

@app.get("/api/health")
async def health_check():
    """Verifica el estado del servicio."""
    return {"status": "healthy", "version": "3.0.0"}

# ============================================================
# RUTAS PROTEGIDAS
# ============================================================

@app.get("/api/hosts", response_model=List[HostResponse])
async def get_hosts(
    limit: int = 100,
    offset: int = 0,
    active: bool = True,
    username: str = Depends(authenticate)
):
    """Obtiene la lista de hosts."""
    session = db.get_session()
    try:
        query = session.query(HostDB)
        if active:
            query = query.filter(HostDB.is_active == True)
        query = query.order_by(HostDB.last_seen.desc()).limit(limit).offset(offset)
        return [
            HostResponse(
                ip=h.ip,
                hostname=h.hostname,
                os=h.os,
                os_family=h.os_family,
                os_accuracy=h.os_accuracy,
                mac=h.mac,
                vendor=h.vendor,
                uptime=h.uptime,
                last_seen=h.last_seen.isoformat() if h.last_seen else None,
                total_vulns=h.total_vulns,
                cvss_score=h.cvss_score,
                is_active=h.is_active
            ) for h in query.all()
        ]
    finally:
        session.close()

@app.get("/api/hosts/{ip}", response_model=HostResponse)
async def get_host(ip: str, username: str = Depends(authenticate)):
    """Obtiene un host por IP."""
    host = db.get_host(ip)
    if not host:
        raise HTTPException(status_code=404, detail="Host no encontrado")
    return HostResponse(
        ip=host.ip,
        hostname=host.hostname,
        os=host.os,
        os_family=host.os_family,
        os_accuracy=host.os_accuracy,
        mac=host.mac,
        vendor=host.vendor,
        uptime=host.uptime,
        last_seen=host.last_seen.isoformat() if host.last_seen else None,
        total_vulns=host.total_vulns,
        cvss_score=host.cvss_score,
        is_active=host.is_active
    )

@app.get("/api/vulnerabilities", response_model=List[VulnerabilityResponse])
async def get_vulnerabilities(
    limit: int = 50,
    offset: int = 0,
    severity: Optional[str] = None,
    cve: Optional[str] = None,
    username: str = Depends(authenticate)
):
    """Obtiene la lista de vulnerabilidades."""
    session = db.get_session()
    try:
        query = session.query(VulnerabilityDB, HostDB.ip)
        query = query.join(HostDB, VulnerabilityDB.host_id == HostDB.id)
        if severity:
            query = query.filter(VulnerabilityDB.severity == severity)
        if cve:
            query = query.filter(VulnerabilityDB.cve == cve)
        query = query.order_by(VulnerabilityDB.detected_at.desc()).limit(limit).offset(offset)

        results = []
        for vuln, ip in query.all():
            results.append(VulnerabilityResponse(
                ip=ip,
                port=vuln.port,
                service=vuln.service,
                cve=vuln.cve,
                cvss_score=vuln.cvss_score,
                severity=vuln.severity,
                detected_at=vuln.detected_at.isoformat()
            ))
        return results
    finally:
        session.close()

@app.get("/api/exploits", response_model=List[ExploitResponse])
async def get_exploits(
    limit: int = 50,
    offset: int = 0,
    success: bool = True,
    plugin: Optional[str] = None,
    username: str = Depends(authenticate)
):
    """Obtiene la lista de exploits."""
    session = db.get_session()
    try:
        query = session.query(ExploitDB, HostDB.ip)
        query = query.join(HostDB, ExploitDB.host_id == HostDB.id)
        if success is not None:
            query = query.filter(ExploitDB.success == success)
        if plugin:
            query = query.filter(ExploitDB.plugin == plugin)
        query = query.order_by(ExploitDB.attempted_at.desc()).limit(limit).offset(offset)

        results = []
        for exploit, ip in query.all():
            results.append(ExploitResponse(
                ip=ip,
                port=exploit.port,
                service=exploit.service,
                plugin=exploit.plugin,
                vulnerability=exploit.vulnerability,
                cve=exploit.cve,
                cvss_score=exploit.cvss_score,
                attempted_at=exploit.attempted_at.isoformat(),
                success=exploit.success,
                output=exploit.output
            ))
        return results
    finally:
        session.close()

@app.get("/api/scan-logs", response_model=List[ScanLogResponse])
async def get_scan_logs(
    limit: int = 50,
    offset: int = 0,
    username: str = Depends(authenticate)
):
    """Obtiene la lista de logs de escaneo."""
    session = db.get_session()
    try:
        query = session.query(ScanLogDB)
        query = query.order_by(ScanLogDB.started_at.desc()).limit(limit).offset(offset)
        return [
            ScanLogResponse(
                target_range=log.target_range,
                started_at=log.started_at.isoformat(),
                finished_at=log.finished_at.isoformat() if log.finished_at else None,
                hosts_found=log.hosts_found,
                exploits_found=log.exploits_found,
                critical_vulns=log.critical_vulns,
                duration=log.duration
            ) for log in query.all()
        ]
    finally:
        session.close()

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(
    days: int = 7,
    username: str = Depends(authenticate)
):
    """Obtiene estadísticas de escaneos."""
    stats = db.get_scan_stats(days)
    return StatsResponse(**stats)

@app.get("/api/priorities", response_model=List[Dict])
async def get_priorities(
    limit: int = 10,
    username: str = Depends(authenticate)
):
    """Obtiene los hosts más prioritarios."""
    return db.get_priorities(limit)

# ============================================================
# WEB SOCKET (Notificaciones en tiempo real)
# ============================================================

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para notificaciones en tiempo real."""
    await manager.connect(websocket)
    try:
        while True:
            # Esperar mensajes del cliente (no usado por ahora)
            data = await websocket.receive_text()
            # Podríamos procesar comandos aquí
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ============================================================
# RUTAS DE ACCIÓN (Para el daemon)
# ============================================================

@app.post("/api/scan")
async def trigger_scan(
    target: str,
    username: str = Depends(authenticate)
):
    """Dispara un escaneo manual."""
    # En una implementación real, esto añadiría la tarea a una cola
    # Por ahora, solo retornamos un mensaje
    logger.info(f"🎯 Escaneo manual solicitado para: {target}")
    return {"status": "queued", "target": target}

@app.post("/api/block-ip")
async def block_ip(
    ip: str,
    username: str = Depends(authenticate)
):
    """Bloquea una IP en el firewall."""
    # Implementación dependiente del sistema
    logger.warning(f"🚫 Bloqueando IP: {ip}")
    # Ejemplo para iptables:
    # subprocess.run(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"])
    return {"status": "blocked", "ip": ip}

# ============================================================
# SERVIDOR
# ============================================================

def main():
    """Inicia el servidor FastAPI."""
    uvicorn.run(
        "kraken.api.app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()
