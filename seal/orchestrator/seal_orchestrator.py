#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEAL ORCHESTRATOR - Orquestador de Operaciones Continuas
====================================================
Sistema de monitoreo continuo y orquestación de operaciones de Red Team.

Capacidades:
- Monitoreo continuo de la red (cada 15 minutos)
- Detección de cambios en dispositivos y servicios
- Alertas en tiempo real
- Ejecución de operaciones programadas
- Integración con ARTO para operaciones autónomas

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 seal_orchestrator.py [--start|--stop|--status]
"""

import asyncio
import json
import sqlite3
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import argparse
import os


# ============================================================
# CONFIGURACIÓN
# ============================================================

class OrchestratorConfig:
    # Base de datos
    DB_PATH = "./seal_orchestrator.db"
    
    # Intervalo de escaneo (segundos)
    SCAN_INTERVAL = 900  # 15 minutos
    
    # Intervalo de alertas (segundos)
    ALERT_INTERVAL = 60  # 1 minuto
    
    # Archivo de estado
    STATE_FILE = "./seal_orchestrator.state"
    
    # Archivo de configuración
    CONFIG_FILE = "./seal_orchestrator.json"
    
    # Log file
    LOG_FILE = "./seal_orchestrator.log"


# ============================================================
# BASE DE DATOS
# ============================================================

def init_db():
    """Inicializa la base de datos."""
    conn = sqlite3.connect(OrchestratorConfig.DB_PATH)
    c = conn.cursor()
    
    # Tabla de dispositivos
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT UNIQUE,
        vendor TEXT,
        type TEXT,
        model TEXT,
        os TEXT,
        risk TEXT,
        ports TEXT,
        services TEXT,
        first_seen TEXT,
        last_seen TEXT,
        last_scan TEXT,
        status TEXT DEFAULT 'active',
        alerts INTEGER DEFAULT 0,
        is_new INTEGER DEFAULT 0
    )''')
    
    # Tabla de alertas
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_ip TEXT,
        alert_type TEXT,
        severity TEXT,
        title TEXT,
        description TEXT,
        evidence TEXT,
        timestamp TEXT,
        resolved INTEGER DEFAULT 0,
        FOREIGN KEY(device_ip) REFERENCES devices(ip)
    )''')
    
    # Tabla de operaciones
    c.execute('''CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_type TEXT,
        target TEXT,
        status TEXT,
        result TEXT,
        timestamp TEXT,
        scheduled_time TEXT
    )''')
    
    # Tabla de configuración
    c.execute('''CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    conn.commit()
    conn.close()


init_db()


# ============================================================
# LOGGING
# ============================================================

class OrchestratorLogger:
    """Logger para el orquestador."""
    
    def __init__(self, log_file: str = OrchestratorConfig.LOG_FILE):
        self.log_file = log_file
    
    def log(self, message: str, level: str = "INFO"):
        """Registra un mensaje."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
        
        print(log_entry.strip())
    
    def info(self, message: str):
        self.log(message, "INFO")
    
    def warning(self, message: str):
        self.log(message, "WARNING")
    
    def error(self, message: str):
        self.log(message, "ERROR")
    
    def success(self, message: str):
        self.log(message, "SUCCESS")


logger = OrchestratorLogger()


# ============================================================
# GESTOR DE ESTADO
# ============================================================

