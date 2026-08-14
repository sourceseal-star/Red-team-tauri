# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - STIX 2.1 & TAXII 2.1 Integration
Este módulo implementa el empaquetado de inteligencia de amenazas en formato STIX 2.1,
la publicación y suscripción a servidores TAXII 2.1, y una base de datos local completa
de MITRE ATT&CK con 50 técnicas mapeadas detalladamente.
"""

import json
import re
import time
import threading
from typing import List, Dict, Any, Optional, Callable
import requests

# Librerías STIX
import stix2


class STIXBundle:
    """Clase wrapper para crear y serializar un bundle de STIX 2.1."""

    def __init__(self):
        self.objects: List[Any] = []

    def add_indicator(self, ioc: str, pattern_type: str = "stix", name: Optional[str] = None, description: str = "") -> stix2.Indicator:
        """Crea un Indicator STIX 2.1 a partir de un valor crudo (IP, Hash, URL, etc.) y lo añade al bundle."""
        # Detectar el patrón adecuado si es patrón stix por defecto
        if pattern_type == "stix":
            pattern = self._auto_detect_pattern(ioc)
        else:
            pattern = ioc

        # Dejamos que stix2 auto-popule 'valid_from' con la fecha/hora actual de forma nativa
        indicator = stix2.Indicator(
            name=name or f"Indicator for {ioc}",
            description=description or f"Indicador automático de compromiso para {ioc}",
            pattern=pattern,
            pattern_type=pattern_type
        )
        self.objects.append(indicator)
        return indicator

    def add_attack_pattern(self, mitre_id: str, name: str, tactic: str, description: str = "") -> stix2.AttackPattern:
        """Crea un AttackPattern STIX 2.1 y lo añade al bundle."""
        attack_pattern = stix2.AttackPattern(
            name=name,
            description=description or f"MITRE ATT&CK Technique {mitre_id}",
            custom_properties={
                "x_mitre_id": mitre_id,
                "x_mitre_tactic": tactic
            }
        )
        self.objects.append(attack_pattern)
        return attack_pattern

    def add_malware(self, name: str, malware_type: str, aliases: List[str] = None, description: str = "") -> stix2.Malware:
        """Crea un objeto Malware STIX 2.1 y lo añade al bundle."""
        malware = stix2.Malware(
            name=name,
            is_family=False,
            malware_types=[malware_type],
            aliases=aliases or [],
            description=description or f"Software malicioso detectado: {name}"
        )
        self.objects.append(malware)
        return malware

    def add_infrastructure(self, name: str, infra_type: str, description: str = "") -> stix2.Infrastructure:
        """Crea un objeto Infrastructure STIX 2.1 y lo añade al bundle."""
        infra = stix2.Infrastructure(
            name=name,
            infrastructure_types=[infra_type],
            description=description or f"Infraestructura maliciosa: {name}"
        )
        self.objects.append(infra)
        return infra

    def add_relationship(self, src_id: str, dst_id: str, rel_type: str, description: str = "") -> stix2.Relationship:
        """Crea un objeto Relationship STIX 2.1 que conecta dos entidades y lo añade al bundle."""
        relationship = stix2.Relationship(
            source_ref=src_id,
            target_ref=dst_id,
            relationship_type=rel_type,
            description=description
        )
        self.objects.append(relationship)
        return relationship

    def to_json(self) -> str:
        """Serializa todos los objetos creados a una cadena JSON de STIX Bundle."""
        bundle = stix2.Bundle(objects=self.objects)
        return bundle.serialize(pretty=True)

    def save(self, filepath: str):
        """Guarda el STIX Bundle actual a un archivo en disco."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def _auto_detect_pattern(self, ioc: str) -> str:
        """Heurística para auto-detectar y generar patrones STIX válidos."""
        # Remover espacios en blanco
        ioc = ioc.strip()

        # IPv4
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ioc):
            return f"[ipv4-addr:value = '{ioc}']"
        # IPv6
        elif ":" in ioc and len(ioc) >= 3 and not ioc.startswith("http"):
            return f"[ipv6-addr:value = '{ioc}']"
        # Hash MD5
        elif re.match(r"^[a-fA-F0-9]{32}$", ioc):
            return f"[file:hashes.MD5 = '{ioc}']"
        # Hash SHA-256
        elif re.match(r"^[a-fA-F0-9]{64}$", ioc):
            return f"[file:hashes.'SHA-256' = '{ioc}']"
        # URL
        elif ioc.startswith("http://") or ioc.startswith("https://"):
            # Escapar comillas simples de URLs si existieran
            clean_url = ioc.replace("'", "%27")
            return f"[url:value = '{clean_url}']"
        # Dominio / Hostname por defecto
        else:
            return f"[domain-name:value = '{ioc}']"


