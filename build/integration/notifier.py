"""
Notificador — Envía alertas por email, Slack o webhook cuando hay hallazgos críticos.
Lee el último reporte y dispara la notificación.
"""
import os
import json
import pathlib
import smtplib
import urllib.request
import urllib.error
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict


SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")
GENERIC_WEBHOOK = os.environ.get("ALERT_WEBHOOK", "")
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_USER = os.environ.get("SMTP_USER", "")
EMAIL_PASS = os.environ.get("SMTP_PASS", "")
EMAIL_FROM = os.environ.get("ALERT_FROM", "redteam@example.com")
EMAIL_TO = [a.strip() for a in os.environ.get("ALERT_TO", "").split(",") if a.strip()]


def _slack(report: Dict) -> bool:
    if not SLACK_WEBHOOK:
        return False
    sev = report.get("by_severity", {})
    text = (f"🔴 *Red Team Reporte* — {report.get('finished_at', '')}\n"
            f"Críticos: *{sev.get('critical', 0)}* | Altos: *{sev.get('high', 0)}*\n"
            f"Total: {report.get('total_findings', 0)}")
    payload = {"text": text, "mrkdwn": True}
    req = urllib.request.Request(SLACK_WEBHOOK, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _webhook(report: Dict) -> bool:
    if not GENERIC_WEBHOOK:
        return False
    req = urllib.request.Request(GENERIC_WEBHOOK, data=json.dumps(report).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _email(report: Dict) -> bool:
    if not (EMAIL_HOST and EMAIL_TO and EMAIL_USER):
        return False
    sev = report.get("by_severity", {})
    if sev.get("critical", 0) == 0 and sev.get("high", 0) == 0:
        return False  # no molestar si no hay críticos ni altos
    body_lines = [
        f"Red Team Reporte — {report.get('finished_at', '')}",
        f"Críticos: {sev.get('critical', 0)} | Altos: {sev.get('high', 0)}",
        f"Total hallazgos: {report.get('total_findings', 0)}",
        "", "Top críticos:", "",
    ]
    for f in report.get("findings", [])[:10]:
        if f.get("severity") in ("critical", "high"):
            body_lines.append(f"- [{f['severity'].upper()}] {f['title']}")
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = f"[RedTeam] {sev.get('critical', 0)} críticos, {sev.get('high', 0)} altos"
    msg.attach(MIMEText("\n".join(body_lines), "plain"))

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=15) as s:
            s.starttls()
            s.login(EMAIL_USER, EMAIL_PASS)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        return True
    except Exception:
        return False


def notify(report_path: str) -> Dict:
    p = pathlib.Path(report_path)
    if not p.exists():
        return {"error": f"No existe {report_path}"}
    report = json.loads(p.read_text())
    return {
        "slack": _slack(report),
        "webhook": _webhook(report),
        "email": _email(report),
        "notified_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 notifier.py <reporte.json>")
        sys.exit(1)
    print(json.dumps(notify(sys.argv[1]), indent=2))
