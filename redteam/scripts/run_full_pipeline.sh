#!/bin/bash
# Pipeline completo del agente Red Team
# Uso: ./scripts/run_full_pipeline.sh [path_a_app.apk] [backend_url]
set -e

APP="${1:-evidence/dummy.apk}"
BACKEND="${2:-https://api.sourcesealcorp.local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p evidence reports

echo "=== [1/4] Ejecutando 11 escenarios ==="
python3 runner/orchestrator.py --target "$APP" --backend "$BACKEND" --output reports/ | tee /tmp/rt-out.log

LATEST_REPORT=$(ls -t reports/report-*.json | head -1)
echo ""
echo "=== [2/4] Notificando hallazgos críticos ==="
python3 integration/notifier.py "$LATEST_REPORT" || echo "(notifier falló, continuando)"

echo ""
echo "=== [3/4] Creando cases en TheHive ==="
python3 integration/thehive/case_creator.py "$LATEST_REPORT" || echo "(thehive no configurado)"

echo ""
echo "=== [4/4] Resumen ==="
python3 -c "
import json
r = json.load(open('$LATEST_REPORT'))
print(f'  Total: {r[\"total_findings\"]} | Sev: {r[\"by_severity\"]}')
print(f'  Reporte: $LATEST_REPORT')
print(f'  Markdown: reports/latest.md')
"

echo ""
echo "=== Tests unitarios ==="
python3 tests/test_luhn.py
