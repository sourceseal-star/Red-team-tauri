import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from kraken.config.settings import settings
from kraken.core.database import db
from kraken.core.logger import logger

class ReportGenerator:
    """Generador de informes en PDF y HTML."""

    def __init__(self):
        self.reports_dir = settings.REPORTS_DIR
        os.makedirs(self.reports_dir, exist_ok=True)

        # Configuración de fuentes para WeasyPrint
        self.font_config = FontConfiguration()

    def generate_html_report(self, data: Dict) -> str:
        """Genera un informe en HTML."""
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>KRAKEN v3.0 - Informe de Seguridad</title>
            <style>
                @page { margin: 1cm; }
                body {
                    font-family: 'DejaVu Sans', Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                    background-color: #fff;
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #e53e3e;
                    padding-bottom: 20px;
                }
                .header h1 { color: #e53e3e; margin: 0; }
                .header p { color: #666; margin: 5px 0; }
                .section {
                    margin-bottom: 30px;
                    page-break-after: always;
                }
                .section h2 {
                    color: #e53e3e;
                    border-bottom: 1px solid #e53e3e;
                    padding-bottom: 10px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                th, td {
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                th {
                    background-color: #f8f9fa;
                    color: #e53e3e;
                    font-weight: bold;
                }
                tr:hover { background-color: #f5f5f5; }
                .critical { background-color: #fee2e2; }
                .high { background-color: #fef3c7; }
                .medium { background-color: #fef9c3; }
                .low { background-color: #d1fae5; }
                .severity-badge {
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                    display: inline-block;
                }
                .critical-badge { background-color: #e53e3e; color: white; }
                .high-badge { background-color: #f59e0b; color: white; }
                .medium-badge { background-color: #fbbf24; color: black; }
                .low-badge { background-color: #10b981; color: white; }
                .footer {
                    text-align: center;
                    margin-top: 50px;
                    color: #666;
                    font-size: 12px;
                }
                .chart-container {
                    margin: 20px 0;
                    text-align: center;
                }
                .chart {
                    max-width: 100%;
                    height: auto;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🦈 KRAKEN v3.0 - Informe de Seguridad</h1>
                <p>Generado el: {report_date}</p>
                <p>Período: {start_date} a {end_date}</p>
            </div>

            <!-- Resumen Ejecutivo -->
            <div class="section">
                <h2>📊 Resumen Ejecutivo</h2>
                <p>
                    <strong>Total de Hosts Escaneados:</strong> {total_hosts}<br>
                    <strong>Vulnerabilidades Críticas:</strong> {critical_vulns}<br>
                    <strong>Vulnerabilidades Altas:</strong> {high_vulns}<br>
                    <strong>Vulnerabilidades Medias:</strong> {medium_vulns}<br>
                    <strong>Vulnerabilidades Bajas:</strong> {low_vulns}<br>
                    <strong>Exploits Exitosos:</strong> {total_exploits}<br>
                    <strong>Tiempo de Escaneo:</strong> {scan_duration} minutos
                </p>
            </div>

            <!-- Vulnerabilidades por Severidad -->
            <div class="section">
                <h2>📈 Vulnerabilidades por Severidad</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{severity_chart}" class="chart" alt="Vulnerabilidades por Severidad">
                </div>
            </div>

            <!-- Top 10 Hosts Prioritarios -->
            <div class="section">
                <h2>🎯 Top 10 Hosts Prioritarios (por CVSS)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>IP</th>
                            <th>Hostname</th>
                            <th>Sistema Operativo</th>
                            <th>CVSS Score</th>
                            <th>Vulnerabilidades</th>
                            <th>Última Vez</th>
                        </tr>
                    </thead>
                    <tbody>
                        {priorities_table}
                    </tbody>
                </table>
            </div>

            <!-- Exploits Exitosos -->
            <div class="section">
                <h2>💀 Exploits Exitosos</h2>
                <table>
                    <thead>
                        <tr>
                            <th>IP</th>
                            <th>Puerto</th>
                            <th>Servicio</th>
                            <th>Vulnerabilidad</th>
                            <th>CVE</th>
                            <th>CVSS</th>
                            <th>Plugin</th>
                            <th>Fecha</th>
                        </tr>
                    </thead>
                    <tbody>
                        {exploits_table}
                    </tbody>
                </table>
            </div>

            <!-- Vulnerabilidades Detectadas -->
            <div class="section">
                <h2>🔍 Vulnerabilidades Detectadas</h2>
                <table>
                    <thead>
                        <tr>
                            <th>IP</th>
                            <th>Puerto</th>
                            <th>Servicio</th>
                            <th>CVE</th>
                            <th>Severidad</th>
                            <th>CVSS</th>
                            <th>Detectada</th>
                        </tr>
                    </thead>
                    <tbody>
                        {vulnerabilities_table}
                    </tbody>
                </table>
            </div>

            <!-- Recomendaciones -->
            <div class="section">
                <h2>💡 Recomendaciones</h2>
                <ol>
                    {recommendations}
                </ol>
            </div>

            <div class="footer">
                <p>KRAKEN v3.0 - Motor de Explotación Autónomo | © 2024 Sealclient</p>
                <p>Generado automáticamente. No distribuir sin autorización.</p>
            </div>
        </body>
        </html>
        """

        # Generar gráficos (simplificado para HTML)
        severity_chart = self._generate_severity_chart_base64(data.get("vulnerabilities_by_severity", {}))

        # Generar tablas
        priorities_table = self._generate_priorities_table(data.get("priorities", []))
        exploits_table = self._generate_exploits_table(data.get("exploits", []))
        vulnerabilities_table = self._generate_vulnerabilities_table(data.get("vulnerabilities", []))

        # Generar recomendaciones
        recommendations = self._generate_recommendations(data)

        # Formatear fechas
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_date = data.get("start_date", report_date)
        end_date = data.get("end_date", report_date)

        # Rellenar template
        html = template.format(
            report_date=report_date,
            start_date=start_date,
            end_date=end_date,
            total_hosts=data.get("total_hosts", 0),
            critical_vulns=data.get("vulnerabilities_by_severity", {}).get("critical", 0),
            high_vulns=data.get("vulnerabilities_by_severity", {}).get("high", 0),
            medium_vulns=data.get("vulnerabilities_by_severity", {}).get("medium", 0),
            low_vulns=data.get("vulnerabilities_by_severity", {}).get("low", 0),
            total_exploits=data.get("total_exploits", 0),
            scan_duration=data.get("scan_duration", 0),
            severity_chart=severity_chart,
            priorities_table=priorities_table,
            exploits_table=exploits_table,
            vulnerabilities_table=vulnerabilities_table,
            recommendations=recommendations
        )

        return html

    def _generate_severity_chart_base64(self, severity_data: Dict) -> str:
        """Genera un gráfico de severidad en base64 (simplificado)."""
        # En una implementación real, usarías matplotlib o plotly para generar el gráfico
        # Aquí retornamos un placeholder
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    def _generate_priorities_table(self, priorities: List[Dict]) -> str:
        """Genera la tabla de prioridades."""
        rows = []
        for i, p in enumerate(priorities, 1):
            severity_class = self._get_severity_class(p.get("cvss", 0))
            rows.append(f"""
                <tr>
                    <td>{i}</td>
                    <td>{p.get('ip', 'N/A')}</td>
                    <td>{p.get('hostname', 'N/A')}</td>
                    <td>{p.get('os', 'Unknown')}</td>
                    <td class="{severity_class}">{p.get('cvss', 0):.1f}</td>
                    <td>{p.get('vulns', 0)}</td>
                    <td>{p.get('last_seen', 'N/A')}</td>
                </tr>
            """)
        return "\n".join(rows)

    def _generate_exploits_table(self, exploits: List[Dict]) -> str:
        """Genera la tabla de exploits."""
        rows = []
        for e in exploits:
            severity_class = self._get_severity_class(e.get("cvss", 0))
            rows.append(f"""
                <tr>
                    <td>{e.get('ip', 'N/A')}</td>
                    <td>{e.get('port', 'N/A')}</td>
                    <td>{e.get('service', 'N/A')}</td>
                    <td>{e.get('vulnerability', 'N/A')}</td>
                    <td>{e.get('cve', 'N/A')}</td>
                    <td class="{severity_class}">{e.get('cvss', 0):.1f}</td>
                    <td>{e.get('plugin', 'N/A')}</td>
                    <td>{e.get('attempted_at', 'N/A')}</td>
                </tr>
            """)
        return "\n".join(rows)

    def _generate_vulnerabilities_table(self, vulnerabilities: List[Dict]) -> str:
        """Genera la tabla de vulnerabilidades."""
        rows = []
        for v in vulnerabilities:
            severity_class = self._get_severity_class(v.get("cvss", 0))
            severity_badge = self._get_severity_badge(v.get("severity", "unknown"))
            rows.append(f"""
                <tr>
                    <td>{v.get('ip', 'N/A')}</td>
                    <td>{v.get('port', 'N/A')}</td>
                    <td>{v.get('service', 'N/A')}</td>
                    <td>{v.get('cve', 'N/A')}</td>
                    <td><span class="severity-badge {severity_badge}">{v.get('severity', 'unknown')}</span></td>
                    <td class="{severity_class}">{v.get('cvss', 0):.1f}</td>
                    <td>{v.get('detected_at', 'N/A')}</td>
                </tr>
            """)
        return "\n".join(rows)

    def _get_severity_class(self, cvss: float) -> str:
        """Obtiene la clase CSS según el CVSS."""
        if cvss >= 9:
            return "critical"
        elif cvss >= 7:
            return "high"
        elif cvss >= 4:
            return "medium"
        else:
            return "low"

    def _get_severity_badge(self, severity: str) -> str:
        """Obtiene la clase CSS para el badge de severidad."""
        return {
            "critical": "critical-badge",
            "high": "high-badge",
            "medium": "medium-badge",
            "low": "low-badge"
        }.get(severity.lower(), "low-badge")

    def _generate_recommendations(self, data: Dict) -> str:
        """Genera recomendaciones basadas en los datos."""
        recommendations = []
        critical_vulns = data.get("vulnerabilities_by_severity", {}).get("critical", 0)
        high_vulns = data.get("vulnerabilities_by_severity", {}).get("high", 0)
        total_exploits = data.get("total_exploits", 0)

        if critical_vulns > 0:
            recommendations.append(
                f"Parchear inmediatamente las {critical_vulns} vulnerabilidades críticas detectadas. "
                "Estas representan el mayor riesgo para la infraestructura."
            )

        if high_vulns > 0:
            recommendations.append(
                f"Revisar y parchear las {high_vulns} vulnerabilidades altas en las próximas 72 horas."
            )

        if total_exploits > 0:
            recommendations.append(
                f"Investigar los {total_exploits} exploits exitosos. "
                "Estos indican que hay sistemas accesibles con credenciales débiles o vulnerabilidades explotables."
            )

        if critical_vulns == 0 and high_vulns == 0 and total_exploits == 0:
            recommendations.append(
                "No se detectaron vulnerabilidades críticas ni exploits exitosos. "
                "Mantener los sistemas actualizados y continuar con los escaneos periódicos."
            )

        recommendations.append(
            "Implementar autenticación multifactor (MFA) en todos los servicios expuestos."
        )
        recommendations.append(
            "Configurar alertas en tiempo real para nuevas vulnerabilidades críticas."
        )
        recommendations.append(
            "Realizar pruebas de penetración manuales en los sistemas con mayor CVSS."
        )

        return "\n".join([f"<li>{rec}</li>" for rec in recommendations])

    def generate_report(self, days: int = 7, output_format: str = "pdf") -> Optional[str]:
        """Genera un informe completo."""
        # Obtener datos
        stats = db.get_scan_stats(days)
        priorities = db.get_priorities(limit=10)
        exploits = db.get_exploits(limit=50, success=True)
        vulnerabilities = db.get_vulnerabilities(limit=50)

        # Preparar datos para el informe
        report_data = {
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
            "total_hosts": stats.get("total_hosts", 0),
            "vulnerabilities_by_severity": stats.get("vulnerabilities", {}),
            "total_exploits": stats.get("total_exploits", 0),
            "scan_duration": stats.get("days", 0) * 24 * 60,  # minutos
            "priorities": [{
                "ip": ip,
                "hostname": db.get_host(ip).hostname if db.get_host(ip) else "N/A",
                "os": db.get_host(ip).os if db.get_host(ip) else "Unknown",
                "cvss": cvss,
                "vulns": vulns,
                "last_seen": db.get_host(ip).last_seen.isoformat() if db.get_host(ip) and db.get_host(ip).last_seen else "N/A"
            } for ip, cvss, vulns in priorities],
            "exploits": [{
                "ip": e["ip"],
                "port": e["port"],
                "service": e["service"],
                "vulnerability": e["vuln"],
                "cve": e["cvss"],
                "cvss": e["cvss"],
                "plugin": e["plugin"],
                "attempted_at": e["time"]
            } for e in exploits],
            "vulnerabilities": [{
                "ip": v["ip"],
                "port": v["port"],
                "service": v["service"],
                "cve": v["cve"],
                "cvss": v["cvss"],
                "severity": v["severity"],
                "detected_at": v["time"]
            } for v in vulnerabilities]
        }

        # Generar HTML
        html = self.generate_html_report(report_data)

        # Guardar archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kraken_report_{timestamp}"

        if output_format == "html":
            filepath = self.reports_dir / f"{filename}.html"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"✅ Informe HTML generado: {filepath}")
            return str(filepath)

        elif output_format == "pdf":
            filepath = self.reports_dir / f"{filename}.pdf"
            try:
                HTML(string=html, base_url=str(self.reports_dir)).write_pdf(
                    str(filepath),
                    stylesheets=[CSS(string="@page { size: A4; margin: 1cm; }")],
                    font_config=self.font_config
                )
                logger.info(f"✅ Informe PDF generado: {filepath}")
                return str(filepath)
            except Exception as e:
                logger.error(f"Error generando PDF: {e}")
                return None

        else:
            logger.error(f"Formato no soportado: {output_format}")
            return None

    def generate_json_report(self, days: int = 7) -> Optional[str]:
        """Genera un informe en formato JSON."""
        stats = db.get_scan_stats(days)
        priorities = db.get_priorities(limit=10)
        exploits = db.get_exploits(limit=50, success=True)
        vulnerabilities = db.get_vulnerabilities(limit=50)

        report_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "period_days": days,
                "kraken_version": "3.0.0"
            },
            "summary": {
                "total_hosts": stats.get("total_hosts", 0),
                "vulnerabilities": stats.get("vulnerabilities", {}),
                "total_exploits": stats.get("total_exploits", 0)
            },
            "priorities": priorities,
            "exploits": exploits,
            "vulnerabilities": vulnerabilities
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.reports_dir / f"kraken_report_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Informe JSON generado: {filepath}")
        return str(filepath)