class TAXIIPublisher:
    """Publicador TAXII 2.1 encargado de realizar envíos POST de STIX Bundles."""

    def __init__(self, server_url: str, collection_id: str, username: str = "", password: str = ""):
        self.server_url = server_url.rstrip("/")
        self.collection_id = collection_id
        self.username = username
        self.password = password
        self.headers = {
            "Content-Type": "application/taxii+json;version=2.1",
            "Accept": "application/taxii+json;version=2.1"
        }

    def publish(self, bundle: STIXBundle) -> Dict[str, Any]:
        """
        Publica un STIXBundle en el servidor TAXII 2.1.
        
        Realiza una petición POST al endpoint de objetos de la colección.
        """
        # Formato TAXII 2.1 oficial: /collections/{id}/objects/
        url = f"{self.server_url}/collections/{self.collection_id}/objects/"
        
        auth = (self.username, self.password) if (self.username or self.password) else None
        
        try:
            # Enviamos el bundle completo de STIX
            response = requests.post(
                url,
                data=bundle.to_json(),
                headers=self.headers,
                auth=auth,
                timeout=30
            )
            
            # En TAXII 2.1, el servidor puede retornar un 202 Accepted (asíncrono) o un 200 OK.
            if response.status_code in [200, 202]:
                try:
                    res_json = response.json()
                    status_id = res_json.get("id") or res_json.get("status", {}).get("id", "N/A")
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "status_id": status_id,
                        "message": "Publicación enviada exitosamente al servidor TAXII.",
                        "details": res_json
                    }
                except ValueError:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "status_id": "N/A",
                        "message": "Publicación exitosa sin cuerpo de respuesta JSON parseable."
                    }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"Error al publicar en TAXII: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "message": f"Excepción durante la conexión TAXII: {str(e)}"
            }

    def get_status(self, status_id: str) -> Dict[str, Any]:
        """
        Consulta el estado de una carga asíncrona mediante el endpoint de Status de TAXII 2.1.
        """
        url = f"{self.server_url}/status/{status_id}/"
        auth = (self.username, self.password) if (self.username or self.password) else None
        
        try:
            response = requests.get(url, headers=self.headers, auth=auth, timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "error",
                    "message": f"Error consultando estatus: {response.text}",
                    "status_code": response.status_code
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Excepción al consultar estatus: {str(e)}"
            }


