#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML REPORTER - Generación de Informes HTML
============================================
Genera informes visuales en formato HTML.

Autor: Harold Paredes / SourceSeal Red Team
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HTMLReport:
    """Informe HTML."""
    title: str = "LEVIATHAN Scan Report"
    target: str = ""
    html_content: str = ""


class HTMLReporter:
    """Generador de informes HTML."""
    
    def __init__(self):
        self.name = "html_reporter"
        self.category = "reporter"
        self.description = "Generación de informes HTML visuales"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Siempre aplicable."""
        return True
    
    async def generate(self, target: str, context: Dict = None) -> Dict:
        """
        Genera un informe HTML.
        
        Args:
            target: Objetivo del informe
            context: Contexto con datos del escaneo
        """
        context = context or {}
        
        results = {
            "target": target,
            "report": None,
            "file_path": None,
            "success": False,
            "error": None
        }
        
        try:
            # Crear informe
            report = await self._create_report(target, context)
            
            results["report"] = report.html_content
            results["success"] = True
            
            # Guardar en archivo
            filename = self._generate_filename(target, context)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report.html_content)
            
            results["file_path"] = filename
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _create_report(self, target: str, context: Dict) -> HTMLReport:
        """Crea un informe HTML."""
        report = HTMLReport(
            title=f"LEVIATHAN - Informe de Escaneo: {target}",
            target=target
        )
        
        # Crear contenido HTML
        html = self._generate_html_content(target, context)
        report.html_content = html
        
        return report
    
    def _generate_html_content(self, target: str, context: Dict) -> str:
        """Genera el contenido HTML."""
        summary = context.get("summary", {})
        findings = context.get("findings", {})
        recommendations = context.get("recommendations", [])
        
        # Colores para nivel de amenaza
        threat_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#28a745",
            "info": "#17a2b8"
        }
        
        threat_level = context.get("threat_level", "low")
        threat_color = threat_colors.get(threat_level, "#6c757d")
        
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f9fa;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .threat-badge {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            font-size: 1.1em;
            background-color: {threat_color};
            margin: 10px 0;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-card .label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: 30px 0;
        }}
        
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        
        .camera-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .camera-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .camera-card h3 {{
            margin-top: 0;
            color: #333;
        }}
        
        .camera-card .detail {{
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }}
        
        .vulnerability-list {{
            list-style: none;
            padding: 0;
        }}
        
        .vulnerability-list li {{
            padding: 15px;
            margin: 10px 0;
            background: #f8f9fa;
            border-radius: 5px;
            border-left: 4px solid #dc3545;
        }}
        
        .vulnerability-list li.critical {{ border-left-color: #dc3545; }}
        .vulnerability-list li.high {{ border-left-color: #fd7e14; }}
        .vulnerability-list li.medium {{ border-left-color: #ffc107; }}
        .vulnerability-list li.low {{ border-left-color: #28a745; }}
        
        .recommendation-box {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        
        .recommendation-box.critical {{
            background: #f8d7da;
            border-color: #dc3545;
        }}
        
        .recommendation-box strong {{
            color: #856404;
        }}
        
        .recommendation-box.critical strong {{
            color: #721c24;
        }}
        
        .footer {{
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin: 30px 0;
        }}
        
        .timestamp {{
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦑 LEVIATHAN</h1>
            <div class="subtitle">Sistema de Red Team Automatizado</div>
            <div class="threat-badge">{threat_level.upper()} RISK</div>
            <div class="timestamp">Generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="number">{summary.get('total_targets', 0)}</div>
                <div class="label">Objetivos Escaneados</div>
            </div>
            <div class="stat-card">
                <div class="number">{summary.get('active_targets', 0)}</div>
                <div class="label">Dispositivos Activos</div>
            </div>
            <div class="stat-card">
                <div class="number">{summary.get('cameras_detected', 0)}</div>
                <div class="label">Cámaras Detectadas</div>
            </div>
            <div class="stat-card">
                <div class="number">{summary.get('vulnerabilities_found', 0)}</div>
                <div class="label">Vulnerabilidades</div>
            </div>
            <div class="stat-card">
                <div class="number">{summary.get('threat_score', 0):.1f}</div>
                <div class="label">Puntuación de Amenaza</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Resumen Ejecutivo</h2>
            <p>
                Este informe presenta los resultados del escaneo realizado por el sistema 
                <strong>LEVIATHAN v3.0</strong> en el objetivo <strong>{target}</strong>.
                El análisis ha identificado {summary.get('cameras_detected', 0)} cámaras IP,
                {summary.get('vulnerabilities_found', 0)} vulnerabilidades y 
                {summary.get('anomalies_detected', 0)} anomalías de comportamiento.
            </p>
            <p>
                <strong>Nivel de Amenaza:</strong> <span style="color: {threat_color}; font-weight: bold;">{threat_level.upper()}</span>
            </p>
        </div>
        
        <div class="section">
            <h2>🎥 Cámaras IP Detectadas</h2>
            <p>Se han identificado las siguientes cámaras en la red:</p>
            <div class="camera-grid">
                {self._generate_camera_cards(findings.get('cameras', []))}
            </div>
        </div>
        
        <div class="section">
            <h2>⚠️ Vulnerabilidades Encontradas</h2>
            <p>Vulnerabilidades detectadas en los dispositivos escaneados:</p>
            <ul class="vulnerability-list">
                {self._generate_vulnerability_items(findings.get('vulnerabilities', []))}
            </ul>
        </div>
        
        <div class="section">
            <h2>💡 Recomendaciones</h2>
            {self._generate_recommendation_boxes(recommendations)}
        </div>
        
        <div class="footer">
            <p><strong>LEVIATHAN v3.0</strong> - SourceSeal Red Team | Harold Paredes</p>
            <p>Sistema de Red Team Automatizado para Detección y Explotación de Cámaras IP</p>
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    def _generate_camera_cards(self, cameras: List[Dict]) -> str:
        """Genera tarjetas de cámaras."""
        if not cameras:
            return "<p>No se detectaron cámaras IP.</p>"
        
        cards = []
        for camera in cameras:
            vendor = camera.get("vendor", "Desconocido")
            model = camera.get("model", "Desconocido")
            ip = camera.get("ip", "")
            port = camera.get("port", 0)
            is_accessible = camera.get("is_accessible", False)
            
            accessible_badge = "🔒" if not is_accessible else "🔓"
            
            card = f"""
            <div class="camera-card">
                <h3>{vendor} {model}</h3>
                <div class="detail"><strong>IP:</strong> {ip}:{port}</div>
                <div class="detail"><strong>Estado:</strong> {accessible_badge} Accesible: {is_accessible}</div>
                {f'<div class="detail"><strong>Credenciales:</strong> {camera.get("credentials", "N/A")}</div>' if is_accessible else ''}
            </div>
            """
            cards.append(card)
        
        return "\n".join(cards)
    
    def _generate_vulnerability_items(self, vulnerabilities: List[Dict]) -> str:
        """Genera elementos de vulnerabilidades."""
        if not vulnerabilities:
            return "<li>No se detectaron vulnerabilidades.</li>"
        
        items = []
        for vuln in vulnerabilities:
            severity = vuln.get("severity", "info").lower()
            cve_id = vuln.get("cve_id", "N/A")
            title = vuln.get("title", "Sin título")
            
            item = f'<li class="{severity}"><strong>{cve_id}:</strong> {title} (Severidad: {severity.upper()})</li>'
            items.append(item)
        
        return "\n".join(items)
    
    def _generate_recommendation_boxes(self, recommendations: List[str]) -> str:
        """Genera cajas de recomendaciones."""
        if not recommendations:
            return "<p>No hay recomendaciones específicas.</p>"
        
        boxes = []
        for rec in recommendations:
            severity = "critical" if "🔴" in rec or "AISLAR" in rec else \
                     "high" if "🟠" in rec else \
                     "medium" if "🟡" in rec else "low"
            
            box = f'<div class="recommendation-box {severity}"><strong>⚠️ </strong>{rec}</div>'
            boxes.append(box)
        
        return "\n".join(boxes)
    
    def _generate_filename(self, target: str, context: Dict) -> str:
        """Genera un nombre de archivo único."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scan_type = context.get("scan_type", "scan")
        
        clean_target = target.replace("/", "_").replace(":", "_").replace(".", "_")
        
        return f"leviathan_{scan_type}_{clean_target}_{timestamp}.html"
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version
        }


def register():
    """Función de registro para el sistema de plugins."""
    return HTMLReporter()
