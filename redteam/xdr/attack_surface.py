# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - Attack Surface Mapper
Módulo encargado de mapear la superficie de ataque, evaluar el riesgo tecnológico,
generar matrices de exposición y realizar comparativas históricas del estado de seguridad.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set


@dataclass
class AttackSurface:
    """Estructura de datos que almacena el mapa detallado de la superficie de ataque."""
    endpoints: List[str] = field(default_factory=list)
    ports: List[int] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    # Lista de diccionarios, ej: [{"cve": "CVE-2023-1234", "cvss": 8.5, "component": "Nginx", "description": "..."}]
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)


class AttackSurfaceMapper:
    """Clase encargada del modelado, cálculo de riesgo y comparación de superficies de ataque."""

    def map_from_scan_results(self, scan_results: dict) -> AttackSurface:
        """
        Mapea los resultados crudos de un escaneo (ej. de Nmap, Shodan, escáner interno)
        a una estructura unificada AttackSurface.
        
        Espera un diccionario con estructura flexible y extrae endpoints, puertos, tecnologías y vulns.
        """
        endpoints = list(set(scan_results.get("endpoints", [])))
        ports = list(set(scan_results.get("ports", [])))
        technologies = list(set(scan_results.get("technologies", [])))
        vulnerabilities = scan_results.get("vulnerabilities", [])

        # Validación y extracción de puertos y tecnologías desde hosts si la estructura es anidada
        if "hosts" in scan_results:
            for host in scan_results["hosts"]:
                if "ip" in host or "hostname" in host:
                    endpoints.append(host.get("ip") or host.get("hostname"))
                for port_info in host.get("ports", []):
                    if isinstance(port_info, dict):
                        p_val = port_info.get("port") or port_info.get("number")
                        if p_val:
                            ports.append(int(p_val))
                        tech_val = port_info.get("service") or port_info.get("product")
                        if tech_val:
                            technologies.append(tech_val)
                    elif isinstance(port_info, (int, str)):
                        ports.append(int(port_info))
                
                # Extraer vulnerabilidades anidadas
                for vuln in host.get("vulnerabilities", []):
                    if isinstance(vuln, dict):
                        v_data = {
                            "cve": vuln.get("cve", "CVE-UNKNOWN"),
                            "cvss": float(vuln.get("cvss", 0.0) or vuln.get("score", 0.0)),
                            "component": vuln.get("component") or vuln.get("product") or host.get("ip", "unknown"),
                            "description": vuln.get("description", "Sin descripción")
                        }
                        vulnerabilities.append(v_data)

        # Normalizar y quitar duplicados preservando tipos originales
        endpoints_cleaned = list(set(str(e) for e in endpoints if e))
        ports_cleaned = sorted(list(set(int(p) for p in ports if p)))
        technologies_cleaned = list(set(str(t) for t in technologies if t))
        
        # Eliminar vulnerabilidades duplicadas basadas en el ID de CVE/componente
        seen_vulns = set()
        vulns_cleaned = []
        for v in vulnerabilities:
            if not isinstance(v, dict):
                continue
            key = (v.get("cve", ""), v.get("component", ""))
            if key not in seen_vulns:
                seen_vulns.add(key)
                vulns_cleaned.append({
                    "cve": v.get("cve", "CVE-UNKNOWN"),
                    "cvss": float(v.get("cvss", 0.0)),
                    "component": v.get("component", "unknown"),
                    "description": v.get("description", "")
                })

        return AttackSurface(
            endpoints=endpoints_cleaned,
            ports=ports_cleaned,
            technologies=technologies_cleaned,
            vulnerabilities=vulns_cleaned
        )

    def calculate_risk_score(self, surface: AttackSurface) -> float:
        """
        Calcula una puntuación de riesgo global de la superficie de ataque (escala de 0.0 a 10.0).
        Considera la severidad de las vulnerabilidades, puertos abiertos y endpoints expuestos.
        """
        # 1. Puntuación por vulnerabilidades (Basado en el CVSS máximo y un modificador por volumen)
        vuln_score = 0.0
        if surface.vulnerabilities:
            cvss_scores = [v.get("cvss", 0.0) for v in surface.vulnerabilities]
            max_cvss = max(cvss_scores) if cvss_scores else 0.0
            
            # Penalización ligera por la cantidad de vulnerabilidades adicionales de alta severidad
            avg_cvss = sum(cvss_scores) / len(cvss_scores)
            vol_penalty = min(2.5, len(surface.vulnerabilities) * 0.15)
            
            # Mezcla ponderada del CVSS máximo (70%), el promedio (15%) y volumen (15%)
            vuln_score = (max_cvss * 0.70) + (avg_cvss * 0.15) + vol_penalty
            vuln_score = min(10.0, vuln_score)

        # 2. Puntuación por exposición de puertos (más puertos abiertos aumenta los vectores de entrada)
        # Puertos críticos comúnmente atacados añaden un multiplicador (ej. 22 RDP, 3389 SMB, 445, etc.)
        critical_ports = {21, 22, 23, 445, 1433, 3306, 3389, 5900, 8080}
        port_base_score = min(3.0, len(surface.ports) * 0.15)
        crit_port_bonus = sum(0.25 for p in surface.ports if p in critical_ports)
        port_score = min(4.0, port_base_score + crit_port_bonus)

        # 3. Exposición de Endpoints (escala logística simple)
        endpoint_score = min(2.5, len(surface.endpoints) * 0.1)

        # 4. Integración del riesgo total
        # Si hay vulnerabilidades, dominan el riesgo general (80% peso). Si no hay vulns, el riesgo se mide
        # meramente por la exposición de puertos y endpoints.
        if surface.vulnerabilities:
            total_risk = (vuln_score * 0.75) + (port_score * 0.15) + (endpoint_score * 0.10)
        else:
            total_risk = (port_score * 0.6) + (endpoint_score * 0.4)

        return round(min(10.0, max(0.0, total_risk)), 2)

    def get_exposure_matrix(self, surface: AttackSurface) -> Dict[str, Any]:
        """
        Genera una matriz de exposición que agrupa puertos, endpoints y vulnerabilidades
        por cada tecnología identificada en la superficie de ataque.
        """
        matrix = {}
        for tech in surface.technologies:
            matrix[tech] = {
                "associated_ports": [],
                "associated_endpoints": [],
                "vulnerabilities": [],
                "exposure_level": "LOW",
                "max_cvss": 0.0
            }

        # Intentar inferir correspondencia para puertos, endpoints y vulns por tecnología
        # Mapeo heurístico sencillo de nombres
        for port in surface.ports:
            # Asignar puertos comunes a tecnologías conocidas de forma genérica
            port_tech_map = {
                80: ["Nginx", "Apache", "HTTP"],
                443: ["Nginx", "Apache", "HTTPS", "SSL/TLS"],
                22: ["SSH", "OpenSSH"],
                3389: ["RDP", "Windows Remote Desktop"],
                3306: ["MySQL"],
                5432: ["PostgreSQL"],
                27017: ["MongoDB"],
                6379: ["Redis"]
            }
            if port in port_tech_map:
                for tech in port_tech_map[port]:
                    if tech in matrix:
                        matrix[tech]["associated_ports"].append(port)

        for vuln in surface.vulnerabilities:
            comp = vuln.get("component", "").lower()
            cvss = vuln.get("cvss", 0.0)
            
            # Asociar la vulnerabilidad con las tecnologías mediante coincidencia de texto
            for tech in surface.technologies:
                if tech.lower() in comp or comp in tech.lower():
                    matrix[tech]["vulnerabilities"].append(vuln)
                    if cvss > matrix[tech]["max_cvss"]:
                        matrix[tech]["max_cvss"] = cvss

        # Definir nivel de exposición e incorporar endpoints
        for tech, data in matrix.items():
            # Limpiar duplicados de puertos
            data["associated_ports"] = list(set(data["associated_ports"]))
            
            # Asignar todos los endpoints por defecto si no es específico
            data["associated_endpoints"] = list(surface.endpoints)

            # Clasificar severidad
            m_cvss = data["max_cvss"]
            if m_cvss >= 9.0:
                data["exposure_level"] = "CRITICAL"
            elif m_cvss >= 7.0:
                data["exposure_level"] = "HIGH"
            elif m_cvss >= 4.0:
                data["exposure_level"] = "MEDIUM"
            elif len(data["associated_ports"]) > 0:
                data["exposure_level"] = "LOW"
            else:
                data["exposure_level"] = "INFO"

        return matrix

    def compare_surfaces(self, before: AttackSurface, after: AttackSurface) -> Dict[str, Any]:
        """
        Realiza un diff completo entre dos superficies de ataque (ej. escaneo anterior vs actual).
        Identifica remediaciones (vulnerabilidades resueltas) y nuevos vectores de riesgo.
        """
        # Comparación de puertos
        ports_before = set(before.ports)
        ports_after = set(after.ports)
        new_ports = sorted(list(ports_after - ports_before))
        removed_ports = sorted(list(ports_before - ports_after))

        # Comparación de endpoints
        endpoints_before = set(before.endpoints)
        endpoints_after = set(after.endpoints)
        new_endpoints = sorted(list(endpoints_after - endpoints_before))
        removed_endpoints = sorted(list(endpoints_before - endpoints_after))

        # Comparación de tecnologías
        tech_before = set(before.technologies)
        tech_after = set(after.technologies)
        new_technologies = sorted(list(tech_after - tech_before))
        removed_technologies = sorted(list(tech_before - tech_after))

        # Comparación de vulnerabilidades (basada en ID de CVE)
        vulns_before_map = {v.get("cve"): v for v in before.vulnerabilities if v.get("cve")}
        vulns_after_map = {v.get("cve"): v for v in after.vulnerabilities if v.get("cve")}
        
        cve_before = set(vulns_before_map.keys())
        cve_after = set(vulns_after_map.keys())

        new_vulns_cve = cve_after - cve_before
        resolved_vulns_cve = cve_before - cve_after

        new_vulnerabilities = [vulns_after_map[cve] for cve in new_vulns_cve]
        resolved_vulnerabilities = [vulns_before_map[cve] for cve in resolved_vulns_cve]

        # Comparación de puntaje de riesgo
        risk_before = self.calculate_risk_score(before)
        risk_after = self.calculate_risk_score(after)
        risk_diff = round(risk_after - risk_before, 2)

        if risk_diff > 0.05:
            risk_status = "INCREASED"
        elif risk_diff < -0.05:
            risk_status = "DECREASED"
        else:
            risk_status = "UNCHANGED"

        return {
            "ports": {
                "added": new_ports,
                "removed": removed_ports,
                "count_delta": len(ports_after) - len(ports_before)
            },
            "endpoints": {
                "added": new_endpoints,
                "removed": removed_endpoints,
                "count_delta": len(endpoints_after) - len(endpoints_before)
            },
            "technologies": {
                "added": new_technologies,
                "removed": removed_technologies,
            },
            "vulnerabilities": {
                "added": new_vulnerabilities,
                "resolved": resolved_vulnerabilities,
                "added_count": len(new_vulnerabilities),
                "resolved_count": len(resolved_vulnerabilities)
            },
            "risk_metrics": {
                "risk_before": risk_before,
                "risk_after": risk_after,
                "risk_delta": risk_diff,
                "status": risk_status
            }
        }
