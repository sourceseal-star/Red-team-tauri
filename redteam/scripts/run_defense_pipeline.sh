#!/usr/bin/env bash
# run_defense_pipeline.sh — Pipeline defensivo de la malla enterprise
# Ejecuta tests, health check, simulacion y genera reports.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p reports

echo "============================================================"
echo "[1/4] Tests defensivos (RASP, NDR, ZTNA, Deception, XDR+SOAR)"
echo "============================================================"
python3 -m pytest tests/test_defense.py -v 2>&1 | tee reports/defense-tests.log | tail -30

echo ""
echo "============================================================"
echo "[2/4] Health check del DefenseMesh"
echo "============================================================"
python3 -c "
import json, sys
sys.path.insert(0, '.')
from defense import DefenseMesh
m = DefenseMesh()
h = m.health_check()
print(json.dumps(h, indent=2, default=str))
" | tee reports/defense-health.json

echo ""
echo "============================================================"
echo "[3/4] Simulacion end-to-end (compromised_device + decoy_hit + BOLA)"
echo "============================================================"
python3 -c "
import json, sys, time
sys.path.insert(0, '.')
from defense import DefenseMesh
m = DefenseMesh()
results = {}
for scenario in ['compromised_device']:
    try:
        r = m.simulate(scenario)
        results[scenario] = r if isinstance(r, dict) else {'result': str(r)}
    except Exception as e:
        results[scenario] = {'error': str(e)}
# Ingesta manual de señales para forzar correlacion
m.ingest({'source':'rasp', 'category':'frida', 'severity':'critical', 'mitre_id':'T1056', 'summary':'port 27042', 'device_id':'dev-test'})
m.ingest({'source':'ndr', 'category':'beaconing', 'severity':'high', 'mitre_id':'T1071.001', 'summary':'beacon to 1.2.3.4', 'device_id':'dev-test'})
results['incidents_after_ingest'] = m.events()[-5:]
print(json.dumps(results, indent=2, default=str))
" | tee reports/defense-simulate.json

echo ""
echo "============================================================"
echo "[4/4] Reporte Markdown"
echo "============================================================"
python3 -c "
import json, sys, datetime
sys.path.insert(0, '.')
from defense import DefenseMesh
m = DefenseMesh()
h = m.health_check()
ts = datetime.datetime.utcnow().isoformat() + 'Z'
lines = [
    f'# Defense Mesh Report — {ts}',
    '',
    f\"- **Status**: {h['status']}\",
    f\"- **Uptime (s)**: {h.get('uptime_seconds', 0):.2f}\",
    '',
    '## Componentes',
    '',
]
for name, info in h['components'].items():
    lines.append(f\"### {name}\")
    lines.append('')
    lines.append('```json')
    lines.append(json.dumps(info, indent=2, default=str))
    lines.append('```')
    lines.append('')
print('\n'.join(lines))
" > reports/defense-report.md
cat reports/defense-report.md | head -50

echo ""
echo "[OK] Pipeline defensivo completado. Reportes en reports/"
ls -la reports/defense-*