class TAXIISubscriber:
    """Suscriptor TAXII 2.1 capaz de descargar y monitorear IoCs de manera asíncrona."""

    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password
        self.headers = {
            "Accept": "application/taxii+json;version=2.1"
        }
        self.polling_thread: Optional[threading.Thread] = None
        self.stop_polling = threading.Event()

    def subscribe(self, server_url: str, collection_id: str, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Realiza una petición GET al servidor TAXII 2.1 para descargar IoCs.
        Retorna una lista simplificada de IoCs mapeados a partir de los Indicators STIX de la colección.
        """
        url = f"{server_url.rstrip('/')}/collections/{collection_id}/objects/"
        auth = (self.username, self.password) if (self.username or self.password) else None
        
        params = {}
        if since:
            params["added_after"] = since

        iocs_extracted = []
        try:
            response = requests.get(url, headers=self.headers, auth=auth, params=params, timeout=30)
            if response.status_code == 200:
                bundle_data = response.json()
                # Extraemos objetos STIX
                objects = bundle_data.get("objects", [])
                for obj in objects:
                    if obj.get("type") == "indicator":
                        # Simplificar el indicador de STIX a nuestro formato de IoC
                        pattern = obj.get("pattern", "")
                        ioc_value = self._extract_ioc_from_pattern(pattern)
                        iocs_extracted.append({
                            "id": obj.get("id"),
                            "value": ioc_value,
                            "name": obj.get("name"),
                            "pattern": pattern,
                            "description": obj.get("description", ""),
                            "created": obj.get("created"),
                            "type": self._infer_ioc_type_from_pattern(pattern)
                        })
            else:
                print(f"[TAXIISubscriber] Error HTTP {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[TAXIISubscriber] Excepción al descargar indicadores: {str(e)}")

        return iocs_extracted

    def poll_loop(self, server_url: str, collection_id: str, interval: int = 300, callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None):
        """
        Inicia un bucle de polling en un hilo de fondo secundario.
        Descarga IoCs de forma periódica y ejecuta un callback cuando se reciben.
        """
        self.stop_polling.clear()
        
        def _poll():
            last_timestamp = None
            while not self.stop_polling.is_set():
                print(f"[TAXIISubscriber] Polling iniciado para {collection_id}...")
                new_iocs = self.subscribe(server_url, collection_id, since=last_timestamp)
                
                if new_iocs and callback:
                    callback(new_iocs)
                
                # Actualizamos la marca de tiempo de la última consulta al momento actual en ISO format UTC
                # En un entorno real se obtendría del encabezado X-TAXII-Date-Added o campo similar
                last_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                
                # Dormir el intervalo con comprobaciones de detención periódicas
                for _ in range(interval):
                    if self.stop_polling.is_set():
                        break
                    time.sleep(1)

        self.polling_thread = threading.Thread(target=_poll, daemon=True)
        self.polling_thread.start()

    def stop(self):
        """Detiene el bucle de polling asíncrono."""
        self.stop_polling.set()
        if self.polling_thread:
            self.polling_thread.join(timeout=5)

    def _extract_ioc_from_pattern(self, pattern: str) -> str:
        """Extrae el valor del IoC de dentro de la sintaxis del patrón STIX."""
        match = re.search(r"=\s*'(.*?)'", pattern)
        if match:
            return match.group(1)
        return pattern

    def _infer_ioc_type_from_pattern(self, pattern: str) -> str:
        """Infiere un tipo simple de IoC analizando el objeto STIX del patrón."""
        if "ipv4-addr" in pattern:
            return "IP_V4"
        elif "ipv6-addr" in pattern:
            return "IP_V6"
        elif "file:hashes.MD5" in pattern:
            return "HASH_MD5"
        elif "file:hashes" in pattern:
            return "HASH_SHA256"
        elif "url:value" in pattern:
            return "URL"
        elif "domain-name" in pattern:
            return "DOMAIN"
        return "UNKNOWN"


# Base de datos global MITRE ATT&CK con exactamente 50 técnicas, cubriendo las 14 tácticas
MITRE_50_DATABASE = {
    # 1. Reconnaissance
    "T1595": {
        "name": "Active Scanning",
        "tactic": "Reconnaissance",
        "description": "El adversario realiza escaneos activos de red para detectar servicios expuestos y vulnerabilidades.",
        "mitigations": ["Implementar cortafuegos y sistemas de detección de intrusos en el borde.", "Bloquear escaneos de red repetitivos."]
    },
    "T1592": {
        "name": "Gather Victim Host Information",
        "tactic": "Reconnaissance",
        "description": "Recolección de datos específicos de hosts como versiones de sistemas operativos, nombres de host y configuraciones.",
        "mitigations": ["Reducir la exposición de firmas de software de cara a internet.", "Limitar detalles en cabeceras de respuesta HTTP."]
    },
    "T1589": {
        "name": "Gather Victim Identity Information",
        "tactic": "Reconnaissance",
        "description": "Búsqueda y recolección de identidades de las víctimas como direcciones de correo, credenciales filtradas y nombres de usuario.",
        "mitigations": ["Monitorear fuentes externas de fugas de datos de credenciales.", "Desplegar capacitación contra OSINT corporativo."]
    },

    # 2. Resource Development
    "T1583": {
        "name": "Acquire Infrastructure",
        "tactic": "Resource Development",
        "description": "Compra o renta de dominios, servidores privados virtuales (VPS) o cuentas de hosting para realizar operaciones.",
        "mitigations": ["Registrar y monitorear la reputación de dominios parecidos a la marca corporativa (Typosquatting)."]
    },
    "T1584": {
        "name": "Compromise Infrastructure",
        "tactic": "Resource Development",
        "description": "Secuestro o compromiso de infraestructura legítima de terceros para hospedar malware o retransmitir tráfico de ataque.",
        "mitigations": ["Utilizar listas de bloqueo de reputación de red actualizadas de forma continua."]
    },
    "T1588": {
        "name": "Obtain Capabilities",
        "tactic": "Resource Development",
        "description": "Compra, robo o adquisición gratuita de malware, herramientas de ataque de código abierto o certificados de firma digital.",
        "mitigations": ["Utilizar firmas de EDR actualizadas para detener herramientas conocidas."]
    },

    # 3. Initial Access
    "T1566": {
        "name": "Phishing",
        "tactic": "Initial Access",
        "description": "Mensajes maliciosos para engañar a los usuarios finales y entregar payloads o recolectar credenciales.",
        "mitigations": ["Utilizar filtrado de SPF/DKIM/DMARC.", "Habilitar Sandboxing de archivos adjuntos de correo."]
    },
    "T1190": {
        "name": "Exploit Public-Facing Application",
        "tactic": "Initial Access",
        "description": "Uso de exploits para comprometer sistemas con aplicaciones expuestas a internet.",
        "mitigations": ["Auditorías frecuentes de seguridad web (SAST/DAST).", "Desplegar Web Application Firewalls (WAF)."]
    },
    "T1133": {
        "name": "External Remote Services",
        "tactic": "Initial Access",
        "description": "Uso de accesos VPN, RDP o SSH legítimos pero expuestos para obtener acceso inicial sin exploits.",
        "mitigations": ["Autenticación Multifactor estricta.", "Políticas de listas de acceso IP permitidas."]
    },
    "T1200": {
        "name": "Hardware Additions",
        "tactic": "Initial Access",
        "description": "Introducción física de dispositivos de ataque de hardware (ej. Rubber Ducky, implantes de red).",
        "mitigations": ["Bloqueo de puertos USB no autorizados.", "Control estricto de accesos físicos al centro de datos."]
    },

    # 4. Execution
    "T1059": {
        "name": "Command and Scripting Interpreter",
        "tactic": "Execution",
        "description": "Ejecución de utilidades integradas de scripting como PowerShell, bash, o python para ejecutar código hostil.",
        "mitigations": ["Configurar Constrained Language Mode en PowerShell.", "Monitorear la creación de procesos cmd.exe/powershell.exe."]
    },
    "T1203": {
        "name": "Exploitation for Client Execution",
        "tactic": "Execution",
        "description": "Compromiso del sistema a través de fallos en lectores de PDF, navegadores web u ofimática ejecutados por un cliente.",
        "mitigations": ["Habilitar mitigaciones de exploit (ASLR, DEP) del SO.", "Actualización automática de aplicaciones de usuario."]
    },
    "T1204": {
        "name": "User Execution",
        "tactic": "Execution",
        "description": "El ataque requiere que un usuario haga doble clic en un ejecutable o habilite macros en un documento.",
        "mitigations": ["Deshabilitar macros de Microsoft Office de fuentes de internet por política de grupo GPO.", "Configurar extensiones peligrosas de archivo para advertir antes de ejecutar."]
    },
    "T1569": {
        "name": "System Services",
        "tactic": "Execution",
        "description": "Ejecución de binarios maliciosos registrándolos como servicios locales o utilizando herramientas como PsExec.",
        "mitigations": ["Monitorear el uso inusual de privilegios administrativos de red.", "Registrar servicios recién creados."]
    },

    # 5. Persistence
    "T1547": {
        "name": "Boot or Logon Autostart Execution",
        "tactic": "Persistence",
        "description": "Modificación del registro de Windows (Run keys) o carpetas de inicio de Linux para auto-arrancar en cada reinicio.",
        "mitigations": ["Auditar de manera automatizada las llaves de persistencia del sistema."]
    },
    "T1543": {
        "name": "Create or Modify System Process",
        "tactic": "Persistence",
        "description": "Creación o modificación de servicios de sistema legítimos o daemons de arranque para ejecutar cargas útiles persistentes.",
        "mitigations": ["Limitar acceso de escritura a directorios de sistema /etc/init.d/ y Systemd."]
    },
    "T1136": {
        "name": "Create Account",
        "tactic": "Persistence",
        "description": "Creación de cuentas locales o de dominio administrativas secundarias para evadir cierres de sesión del acceso inicial.",
        "mitigations": ["Monitorear los eventos de auditoría de Windows 4720 (Creación de usuario).", "Alerta automática al agregar administradores."]
    },
    "T1098": {
        "name": "Account Manipulation",
        "tactic": "Persistence",
        "description": "Modificación de credenciales de cuentas, adición de llaves SSH autorizadas o cambio de permisos de MFA.",
        "mitigations": ["Auditar cambios en archivos .ssh/authorized_keys.", "Monitorear eventos de alteración de credenciales."]
    },

    # 6. Privilege Escalation
    "T1548": {
        "name": "Abuse Privilege Escalation Mechanism",
        "tactic": "Privilege Escalation",
        "description": "Evasión de controles de elevación de privilegios como sudo en Linux o UAC en Windows.",
        "mitigations": ["Forzar contraseña al usar sudo.", "Configurar el nivel de UAC de Windows al nivel más estricto ('Siempre notificar')."]
    },
    "T1068": {
        "name": "Exploitation for Privilege Escalation",
        "tactic": "Privilege Escalation",
        "description": "Uso de exploits locales del núcleo (kernel exploits) o de controladores vulnerables para convertirse en SYSTEM o ROOT.",
        "mitigations": ["Ciclo constante de parches de seguridad de kernel.", "Restringir la carga de controladores de terceros no validados."]
    },
    "T1055": {
        "name": "Process Injection",
        "tactic": "Privilege Escalation",
        "description": "Inyección de cargas dinámicas en procesos legítimos de alta integridad (como svchost.exe o lsass.exe).",
        "mitigations": ["Bloquear llamadas API nativas mediante reglas del EDR.", "Utilizar herramientas de análisis de integridad de procesos."]
    },

    # 7. Defense Evasion
    "T1027": {
        "name": "Obfuscated Files or Information",
        "tactic": "Defense Evasion",
        "description": "Uso de cifrado, codificación en Base64 o empaquetado personalizado para ocultar binarios frente a escáneres estáticos de firmas.",
        "mitigations": ["Detección de patrones inusuales de entropía de datos de archivos.", "Monitoreo heurístico en memoria RAM."]
    },
    "T1070": {
        "name": "Indicator Removal",
        "tactic": "Defense Evasion",
        "description": "Borrado de registros de eventos de Windows, purga de logs de auditoría de seguridad o alteración de marcas de tiempo de archivos (Timestomping).",
        "mitigations": ["Envío inmediato de logs en tiempo real a un servidor SIEM externo e inmutable.", "Proteger archivos de registros."]
    },
    "T1112": {
        "name": "Modify Registry",
        "tactic": "Defense Evasion",
        "description": "Modificación del registro del sistema para deshabilitar características de seguridad e inhabilitar alertas.",
        "mitigations": ["Bloquear por GPO la edición no autorizada de llaves de registro críticas."]
    },
    "T1562": {
        "name": "Impair Defenses",
        "tactic": "Defense Evasion",
        "description": "Deshabilitar cortafuegos locales, detener daemons de antivirus o inhabilitar de manera deliberada la telemetría del EDR.",
        "mitigations": ["Habilitar protección contra manipulación (Tamper Protection) inmanente al agente de seguridad."]
    },

    # 8. Credential Access
    "T1110": {
        "name": "Brute Force",
        "tactic": "Credential Access",
        "description": "Ataques de fuerza bruta, adivinación de contraseñas por diccionario o password spraying contra servicios públicos.",
        "mitigations": ["Límites de bloqueos de cuenta tras intentos erróneos.", "Implementar CAPTCHAs y detección de velocidad de intentos."]
    },
    "T1003": {
        "name": "OS Credential Dumping",
        "tactic": "Credential Access",
        "description": "Extracción directa de la base SAM de Windows, hashes de shadow en Linux o volcado del proceso LSASS en memoria.",
        "mitigations": ["Activar protección LSA (LSA Protection) y Windows Defender Credential Guard.", "Evitar almacenamiento de contraseñas de texto claro."]
    },
    "T1555": {
        "name": "Credentials from Password Stores",
        "tactic": "Credential Access",
        "description": "Extracción de claves almacenadas en navegadores web (Chrome, Edge), clientes de correo o llaveros de contraseñas del SO.",
        "mitigations": ["Cifrar bases de datos locales de perfiles de usuario.", "Uso de gestores de contraseñas corporativos centralizados."]
    },
    "T1212": {
        "name": "Exploitation for Credential Access",
        "tactic": "Credential Access",
        "description": "Explotación de fallos de diseño en protocolos de autenticación (ej. kerberoasting, vulnerabilidades de AD como Zerologon).",
        "mitigations": ["Forzar el cifrado AES para tickets de Kerberos.", "Monitorear consultas inusuales de SPN en el Directorio Activo."]
    },

    # 9. Discovery
    "T1087": {
        "name": "Account Discovery",
        "tactic": "Discovery",
        "description": "Búsqueda activa de usuarios configurados en el sistema local o mapeo de objetos de usuario en el Directorio Activo.",
        "mitigations": ["Limitar los privilegios de lectura para usuarios estándar sobre consultas generales de LDAP en AD."]
    },
    "T1018": {
        "name": "Remote System Discovery",
        "tactic": "Discovery",
        "description": "Mapeo de nombres DNS internos, consultas de NETBIOS o ping sweeps para enumerar otros sistemas activos de la red.",
        "mitigations": ["Deshabilitar respuestas ICMP echo request internas de host a host.", "Desactivar protocolos obsoletos de resolución local."]
    },
    "T1082": {
        "name": "System Information Discovery",
        "tactic": "Discovery",
        "description": "Ejecución de utilidades para conocer versión de sistema operativo, arquitectura de procesador y nivel de parches instalados.",
        "mitigations": ["Monitorear el uso excesivo de comandos como systeminfo, uname -a, o lsb_release."]
    },
    "T1046": {
        "name": "Network Service Discovery",
        "tactic": "Discovery",
        "description": "Escaneo interno de puertos desde un host ya comprometido para identificar puertos abiertos en redes vecinas.",
        "mitigations": ["Segmentación estricta de red por zonas (microsegmentación).", "Alertas automáticas ante conexiones a múltiples hosts internos."]
    },

    # 10. Lateral Movement
    "T1021": {
        "name": "Remote Services",
        "tactic": "Lateral Movement",
        "description": "Movimiento lateral autenticado utilizando sesiones de RDP, conexiones SSH o administración de PowerShell remota (WinRM).",
        "mitigations": ["Bloquear conexiones de administración RDP o SSH directas entre estaciones de trabajo (workstation-to-workstation)."]
    },
    "T1210": {
        "name": "Exploitation of Remote Services",
        "tactic": "Lateral Movement",
        "description": "Uso de exploits a través de la red contra servicios internos desprotegidos (ej. EternalBlue contra SMB).",
        "mitigations": ["Desplegar parches críticos de red local.", "Habilitar firmas IDS para tráfico de red este-oeste."]
    },
    "T1072": {
        "name": "Software Deployment",
        "tactic": "Lateral Movement",
        "description": "Movimiento lateral abusando de herramientas legítimas de distribución de software corporativo (ej. SCCM, Ansible, Puppet).",
        "mitigations": ["Restringir de forma estricta los accesos administrativos a servidores de distribución de software."]
    },

    # 11. Collection
    "T1005": {
        "name": "Data from Local System",
        "tactic": "Collection",
        "description": "Recolección y centralización de archivos PDF, documentos Excel y bases de datos locales para preparar su exfiltración.",
        "mitigations": ["Cifrar almacenamiento sensible local.", "Políticas estrictas de control de acceso a nivel de archivo."]
    },
    "T1113": {
        "name": "Screen Capture",
        "tactic": "Collection",
        "description": "Captura visual periódica de la pantalla del usuario comprometido para monitorear sus actividades e información ingresada.",
        "mitigations": ["Auditar de manera aplicativa que soliciten permisos de grabación de pantalla.", "Bloqueo automático de software de control remoto."]
    },
    "T1114": {
        "name": "Email Collection",
        "tactic": "Collection",
        "description": "Búsqueda y extracción de correos electrónicos desde buzones de Outlook locales (.pst, .ost) o APIs de correo de Office 365.",
        "mitigations": ["Limitar el acceso de aplicaciones de terceros mediante OAuth a los buzones corporativos."]
    },

    # 12. Command and Control
    "T1071": {
        "name": "Application Layer Protocol",
        "tactic": "Command and Control",
        "description": "Uso de protocolos comunes como HTTP/HTTPS o consultas DNS para ocultar el tráfico de mando y control.",
        "mitigations": ["Utilizar proxies con análisis SSL y filtrado de categorías.", "Bloquear peticiones directas salientes que no pasen por el proxy."]
    },
    "T1090": {
        "name": "Proxy",
        "tactic": "Command and Control",
        "description": "Enrutamiento del tráfico C2 a través de proxies abiertos, la red TOR o redes de distribución de contenido (CDNs).",
        "mitigations": ["Bloquear salidas directas a nodos de salida TOR conocidos.", "Inspección SSL/TLS profunda."]
    },
    "T1573": {
        "name": "Encrypted Channel",
        "tactic": "Command and Control",
        "description": "Cifrado personalizado del tráfico de red para evitar la firma de firmas estáticas de IDS de red.",
        "mitigations": ["Análisis de entropía de datos de tráfico.", "Detección de patrones inusuales de volumen de subida/bajada."]
    },
    "T1105": {
        "name": "Ingress Tool Transfer",
        "tactic": "Command and Control",
        "description": "Descarga de herramientas maliciosas adicionales en el sistema comprometido desde repositorios externos.",
        "mitigations": ["Bloquear acceso a servidores de hosting de código no autorizado como Github personal, Pastebin, etc."]
    },

    # 13. Exfiltration
    "T1048": {
        "name": "Exfiltration Over Alternative Protocol",
        "tactic": "Exfiltration",
        "description": "Envío de archivos e información fuera de la red mediante protocolos alternativos (FTP, DNS, ICMP, HTTPS personal).",
        "mitigations": ["Implementar controles DLP avanzados basados en red.", "Monitorear flujos inusuales de tráfico saliente DNS/ICMP."]
    },
    "T1041": {
        "name": "Exfiltration Over C2 Channel",
        "tactic": "Exfiltration",
        "description": "Uso del canal principal de mando y control (C2) ya establecido para extraer subrepticiamente la información robada.",
        "mitigations": ["Análisis de comportamiento e historial de volumen de datos transmitidos por el canal C2."]
    },
    "T1020": {
        "name": "Automated Exfiltration",
        "tactic": "Exfiltration",
        "description": "Sistemas de exfiltración programada que empaquetan, cifran y envían de forma automática información ante eventos específicos.",
        "mitigations": ["Monitoreo heurístico y de comportamiento para identificar envíos automáticos repetitivos de datos."]
    },

    # 14. Impact
    "T1485": {
        "name": "Data Destruction",
        "tactic": "Impact",
        "description": "Destrucción irreversible de información crítica de bases de datos o sistemas de archivos (Wipers) para dañar operaciones.",
        "mitigations": ["Establecer réplicas en tiempo real no editables de bases de datos.", "Uso de políticas de backups inmutables."]
    },
    "T1486": {
        "name": "Data Encrypted for Impact",
        "tactic": "Impact",
        "description": "Cifrado no autorizado masivo de datos mediante Ransomware con fines extorsivos de rescate de clave.",
        "mitigations": ["Habilitar detección basada en comportamiento de escritura del antivirus local.", "Respaldos periódicos probados de restauración."]
    },
    "T1489": {
        "name": "Service Stop",
        "tactic": "Impact",
        "description": "Detención deliberada de servicios esenciales del negocio (servidores web, motores de bases de datos) para causar caídas.",
        "mitigations": ["Monitorear detenciones inusuales de servicios mediante herramientas de SIEM.", "Reinicios automáticos de servicios críticos."]
    },
    "T1490": {
        "name": "Inhibit System Recovery",
        "tactic": "Impact",
        "description": "Eliminación intencional de copias de seguridad locales (ej. shadow copies en Windows) para impedir la autoreparación del sistema.",
        "mitigations": ["Alertar inmediatamente ante el uso de comandos de eliminación de instantáneas (vssadmin delete shadows)."]
    }
}


class MITREAttackMapper:
    """Mapeador completo de técnicas MITRE ATT&CK."""

    @staticmethod
    def get_technique(tech_id: str) -> Optional[Dict[str, Any]]:
        """Retorna los detalles (nombre, táctica, descripción, mitigaciones) de una técnica específica."""
        # Buscar en la base de datos de 50 técnicas
        info = MITRE_50_DATABASE.get(tech_id)
        if info:
            return {
                "id": tech_id,
                "name": info["name"],
                "tactic": info["tactic"],
                "description": info["description"],
                "mitigations": info["mitigations"]
            }
        return None

    @staticmethod
    def get_by_tactic(tactic: str) -> List[Dict[str, Any]]:
        """Retorna todas las técnicas correspondientes a una táctica de MITRE."""
        tactic_lower = tactic.lower()
        results = []
        for tech_id, info in MITRE_50_DATABASE.items():
            if info["tactic"].lower() == tactic_lower:
                results.append({
                    "id": tech_id,
                    "name": info["name"],
                    "tactic": info["tactic"],
                    "description": info["description"],
                    "mitigations": info["mitigations"]
                })
        return results

    @staticmethod
    def techniques_for_alert(alert_type: str) -> List[str]:
        """
        Mapea dinámicamente un tipo de alerta de seguridad a un conjunto de IDs de técnicas de MITRE.
        """
        alert_type_lower = alert_type.lower()
        
        # Mapeos predefinidos de alertas a técnicas
        alert_mapping = {
            "brute_force": ["T1110"],
            "rdp_brute_force": ["T1110", "T1021"],
            "credential_dumping": ["T1003"],
            "privilege_escalation": ["T1548", "T1068"],
            "uac_bypass": ["T1548"],
            "dll_injection": ["T1055"],
            "process_injection": ["T1055"],
            "phishing_mail": ["T1566", "T1204"],
            "phishing_link": ["T1566", "T1204"],
            "sql_injection": ["T1190"],
            "web_exploit": ["T1190"],
            "unauthorized_service": ["T1569", "T1543"],
            "persistence_registry": ["T1547", "T1112"],
            "persistence_cron": ["T1543"],
            "account_creation": ["T1136"],
            "antivirus_disabled": ["T1562", "T1070"],
            "logs_cleared": ["T1070"],
            "recon_scan": ["T1595", "T1046"],
            "internal_port_scan": ["T1046", "T1018"],
            "network_discovery": ["T1046", "T1018", "T1082"],
            "active_directory_query": ["T1087"],
            "psexec_lateral": ["T1569", "T1021"],
            "ssh_lateral": ["T1021"],
            "data_staging": ["T1005"],
            "email_harvesting": ["T1114"],
            "screen_capture_malicious": ["T1113"],
            "c2_http_beacon": ["T1071", "T1090"],
            "c2_dns_tunneling": ["T1071", "T1573", "T1048"],
            "ingress_download": ["T1105"],
            "data_exfiltration": ["T1048", "T1041"],
            "automated_exfiltration": ["T1020"],
            "ransomware_encryption": ["T1486", "T1490"],
            "data_destruction_wiper": ["T1485"],
            "service_stop_malicious": ["T1489"],
            "shadow_copies_removed": ["T1490"]
        }

        # Búsqueda exacta
        if alert_type_lower in alert_mapping:
            return alert_mapping[alert_type_lower]

        # Búsqueda por sub-coincidencia aproximada
        for keyword, tech_ids in alert_mapping.items():
            if keyword in alert_type_lower or alert_type_lower in keyword:
                return tech_ids

        return []  # Si no hay coincidencia, retorna una lista vacía
