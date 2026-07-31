# SOAR — Security Orchestration, Automation & Response

Módulo SOAR del SourceSeal Red Team Toolkit. Ejecuta playbooks de respuesta como DAGs con paralelismo, rollback automático y tracking de incidentes.

## Arquitectura

```
soar/
├── engine.py           # SOAREngine original (8 playbooks básicos inline)
├── dag_executor.py     # DAG executor: topological sort + paralelismo + rollback
├── handlers.py         # HTTP handlers reales (WAF, ZTNA, Auth, Email, DNS, Slack)
├── incident_manager.py # Ciclo de vida de incidentes + MTTR/MTTD
├── playbooks/          # 6 playbooks JSON separados
│   ├── playbook_phishing.json
│   ├── playbook_ransomware.json
│   ├── playbook_c2_beaconing.json
│   ├── playbook_credential_stuffing.json
│   ├── playbook_lateral_movement.json
│   └── playbook_data_exfiltration.json
├── test_dag_executor.py
└── requirements.txt
```

## DAG Executor — Uso

```python
import json
from soar.dag_executor import DAGExecutor
from soar.handlers import HANDLER_REGISTRY

with open("soar/playbooks/playbook_phishing.json") as f:
    playbook = json.load(f)

executor = DAGExecutor(playbook, HANDLER_REGISTRY)
report = executor.execute(context={
    "incident_id": "INC-2026-001",
    "source_ip": "192.168.1.100",
    "sender_email": "evil@attacker.com",
    "user_id": "user-abc123",
    "slack_webhook_url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
})
print(report["overall_status"])  # SUCCESS / PARTIAL / FAILED
```

## Ciclo de vida de incidentes

```
OPEN → INVESTIGATING → CONTAINED → ERADICATED → RECOVERED → CLOSED
```

```python
from soar.incident_manager import IncidentManager

mgr = IncidentManager()
inc = mgr.create_incident({
    "title": "Phishing attack detected",
    "severity": "HIGH",
    "mitre_techniques": ["T1566"],
    "source_ip": "1.2.3.4",
    "affected_hosts": ["host-01"],
})

mgr.update_state(inc.id, "INVESTIGATING", note="SOC analyst assigned")
mgr.update_state(inc.id, "CONTAINED")
mgr.update_state(inc.id, "RECOVERED")

report = mgr.export_report(inc.id)
metrics = mgr.get_metrics()
print(metrics["avg_mttr_seconds"])
```

## Playbooks disponibles

| Playbook                     | MITRE       | Severidad | Pasos |
|------------------------------|-------------|-----------|-------|
| playbook_phishing            | T1566       | HIGH      | 4     |
| playbook_ransomware          | T1486       | CRITICAL  | 4     |
| playbook_c2_beaconing        | T1071       | HIGH      | 4     |
| playbook_credential_stuffing | T1110       | MEDIUM    | 3     |
| playbook_lateral_movement    | T1021       | HIGH      | 3     |
| playbook_data_exfiltration   | T1041       | CRITICAL  | 3     |

## Schema de un playbook JSON

```json
{
  "name": "playbook_example",
  "description": "...",
  "mitre_techniques": ["T1566"],
  "severity": "HIGH",
  "steps": [
    {
      "id": "step_1",
      "name": "Human-readable name",
      "handler": "quarantine_email",
      "params": {"email_provider": "o365"},
      "depends_on": [],
      "timeout_seconds": 30,
      "rollback_handler": "restore_email",
      "continue_on_failure": false
    }
  ]
}
```

## Handlers disponibles

| Handler              | Acción                             | Rollback         |
|----------------------|------------------------------------|------------------|
| block_ip_waf         | Bloquear IP en Cloudflare/AWS WAF  | unblock_ip_waf   |
| revoke_ztna_session  | Revocar sesión ZTNA                | —                |
| disable_user_auth    | Deshabilitar usuario Auth0/Keycloak| —                |
| quarantine_email     | Cuarentena email O365/Workspace    | restore_email    |
| dns_sinkhole         | Sinkhole DNS para dominio C2       | —                |
| slack_alert          | Alerta a webhook Slack             | —                |

## Ejecutar tests

```bash
cd redteam/soar
pip install -r requirements.txt
python -m pytest test_dag_executor.py -v
# o con unittest:
python test_dag_executor.py
```

## Integración con XDR

El flujo típico es:
1. `correlator.py` detecta un patrón → genera `XDREvent`
2. `incident_manager.py` crea un `Incident` y auto-asigna el playbook según MITRE
3. `dag_executor.py` carga el playbook JSON y lo ejecuta
4. Los `handlers.py` ejecutan las acciones reales (WAF, ZTNA, email, Slack)
5. El reporte se almacena en el incidente para auditoría
