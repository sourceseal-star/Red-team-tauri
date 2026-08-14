"""
Integración con TheHive — Crea un case por cada hallazgo crítico/alto.
Lee el último reporte y abre cases via TheHive REST API.
"""
import os
import json
import pathlib
import urllib.request
import urllib.error
import datetime
from typing import List, Dict, Optional


THEHIVE_URL = os.environ.get("THEHIVE_URL", "http://localhost:9000")
THEHIVE_KEY = os.environ.get("THEHIVE_API_KEY", "")


def _request(method: str, path: str, body: Dict = None) -> Dict:
    url = f"{THEHIVE_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if THEHIVE_KEY:
        headers["Authorization"] = f"Bearer {THEHIVE_KEY}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return {"ok": True, "status": r.status, "body": r.read().decode()[:1000]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode()[:500]}
    except Exception as e:
        return {"ok": None, "error": str(e), "dry_run": True}


def create_case_for_finding(finding: Dict, agent_id: str = "redteam-agent") -> Optional[str]:
    """Crea un case en TheHive para un finding de severidad critical/high."""
    if not THEHIVE_KEY:
        return None

    sev_map = {
        "critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0,
    }
    severity = sev_map.get(finding.get("severity", "info"), 0)
    if severity < 3:  # solo critical/high
        return None

    body = {
        "title": f"[{finding['severity'].upper()}] {finding['title']}",
        "description": f"**Escenario**: {finding['scenario']}\n\n"
                       f"**Descripción**: {finding['description']}\n\n"
                       f"**Evidencia**: `{finding.get('evidence_path', '')}`\n\n"
                       f"**Remediación**: {finding.get('remediation', '')}",
        "severity": severity,
        "tags": ["redteam", "sourcesealcorp", finding["scenario"], agent_id],
        "tlp": 2,  # AMBER
        "pap": 2,  # AMBER
        "status": "Open",
    }
    r = _request("POST", "/api/case", body)
    if r.get("ok"):
        try:
            return json.loads(r["body"]).get("_id")
        except Exception:
            return "created"
    return None


def ingest_report(report_path: str) -> Dict:
    """Lee un reporte JSON y crea cases para hallazgos críticos/altos."""
    p = pathlib.Path(report_path)
    if not p.exists():
        return {"error": f"No existe {report_path}"}

    report = json.loads(p.read_text())
    findings = report.get("findings", [])
    created = []

    for f in findings:
        case_id = create_case_for_finding(f)
        if case_id:
            created.append({"scenario": f["scenario"], "title": f["title"], "case_id": case_id})

    return {
        "report": str(p),
        "findings_total": len(findings),
        "cases_created": len(created),
        "created": created,
        "ingested_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 case_creator.py <ruta_al_reporte.json>")
        sys.exit(1)
    print(json.dumps(ingest_report(sys.argv[1]), indent=2))
