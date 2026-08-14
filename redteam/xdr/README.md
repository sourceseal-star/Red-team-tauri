# SourceSeal Red Team Toolkit - XDR (Extended Detection & Response) Module

Este módulo contiene el motor de correlación de eventos de seguridad (XDR), el analizador de la cadena de ataque (Cyber Kill Chain) y el mapeador de la superficie de ataque para evaluar el progreso y madurez de una intrusión cibernética.

## Estructura del Módulo

El módulo consta de tres componentes principales:

1. **XDR Correlator (`correlator.py`)**:
   - Define las estructuras para `XDREvent` e `Incident`.
   - Incluye una base de datos local con las 20 técnicas MITRE ATT&CK base para el correlador, incluyendo descripciones detalladas y mitigaciones recomendadas.
   - Implementa `XDRCorrelator` para agrupar eventos de seguridad concurrentes o relacionados e identificar incidentes.

2. **Kill Chain Analyzer (`kill_chain.py`)**:
   - Define el enum `KillChainPhase` con las 7 fases de la Cyber Kill Chain de Lockheed Martin:
     - `RECONNAISSANCE`
     - `WEAPONIZATION`
     - `DELIVERY`
     - `EXPLOITATION`
     - `INSTALLATION`
     - `C2`
     - `ACTIONS_ON_OBJECTIVES`
   - Implementa `KillChainAnalyzer` para mapear tácticas MITRE ATT&CK a las fases lógicas de la Kill Chain, calcular la madurez del ataque (`calculate_attack_maturity`) y predecir el próximo paso probable (`predict_next_phase`).
   - Implementa `KillChainVisualizer` para generar visualizaciones del progreso de la intrusión en tres formatos:
     - **ASCII Art**: Una barra secuencial interactiva en terminal.
     - **Diagrama Mermaid**: Código autogenerado para diagramas dinámicos.
     - **JSON Dashboard**: Exportación estructurada para interfaces web de SOC/Red Team.

3. **Attack Surface Mapper (`attack_surface.py`)**:
   - Define el dataclass `AttackSurface`.
   - Implementa `AttackSurfaceMapper` para evaluar el riesgo de seguridad de la infraestructura a partir de puertos abiertos, tecnologías y vulnerabilidades CVE detectadas.
   - Proporciona métricas como puntuación de riesgo global (`calculate_risk_score`), matriz de exposición detallada (`get_exposure_matrix`) y comparación histórica de superficies (`compare_surfaces`) para identificar regresiones o nuevas exposiciones de seguridad.

---

## Modelos de Datos Clave

### 1. XDREvent
Representa un evento de seguridad recolectado por un agente.
```python
from datetime import datetime
from xdr import XDREvent

event = XDREvent(
    event_id="EV-001",
    timestamp=datetime.now(),
    source="endpoint_agent",
    event_type="process_creation",
    description="Ejecución sospechosa de PowerShell",
    mitre_techniques=["T1059"]
)
```

### 2. Incident
Representa un conjunto de eventos correlacionados bajo un único incidente de seguridad.
```python
from datetime import datetime
from xdr import Incident, XDREvent

incident = Incident(
    incident_id="INC-100",
    title="Intrusión en fase temprana detectada",
    description="Se detectó una secuencia sospechosa de escaneo y ejecución de comandos.",
    severity="HIGH",
    timestamp=datetime.now(),
    events=[event],
    mitre_techniques=["T1059"]
)
```

---

## Uso Básico

### 1. Correlación de Eventos y Análisis de Kill Chain
```python
from datetime import datetime
from xdr import XDREvent, Incident, KillChainAnalyzer, KillChainVisualizer

# Crear eventos representativos
ev1 = XDREvent("EV-01", datetime.now(), "firewall", "network_scan", "Escaneo de puertos", ["T1595"])
ev2 = XDREvent("EV-02", datetime.now(), "email", "phishing", "Phishing recibido", ["T1566"])
ev3 = XDREvent("EV-03", datetime.now(), "endpoint", "powershell", "PowerShell malicioso", ["T1059"])

# Correlacionar en un Incidente
incident = Incident(
    incident_id="INC-001",
    title="Intrusión Detectada",
    description="Múltiples eventos sospechosos correlacionados",
    severity="HIGH",
    timestamp=datetime.now(),
    events=[ev1, ev2, ev3],
    mitre_techniques=["T1595", "T1566", "T1059"]
)

# Analizar la trayectoria de ataque
analyzer = KillChainAnalyzer()
path = analyzer.analyze([incident])

print(f"Fases activas: {[phase.value for phase in path.phases]}")
print(f"Madurez del ataque: {analyzer.calculate_attack_maturity(path)}%")
print(f"Confianza del análisis: {path.confidence_score}%")

# Obtener recomendaciones de mitigación por fase detectada
countermeasures = analyzer.get_recommended_countermeasures(path)
print("Contramedidas recomendadas:", countermeasures)

# Visualizar en ASCII Art
print(KillChainVisualizer.to_ascii(path))
```

### 2. Evaluación de la Superficie de Ataque
```python
from xdr import AttackSurfaceMapper

scan_data = {
    "endpoints": ["192.168.1.50"],
    "ports": [22, 443, 8080],
    "technologies": ["OpenSSH", "Nginx", "Apache Tomcat"],
    "vulnerabilities": [
        {
            "cve": "CVE-2023-4567",
            "cvss": 9.8,
            "component": "Nginx",
            "description": "RCE en cabecera HTTP"
        }
    ]
}

mapper = AttackSurfaceMapper()
surface = mapper.map_from_scan_results(scan_data)
risk_score = mapper.calculate_risk_score(surface)

print(f"Score de riesgo de la superficie: {risk_score}/10")
```

---

## Pruebas Unitarias
Para correr las pruebas locales de este módulo:
```bash
python3 -m unittest test_correlator.py
```
