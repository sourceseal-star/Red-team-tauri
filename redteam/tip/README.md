# TIP — Threat Intelligence Platform

Plataforma centralizada de inteligencia de amenazas que gestiona IoCs detectados por todos los módulos del Red Team, los distribuye como blocklists, y exporta a formato STIX 2.1 compatible con MISP, OpenCTI y ThreatConnect. Incluye integración TAXII 2.1 para federación de inteligencia.

---

## Estructura

```
tip/
├── __init__.py          # Exports: IoC, ThreatIntelPlatform
├── platform.py          # IoC dataclass + ThreatIntelPlatform (gestión de IoCs, blocklists)
├── stix_exporter.py     # StixExporter — construye STIX 2.1 bundles manualmente (sin lib stix2)
├── stix_taxii.py        # STIXBundle + TAXIIPublisher + TAXIISubscriber (usa lib stix2, 50 técnicas MITRE)
├── taxii_client.py      # TaxiiClient — push STIX bundles a servidor TAXII 2.1
└── test_stix_export.py # Unit tests
```

---

## Componentes

### ThreatIntelPlatform (platform.py)

Gestión centralizada de IoCs:

```python
from tip.platform import IoC, ThreatIntelPlatform

tip = ThreatIntelPlatform()

# Agregar IoCs detectados por diferentes módulos
tip.add_ioc(IoC(type="ip", value="203.0.113.50", source="ndr", confidence=0.95, tags=["c2"]))
tip.add_ioc(IoC(type="domain", value="evil.com", source="deception", confidence=0.8))
tip.add_ioc(IoC(type="hash", value="a"*64, source="probe", confidence=0.7))

# Blocklist automática (confidence >= 0.7)
print(tip.get_blocklist())  # ['203.0.113.50', 'a'*64, 'evil.com']

# Resumen
print(tip.get_summary())
# {'total_iocs': 3, 'blocklist_size': 3, 'by_type': {...}, 'by_source': {...}}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `type` | str | ip, domain, hash, url, email |
| `value` | str | Valor del IoC |
| `source` | str | Módulo que lo detectó (ndr, deception, probe, soar, xdr) |
| `confidence` | float | 0.0 a 1.0 — >= 0.7 va a blocklist |
| `first_seen` | datetime | Timestamp de primera detección |
| `tags` | list | Tags adicionales (c2, beaconing, malware, etc.) |

### StixExporter (stix_exporter.py)

Exporta IoCs a STIX 2.1 bundles **sin requerir la librería `stix2`** — construye el JSON manualmente:

- **Indicators** — Crea objetos STIX Indicator con patrones (ej. `[ipv4-addr:value = '203.0.113.50']`)
- **Observables** — Crea objetos STIX observables (ipv4-addr, domain-name, url, file, email-addr)
- **Report** — Genera un STIX Report que agrupa todos los hallazgos
- **MISP export** — Convierte IoCs a formato MISP event para importación directa en MISP
- **Validación** — Verifica schema básico STIX 2.1 del bundle

#### Mapeo de tipos STIX

| IoC type | STIX pattern | STIX type |
|----------|-------------|-----------|
| ip | `ipv4-addr:value` | ipv4-addr |
| domain | `domain-name:value` | domain-name |
| url | `url:value` | url |
| hash | `file:hashes.'SHA-256'` | file |
| email | `email-addr:value` | email-addr |

#### Labels por fuente

| Source | Label STIX |
|--------|------------|
| soar | malicious-activity |
| probe | anomalous-activity |
| otros | suspicious-activity |

### STIX + TAXII (stix_taxii.py)

Integración completa con librería `stix2`:

- **STIXBundle** — Wrapper para crear bundles STIX 2.1 con Indicator, AttackPattern, Malware, Infrastructure, Relationship
- **50 técnicas MITRE ATT&CK** — Base de datos embebida con táctica, kill chain phase y descripción
- **TAXIIPublisher** — Publica bundles a un servidor TAXII 2.1
- **TAXIISubscriber** — Se suscribe a colecciones TAXII para recibir inteligencia

### TaxiiClient (taxii_client.py)

Cliente TAXII 2.1 para enviar STIX bundles:

```python
from tip.taxii_client import TaxiiClient

client = TaxiiClient(
    server_url="https://taxii.server.com",
    api_key="bearer-token",
    collection_id="col-uuid"
)

# Descubrir colecciones disponibles
collections = client.discover_collections()

# Enviar bundle
result = client.push_to_collection(stix_bundle)
# Sin server configurado → fallback a archivo local en reports/
```

---

## Uso completo

```python
from tip.platform import IoC, ThreatIntelPlatform
from tip.stix_exporter import StixExporter
from tip.taxii_client import TaxiiClient

# 1. Centralizar IoCs
tip = ThreatIntelPlatform()
tip.add_ioc(IoC(type="ip", value="203.0.113.50", source="ndr", confidence=0.95, tags=["c2"]))
tip.add_ioc(IoC(type="domain", value="malware.evil.com", source="soar", confidence=0.9))

# 2. Exportar a STIX 2.1
exporter = StixExporter()
bundle = exporter.export_iocs(tip.iocs)
assert exporter.validate()  # Validar schema

# 3. Guardar a archivo
exporter.save("reports/threat-intel-2026-07-23.json")

# 4. O exportar a MISP
misp_event = exporter.to_misp_event(tip.iocs, event_info="Red Team Scan 2026-07-23")

# 5. Push a TAXII server
taxii = TaxiiClient(server_url="https://taxii.server.com", api_key="key", collection_id="col-1")
result = taxii.push_to_collection(bundle)
```

---

## Tests

```bash
cd tip/
python -m pytest test_stix_export.py -v
# o
python test_stix_export.py
```

Cobertura: IoC creation, ThreatIntelPlatform (add, blocklist threshold, summary), StixExporter (indicator, observable, bundle, validation, JSON, save, labels, report, MISP), TaxiiClient (init, local fallback, discover).

---

## Dependencias

```
# StixExporter — sin dependencias externas (stdlib only)
# stix_taxii.py — requiere:
stix2>=3.0
requests>=2.31
# taxii_client.py — requiere:
requests>=2.31
```
