# -*- coding: utf-8 -*-
"""
=== FILE: deception/stix_tip.py ===
Módulo Threat Intelligence Platform (TIP) integrado con STIX 2.1 y TAXII 2.1.
Permite la exportación de IoCs (Indicadores de Compromiso) a formato STIX 2.1,
la federación y publicación de inteligencia a servidores TAXII, y el mapeo inteligente
de alertas de red a técnicas y tácticas de MITRE ATT&CK.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Intentamos importar librerías STIX
try:
    from stix2 import (
        Indicator, Malware, Infrastructure, Bundle,
        AttackPattern, Relationship
    )
    STIX2_AVAILABLE = True
except ImportError:
    STIX2_AVAILABLE = False

import requests
from requests.auth import HTTPBasicAuth


# Constante con un subset representativo de 25 técnicas de MITRE ATT&CK
MITRE_ATTACK_SUBSET: Dict[str, Dict[str, str]] = {
    "T1566": {
        "name": "Phishing",
        "tactic": "initial-access",
        "kill_chain_phase": "initial-access",
        "description": "Envío de correos o mensajes maliciosos para engañar a los usuarios y obtener credenciales o acceso."
    },
    "T1190": {
        "name": "Exploit Public-Facing Application",
        "tactic": "initial-access",
        "kill_chain_phase": "initial-access",
        "description": "Explotación de vulnerabilidades o debilidades en aplicaciones expuestas a Internet."
    },
    "T1133": {
        "name": "External Remote Services",
        "tactic": "initial-access",
        "kill_chain_phase": "initial-access",
        "description": "Uso de VPNs, RDP o SSH legítimos para entrar a la red corporativa sin autorización."
    },
    "T1059": {
        "name": "Command and Scripting Interpreter",
        "tactic": "execution",
        "kill_chain_phase": "execution",
        "description": "Abuso de intérpretes de comandos locales como PowerShell, CMD, Bash para ejecutar código arbitrario."
    },
    "T1203": {
        "name": "Exploitation for Client Execution",
        "tactic": "execution",
        "kill_chain_phase": "execution",
        "description": "Explotación de fallos de software en programas cliente (ej. navegadores, suites de oficina) para correr payloads."
    },
    "T1547": {
        "name": "Boot or Logon Autostart Execution",
        "tactic": "persistence",
        "kill_chain_phase": "persistence",
        "description": "Modificación de claves de registro, archivos de arranque o scripts periódicos para mantener acceso persistente."
    },
    "T1078": {
        "name": "Valid Accounts",
        "tactic": "persistence",
        "kill_chain_phase": "persistence",
        "description": "Uso de credenciales comprometidas de cuentas legítimas (del sistema, dominio o cloud) para mantener acceso."
    },
    "T1543": {
        "name": "Create or Modify System Process",
        "tactic": "privilege-escalation",
        "kill_chain_phase": "privilege-escalation",
        "description": "Creación o edición de servicios del sistema o tareas programadas para ganar privilegios elevados."
    },
    "T1055": {
        "name": "Process Injection",
        "tactic": "privilege-escalation",
        "kill_chain_phase": "privilege-escalation",
        "description": "Inyección de código malicioso en procesos legítimos en ejecución para evadir controles y escalar privilegios."
    },
    "T1027": {
        "name": "Obfuscated Files or Information",
        "tactic": "defense-evasion",
        "kill_chain_phase": "defense-evasion",
        "description": "Uso de ofuscación, cifrado, esteganografía o empaquetado para ocultar artefactos ante herramientas de inspección."
    },
    "T1070": {
        "name": "Indicator Removal",
        "tactic": "defense-evasion",
        "kill_chain_phase": "defense-evasion",
        "description": "Limpieza deliberada de registros de eventos, archivos temporales, o logs de seguridad para ocultar el rastro."
    },
    "T1112": {
        "name": "Modify Registry",
        "tactic": "defense-evasion",
        "kill_chain_phase": "defense-evasion",
        "description": "Modificación directa del registro del sistema para evadir detecciones del antivirus o alterar políticas de seguridad."
    },
    "T1003": {
        "name": "OS Credential Dumping",
        "tactic": "credential-access",
        "kill_chain_phase": "credential-access",
        "description": "Volcado y extracción de credenciales en texto claro, hashes NTLM o tickets Kerberos desde la memoria del sistema."
    },
    "T1555": {
        "name": "Credentials from Password Stores",
        "tactic": "credential-access",
        "kill_chain_phase": "credential-access",
        "description": "Extracción de claves almacenadas en navegadores web, administradores de contraseñas de terceros o llaveros de SO."
    },
    "T1046": {
        "name": "Network Service Discovery",
        "tactic": "discovery",
        "kill_chain_phase": "discovery",
        "description": "Escaneo de puertos, servicios y configuraciones en la red interna para mapear posibles vectores de ataque."
    },
    "T1083": {
        "name": "File and Directory Discovery",
        "tactic": "discovery",
        "kill_chain_phase": "discovery",
        "description": "Enumeración de rutas y bases de datos en búsqueda de archivos de configuración, código fuente o datos de valor."
    },
    "T1021": {
        "name": "Remote Services",
        "tactic": "lateral-movement",
        "kill_chain_phase": "lateral-movement",
        "description": "Movimiento lateral interno a través de servicios de compartición remota como RDP, SSH, SMB, WinRM o VNC."
    },
    "T1570": {
        "name": "Lateral Tool Transfer",
        "tactic": "lateral-movement",
        "kill_chain_phase": "lateral-movement",
        "description": "Copia de herramientas de post-explotación o scripts de un nodo de la red interna a otro."
    },
    "T1114": {
        "name": "Email Collection",
        "tactic": "collection",
        "kill_chain_phase": "collection",
        "description": "Recolección centralizada o local de correos electrónicos de servidores corporativos en búsqueda de datos sensibles."
    },
    "T1041": {
        "name": "Exfiltration Over C2 Channel",
        "tactic": "exfiltration",
        "kill_chain_phase": "exfiltration",
        "description": "Transmisión estructurada de datos recopilados hacia la infraestructura de comando y control establecida."
    },
    "T1048": {
        "name": "Exfiltration Over Alternative Protocol",
        "tactic": "exfiltration",
        "kill_chain_phase": "exfiltration",
        "description": "Exfiltración de datos a través de canales alternos como túneles DNS, ICMP o servidores web de terceros."
    },
    "T1071": {
        "name": "Application Layer Protocol",
        "tactic": "command-and-control",
        "kill_chain_phase": "command-and-control",
        "description": "Abuso de protocolos estándar de nivel de aplicación (HTTP, HTTPS, DNS, SMTP) para camuflar el tráfico de C2."
    },
    "T1568": {
        "name": "Dynamic Resolution",
        "tactic": "command-and-control",
        "kill_chain_phase": "command-and-control",
        "description": "Resolución dinámica y rotativa de IPs de comando y control usando algoritmos DGA o servicios DNS dinámicos."
    },
    "T1090": {
        "name": "Proxy",
        "tactic": "command-and-control",
        "kill_chain_phase": "command-and-control",
        "description": "Uso de proxies comerciales, Tor o de sistemas vulnerados para ocultar la verdadera dirección IP del C2."
    },
    "T1498": {
        "name": "Network Denial of Service",
        "tactic": "impact",
        "kill_chain_phase": "impact",
        "description": "Inundación intencionada de recursos de red con tráfico anómalo para degradar o tumbar servicios críticos."
    }
}


class STIXExporter:
    """
    Exportador de IoCs (IPs, dominios, hashes, URLs) y técnicas de ataque
    a objetos y bundles válidos según el estándar STIX 2.1.
    """
    
    @staticmethod
    def ioc_to_stix(ioc: Dict[str, Any]) -> Any:
        """
        Convierte un diccionario de IoC a un objeto STIX 2.1 correspondiente.
        Estructura requerida para `ioc`:
          - 'type': 'ip', 'domain', 'url', 'hash', 'malware', 'infrastructure'
          - 'value': valor observable (ej. '203.0.113.5' o 'attacker.com')
          - 'name': nombre descriptivo para el objeto
          - 'description': descripción contextual adicional
        """
        if not STIX2_AVAILABLE:
            raise RuntimeError("La librería 'stix2' no está disponible en este entorno.")

        ioc_type = ioc.get("type", "").lower()
        val = ioc.get("value", "")
        name = ioc.get("name", f"IOC: {val}")
        desc = ioc.get("description", "")
        
        if ioc_type == "ip":
            pattern = f"[ipv4-addr:value = '{val}']"
            return Indicator(
                name=name,
                description=desc or "IP maliciosa detectada en actividades del Red Team.",
                pattern_type="stix",
                pattern=pattern,
                valid_from=datetime.utcnow()
            )
            
        elif ioc_type == "domain":
            pattern = f"[domain-name:value = '{val}']"
            return Indicator(
                name=name,
                description=desc or "Dominio malicioso asociado a infraestructura enemiga.",
                pattern_type="stix",
                pattern=pattern,
                valid_from=datetime.utcnow()
            )
            
        elif ioc_type == "url":
            pattern = f"[url:value = '{val}']"
            return Indicator(
                name=name,
                description=desc or "URL de phishing o comando y control.",
                pattern_type="stix",
                pattern=pattern,
                valid_from=datetime.utcnow()
            )
            
        elif ioc_type == "hash":
            pattern = f"[file:hashes.'SHA-256' = '{val}']"
            return Indicator(
                name=name,
                description=desc or "Huella SHA256 asociada a un archivo malicioso.",
                pattern_type="stix",
                pattern=pattern,
                valid_from=datetime.utcnow()
            )
            
        elif ioc_type == "malware":
            return Malware(
                name=val,
                description=desc or "Familia de malware detectada o utilizada para persistencia.",
                is_family=True
            )
            
        elif ioc_type == "infrastructure":
            return Infrastructure(
                name=name,
                description=desc or "Servidores u hostings de control de ataque.",
                infrastructure_types=["hosting-malicious"]
            )
            
        else:
            # Fallback a indicador genérico
            return Indicator(
                name=name,
                description=desc or "Indicador de compromiso genérico.",
                pattern_type="stix",
                pattern=f"[file:name = '{val}']",
                valid_from=datetime.utcnow()
            )

    @classmethod
    def create_bundle(cls, iocs: List[Dict[str, Any]]) -> Any:
        """
        Crea un objeto Bundle de STIX 2.1 a partir de una lista de diccionarios IoC.
        """
        if not STIX2_AVAILABLE:
            raise RuntimeError("La librería 'stix2' no está disponible.")

        stix_objects = []
        for ioc in iocs:
            try:
                stix_obj = cls.ioc_to_stix(ioc)
                stix_objects.append(stix_obj)
            except Exception as e:
                print(f"[STIX-EXPORT] Error procesando IOC '{ioc}': {e}")
                
        return Bundle(objects=stix_objects)

    @staticmethod
    def export_to_file(bundle, path: str):
        """
        Serializa un Bundle de STIX 2.1 y lo guarda en un archivo en formato JSON.
        """
        if not STIX2_AVAILABLE:
            raise RuntimeError("La librería 'stix2' no está disponible.")
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(bundle.serialize(pretty=True))
        print(f"[STIX-EXPORT] Bundle STIX exportado correctamente en: {path}")

    @staticmethod
    def create_attack_pattern(mitre_id: str, name: str, tactic: str) -> Any:
        """
        Crea un objeto de tipo AttackPattern STIX 2.1 con referencias a MITRE ATT&CK.
        """
        if not STIX2_AVAILABLE:
            raise RuntimeError("La librería 'stix2' no está disponible.")

        ext_ref = {
            "source_name": "mitre-attack",
            "external_id": mitre_id,
            "url": f"https://attack.mitre.org/techniques/{mitre_id}/"
        }
        return AttackPattern(
            name=name,
            description=f"Patrón de ataque catalogado bajo técnica MITRE {mitre_id}.",
            external_references=[ext_ref],
            custom_properties={"x_mitre_tactic": tactic}
        )

    @staticmethod
    def create_relationship(source, target, rel_type: str) -> Any:
        """
        Establece una relación STIX 2.1 entre dos objetos (SRO - STIX Relationship Object).
        Permite conectar, por ejemplo, un Indicator con un Malware o un Malware con un AttackPattern.
        """
        if not STIX2_AVAILABLE:
            raise RuntimeError("La librería 'stix2' no está disponible.")

        src_id = source.id if hasattr(source, 'id') else source
        tgt_id = target.id if hasattr(target, 'id') else target
        
        return Relationship(
            relationship_type=rel_type,
            source_ref=src_id,
            target_ref=tgt_id
        )


class TAXIIClient:
    """
    Cliente REST nativo y optimizado para TAXII 2.1 que opera sobre la API HTTP estándar.
    Permite publicar Bundles de STIX 2.1 y consultar listas de indicadores
    desde repositorios federados de Threat Intelligence.
    """
    def __init__(self):
        self.server_url = ""
        self.collection_id = ""
        self.api_key = ""
        self.headers = {
            "Accept": "application/taxii+json;version=2.1",
            "Content-Type": "application/taxii+json;version=2.1"
        }
        self.auth = None

    def connect(self, server_url: str, collection_id: str, api_key: str = ''):
        """
        Configura los parámetros de conexión para el servidor TAXII 2.1.
        Soporta autenticación básica (usuario:password) o token de tipo Bearer.
        """
        self.server_url = server_url.rstrip('/')
        self.collection_id = collection_id
        self.api_key = api_key
        
        # Estrategia de autenticación robusta
        if api_key:
            if ":" in api_key:
                # Caso usuario:contraseña (Basic Auth)
                username, password = api_key.split(":", 1)
                self.auth = HTTPBasicAuth(username, password)
            else:
                # Caso Token Bearer / API-Key directo
                self.headers["Authorization"] = f"Bearer {api_key}"
        else:
            self.auth = None

    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Solicita la lista de colecciones autorizadas en el servidor TAXII.
        Enlace de API: /collections/
        """
        url = f"{self.server_url}/collections/"
        try:
            response = requests.get(url, headers=self.headers, auth=self.auth, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("collections", [])
        except Exception as e:
            print(f"[TAXII-CLIENT] Error al obtener colecciones de {url}: {e}")
            return []

    def push_bundle(self, bundle) -> bool:
        """
        Realiza una petición POST de tipo TAXII 2.1 para insertar un Bundle STIX
        en el repositorio remoto configurado.
        Enlace de API: /collections/{collection_id}/objects/
        """
        url = f"{self.server_url}/collections/{self.collection_id}/objects/"
        try:
            # Serialización a JSON nativo STIX 2.1
            payload = bundle.serialize() if hasattr(bundle, 'serialize') else json.dumps(bundle)
            response = requests.post(url, data=payload, headers=self.headers, auth=self.auth, timeout=15)
            response.raise_for_status()
            # El servidor TAXII responde con códigos 200/202 si procesa exitosamente los objetos
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"[TAXII-CLIENT] Error al enviar Bundle STIX a {url}: {e}")
            return False

    def pull_indicators(self, since_datetime: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Consulta indicadores activos en la colección de TAXII.
        Retorna una lista filtrada de IoCs adaptados a diccionarios manipulables.
        """
        url = f"{self.server_url}/collections/{self.collection_id}/objects/"
        params = {"match[type]": "indicator"}
        if since_datetime:
            # Requisito de formato de fecha UTC para TAXII
            params["added_after"] = since_datetime.isoformat() + "Z"
            
        try:
            response = requests.get(url, headers=self.headers, params=params, auth=self.auth, timeout=15)
            response.raise_for_status()
            bundle_data = response.json()
            
            iocs = []
            objects = bundle_data.get("objects", [])
            for obj in objects:
                if obj.get("type") == "indicator":
                    pattern = obj.get("pattern", "")
                    
                    # Parsers regex ligeros para decodificar patrones de observables STIX 2.1
                    ioc_value = ""
                    ioc_type = "indicator"
                    
                    if "ipv4-addr:value" in pattern:
                        ioc_type = "ip"
                        ioc_value = pattern.split("=")[-1].strip(" '\"[]")
                    elif "domain-name:value" in pattern:
                        ioc_type = "domain"
                        ioc_value = pattern.split("=")[-1].strip(" '\"[]")
                    elif "url:value" in pattern:
                        ioc_type = "url"
                        ioc_value = pattern.split("=")[-1].strip(" '\"[]")
                    else:
                        ioc_value = obj.get("name", "Observable-General")
                        
                    iocs.append({
                        "id": obj.get("id"),
                        "type": ioc_type,
                        "value": ioc_value,
                        "name": obj.get("name"),
                        "description": obj.get("description"),
                        "severity": obj.get("x_severity", "MEDIUM"),
                        "valid_from": obj.get("valid_from")
                    })
            return iocs
        except Exception as e:
            print(f"[TAXII-CLIENT] Error al descargar indicadores de {url}: {e}")
            return []


class MITREMapper:
    """
    Motor de mapeo y alineación de incidentes con la base de conocimiento de MITRE ATT&CK.
    Mapea alertas automáticas NDR a técnicas tácticas robustas y genera objetos AttackPattern STIX 2.1.
    """
    
    @staticmethod
    def technique_to_stix(technique_id: str) -> Any:
        """
        Consulta la técnica en el diccionario local y retorna un objeto de tipo AttackPattern STIX.
        """
        if technique_id in MITRE_ATTACK_SUBSET:
            tech_info = MITRE_ATTACK_SUBSET[technique_id]
            return STIXExporter.create_attack_pattern(
                mitre_id=technique_id,
                name=tech_info["name"],
                tactic=tech_info["tactic"]
            )
        else:
            # Fallback si no está en el subset
            return STIXExporter.create_attack_pattern(
                mitre_id=technique_id,
                name=f"Técnica {technique_id}",
                tactic="unknown"
            )

    @staticmethod
    def get_kill_chain_phase(technique_id: str) -> str:
        """
        Retorna la fase del ciclo de vida de ataque (Kill Chain Phase) asociada a la técnica dada.
        """
        if technique_id in MITRE_ATTACK_SUBSET:
            return MITRE_ATTACK_SUBSET[technique_id]["kill_chain_phase"]
        return "unknown"

    @classmethod
    def map_alert_to_mitre(cls, alert: Any) -> Dict[str, Any]:
        """
        Asocia una alerta NDR comportamental (AnomalyAlert) con información
        descriptiva completa de MITRE ATT&CK.
        """
        mitre_id = "T1071"  # Protocolo a nivel de aplicación por defecto
        
        # Mapeos de alta fidelidad según el detector que disparó la alerta
        detector_name = getattr(alert, "detector_name", "")
        
        if detector_name == "DNSTunnelingDetector":
            mitre_id = "T1048"  # Exfiltración por canal alternativo (Túnel DNS)
        elif detector_name == "ICMPTunnelingDetector":
            # ICMP suele usarse para túneles y exfiltración alterna
            mitre_id = "T1048"
        elif detector_name == "ZScoreAnomalyDetector":
            # Anomalías de volumen suelen correlacionarse con exfiltración
            mitre_id = "T1041"  # Exfiltración sobre C2
        elif detector_name == "IsolationForestDetector":
            # Anomalías generales de comportamiento o cifrados anómalos
            mitre_id = "T1027"  # Ofuscación / Evasión de defensas

        tech_info = MITRE_ATTACK_SUBSET.get(mitre_id, {
            "name": "Application Layer Protocol",
            "tactic": "command-and-control",
            "kill_chain_phase": "command-and-control",
            "description": "Uso de protocolos de aplicación para tráfico malicioso."
        })
        
        return {
            "mitre_id": mitre_id,
            "name": tech_info["name"],
            "tactic": tech_info["tactic"],
            "kill_chain_phase": tech_info["kill_chain_phase"],
            "description": tech_info["description"],
            "detector_source": detector_name,
            "alert_severity": getattr(alert, "severity", "MEDIUM"),
            "mapped_timestamp": datetime.utcnow().isoformat()
        }
