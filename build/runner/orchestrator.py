#!/usr/bin/env python3
"""
Red Team Orchestrator
=====================
Ejecuta los escenarios de ataque contra el software propio (app móvil + backend web),
recoge evidencia y produce un reporte diario. Diseñado para correr en CI/CD o como cron.

Uso:
    python3 orchestrator.py --target build/app.apk --backend https://api.example.com --output reports/
"""
import argparse
import json
import os
import sys
import datetime
import importlib
import pathlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

# Asegurar que la raíz del agente está en sys.path sin importar desde dónde se ejecute
_AGENT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))


@dataclass
class Finding:
    scenario: str
    severity: str          # critical | high | medium | low | info
    title: str
    description: str
    evidence_path: str     # ruta a artefacto (pcap, log, captura)
    remediation: str
    timestamp: str


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
                self.findings.append(Finding(timestamp=datetime.datetime.utcnow().isoformat(), **r))
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
            "findings": [asdict(f) for f in self.findings],
        }
        out = self.output_dir / f"report-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        md = self._to_markdown(report)
        (self.output_dir / "latest.md").write_text(md)
        print(f"[OK] Reporte escrito en {out}")

    def _count_by_severity(self) -> Dict[str, int]:
        out = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out

    def _to_markdown(self, r: Dict[str, Any]) -> str:
        sev = r["by_severity"]
        lines = [
            f"# Reporte Red Team — {r['finished_at']}",
            f"- **Target**: `{r['target']}`",
            f"- **Backend**: `{r['backend']}`",
            f"- **Total hallazgos**: {r['total_findings']}",
            f"- **Severidad**: 🔴 {sev['critical']} críticos · 🟠 {sev['high']} altos · 🟡 {sev['medium']} medios · 🔵 {sev['low']} bajos",
            "",
            "## Hallazgos",
            "",
        ]
        for f in r["findings"]:
            lines.append(f"### [{f['severity'].upper()}] {f['title']}")
            lines.append(f"- **Escenario**: `{f['scenario']}`")
            lines.append(f"- **Descripción**: {f['description']}")
            lines.append(f"- **Evidencia**: `{f['evidence_path']}`")
            lines.append(f"- **Remediación**: {f['remediation']}")
            lines.append("")
        return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="Ruta al APK/IPA o identificador de build")
    p.add_argument("--backend", required=True, help="URL del backend/API")
    p.add_argument("--output", default="reports/", help="Directorio de salida")
    args = p.parse_args()

    o = Orchestrator(args.target, args.backend, args.output)
    o.run_all()


if __name__ == "__main__":
    main()
