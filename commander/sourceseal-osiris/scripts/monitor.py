# scripts/monitor.py
import asyncio
import aiohttp
import json
import os
import time
from datetime import datetime, timedelta
import sqlite3
import curses

class MonitorDashboard:
    """Dashboard de monitoreo en consola"""
    
    def __init__(self):
        self.stdscr = None
        self.running = True
        self.last_update = 0
    
    def init_screen(self):
        """Inicializar pantalla"""
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        curses.curs_set(0)
    
    def cleanup(self):
        """Limpiar pantalla"""
        if self.stdscr:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()
    
    def draw_header(self):
        """Dibujar encabezado"""
        self.stdscr.addstr(0, 0, "="*70, curses.A_BOLD)
        self.stdscr.addstr(1, 0, "📊 SOURCESEAL + OSIRIS MONITOR", curses.A_BOLD)
        self.stdscr.addstr(2, 0, f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdscr.addstr(3, 0, "="*70, curses.A_BOLD)
    
    def draw_section(self, y, title):
        """Dibujar sección"""
        self.stdscr.addstr(y, 0, f" {title} ", curses.A_BOLD)
        self.stdscr.addstr(y, len(title) + 2, "─"*(70 - len(title) - 3))
    
    async def get_osiris_stats(self) -> dict:
        """Obtener estadísticas de OSIRIS"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:3000/api/status", timeout=5) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except:
            pass
        return {}
    
    def get_connector_stats(self) -> dict:
        """Obtener estadísticas del conector"""
        stats = {"pending": 0, "sent": 0, "errors": 0}
        
        try:
            db_path = os.path.expanduser("~/connector_cache.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) FROM pending")
                stats["pending"] = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM metrics WHERE status = 'sent'")
                stats["sent"] = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM metrics WHERE status = 'retry_sent'")
                stats["retry"] = c.fetchone()[0]
                
                conn.close()
        except:
            pass
        
        return stats
    
    def get_playbook_stats(self) -> dict:
        """Obtener estadísticas de playbooks"""
        stats = {"total": 0, "running": 0, "completed": 0, "failed": 0}
        
        try:
            db_path = "/home/user/playbook_cache.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) FROM playbook_executions")
                stats["total"] = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM playbook_executions WHERE status = 'running'")
                stats["running"] = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM playbook_executions WHERE status = 'completed'")
                stats["completed"] = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM playbook_executions WHERE status = 'failed'")
                stats["failed"] = c.fetchone()[0]
                
                conn.close()
        except:
            pass
        
        return stats
    
    def draw_stats(self):
        """Dibujar estadísticas"""
        osiris_stats = asyncio.run(self.get_osiris_stats())
        connector_stats = self.get_connector_stats()
        playbook_stats = self.get_playbook_stats()
        
        # OSIRIS
        self.draw_section(5, "🌐 OSIRIS")
        self.stdscr.addstr(6, 2, f"Estado: {'✅ Online' if osiris_stats else '❌ Offline'}")
        if osiris_stats:
            self.stdscr.addstr(7, 2, f"Versión: {osiris_stats.get('version', 'N/A')}")
        
        # Conector
        self.draw_section(9, "🔌 CONECTOR")
        self.stdscr.addstr(10, 2, f"Pendientes: {connector_stats['pending']}")
        self.stdscr.addstr(11, 2, f"Enviados: {connector_stats['sent']}")
        self.stdscr.addstr(12, 2, f"Reintentos: {connector_stats['retry']}")
        
        # Playbooks
        self.draw_section(14, "📋 PLAYBOOKS")
        self.stdscr.addstr(15, 2, f"Total: {playbook_stats['total']}")
        self.stdscr.addstr(16, 2, f"Ejecutándose: {playbook_stats['running']}")
        self.stdscr.addstr(17, 2, f"Completados: {playbook_stats['completed']}")
        self.stdscr.addstr(18, 2, f"Fallidos: {playbook_stats['failed']}")
        
        # Logs recientes
        self.draw_section(20, "📝 ÚLTIMOS LOGS")
        self._draw_recent_logs(21)
    
    def _draw_recent_logs(self, y):
        """Dibujar logs recientes"""
        try:
            log_file = os.path.expanduser("~/connector.log")
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-5:]  # Últimas 5 líneas
                
                for i, line in enumerate(lines):
                    if y + i < curses.LINES - 1:
                        self.stdscr.addstr(y + i, 2, line.strip()[:68])
        except:
            pass
    
    def draw_footer(self):
        """Dibujar pie de página"""
        self.stdscr.addstr(curses.LINES - 1, 0, "="*70, curses.A_BOLD)
        self.stdscr.addstr(curses.LINES - 1, 2, "Presiona 'q' para salir")
    
    async def run(self):
        """Ejecutar monitor"""
        self.init_screen()
        
        try:
            while self.running:
                self.stdscr.clear()
                
                self.draw_header()
                self.draw_stats()
                self.draw_footer()
                
                self.stdscr.refresh()
                
                # Esperar tecla o timeout
                self.stdscr.nodelay(True)
                key = self.stdscr.getch()
                
                if key == ord('q'):
                    self.running = False
                elif key == curses.KEY_RESIZE:
                    pass  # Redibujar en el siguiente ciclo
                else:
                    await asyncio.sleep(5)
                    
        finally:
            self.cleanup()

def main():
    """Función principal"""
    monitor = MonitorDashboard()
    asyncio.run(monitor.run())

if __name__ == "__main__":
    main()
