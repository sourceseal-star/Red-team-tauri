#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF REPORTER - Generación de Informes PDF
==========================================
Genera informes profesionales en formato PDF.

Autor: Harold Paredes / SourceSeal Red Team
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PDFReport:
    """Informe PDF."""
    title: str = "LEVIATHAN Scan Report"
    target: str = ""
    content: Dict = field(default_factory=dict)


class PDFReporter:
    """Generador de informes PDF."""
    
    def __init__(self):
        self.name = "pdf_reporter"
        self.category = "reporter"
        self.description = "Generación de informes PDF profesionales"
        self.author = "Harold Paredes"
        self.version = "3.0.0"
        
    def is_applicable(self, target: str, context: Dict = None) -> bool:
        """Siempre aplicable."""
        return True
    
    async def generate(self, target: str, context: Dict = None) -> Dict:
        """
        Genera un informe PDF.
        
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
            # Verificar si reportlab está instalado
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
            except ImportError:
                results["error"] = "reportlab no está instalado. Usa: pip install reportlab"
                return results
            
            # Crear informe
            report = await self._create_report(target, context)
            
            # Guardar en archivo
            filename = self._generate_filename(target, context)
            
            doc = SimpleDocTemplate(filename, pagesize=letter)
            story = []
            
            # Estilos
            styles = getSampleStyleSheet()
            
            # Título
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"LEVIATHAN - Informe de Escaneo", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Subtítulo
            subtitle = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#764ba2'),
                spaceAfter=20,
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"Objetivo: {target}", subtitle))
            story.append(Paragraph(f"Fecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", subtitle))
            story.append(Spacer(1, 0.3*inch))
            
            # Resumen
            story.append(Paragraph("<b>Resumen Ejecutivo</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            summary = report.content.get("summary", {})
            threat_level = report.content.get("threat_level", "low")
            
            # Tabla de resumen
            summary_data = [
                ["Dispositivos Escaneados", str(summary.get("total_targets", 0))],
                ["Dispositivos Activos", str(summary.get("active_targets", 0))],
                ["Cámaras Detectadas", str(summary.get("cameras_detected", 0))],
                ["Vulnerabilidades", str(summary.get("vulnerabilities_found", 0))],
                ["Puntuación de Amenaza", f"{summary.get('threat_score', 0):.1f}"],
                ["Nivel de Amenaza", threat_level.upper()]
            ]
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Cámaras detectadas
            cameras = report.content.get("findings", {}).get("cameras", [])
            if cameras:
                story.append(Paragraph("<b>Cámaras IP Detectadas</b>", styles['Heading2']))
                story.append(Spacer(1, 0.1*inch))
                
                camera_data = [['IP', 'Vendor', 'Modelo', 'Puerto', 'Accesible']]
                for camera in cameras:
                    camera_data.append([
                        camera.get("ip", ""),
                        camera.get("vendor", ""),
                        camera.get("model", ""),
                        str(camera.get("port", 0)),
                        "Sí" if camera.get("is_accessible", False) else "No"
                    ])
                
                camera_table = Table(camera_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1*inch, 1*inch])
                camera_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(camera_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Vulnerabilidades
            vulnerabilities = report.content.get("findings", {}).get("vulnerabilities", [])
            if vulnerabilities:
                story.append(Paragraph("<b>Vulnerabilidades Encontradas</b>", styles['Heading2']))
                story.append(Spacer(1, 0.1*inch))
                
                vuln_data = [['CVE', 'Severidad', 'Título', 'CVSS']]
                for vuln in vulnerabilities:
                    vuln_data.append([
                        vuln.get("cve_id", "N/A"),
                        vuln.get("severity", "info").upper(),
                        vuln.get("title", ""),
                        str(vuln.get("cvss_score", 0))
                    ])
                
                vuln_table = Table(vuln_data, colWidths=[1.5*inch, 1*inch, 2.5*inch, 1*inch])
                vuln_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc3545')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightpink),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(vuln_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Recomendaciones
            recommendations = report.content.get("recommendations", [])
            if recommendations:
                story.append(Paragraph("<b>Recomendaciones</b>", styles['Heading2']))
                story.append(Spacer(1, 0.1*inch))
                
                for rec in recommendations:
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
                    story.append(Spacer(1, 0.05*inch))
            
            # Pie de página
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("LEVIATHAN v3.0 - SourceSeal Red Team | Harold Paredes", styles['Italic']))
            
            # Generar PDF
            doc.build(story)
            
            # Leer contenido del PDF
            with open(filename, 'rb') as f:
                pdf_content = f.read()
            
            results["report"] = pdf_content.decode('latin-1')
            results["file_path"] = filename
            results["success"] = True
            
            return results
            
        except Exception as e:
            results["error"] = str(e)
            return results
    
    async def _create_report(self, target: str, context: Dict) -> PDFReport:
        """Crea un informe PDF."""
        report = PDFReport(
            title=f"LEVIATHAN - Informe de Escaneo: {target}",
            target=target,
            content=context
        )
        
        return report
    
    def _generate_filename(self, target: str, context: Dict) -> str:
        """Genera un nombre de archivo único."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scan_type = context.get("scan_type", "scan")
        
        clean_target = target.replace("/", "_").replace(":", "_").replace(".", "_")
        
        return f"leviathan_{scan_type}_{clean_target}_{timestamp}.pdf"
    
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
    return PDFReporter()
