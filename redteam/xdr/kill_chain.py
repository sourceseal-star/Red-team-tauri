# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - Kill Chain Analyzer & Visualizer
Este módulo implementa el mapeo, análisis y visualización del progreso de una intrusión
según las fases tradicionales de la Cyber Kill Chain de Lockheed Martin combinadas con tácticas MITRE ATT&CK.
"""

import json
from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Importamos las clases e incidentes de XDR correlator
from xdr.correlator import Incident, XDREvent, MITRE_TECHNIQUES


class KillChainPhase(str, Enum):
    """Fases de la Cyber Kill Chain de Lockheed Martin."""
    RECONNAISSANCE = "RECONNAISSANCE"
    WEAPONIZATION = "WEAPONIZATION"
    DELIVERY = "DELIVERY"
    EXPLOITATION = "EXPLOITATION"
    INSTALLATION = "INSTALLATION"
    C2 = "C2"
    ACTIONS_ON_OBJECTIVES = "ACTIONS_ON_OBJECTIVES"


@dataclass
class AttackPath:
    """Representa la trayectoria detectada de un ataque a través de la Kill Chain."""
    phases: List[KillChainPhase] = field(default_factory=list)
    techniques: Dict[KillChainPhase, List[str]] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0  # Puntuación de confianza (0.0 a 100.0)


# Mapeo estricto de tácticas de MITRE a fases de la Cyber Kill Chain
TACTIC_TO_PHASE_MAP = {
    "reconnaissance": KillChainPhase.RECONNAISSANCE,
    "resource-development": KillChainPhase.WEAPONIZATION,
    "initial-access": KillChainPhase.DELIVERY,
    "execution": KillChainPhase.EXPLOITATION,
    "privilege-escalation": KillChainPhase.EXPLOITATION,
    "defense-evasion": KillChainPhase.EXPLOITATION,
    "persistence": KillChainPhase.INSTALLATION,
    "command-and-control": KillChainPhase.C2,
    "credential-access": KillChainPhase.ACTIONS_ON_OBJECTIVES,
    "discovery": KillChainPhase.ACTIONS_ON_OBJECTIVES,
    "lateral-movement": KillChainPhase.ACTIONS_ON_OBJECTIVES,
    "collection": KillChainPhase.ACTIONS_ON_OBJECTIVES,
    "exfiltration": KillChainPhase.ACTIONS_ON_OBJECTIVES,
    "impact": KillChainPhase.ACTIONS_ON_OBJECTIVES
}

# Recomendaciones defensivas detalladas por fase de la Kill Chain
DEFENSIVE_COUNTERMEASURES = {
    KillChainPhase.RECONNAISSANCE: [
        "Implementar limitación de tasa (rate limiting) de peticiones externas y bloquear IPs que realicen escaneos.",
        "Monitorear directorios públicos e información corporativa expuesta en buscadores (OSINT).",
        "Configurar reglas estrictas de firewall para puertos públicos no indispensables."
    ],
    KillChainPhase.WEAPONIZATION: [
        "Establecer sistemas de detección de intrusiones para firmas de frameworks de ataque comunes (Cobalt Strike, Metasploit, Havoc).",
        "Implementar análisis estático y dinámico de archivos en pasarelas de correo y proxies web.",
        "Auditar y endurecer las políticas de firma de binarios de desarrollo interno."
    ],
    KillChainPhase.DELIVERY: [
        "Utilizar pasarelas de correo electrónico seguras (SEG) para filtrar phishing, adjuntos sospechosos y URLs maliciosas.",
        "Desplegar políticas de aislamiento de navegador o Web Proxy con filtrado de reputación en tiempo real.",
        "Implementar autenticación multifactor (MFA) robusta en todos los accesos VPN y portales web externos."
    ],
    KillChainPhase.EXPLOITATION: [
        "Mantener un ciclo riguroso de parcheo de sistemas operativos y aplicaciones expuestas.",
        "Desplegar soluciones EDR/XDR avanzadas con prevención activa frente a exploits y protecciones de memoria.",
        "Restringir la ejecución de PowerShell, bash y otros lenguajes de scripting mediante políticas del sistema (WDAC, AppLocker)."
    ],
    KillChainPhase.INSTALLATION: [
        "Auditar llaves de registro de inicio automático (Autoruns), tareas programadas y servicios recién instalados.",
        "Restringir privilegios de administrador local e implementar el principio de mínimo privilegio (LUA).",
        "Utilizar herramientas de monitoreo de integridad de archivos del sistema (FIM)."
    ],
    KillChainPhase.C2: [
        "Implementar análisis de reputación DNS y bloquear consultas a dominios de reciente registro o categorizados como maliciosos.",
        "Configurar inspección SSL/TLS en firewalls corporativos para identificar tráfico de control remoto encriptado.",
        "Monitorear patrones de tráfico tipo latido (beaconing) hacia servidores externos inusuales."
    ],
    KillChainPhase.ACTIONS_ON_OBJECTIVES: [
        "Desplegar políticas rígidas de prevención de pérdida de datos (DLP) para bloquear descargas masivas e intentos de exfiltración.",
        "Segmentar la red interna de manera estricta para impedir el movimiento lateral no autorizado.",
        "Habilitar protecciones contra ransomware (monitoreo de tasa de escritura rápida y copias de seguridad inmutables fuera de línea)."
    ]
}


class KillChainAnalyzer:
    """Analizador encargado de reconstruir la trayectoria del ataque e inferir su estado."""

    def __init__(self):
        self.phase_order = [
            KillChainPhase.RECONNAISSANCE,
            KillChainPhase.WEAPONIZATION,
            KillChainPhase.DELIVERY,
            KillChainPhase.EXPLOITATION,
            KillChainPhase.INSTALLATION,
            KillChainPhase.C2,
            KillChainPhase.ACTIONS_ON_OBJECTIVES
        ]

    def analyze(self, incidents: List[Incident]) -> AttackPath:
        """
        Analiza una lista de incidentes correlacionados y construye la trayectoria de la Kill Chain.
        
        Ordena cronológicamente, mapea técnicas a fases y calcula puntuaciones.
        """
        if not incidents:
            return AttackPath()

        # 1. Ordenar incidentes cronológicamente
        sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)
        
        detected_phases_set = set()
        techniques_by_phase: Dict[KillChainPhase, List[str]] = {p: [] for p in self.phase_order}
        timeline = []

        # 2. Mapear cada incidente a fases y técnicas
        for inc in sorted_incidents:
            inc_phases = set()
            for tech_id in inc.mitre_techniques:
                # Obtener la técnica de MITRE_TECHNIQUES si existe
                tech_info = MITRE_TECHNIQUES.get(tech_id)
                if tech_info:
                    tactic = tech_info.get("tactic", "").lower()
                    phase = TACTIC_TO_PHASE_MAP.get(tactic)
                    if phase:
                        detected_phases_set.add(phase)
                        inc_phases.add(phase)
                        if tech_id not in techniques_by_phase[phase]:
                            techniques_by_phase[phase].append(tech_id)

            # Si el incidente no tiene técnicas asociadas directamente, buscar en sus eventos individuales
            if not inc_phases:
                for ev in inc.events:
                    for tech_id in ev.mitre_techniques:
                        tech_info = MITRE_TECHNIQUES.get(tech_id)
                        if tech_info:
                            tactic = tech_info.get("tactic", "").lower()
                            phase = TACTIC_TO_PHASE_MAP.get(tactic)
                            if phase:
                                detected_phases_set.add(phase)
                                inc_phases.add(phase)
                                if tech_id not in techniques_by_phase[phase]:
                                    techniques_by_phase[phase].append(tech_id)

            # Añadir registro detallado a la línea de tiempo
            timeline.append({
                "incident_id": inc.incident_id,
                "title": inc.title,
                "severity": inc.severity,
                "timestamp": inc.timestamp.isoformat() if isinstance(inc.timestamp, datetime) else str(inc.timestamp),
                "phases": [p.value for p in inc_phases],
                "techniques": inc.mitre_techniques
            })

        # 3. Ordenar las fases detectadas según el orden lógico de la Cyber Kill Chain
        phases_sorted = [p for p in self.phase_order if p in detected_phases_set]

        # 4. Limpiar diccionario de técnicas para fases no detectadas
        techniques_cleaned = {k: v for k, v in techniques_by_phase.items() if v}

        # 5. Calcular puntuación de confianza (confidence_score)
        # Basado en la cantidad de fases detectadas, la severidad promedio de los incidentes y el alineamiento del flujo
        confidence = self._calculate_confidence(incidents, phases_sorted)

        return AttackPath(
            phases=phases_sorted,
            techniques=techniques_cleaned,
            timeline=timeline,
            confidence_score=round(confidence, 2)
        )

    def calculate_attack_maturity(self, path: AttackPath) -> float:
        """
        Calcula el porcentaje de madurez del ataque (progreso total en la Kill Chain).
        Retorna un valor de 0.0 a 100.0%.
        """
        if not path.phases:
            return 0.0

        # Identificamos el índice máximo de las fases detectadas en el orden lógico
        max_idx = max(self.phase_order.index(p) for p in path.phases)
        
        # El progreso se calcula como la proporción del orden completado
        # Si llega a ACTIONS_ON_OBJECTIVES (el último), se considera 100% de madurez.
        maturity = ((max_idx + 1) / len(self.phase_order)) * 100.0
        return round(maturity, 2)

    def predict_next_phase(self, current_path: AttackPath) -> List[str]:
        """
        Predice las técnicas probables de la siguiente fase lógica de la Kill Chain.
        """
        if not current_path.phases:
            # Si no hay fases detectadas, predecimos la fase inicial: RECONNAISSANCE
            next_phase = KillChainPhase.RECONNAISSANCE
        else:
            # Determinamos cuál es la fase más avanzada actualmente alcanzada
            max_idx = max(self.phase_order.index(p) for p in current_path.phases)
            if max_idx == len(self.phase_order) - 1:
                # Ya llegó al final (ACTIONS_ON_OBJECTIVES), sugerir otras técnicas de impacto o persistencia
                return [
                    "T1486 (Data Encrypted for Impact) - El adversario podría desplegar Ransomware.",
                    "T1048 (Exfiltration Over Alternative Protocol) - El adversario podría exfiltrar datos robados.",
                    "T1547 (Boot or Logon Autostart Execution) - El adversario reforzará la persistencia."
                ]
            next_phase = self.phase_order[max_idx + 1]

        # Mapeamos las técnicas asociadas a la siguiente fase
        predicted_techniques = []
        for tech_id, info in MITRE_TECHNIQUES.items():
            tactic = info.get("tactic", "").lower()
            mapped_phase = TACTIC_TO_PHASE_MAP.get(tactic)
            if mapped_phase == next_phase:
                predicted_techniques.append(f"{tech_id} ({info.get('name')})")

        return predicted_techniques[:5]  # Retorna el top 5 de técnicas sugeridas

    def get_recommended_countermeasures(self, path: AttackPath) -> List[str]:
        """
        Obtiene recomendaciones defensivas y mitigaciones priorizadas para bloquear el ataque en curso
        o contener la siguiente fase predicha.
        """
        countermeasures = []
        
        # Obtener countermeasures para las fases activas detectadas
        for phase in path.phases:
            countermeasures.extend(DEFENSIVE_COUNTERMEASURES.get(phase, []))

        # Si hay un ataque en curso, sugerimos además de la siguiente fase predicha
        if path.phases:
            max_idx = max(self.phase_order.index(p) for p in path.phases)
            if max_idx < len(self.phase_order) - 1:
                next_phase = self.phase_order[max_idx + 1]
                countermeasures.append(f"--- RECOMENDACIONES PREVENTIVAS PARA SIGUIENTE FASE ({next_phase.value}) ---")
                countermeasures.extend(DEFENSIVE_COUNTERMEASURES.get(next_phase, []))

        # Retornar recomendaciones únicas
        seen = set()
        unique_countermeasures = []
        for cm in countermeasures:
            if cm not in seen:
                seen.add(cm)
                unique_countermeasures.append(cm)

        return unique_countermeasures

    def _calculate_confidence(self, incidents: List[Incident], detected_phases: List[KillChainPhase]) -> float:
        """
        Método interno para calcular la puntuación de confianza de la trayectoria del ataque.
        """
        if not incidents:
            return 0.0

        # Puntuación base según el número de fases detectadas (mayor consistencia de la kill chain = mayor confianza)
        num_phases = len(detected_phases)
        phase_ratio = num_phases / len(self.phase_order)
        score = phase_ratio * 40.0  # Máximo 40 puntos por número de fases

        # Factor de severidad (los incidentes de alta severidad aportan mayor confianza de detección real)
        severity_weights = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.5, "LOW": 0.2}
        total_weight = 0.0
        for inc in incidents:
            total_weight += severity_weights.get(inc.severity.upper(), 0.3)
        avg_severity_modifier = (total_weight / len(incidents)) * 30.0  # Máximo 30 puntos

        # Secuencialidad cronológica: ¿los incidentes ocurren en la secuencia lógica de la kill chain?
        sequentiality_bonus = 0.0
        if len(incidents) >= 2:
            logical_progression = 0
            for i in range(len(incidents) - 1):
                # Obtener la fase del incidente i y del incidente i+1
                p_current = self._get_highest_phase_for_incident(incidents[i])
                p_next = self._get_highest_phase_for_incident(incidents[i+1])
                if p_current and p_next:
                    idx_curr = self.phase_order.index(p_current)
                    idx_nxt = self.phase_order.index(p_next)
                    if idx_nxt >= idx_curr:  # Sigue adelante o se mantiene
                        logical_progression += 1
            
            sequentiality_bonus = (logical_progression / (len(incidents) - 1)) * 30.0  # Máximo 30 puntos

        return min(100.0, score + avg_severity_modifier + sequentiality_bonus)

    def _get_highest_phase_for_incident(self, incident: Incident) -> Optional[KillChainPhase]:
        """Obtiene la fase de Kill Chain más avanzada asociada a un incidente."""
        highest_phase = None
        highest_idx = -1
        
        # Recopilar técnicas del incidente y sus eventos
        techniques = list(incident.mitre_techniques)
        for ev in incident.events:
            techniques.extend(ev.mitre_techniques)

        for tech_id in set(techniques):
            tech_info = MITRE_TECHNIQUES.get(tech_id)
            if tech_info:
                tactic = tech_info.get("tactic", "").lower()
                phase = TACTIC_TO_PHASE_MAP.get(tactic)
                if phase:
                    idx = self.phase_order.index(phase)
                    if idx > highest_idx:
                        highest_idx = idx
                        highest_phase = phase
        return highest_phase


class KillChainVisualizer:
    """Visualizador especializado en representar el AttackPath en múltiples formatos."""

    @staticmethod
    def to_ascii(path: AttackPath) -> str:
        """
        Genera una hermosa representación en ASCII art del progreso del ataque en la Kill Chain.
        """
        phase_order = [
            KillChainPhase.RECONNAISSANCE,
            KillChainPhase.WEAPONIZATION,
            KillChainPhase.DELIVERY,
            KillChainPhase.EXPLOITATION,
            KillChainPhase.INSTALLATION,
            KillChainPhase.C2,
            KillChainPhase.ACTIONS_ON_OBJECTIVES
        ]

        # Abreviaciones artísticas
        abbr = {
            KillChainPhase.RECONNAISSANCE: " RECON ",
            KillChainPhase.WEAPONIZATION: "WEAPON ",
            KillChainPhase.DELIVERY: "DELIVER",
            KillChainPhase.EXPLOITATION: "EXPLOIT",
            KillChainPhase.INSTALLATION: "INSTALL",
            KillChainPhase.C2: "  C2   ",
            KillChainPhase.ACTIONS_ON_OBJECTIVES: "ACTIONS"
        }

        # Dibujar bloques de fases
        line_boxes = []
        line_states = []
        for phase in phase_order:
            if phase in path.phases:
                # Fase Activa - Resaltada con [X] y bordes dobles
                line_boxes.append(f"╔═════════╗")
                line_states.append(f"║ [X] {abbr[phase]} ║")
            else:
                # Fase Inactiva - Con [ ] y bordes simples
                line_boxes.append(f"┌─────────┐")
                line_states.append(f"│ [ ] {abbr[phase]} │")

        output = []
        output.append("=== DETECCIÓN DE AVANCE EN CYBER KILL CHAIN ===")
        output.append("  " + "   ===>   ".join(line_boxes))
        output.append("  " + "   --->   ".join(line_states))
        output.append("  " + "   ===>   ".join(line_boxes))
        output.append("")
        
        # Añadir detalles debajo del gráfico
        output.append(f"Métricas del Ataque:")
        analyzer = KillChainAnalyzer()
        maturity = analyzer.calculate_attack_maturity(path)
        output.append(f" └─> Madurez del Ataque: {maturity}%")
        output.append(f" └─> Confianza del Análisis: {path.confidence_score}%")
        output.append("")

        output.append("Técnicas Detectadas por Fase:")
        found_any = False
        for phase in phase_order:
            if phase in path.phases and path.techniques.get(phase):
                found_any = True
                tech_list = []
                for t in path.techniques[phase]:
                    t_info = MITRE_TECHNIQUES.get(t)
                    t_name = t_info["name"] if t_info else "Técnica Desconocida"
                    tech_list.append(f"{t} ({t_name})")
                output.append(f" [★] {phase.value}:")
                for t_detail in tech_list:
                    output.append(f"     └─> {t_detail}")
        if not found_any:
            output.append(" No se han detectado técnicas MITRE correlacionadas en ninguna fase aún.")

        return "\n".join(output)

    @staticmethod
    def to_json(path: AttackPath) -> str:
        """
        Serializa el AttackPath en un formato JSON completo, ideal para renderizar en el Dashboard.
        """
        analyzer = KillChainAnalyzer()
        data = {
            "phases_detected": [p.value for p in path.phases],
            "techniques_by_phase": {k.value: v for k, v in path.techniques.items()},
            "timeline": path.timeline,
            "metrics": {
                "confidence_score": path.confidence_score,
                "attack_maturity_percentage": analyzer.calculate_attack_maturity(path),
                "is_active": len(path.phases) > 0
            },
            "predictions": {
                "predicted_next_phase_techniques": analyzer.predict_next_phase(path)
            }
        }
        return json.dumps(data, indent=4, ensure_ascii=False)

    @staticmethod
    def to_mermaid(path: AttackPath) -> str:
        """
        Genera el código de un diagrama Mermaid que ilustra de manera secuencial e interactiva la Kill Chain.
        """
        phase_order = [
            KillChainPhase.RECONNAISSANCE,
            KillChainPhase.WEAPONIZATION,
            KillChainPhase.DELIVERY,
            KillChainPhase.EXPLOITATION,
            KillChainPhase.INSTALLATION,
            KillChainPhase.C2,
            KillChainPhase.ACTIONS_ON_OBJECTIVES
        ]

        # Nombres limpios para Mermaid
        node_names = {
            KillChainPhase.RECONNAISSANCE: "Reconnaissance",
            KillChainPhase.WEAPONIZATION: "Weaponization",
            KillChainPhase.DELIVERY: "Delivery",
            KillChainPhase.EXPLOITATION: "Exploitation",
            KillChainPhase.INSTALLATION: "Installation",
            KillChainPhase.C2: "C2_Command_Control",
            KillChainPhase.ACTIONS_ON_OBJECTIVES: "Actions_on_Objectives"
        }

        mermaid = ["graph TD", "    %% Definición de Estilos para fases activas y pasivas"]
        
        # Añadir nodos secuenciales
        for i in range(len(phase_order) - 1):
            curr_p = phase_order[i]
            next_p = phase_order[i+1]
            arrow = " ==&gt; " if (curr_p in path.phases and next_p in path.phases) else " --&gt; "
            
            curr_lbl = f'"{curr_p.value}"'
            next_lbl = f'"{next_p.value}"'
            
            mermaid.append(f"    {node_names[curr_p]}[{curr_lbl}]{arrow}{node_names[next_p]}[{next_lbl}]")

        # Añadir metadatos e incidentes enlazados si los hay
        if path.timeline:
            mermaid.append("\n    %% Incidentes Correlacionados")
            for idx, entry in enumerate(path.timeline):
                inc_id = entry["incident_id"]
                clean_title = entry["title"].replace('"', '\\"').replace('[', '(').replace(']', ')')
                severity = entry["severity"]
                
                # Crear nodo de incidente
                mermaid.append(f'    Inc_{inc_id}["Incident: {clean_title} ({severity})"]')
                
                # Conectar incidente con sus respectivas fases detectadas
                for p_val in entry["phases"]:
                    phase_enum = KillChainPhase(p_val)
                    mermaid.append(f"    Inc_{inc_id} -. Mapeado a .-> {node_names[phase_enum]}")

        # Aplicar estilos CSS en Mermaid para fases activas vs inactivas
        mermaid.append("\n    %% Estilos de los Nodos")
        for p in phase_order:
            if p in path.phases:
                # Estilo para fase activa: rojo/naranja indicando peligro
                mermaid.append(f"    style {node_names[p]} fill:#f9d5d5,stroke:#e74c3c,stroke-width:2px,color:#c0392b;")
            else:
                # Estilo para fase inactiva: gris
                mermaid.append(f"    style {node_names[p]} fill:#f5f5f5,stroke:#bdc3c7,stroke-width:1px,color:#7f8c8d;")

        return "\n".join(mermaid)