class StateManager:
    """Gestiona el estado del orquestador."""
    
    def __init__(self):
        self.state_file = OrchestratorConfig.STATE_FILE
        self.state = {"running": False, "last_scan": None, "last_alert": None}
    
    def load(self):
        """Carga el estado."""
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except:
            self.state = {"running": False, "last_scan": None, "last_alert": None}
    
    def save(self):
        """Guarda el estado."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)
    
    def set_running(self, running: bool):
        """Establece el estado de ejecución."""
        self.state["running"] = running
        self.state["last_update"] = datetime.now().isoformat()
        self.save()
    
    def update_scan_time(self):
        """Actualiza el tiempo del último escaneo."""
        self.state["last_scan"] = datetime.now().isoformat()
        self.save()
    
    def update_alert_time(self):
        """Actualiza el tiempo de la última alerta."""
        self.state["last_alert"] = datetime.now().isoformat()
        self.save()


# ============================================================
# GESTOR DE DISPOSITIVOS
# ============================================================

class DeviceManager:
    """Gestiona los dispositivos detectados."""
    
    def __init__(self):
        self.db_path = OrchestratorConfig.DB_PATH
    
    def add_device(self, device: Dict) -> bool:
        """Agrega un nuevo dispositivo."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO devices 
                (ip, vendor, type, model, os, risk, ports, services, first_seen, last_seen, last_scan, status, is_new)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    device.get("ip"),
                    device.get("vendor", "Unknown"),
                    device.get("type", "Unknown"),
                    device.get("model", "Unknown"),
                    device.get("os", "Unknown"),
                    device.get("risk", "low"),
                    json.dumps(device.get("ports", [])),
                    json.dumps(device.get("services", [])),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Dispositivo ya existe, actualizar
            c.execute("""UPDATE devices SET 
                vendor = ?, type = ?, model = ?, os = ?, risk = ?, 
                ports = ?, services = ?, last_seen = ?, last_scan = ?, 
                status = 'active', is_new = 0
                WHERE ip = ?""",
                (
                    device.get("vendor", "Unknown"),
                    device.get("type", "Unknown"),
                    device.get("model", "Unknown"),
                    device.get("os", "Unknown"),
                    device.get("risk", "low"),
                    json.dumps(device.get("ports", [])),
                    json.dumps(device.get("services", [])),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    device.get("ip")
                ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al agregar dispositivo: {e}")
            conn.close()
            return False
    
    def update_device(self, ip: str, updates: Dict) -> bool:
        """Actualiza un dispositivo existente."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""UPDATE devices SET 
                vendor = ?, type = ?, model = ?, os = ?, risk = ?, 
                ports = ?, services = ?, last_seen = ?, last_scan = ?
                WHERE ip = ?""",
                (
                    updates.get("vendor", "Unknown"),
                    updates.get("type", "Unknown"),
                    updates.get("model", "Unknown"),
                    updates.get("os", "Unknown"),
                    updates.get("risk", "low"),
                    json.dumps(updates.get("ports", [])),
                    json.dumps(updates.get("services", [])),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    ip
                ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al actualizar dispositivo: {e}")
            conn.close()
            return False
    
    def mark_device_inactive(self, ip: str) -> bool:
        """Marca un dispositivo como inactivo."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("UPDATE devices SET status = 'inactive' WHERE ip = ?", (ip,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al marcar dispositivo como inactivo: {e}")
            conn.close()
            return False
    
    def get_device(self, ip: str) -> Optional[Dict]:
        """Obtiene un dispositivo por IP."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM devices WHERE ip = ?", (ip,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "ip": row[1],
                "vendor": row[2],
                "type": row[3],
                "model": row[4],
                "os": row[5],
                "risk": row[6],
                "ports": json.loads(row[7]) if row[7] else [],
                "services": json.loads(row[8]) if row[8] else [],
                "first_seen": row[9],
                "last_seen": row[10],
                "last_scan": row[11],
                "status": row[12],
                "alerts": row[13],
                "is_new": bool(row[14])
            }
        return None
    
    def get_all_devices(self, status: str = None) -> List[Dict]:
        """Obtiene todos los dispositivos."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if status:
            c.execute("SELECT * FROM devices WHERE status = ?", (status,))
        else:
            c.execute("SELECT * FROM devices")
        
        rows = c.fetchall()
        conn.close()
        
        devices = []
        for row in rows:
            devices.append({
                "id": row[0],
                "ip": row[1],
                "vendor": row[2],
                "type": row[3],
                "model": row[4],
                "os": row[5],
                "risk": row[6],
                "ports": json.loads(row[7]) if row[7] else [],
                "services": json.loads(row[8]) if row[8] else [],
                "first_seen": row[9],
                "last_seen": row[10],
                "last_scan": row[11],
                "status": row[12],
                "alerts": row[13],
                "is_new": bool(row[14])
            })
        
        return devices
    
    def get_new_devices(self) -> List[Dict]:
        """Obtiene dispositivos nuevos (no escaneados antes)."""
        return [d for d in self.get_all_devices() if d.get("is_new", False)]
    
    def get_active_devices(self) -> List[Dict]:
        """Obtiene dispositivos activos."""
        return [d for d in self.get_all_devices() if d.get("status") == "active"]
    
    def get_inactive_devices(self) -> List[Dict]:
        """Obtiene dispositivos inactivos."""
        return [d for d in self.get_all_devices() if d.get("status") == "inactive"]
    
    def get_high_risk_devices(self) -> List[Dict]:
        """Obtiene dispositivos de alto riesgo."""
        return [d for d in self.get_all_devices() if d.get("risk") in ["high", "critical"]]


# ============================================================
# GESTOR DE ALERTAS
# ============================================================

class AlertManager:
    """Gestiona las alertas del sistema."""
    
    def __init__(self):
        self.db_path = OrchestratorConfig.DB_PATH
    
    def add_alert(self, alert: Dict) -> bool:
        """Agrega una nueva alerta."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO alerts 
                (device_ip, alert_type, severity, title, description, evidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert.get("device_ip"),
                    alert.get("alert_type"),
                    alert.get("severity", "info"),
                    alert.get("title"),
                    alert.get("description"),
                    json.dumps(alert.get("evidence", {})),
                    datetime.now().isoformat()
                ))
            conn.commit()
            
            # Incrementar contador de alertas del dispositivo
            c.execute("UPDATE devices SET alerts = alerts + 1 WHERE ip = ?", 
                     (alert.get("device_ip"),))
            conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al agregar alerta: {e}")
            conn.close()
            return False
    
    def get_alerts(self, device_ip: str = None, severity: str = None, 
                   resolved: bool = None, limit: int = 100) -> List[Dict]:
        """Obtiene alertas."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query = "SELECT * FROM alerts"
        params = []
        
        if device_ip:
            query += " WHERE device_ip = ?"
            params.append(device_ip)
        
        if severity:
            if "WHERE" in query:
                query += " AND severity = ?"
            else:
                query += " WHERE severity = ?"
            params.append(severity)
        
        if resolved is not None:
            if "WHERE" in query:
                query += " AND resolved = ?"
            else:
                query += " WHERE resolved = ?"
            params.append(1 if resolved else 0)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": row[0],
                "device_ip": row[1],
                "alert_type": row[2],
                "severity": row[3],
                "title": row[4],
                "description": row[5],
                "evidence": json.loads(row[6]) if row[6] else {},
                "timestamp": row[7],
                "resolved": bool(row[8])
            })
        
        return alerts
    
    def resolve_alert(self, alert_id: int) -> bool:
        """Marca una alerta como resuelta."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al resolver alerta: {e}")
            conn.close()
            return False
    
    def get_unresolved_alerts(self) -> List[Dict]:
        """Obtiene alertas no resueltas."""
        return self.get_alerts(resolved=False)


# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================

class SealOrchestrator:
    """Orquestador principal."""
    
    def __init__(self):
        self.device_manager = DeviceManager()
        self.alert_manager = AlertManager()
        self.state_manager = StateManager()
        self.running = False
        self.scan_task = None
        self.alert_task = None
        
        # Cargar estado
        self.state_manager.load()
        
        # Configuración
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Carga la configuración."""
        try:
            with open(OrchestratorConfig.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {
                "scan_interval": OrchestratorConfig.SCAN_INTERVAL,
                "alert_interval": OrchestratorConfig.ALERT_INTERVAL,
                "network": "192.168.1.0/24",
                "auto_scan": True,
                "auto_alert": True
            }
    
    def _save_config(self):
        """Guarda la configuración."""
        with open(OrchestratorConfig.CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    async def start(self):
        """Inicia el orquestador."""
        if self.running:
            logger.warning("El orquestador ya está en ejecución")
            return
        
        logger.info("Iniciando SEAL Orchestrator...")
        
        # Marcar como en ejecución
        self.running = True
        self.state_manager.set_running(True)
        
        # Iniciar tareas
        self.scan_task = asyncio.create_task(self._scan_loop())
        self.alert_task = asyncio.create_task(self._alert_loop())
        
        logger.success("SEAL Orchestrator iniciado")
    
    async def stop(self):
        """Detiene el orquestador."""
        if not self.running:
            logger.warning("El orquestador no está en ejecución")
            return
        
        logger.info("Deteniendo SEAL Orchestrator...")
        
        # Cancelar tareas
        if self.scan_task:
            self.scan_task.cancel()
        if self.alert_task:
            self.alert_task.cancel()
        
        # Marcar como detenido
        self.running = False
        self.state_manager.set_running(False)
        
        logger.success("SEAL Orchestrator detenido")
    
    async def _scan_loop(self):
        """Bucle de escaneo."""
        logger.info(f"Iniciando bucle de escaneo (intervalo: {self.config['scan_interval']}s)")
        
        while self.running:
            try:
                logger.info("Iniciando escaneo de red...")
                
                # Importar escáner
                from seal.scanners.network_sweep_ultimate import (
                    discover_active_ips, scan_target
                )
                
                # Escanear IPs activas
                active_ips = await discover_active_ips(self.config["network"])
                logger.info(f"IPs activas encontradas: {len(active_ips)}")
                
                # Escanear cada IP
                for ip in active_ips:
                    target_data = await scan_target(ip)
                    
                    # Verificar si el dispositivo ya existe
                    existing_device = self.device_manager.get_device(ip)
                    
                    if existing_device:
                        # Actualizar dispositivo
                        updates = {
                            "vendor": target_data.get("info", {}).get("vendor", "Unknown"),
                            "type": target_data.get("info", {}).get("type", "Unknown"),
                            "model": target_data.get("info", {}).get("model", "Unknown"),
                            "os": target_data.get("info", {}).get("os", "Unknown"),
                            "risk": target_data.get("info", {}).get("risk", "low"),
                            "ports": [s.get("port") for s in target_data.get("services", [])],
                            "services": [s.get("service") for s in target_data.get("services", [])]
                        }
                        self.device_manager.update_device(ip, updates)
                        
                        # Verificar cambios
                        self._check_changes(existing_device, target_data)
                    else:
                        # Nuevo dispositivo
                        device = {
                            "ip": ip,
                            "vendor": target_data.get("info", {}).get("vendor", "Unknown"),
                            "type": target_data.get("info", {}).get("type", "Unknown"),
                            "model": target_data.get("info", {}).get("model", "Unknown"),
                            "os": target_data.get("info", {}).get("os", "Unknown"),
                            "risk": target_data.get("info", {}).get("risk", "low"),
                            "ports": [s.get("port") for s in target_data.get("services", [])],
                            "services": [s.get("service") for s in target_data.get("services", [])]
                        }
                        self.device_manager.add_device(device)
                        
                        # Alerta de nuevo dispositivo
                        self.alert_manager.add_alert({
                            "device_ip": ip,
                            "alert_type": "new_device",
                            "severity": "info",
                            "title": f"Nuevo dispositivo detectado: {ip}",
                            "description": f"Se ha detectado un nuevo dispositivo en la red: {ip}",
                            "evidence": {
                                "vendor": device["vendor"],
                                "type": device["type"],
                                "model": device["model"]
                            }
                        })
                        
                        logger.info(f"Nuevo dispositivo detectado: {ip}")
                
                # Marcar dispositivos no vistos como inactivos
                self._mark_inactive_devices(active_ips)
                
                # Actualizar tiempo de escaneo
                self.state_manager.update_scan_time()
                logger.info("Escaneo completado")
                
            except Exception as e:
                logger.error(f"Error en bucle de escaneo: {e}")
            
            # Esperar al próximo escaneo
            await asyncio.sleep(self.config["scan_interval"])
    
    async def _alert_loop(self):
        """Bucle de alertas."""
        logger.info(f"Iniciando bucle de alertas (intervalo: {self.config['alert_interval']}s)")
        
        while self.running:
            try:
                # Verificar alertas no resueltas
                unresolved_alerts = self.alert_manager.get_unresolved_alerts()
                
                if unresolved_alerts:
                    logger.warning(f"Hay {len(unresolved_alerts)} alertas no resueltas")
                    for alert in unresolved_alerts:
                        logger.warning(f"  - {alert['title']} ({alert['severity'].upper()})")
                
                # Actualizar tiempo de alerta
                self.state_manager.update_alert_time()
                
            except Exception as e:
                logger.error(f"Error en bucle de alertas: {e}")
            
            # Esperar al próximo chequeo
            await asyncio.sleep(self.config["alert_interval"])
    
    def _check_changes(self, existing_device: Dict, new_data: Dict):
        """Verifica cambios en un dispositivo."""
        changes = []
        
        # Comparar vendor
        if existing_device.get("vendor") != new_data.get("info", {}).get("vendor"):
            changes.append({
                "field": "vendor",
                "old": existing_device.get("vendor"),
                "new": new_data.get("info", {}).get("vendor")
            })
        
        # Comparar tipo
        if existing_device.get("type") != new_data.get("info", {}).get("type"):
            changes.append({
                "field": "type",
                "old": existing_device.get("type"),
                "new": new_data.get("info", {}).get("type")
            })
        
        # Comparar puertos
        existing_ports = set(existing_device.get("ports", []))
        new_ports = set(s.get("port") for s in new_data.get("services", []))
        
        if existing_ports != new_ports:
            added_ports = list(new_ports - existing_ports)
            removed_ports = list(existing_ports - new_ports)
            
            if added_ports:
                changes.append({
                    "field": "ports",
                    "type": "added",
                    "value": added_ports
                })
            if removed_ports:
                changes.append({
                    "field": "ports",
                    "type": "removed",
                    "value": removed_ports
                })
        
        # Comparar riesgo
        if existing_device.get("risk") != new_data.get("info", {}).get("risk"):
            changes.append({
                "field": "risk",
                "old": existing_device.get("risk"),
                "new": new_data.get("info", {}).get("risk")
            })
        
        # Si hay cambios, generar alerta
        if changes:
            self.alert_manager.add_alert({
                "device_ip": existing_device.get("ip"),
                "alert_type": "device_changed",
                "severity": "warning",
                "title": f"Cambios detectados en {existing_device.get('ip')}",
                "description": f"Se han detectado cambios en el dispositivo {existing_device.get('ip')}",
                "evidence": {"changes": changes}
            })
            
            logger.info(f"Cambios detectados en {existing_device.get('ip')}: {len(changes)} cambios")
    
    def _mark_inactive_devices(self, active_ips: List[str]):
        """Marca dispositivos no vistos como inactivos."""
        all_devices = self.device_manager.get_active_devices()
        
        for device in all_devices:
            if device.get("ip") not in active_ips:
                self.device_manager.mark_device_inactive(device.get("ip"))
                
                # Alerta de dispositivo inactivo
                self.alert_manager.add_alert({
                    "device_ip": device.get("ip"),
                    "alert_type": "device_offline",
                    "severity": "warning",
                    "title": f"Dispositivo desconectado: {device.get('ip')}",
                    "description": f"El dispositivo {device.get('ip')} ya no está activo en la red",
                    "evidence": {
                        "vendor": device.get("vendor"),
                        "type": device.get("type")
                    }
                })
                
                logger.info(f"Dispositivo marcado como inactivo: {device.get('ip')}")
    
    def get_status(self) -> Dict:
        """Obtiene el estado del orquestador."""
        return {
            "running": self.running,
            "last_scan": self.state_manager.state.get("last_scan"),
            "last_alert": self.state_manager.state.get("last_alert"),
            "devices": {
                "total": len(self.device_manager.get_all_devices()),
                "active": len(self.device_manager.get_active_devices()),
                "inactive": len(self.device_manager.get_inactive_devices()),
                "new": len(self.device_manager.get_new_devices()),
                "high_risk": len(self.device_manager.get_high_risk_devices())
            },
            "alerts": {
                "unresolved": len(self.alert_manager.get_unresolved_alerts()),
                "total": len(self.alert_manager.get_alerts())
            },
            "config": self.config
        }
    
    def set_config(self, key: str, value: Any):
        """Establece una configuración."""
        self.config[key] = value
        self._save_config()


# ============================================================
# FUNCIONES DE INTEGRACIÓN
# ============================================================

orchestrator = None


def get_orchestrator() -> SealOrchestrator:
    """Obtiene la instancia del orquestador."""
    global orchestrator
    if orchestrator is None:
        orchestrator = SealOrchestrator()
    return orchestrator


async def start_orchestrator():
    """Inicia el orquestador."""
    orch = get_orchestrator()
    await orch.start()


async def stop_orchestrator():
    """Detiene el orquestador."""
    orch = get_orchestrator()
    await orch.stop()


def get_status() -> Dict:
    """Obtiene el estado del orquestador."""
    orch = get_orchestrator()
    return orch.get_status()


# ============================================================
# PRINCIPAL
# ============================================================

async def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="SEAL Orchestrator - Orquestador de operaciones continuas"
    )
    parser.add_argument("--start", action="store_true", help="Inicia el orquestador")
    parser.add_argument("--stop", action="store_true", help="Detiene el orquestador")
    parser.add_argument("--status", action="store_true", help="Muestra el estado")
    parser.add_argument("--scan", action="store_true", help="Ejecuta un escaneo manual")
    parser.add_argument("--config", action="store_true", help="Muestra la configuración")
    
    args = parser.parse_args()
    
    if args.start:
        await start_orchestrator()
    elif args.stop:
        await stop_orchestrator()
    elif args.status:
        status = get_status()
        print("\n" + "="*70)
        print("  📊 ESTADO DEL ORQUESTADOR")
        print("="*70)
        
        print(f"\nEstado: {'✅ En ejecución' if status['running'] else '❌ Detenido'}")
        print(f"Último escaneo: {status['last_scan'] or 'Nunca'}")
        print(f"Última alerta: {status['last_alert'] or 'Nunca'}")
        
        print(f"\n📱 Dispositivos:")
        for key, value in status['devices'].items():
            print(f"  {key}: {value}")
        
        print(f"\n🔔 Alertas:")
        for key, value in status['alerts'].items():
            print(f"  {key}: {value}")
        
        print(f"\n⚙️  Configuración:")
        for key, value in status['config'].items():
            print(f"  {key}: {value}")
    elif args.scan:
        orch = get_orchestrator()
        status = orch.get_status()
        if status['running']:
            print("❌ No se puede ejecutar escaneo manual mientras el orquestador está en ejecución")
        else:
            print("🔍 Ejecutando escaneo manual...")
            asyncio.run(orch._scan_loop())
    elif args.config:
        orch = get_orchestrator()
        print("\n" + "="*70)
        print("  ⚙️  CONFIGURACIÓN")
        print("="*70)
        for key, value in orch.config.items():
            print(f"  {key}: {value}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
