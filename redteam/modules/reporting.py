# -*- coding: utf-8 -*-
"""
REPORTING — Generación de informes sellados con SHA-256.
Crea reportes HTML y JSON con firma criptográfica del engagement.
"""
import json, hashlib, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from redteam.modules.base import BaseModule

REPORTS_DIR = Path(os.environ.get(
    "SOURCESEAL_REPORTS_DIR",
    str(Path.home() / ".sourceseal" / "reports")
)).expanduser()
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "reports" / "templates"


class ReportingModule(BaseModule):
    name = "reporting"
    description = "Generación de informes sellados HTML/JSON"
    version = "1.0"

    def _execute(self, target: str, **kwargs: Any) -> dict[str, Any]:
        findings = kwargs.get("findings", [])
        engagement_id = kwargs.get("engagement_id", self.engagement_id)
        format_type = kwargs.get("format", "html")  # html | json | both

        ts = datetime.now(timezone.utc)
        ts_str = ts.isoformat()
        ts_unix = int(ts.timestamp())

        # Compilar resumen
        summary = self._build_summary(target, findings, engagement_id, ts_str)

        # Hash del reporte
        canonical = json.dumps(summary, sort_keys=True, ensure_ascii=False)
        report_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # Sello SourceSeal
        seal = {
            "report_id": f"RPT-{ts_unix}-{report_hash[:8]}",
            "engagement_id": engagement_id,
            "target": target,
            "timestamp": ts_str,
            "sha256": report_hash,
            "chain_hash": hashlib.sha256(
                f"{report_hash}|{engagement_id}|{ts_unix}".encode()
            ).hexdigest()
        }

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        result = {"seal": seal, "files": []}

        if format_type in ("json", "both"):
            json_file = REPORTS_DIR / f"{seal['report_id']}.json"
            json_file.write_text(
                json.dumps({"summary": summary, "seal": seal}, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            result["files"].append(str(json_file))

        if format_type in ("html", "both"):
            html_file = REPORTS_DIR / f"{seal['report_id']}.html"
            html_file.write_text(
                self._build_html(summary, seal),
                encoding="utf-8"
            )
            result["files"].append(str(html_file))

        result["report_id"] = seal["report_id"]
        result["sha256"] = report_hash
        return result

    def _build_summary(self, target: str, findings: list, engagement_id: str, ts: str) -> dict:
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        all_cves = set()

        for f in findings:
            sev = f.get("severity", "info").lower()
            if sev in severity_counts:
                severity_counts[sev] += 1
            for cve in f.get("cves", []):
                all_cves.add(cve)

        return {
            "engagement_id": engagement_id,
            "target": target,
            "timestamp": ts,
            "total_findings": len(findings),
            "severity": severity_counts,
            "unique_cves": sorted(all_cves),
            "findings": findings
        }

    def _build_html(self, summary: dict, seal: dict) -> str:
        """Genera un HTML profesional firmado."""
        findings_rows = ""
        for f in summary.get("findings", []):
            sev = f.get("severity", "info")
            sev_color = {
                "critical": "#dc2626",
                "high": "#ea580c",
                "medium": "#ca8a04",
                "low": "#2563eb",
                "info": "#6b7280"
            }.get(sev, "#6b7280")

            cves = ", ".join(f.get("cves", [])) if f.get("cves") else "—"
            findings_rows += f"""
            <tr>
                <td><span class="badge" style="background:{sev_color}">{sev.upper()}</span></td>
                <td>{f.get('source', '')}</td>
                <td>{f.get('name', f.get('detail', ''))}</td>
                <td>{cves}</td>
                <td><code>{f.get('matched', '')}</code></td>
            </tr>"""

        cve_list = ", ".join(summary.get("unique_cves", [])) or "Ninguno"

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SourceSeal Report — {seal['report_id']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
        .header {{ text-align: center; padding: 2rem; background: #1e293b; border-radius: 12px; margin-bottom: 2rem; }}
        .header h1 {{ color: #38bdf8; font-size: 1.8rem; }}
        .header .subtitle {{ color: #94a3b8; margin-top: 0.5rem; }}
        .seal-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }}
        .seal-box h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }}
        .seal-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }}
        .seal-item {{ font-size: 0.85rem; }}
        .seal-item .label {{ color: #64748b; }}
        .seal-item .value {{ color: #e2e8f0; font-family: monospace; word-break: break-all; }}
        .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin: 2rem 0; }}
        .stat {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; text-align: center; }}
        .stat .number {{ font-size: 2rem; font-weight: bold; }}
        .stat .label {{ color: #94a3b8; font-size: 0.8rem; margin-top: 0.3rem; }}
        .stat.critical .number {{ color: #dc2626; }}
        .stat.high .number {{ color: #ea580c; }}
        .stat.medium .number {{ color: #ca8a04; }}
        .stat.low .number {{ color: #2563eb; }}
        .stat.info .number {{ color: #6b7280; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
        th {{ background: #334155; padding: 1rem; text-align: left; color: #94a3b8; font-size: 0.85rem; }}
        td {{ padding: 0.8rem 1rem; border-top: 1px solid #334155; font-size: 0.85rem; }}
        .badge {{ padding: 0.2rem 0.6rem; border-radius: 4px; color: white; font-size: 0.7rem; font-weight: bold; }}
        .cve-section {{ margin: 2rem 0; padding: 1.5rem; background: #1e293b; border-radius: 8px; }}
        .cve-section h2 {{ color: #38bdf8; margin-bottom: 1rem; }}
        .cve-list {{ font-family: monospace; color: #fbbf24; }}
        .footer {{ text-align: center; margin-top: 3rem; color: #475569; font-size: 0.8rem; }}
        .footer a {{ color: #38bdf8; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ SourceSeal Tactical Report</h1>
        <div class="subtitle">Report ID: {seal['report_id']} · Engagement: {seal['engagement_id']}</div>
        <div class="subtitle">Target: <code>{seal['target']}</code> · {seal['timestamp']}</div>
    </div>

    <div class="seal-box">
        <h2>🔐 Sello Criptográfico</h2>
        <div class="seal-grid">
            <div class="seal-item"><span class="label">SHA-256:</span> <span class="value">{seal['sha256']}</span></div>
            <div class="seal-item"><span class="label">Chain Hash:</span> <span class="value">{seal['chain_hash']}</span></div>
        </div>
    </div>

    <div class="summary">
        <div class="stat critical"><div class="number">{summary['severity']['critical']}</div><div class="label">CRITICAL</div></div>
        <div class="stat high"><div class="number">{summary['severity']['high']}</div><div class="label">HIGH</div></div>
        <div class="stat medium"><div class="number">{summary['severity']['medium']}</div><div class="label">MEDIUM</div></div>
        <div class="stat low"><div class="number">{summary['severity']['low']}</div><div class="label">LOW</div></div>
        <div class="stat info"><div class="number">{summary['severity']['info']}</div><div class="label">INFO</div></div>
    </div>

    <div class="cve-section">
        <h2>📋 CVEs Encontrados ({len(summary.get('unique_cves', []))})</h2>
        <div class="cve-list">{cve_list}</div>
    </div>

    <table>
        <thead>
            <tr><th>Severidad</th><th>Source</th><th>Detalle</th><th>CVEs</th><th>Match</th></tr>
        </thead>
        <tbody>
            {findings_rows if findings_rows else '<tr><td colspan="5">Sin hallazgos</td></tr>'}
        </tbody>
    </table>

    <div class="footer">
        Generado por <strong>SourceSeal Tactical Engine v6.0</strong><br>
        Protocolo SourceSealGlobal v2.1 · Zero-PII · SHA-256<br>
        <a href="https://github.com/sourceseal-star/Red-team-tauri">Red-team-tauri</a>
    </div>
</body>
</html>"""
