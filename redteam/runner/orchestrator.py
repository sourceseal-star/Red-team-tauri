#!/usr/bin/env python3
"""
Red Team Orchestrator
=====================
Ejecuta los escenarios de ataque contra el software propio (app móvil + backend web),
recoge evidencia y produce un reporte diario. Diseñado para correr en CI/CD o como cron.

Uso:
    python3 orchestrator.py --target build/app.apk --backend https://api.example.com --output reports/

v2.1 (2026-07-27): Finding incluye campo 'status'; _to_markdown muestra columna Estado
  y advertencia de tests no ejecutados. _count_by_severity excluye skipped del conteo real.
"""
import argparse
import json
import os
import sys
import datetime
import importlib
import pathlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

_AGENT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))


@dataclass
class Finding:
    scenario: str
    severity: str          # critical | high | medium | low | info
    title: str
    description: str
    evidence_path: str
    remediation: str
    timestamp: str
    status: str = "executed"   # executed | skipped | error — v2.1


class Orchestrator:
    def __init__(self, target: str, backend: str, output_dir: str):
        self.target = target
        self.backend = backend
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.findings: List[Finding] = []
        self.started_at = datetime.datetime.utcnow().isoformat()

    def run_scenario(self, module_name: str):
        try:
            mod = importlib.import_module(f"scenarios.{module_name}")
            print(f"[+] Ejecutando escenario: {module_name}")
            results = mod.run(self.target, self.backend, str(self.output_dir))
            for r in results:
                # Detectar si el finding viene de un ataque skipped
                # (título contiene "NO EJECUTADO" o "no evaluado" o "no accesible")
                title_lower = r.get("title", "").lower()
                desc_lower = r.get("description", "").lower()
                finding_status = "executed"
                if ("no ejecutado" in title_lower or "no evaluado" in title_lower
                        or "no accesible" in title_lower
                        or "backend no accesible" in desc_lower
                        or "no responde" in desc_lower):
                    finding_status = "skipped"
                self.findings.append(Finding(
                    timestamp=datetime.datetime.utcnow().isoformat(),
                    status=finding_status,
                    **{k: v for k, v in r.items() if k != "status"},
                ))
        except Exception as e:
            print(f"[!] Fallo en escenario {module_name}: {e}", file=sys.stderr)
            self.findings.append(Finding(
                scenario=module_name,
                severity="info",
                title=f"Escenario {module_name} no se ejecutó",
                description=str(e),
                evidence_path="",
                remediation="Revisar dependencias y configuración del runner.",
                timestamp=datetime.datetime.utcnow().isoformat(),
                status="error",
            ))

    def run_all(self):
        scenarios = [
            "rng", "pinning", "sidechannel", "keyhandling",
            "payments", "biometric", "business_logic", "imei", "multiplatform",
            "sourcesealcorp", "recovery_page", "pegasus",
        ]
        for s in scenarios:
            self.run_scenario(s)
        self.write_report()

    def write_report(self):
        report = {
            "started_at": self.started_at,
            "finished_at": datetime.datetime.utcnow().isoformat(),
            "target": self.target,
            "backend": self.backend,
            "total_findings": len(self.findings),
            "by_severity": self._count_by_severity(),
            "skipped_count": sum(1 for f in self.findings if f.status == "skipped"),
            "findings": [asdict(f) for f in self.findings],
        }
        out = self.output_dir / f"report-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        md = self._to_markdown(report)
        (self.output_dir / "latest.md").write_text(md)
        print(f"[OK] Reporte escrito en {out}")

    def _count_by_severity(self) -> Dict[str, int]:
        """Cuenta severidad SOLO de hallazgos ejecutados (excluye skipped)."""
        out = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in self.findings:
            if f.status != "skipped":   # FIX: skipped no cuenta como fallo
                out[f.severity] = out.get(f.severity, 0) + 1
        return out

    def _to_markdown(self, r: Dict[str, Any]) -> str:
        sev = r["by_severity"]
        skipped_count = r.get("skipped_count", 0)
        findings_all = r["findings"]

        # Hallazgos skipped para la sección de advertencia
        skipped_findings = [f for f in findings_all if f.get("status") == "skipped"]
        active_findings = [f for f in findings_all if f.get("status") != "skipped"]

        lines = [
            f"# Reporte Red Team — {r['finished_at']}",
            f"- **Target**: `{r['target']}`",
            f"- **Backend**: `{r['backend']}`",
            f"- **Total hallazgos**: {r['total_findings']} ({skipped_count} no ejecutados)",
            f"- **Severidad** (ejecutados): 🔴 {sev['critical']} críticos · "
            f"🟠 {sev['high']} altos · 🟡 {sev['medium']} medios · "
            f"🔵 {sev['low']} bajos · ⚪ {sev['info']} info",
            "",
        ]

        # ── Sección de advertencia si hay skipped ──────────────────────────────
        if skipped_findings:
            lines += [
                "## ⚠️ Tests No Ejecutados",
                "",
                "Los siguientes ataques **no se ejecutaron** porque el backend no responde:",
                "",
            ]
            # Agrupar por escenario
            by_scenario: Dict[str, List] = {}
            for f in skipped_findings:
                s = f.get("scenario", "unknown")
                by_scenario.setdefault(s, []).append(f)
            for scenario, sfs in by_scenario.items():
                lines.append(f"- **{scenario}**: {sfs[0].get('description', 'sin detalle')}")
                lines.append(f"  - Total no ejecutados: {len(sfs)}")
            lines += [
                "",
                "> **Recomendación:** Verifica la configuración de `SOURCESEAL_API` y la "
                "conectividad de red antes de tomar acción sobre estos ataques.",
                "",
            ]

        # ── Tabla de hallazgos ejecutados ─────────────────────────────────────
        lines += [
            "## Hallazgos",
            "",
            "| Estado | Severidad | Escenario | Título |",
            "|--------|-----------|-----------|--------|",
        ]
        STATUS_BADGE = {
            "executed": "",
            "skipped": "⏭️ SKIPPED",
            "error": "⚠️ ERROR",
        }
        SEV_BADGE = {
            "critical": "🔴 CRITICAL",
            "high": "🟠 HIGH",
            "medium": "🟡 MEDIUM",
            "low": "🔵 LOW",
            "info": "⚪ INFO",
        }
        for f in findings_all:
            status_label = STATUS_BADGE.get(f.get("status", "executed"), "▶️ OK")
            sev_label = SEV_BADGE.get(f.get("severity", "info"), f.get("severity", "").upper())
            title = f.get("title", "")
            # Badges inline en el título
            if f.get("status") == "skipped":
                title_display = f"⏭️ {title}"
            elif f.get("severity") in ("critical", "high") and f.get("status") == "executed":
                title_display = f"❌ {title}"
            elif f.get("severity") == "info" and f.get("status") == "executed":
                title_display = f"✅ {title}"
            else:
                title_display = title
            lines.append(
                f"| {status_label} | {sev_label} | `{f.get('scenario','')}` | {title_display} |"
            )

        lines.append("")
        lines.append("## Detalle de Hallazgos")
        lines.append("")

        for f in findings_all:
            status = f.get("status", "executed")
            badge = "⏭️ SKIPPED" if status == "skipped" else \
                    "⚠️ ERROR" if status == "error" else \
                    f"[{f.get('severity','').upper()}]"
            lines.append(f"### {badge} {f.get('title','')}")
            lines.append(f"- **Escenario**: `{f.get('scenario','')}`")
            lines.append(f"- **Estado**: `{status}`")
            lines.append(f"- **Descripción**: {f.get('description','')}")
            lines.append(f"- **Evidencia**: `{f.get('evidence_path','')}`")
            lines.append(f"- **Remediación**: {f.get('remediation','')}")
            lines.append("")

        return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--backend", required=True)
    p.add_argument("--output", default="reports/")
    args = p.parse_args()
    o = Orchestrator(args.target, args.backend, args.output)
    o.run_all()


if __name__ == "__main__":
    main()
