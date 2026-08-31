#!/usr/bin/env python3
"""
Script de verificación completo para SourceSeal + OSIRIS
"""

import asyncio
import aiohttp
import os
import sys
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

class ServiceChecker:
    """Verificador de servicios"""
    
    def __init__(self):
        self.results = []
        self.warnings = []
        self.errors = []
    
    async def check_osiris(self, url: str = "http://localhost:3000/api") -> Tuple[str, str]:
        """Verificar OSIRIS"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/status", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        version = data.get("version", "unknown")
                        return "✅", f"Funcionando (v{version})"
                    else:
                        return "⚠️ ", f"Código {resp.status}"
        except asyncio.TimeoutError:
            return "❌", "Timeout"
        except Exception as e:
            return "❌", str(e)
    
    async def check_connector(self) -> Tuple[str, str]:
        """Verificar conector principal"""
        log_file = os.path.expanduser("~/connector.log")
        
        if not os.path.exists(log_file):
            return "⚠️ ", "Archivo de log no encontrado"
        
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            if "Conector iniciado" in content or "MainConnector" in content:
                # Verificar última entrada
                lines = content.split('\n')
                last_line = lines[-1] if lines else ""
                
                if "error" in last_line.lower() or "❌" in last_line:
                    return "⚠️ ", "Última entrada es un error"
                return "✅", "Funcionando"
            else:
                return "⚠️ ", "No se encontró inicio del conector"
        except Exception as e:
            return "❌", str(e)
    
    async def check_camera_connector(self) -> Tuple[str, str]:
        """Verificar conector de cámaras"""
        log_file = "/home/user/camera_connector.log"
        config_file = "configs/cameras_config.json"
        
        if not os.path.exists(config_file):
            return "⚠️ ", "Configuración no encontrada"
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            if not config.get("enabled", False):
                return "ℹ️", "Deshabilitado"
            
            cameras = config.get("cameras", [])
            return "✅", f"{len(cameras)} cámara(s) configurada(s)"
        except Exception as e:
            return "❌", str(e)
    
    async def check_playbook_connector(self) -> Tuple[str, str]:
        """Verificar conector de playbooks"""
        config_file = "configs/playbooks_config.json"
        
        if not os.path.exists(config_file):
            return "⚠️ ", "Configuración no encontrada"
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            playbooks = config.get("playbooks", [])
            return "✅", f"{len(playbooks)} playbook(s) configurado(s)"
        except Exception as e:
            return "❌", str(e)
    
    async def check_cache(self) -> Tuple[str, str]:
        """Verificar caché"""
        db_path = os.path.expanduser("~/connector_cache.db")
        
        if not os.path.exists(db_path):
            return "⚠️ ", "Base de datos no encontrada"
        
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM pending")
            pending_count = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM metrics")
            metrics_count = c.fetchone()[0]
            
            conn.close()
            
            if pending_count > 100:
                return "⚠️ ", f"{pending_count} mensajes pendientes (¡Demasiados!)"
            return "✅", f"{pending_count} pendientes, {metrics_count} métricas"
        except Exception as e:
            return "❌", str(e)
    
    async def check_ports(self) -> Tuple[str, str]:
        """Verificar puertos clave"""
        import subprocess
        
        ports = [3000, 8000, 8001]
        active_ports = []
        
        try:
            result = subprocess.run(
                ["netstat", "-tuln"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for port in ports:
                if str(port) in result.stdout:
                    active_ports.append(str(port))
            
            if active_ports:
                return "✅", f"Puertos activos: {', '.join(active_ports)}"
            else:
                return "⚠️ ", "Ningún puerto activo encontrado"
        except Exception as e:
            return "⚠️ ", f"No se pudo verificar (netstat no disponible: {e})"
    
    async def check_disk_space(self) -> Tuple[str, str]:
        """Verificar espacio en disco"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            
            free_gb = free / (1024 ** 3)
            used_percent = (used / total) * 100
            
            if free_gb < 1:
                return "❌", f"Solo {free_gb:.2f} GB libres ({used_percent:.1f}% usado)"
            elif free_gb < 5:
                return "⚠️ ", f"{free_gb:.2f} GB libres ({used_percent:.1f}% usado)"
            else:
                return "✅", f"{free_gb:.2f} GB libres"
        except Exception as e:
            return "⚠️ ", f"No se pudo verificar: {e}"
    
    async def run_all_checks(self) -> Dict:
        """Ejecutar todas las verificaciones"""
        checks = [
            ("OSIRIS", self.check_osiris()),
            ("Conector Principal", self.check_connector()),
            ("Conector de Cámaras", self.check_camera_connector()),
            ("Conector de Playbooks", self.check_playbook_connector()),
            ("Caché", self.check_cache()),
            ("Puertos", self.check_ports()),
            ("Espacio en Disco", self.check_disk_space()),
        ]
        
        results = {}
        for name, check in checks:
            status, message = await check
            results[name] = (status, message)
            
            if "✅" in status:
                self.results.append(f"{status} {name}: {message}")
            elif "⚠️ " in status:
                self.warnings.append(f"{status} {name}: {message}")
            else:
                self.errors.append(f"{status} {name}: {message}")
        
        return results
    
    def print_report(self):
        """Imprimir reporte"""
        print("\n" + "="*70)
        print("📊 REPORTE DE VERIFICACIÓN - SOURCESEAL + OSIRIS")
        print("="*70)
        print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Resultados
        if self.results:
            print("\n✅ SERVICIOS FUNCIONANDO:")
            for result in self.results:
                print(f"  {result}")
        
        # Advertencias
        if self.warnings:
            print("\n⚠️  ADVERTENCIAS:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        # Errores
        if self.errors:
            print("\n❌ ERRORES:")
            for error in self.errors:
                print(f"  {error}")
        
        print("\n" + "="*70)
        
        # Resumen
        total = len(self.results) + len(self.warnings) + len(self.errors)
        ok = len(self.results)
        
        if self.errors:
            print("❌ ALGUNOS SERVICIOS NO FUNCIONAN CORRECTAMENTE")
            print(f"   {ok}/{total} servicios OK")
        elif self.warnings:
            print("⚠️  TODOS LOS SERVICIOS FUNCIONAN, PERO HAY ADVERTENCIAS")
            print(f"   {ok}/{total} servicios OK")
        else:
            print("✅ TODOS LOS SERVICIOS FUNCIONAN CORRECTAMENTE!")
            print(f"   {ok}/{total} servicios OK")
            print("\n🌐 Accede al dashboard: http://localhost:3000")
        
        print("="*70 + "\n")
        
        return len(self.errors) == 0

async def main():
    """Función principal"""
    checker = ServiceChecker()
    await checker.run_all_checks()
    
    success = checker.print_report()
    
    if not success:
        print("\n💡 SUGERENCIAS:")
        print("  1. Verifica que OSIRIS esté corriendo: npm start en el directorio osiris/")
        print("  2. Verifica que SourceSeal esté corriendo: python3 -m sourceseal")
        print("  3. Revisa los logs: tail -f ~/connector.log")
        print("  4. Verifica la configuración: configs/default_config.json")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
