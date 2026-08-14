# NDR — Network Detection & Response

Módulo de detección y respuesta de red que combina heurísticas estadísticas con ML (Isolation Forest) para identificar anomalías en tiempo real: beaconing C2, exfiltración low-and-slow, tunneling DNS/ICMP, DGA y tráfico anómalo.

---

## Estructura

```
ndr/
├── __init__.py          # Exports: NDREngine, TrafficFlow, AnomalyAlert, C2Detector, ExfilDetector, AnomalyDetector
├── engine.py            # Motor comportamental (heuristicas estadísticas — baseline adaptativo)
├── ml_detector.py       # ML detector (IsolationForest + Z-Score + DNS tunneling + DGA)
├── network_capture.py   # Captura Scapy/Pyshark + buffer circular 10K flujos + reconstrucción TCP/UDP
├── behavioral.py        # Análisis comportamental adicional
└── test_detector.py     # Unit tests
```

---

## Componentes

### NDREngine (engine.py)

Motor comportacional que reemplaza reglas estáticas con detección estadística:

- **C2Detector** — Detecta beaconing por intervalos regulares entre conexiones. Mínimo 5 conexiones, tolerancia de intervalo configurable (default 30%).
- **ExfilDetector** — Detecta exfiltración low-and-slow por volumen acumulado anómalo. Compara bytes enviados vs. recibidos.
- **Baseline adaptativo** — Aprende el patrón normal de tráfico y alerta cuando hay desviaciones significativas.

### ML Detector (ml_detector.py)

Capa de ML con múltiples detectores:

| Detector | Técnica | Detección |
|----------|---------|-----------|
| `ZScoreAnomalyDetector` | Z-Score estadístico | Desviación > 3σ en bytes/duración por IP:puerto |
| `IsolationForestDetector` | Isolation Forest (sklearn) | Anomalías multidimensionales [bytes, puerto, hora, día] |
| `DNSTunnelingDetector` | Heurística + entropía Shannon | Subdominios largos, alta entropía, frecuencia anómala |
| `DGA detection` | Entropía + patrones | Nombres de dominio generados aleatoriamente |

#### Dependencias opcionales

```
numpy
scikit-learn
```

Si `sklearn` no está instalado, el `IsolationForestDetector` se desactiva automáticamente (graceful fallback). Los demás detectores funcionan con stdlib únicamente.

### Network Capture (network_capture.py)

- Captura de paquetes vía Scapy o PyShark
- Buffer circular de 10,000 flujos concurrentes
- Reconstrucción TCP/UDP bidireccional
- Parsing de DNS queries y respuestas
- Detección de ICMP tunneling por payload anómalo

---

## Tipos de Alerta

| Tipo | Severidad | MITRE | Descripción |
|------|-----------|-------|-------------|
| `beaconing` | HIGH | T1071 | Comunicaciones C2 con intervalos regulares |
| `exfiltration` | CRITICAL | T1041 | Transferencia de datos anómala hacia exterior |
| `tunneling` | HIGH | T1572 | Tunneling DNS o ICMP no autorizado |
| `anomaly` | MEDIUM | — | Anomalía estadística genérica (Z-Score o IsolationForest) |

---

## Uso

```python
from ndr.engine import NDREngine, TrafficFlow
from ndr.ml_detector import AnomalyDetector

# Motor heurístico
engine = NDREngine()

# ML detector
ml_detector = AnomalyDetector()

# Procesar un flujo
flow = TrafficFlow(
    src_ip="192.168.1.10", dst_ip="203.0.113.50", dst_port=443,
    protocol="TCP", bytes_sent=1024, bytes_received=4096,
    timestamp=time.time()
)

alert = engine.observe(flow)
if alert:
    print(f"[{alert.severity}] {alert.type}: {alert.description}")

# ML analysis
from ndr.ml_detector import TrafficFlow as MLFlow, ZScoreAnomalyDetector

ml_flow = MLFlow(
    src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=50000, dst_port=443,
    protocol="TCP", bytes_sent=999999, bytes_recv=100, duration_ms=100.0
)

detector = ZScoreAnomalyDetector()
alerts = detector.analyze(ml_flow)
```

---

## Tests

```bash
cd ndr/
python -m pytest test_detector.py -v
# o
python test_detector.py
```

---

## Dependencias

```
scapy>=2.5
pyshark>=0.6
numpy>=1.24          # opcional — para IsolationForest
scikit-learn>=1.3    # opcional — para IsolationForest
```
