"""
defense.integration — DefenseMesh
==================================

Bus central que conecta todos los componentes. ``ingest(signal)`` enruta
la señal al componente correcto; ``health_check()`` retorna el estado de
cada subsistema.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import pathlib
import threading
import time
from typing import Any, Dict, List, Optional, Union

from defense._yaml import load as _yaml_load
from defense.rasp import RASPProbe, RASPEnforcer, ThreatSignal, MockBus
from defense.attestation import HardwareKeystore, AttestationVerifier
from defense.ndr import NDREngine, TLSInterceptionProxy, FlowEvent, NDRFinding
from defense.ztna import ZTNAGateway, ZTNAContext
from defense.deception import DecoyToken, DecoyDB, DecoyEndpoint, STIXExporter
from defense.xdr import EventBus, MITREMapper, Correlator, IncidentStore, XdrEvent
from defense.soar import PlaybookEngine, ActionRegistry, default_playbooks

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"
DEFAULT_MITRE_PATH = pathlib.Path(__file__).parent / "mitre_map.yaml"


@dataclasses.dataclass
class MeshHealth:
    status: str
    components: Dict[str, Dict[str, Any]]
    uptime_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class DefenseMesh:
    """Bus central del DefenseMesh.

    Carga config.yaml, instancia los 7 subsistemas y los conecta.
    Expone:

      * ``ingest(signal)`` → enruta al subsistema correcto.
      * ``health_check()`` → estado de cada uno.
      * ``simulate(scenario)`` → corre una simulación end-to-end."""

    def __init__(self, *, config_path: Optional[pathlib.Path] = None,
                 mitre_path: Optional[pathlib.Path] = None,
                 load_playbooks_dir: bool = True):
        self._t0 = time.time()
        self.config_path = pathlib.Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.mitre_path = pathlib.Path(mitre_path) if mitre_path else DEFAULT_MITRE_PATH
        self.config: Dict[str, Any] = {}
        self.mitre_data: Dict[str, Any] = {}
        if self.config_path.exists():
            self.config = _yaml_load(open(self.config_path))
        if self.mitre_path.exists():
            self.mitre_data = _yaml_load(open(self.mitre_path))
        # Estado
        self.bus = EventBus(buffer_size=self.config.get("xdr", {}).get("buffer_size", 100_000))
        self.mapper = MITREMapper(technique_map=self.mitre_data)
        self.correlator = Correlator(self.bus, self.mapper)
        self.incidents = IncidentStore()
        # Subsistemas
        rasp_cfg = self.config.get("rasp", {})
        self.rasp_probe = RASPProbe(
            frida_ports=tuple(rasp_cfg.get("frida_ports", (27042, 27043))),
            frida_libs=tuple(rasp_cfg.get("frida_libs", RASPProbe.DEFAULT_FRIDA_LIBS)),
            xposed_indicators=tuple(rasp_cfg.get("xposed_indicators", RASPProbe.DEFAULT_XPOSED_INDICATORS)),
            emulator_indicators=tuple(rasp_cfg.get("emulator_indicators", RASPProbe.DEFAULT_EMULATOR_INDICATORS)),
            binary_allowlist=rasp_cfg.get("binary_allowlist", []),
        )
        self.rasp_bus = MockBus()
        self.rasp_enforcer = RASPEnforcer(bus=self.rasp_bus)
        # Attestation
        att_cfg = self.config.get("attestation", {})
        self.keystore = HardwareKeystore(key_bits=att_cfg.get("attestation_key_bits", 2048))
        self.attestation = AttestationVerifier(
            min_os_version=att_cfg.get("min_os_version", "13"),
            min_patch_level=att_cfg.get("min_patch_level", "2024-09"),
            required_key_strongbox=att_cfg.get("required_key_strongbox", True),
        )
        self.attestation.add_trusted_root(self.keystore.root_public_pem)
        # NDR
        ndr_cfg = self.config.get("ndr", {})
        bc = ndr_cfg.get("beaconing", {})
        self.ndr = NDREngine(
            window_seconds=ndr_cfg.get("window_seconds", 300),
            beaconing_max_interval=bc.get("max_interval_seconds", 60),
            beaconing_max_jitter_pct=bc.get("max_jitter_pct", 20.0),
            beaconing_min_samples=bc.get("min_samples", 5),
        )
        self.proxy = TLSInterceptionProxy(self.ndr)
        # ZTNA
        ztna_cfg = self.config.get("ztna", {})
        self.ztna = ZTNAGateway(
            default_deny=ztna_cfg.get("default_deny", True),
            posture_min=ztna_cfg.get("posture_min_score", 0.7),
            jwt_ttl=ztna_cfg.get("jwt_ttl_seconds", 900),
        )
        # Deception
        dec_cfg = self.config.get("deception", {})
        self.decoy_token = DecoyToken()
        self.decoy_db = DecoyDB(seed=dec_cfg.get("decoy_db_seed", "honey-vault-001"))
        self.decoy_endpoint = DecoyEndpoint(
            routes=tuple(dec_cfg.get("decoy_endpoints", DecoyEndpoint.DEFAULT_ROUTES))
        )
        self.stix = STIXExporter()
        # SOAR
        soar_cfg = self.config.get("soar", {})
        self.action_registry = ActionRegistry()
        self._register_default_actions()
        self.playbook_engine = PlaybookEngine(
            self.action_registry,
            max_latency_ms=soar_cfg.get("max_latency_ms", 500),
            playbooks_dir=pathlib.Path(__file__).parent / "playbooks"
            if soar_cfg.get("playbooks_dir") is None else pathlib.Path(soar_cfg["playbooks_dir"]),
            default_actions=default_playbooks(),
        )
        if load_playbooks_dir:
            pb_dir = pathlib.Path(__file__).parent / "playbooks"
            if pb_dir.exists():
                self.playbook_engine.load_directory(pb_dir)
        self._lock = threading.Lock()
        # Suscribir correlaciones → playbook automático
        self.bus.subscribe("xdr.incident", self._auto_playbook)
        # Snapshot para ingest
        self._events: List[Dict[str, Any]] = []
        self._lock_events = threading.Lock()

    # ---------- Action registration ----------

    def _register_default_actions(self) -> None:
        """Registra callables para los targets de los playbooks."""
        # RASPEnforcer.revoke_session
        def revoke_session(params, context):
            inputs = params.get("inputs", {})
            payload = self.rasp_enforcer.revoke_session(
                reason=inputs.get("reason", "playbook"),
                user_id=inputs.get("user_id"),
            )
            return {"side_effects": [f"rasp.revoke_session:{payload['user_id']}"]}

        def quarantine(params, context):
            inputs = params.get("inputs", {})
            payload = self.rasp_enforcer.quarantine(
                reason=inputs.get("reason", "playbook"),
            )
            return {"side_effects": [f"rasp.quarantine:{payload['device_id']}"]}

        def jwt_revoke(params, context):
            inputs = params.get("inputs", {})
            user = inputs.get("user_id", "")
            dev = inputs.get("device_id", "")
            self.ztna.validator.revoke_subject_device(user, dev)
            return {"side_effects": [f"ztna.jwt_revoke:{user}:{dev}"]}

        def deny_device(params, context):
            inputs = params.get("inputs", {})
            self.ztna.policy.deny_device(inputs.get("device_id", ""))
            return {"side_effects": [f"ztna.deny_device:{inputs.get('device_id')}"]}

        def incident_append(params, context):
            inputs = params.get("inputs", {})
            inc_id = self.incidents.append(
                title=params.get("id", "playbook"),
                severity="high",
                mitre=";".join(params.get("mitre", []) or []),
                extra={"playbook": context.get("playbook_id"), "inputs": inputs},
            )
            return {"side_effects": [f"xdr.incident:{inc_id}"]}

        def blocklist_add(params, context):
            inputs = params.get("inputs", {})
            self.ndr.blocklist_add(
                inputs.get("ioc_type", "domain"),
                inputs.get("ioc_value", ""),
                inputs.get("source", "soar"),
            )
            return {"side_effects": [f"ndr.blocklist:{inputs.get('ioc_value')}"]}

        def stix_export(params, context):
            inputs = params.get("inputs", {})
            self.stix.export(
                ioc_type=inputs.get("ioc_type", "domain"),
                value=inputs.get("ioc_value", ""),
                source=context.get("playbook_id", "soar"),
            )
            return {"side_effects": ["stix.exported"]}

        def hash_allowlist_remove(params, context):
            sha = params.get("inputs", {}).get("sha256", "")
            if sha:
                with self.rasp_probe._lock:
                    self.rasp_probe.binary_allowlist.discard(sha)
            return {"side_effects": [f"rasp.allowlist_remove:{sha}"]}

        def thehive_case(params, context):
            # Mock: registra el intento en el bus para inspección.
            self.bus.publish("thehive.case", {
                "source": "soar", "category": "thehive_case",
                "severity": "info", "summary": "mock case",
                "playbook": context.get("playbook_id"),
            })
            return {"side_effects": ["thehive.case:created"]}

        registry = {
            "RASPEnforcer.revoke_session": revoke_session,
            "RASPEnforcer.quarantine": quarantine,
            "ZTNA.JWTValidator.revocation_set": jwt_revoke,
            "ZTNA.PolicyEngine.deny_device": deny_device,
            "XDR.IncidentStore.append": incident_append,
            "NDR.blocklist_add": blocklist_add,
            "Deception.STIXExporter.export": stix_export,
            "RASPProbe.hash_allowlist_remove": hash_allowlist_remove,
            "thehive.case_creator": thehive_case,
        }
        for name, fn in registry.items():
            self.action_registry.register(name, fn)

    # ---------- Ingest ----------

    def ingest(self, signal: Union[ThreatSignal, NDRFinding, XdrEvent, Dict[str, Any], str]) -> List[XdrEvent]:
        """Enruta la señal al componente correcto y la publica al bus.

        Acepta: ``ThreatSignal`` (RASP), ``NDRFinding``, ``XdrEvent`` o un
        dict libre con ``source`` y ``category``."""
        if isinstance(signal, str):
            signal = {"source": "external", "category": "ingest",
                      "severity": "info", "summary": signal}
        if isinstance(signal, ThreatSignal):
            evt = XdrEvent(
                source="rasp",
                category=signal.category,
                severity=signal.severity,
                mitre_id=signal.mitre_id,
                summary=signal.evidence,
                payload=signal.to_dict(),
            )
            self.bus.publish("rasp.signal", evt)
            return [evt]
        if isinstance(signal, NDRFinding):
            evt = XdrEvent(
                source="ndr",
                category=signal.category,
                severity=signal.severity,
                mitre_id=signal.mitre_id,
                summary=signal.evidence,
                payload={"endpoint_id": getattr(signal, "endpoint_id", ""),
                         **signal.to_dict()} if hasattr(signal, "to_dict") else
                        {"endpoint_id": getattr(signal, "endpoint_id", "")},
            )
            self.bus.publish("ndr.finding", evt)
            return [evt]
        if isinstance(signal, XdrEvent):
            self.bus.publish(f"{signal.source}.event", signal)
            return [signal]
        if isinstance(signal, dict):
            evt = XdrEvent(
                source=str(signal.get("source", "external")),
                category=str(signal.get("category", "generic")),
                severity=str(signal.get("severity", "info")),
                mitre_id=str(signal.get("mitre_id", "")),
                summary=str(signal.get("summary", signal.get("evidence", ""))),
                payload=dict(signal),
            )
            self.bus.publish(f"{evt.source}.event", evt)
            with self._lock_events:
                self._events.append(evt.to_dict())
            return [evt]
        raise TypeError(f"tipo de signal no soportado: {type(signal)}")

    def ingest_flow(self, event: FlowEvent) -> List[NDRFinding]:
        """Ingesta un evento de red al NDR y propaga al bus si produce findings."""
        findings = self.ndr.ingest(event)
        for f in findings:
            self.ingest(f)
        return findings

    def ingest_threat_signals(self) -> List[ThreatSignal]:
        """Corre RASP.scan() e ingesta todas las señales resultantes."""
        signals = self.rasp_probe.scan()
        for s in signals:
            self.ingest(s)
        return signals

    # ---------- Auto playbook ----------

    def _auto_playbook(self, event: XdrEvent) -> None:
        """Cuando XDR genera un incidente, dispara el playbook asociado a
        la técnica MITRE (si existe)."""
        mitre = event.mitre_id
        if not mitre:
            return
        mapping = {
            "T1056.001": "pb_isolate_device",
            "T1611": "pb_isolate_device",
            "T1078": "pb_revoke_jwt",
            "T1078.004": "pb_revoke_jwt",
            "T1190": "pb_revoke_jwt",
            "T1071.004": "pb_block_ioc",
            "T1071.001": "pb_isolate_device",
            "T1048": "pb_block_ioc",
            "T1572": "pb_block_ioc",
            "T1095": "pb_block_ioc",
            "T1518": "pb_quarantine_apk",
            "T1623": "pb_quarantine_apk",
        }
        pb_id = mapping.get(mitre)
        if not pb_id:
            return
        try:
            self.playbook_engine.run(pb_id, inputs={
                "user_id": event.payload.get("user_id", "unknown"),
                "device_id": event.payload.get("device_id", "unknown"),
                "reason": f"auto from {event.summary}",
            })
        except Exception as e:  # pragma: no cover
            logger.warning("auto playbook %s failed: %s", pb_id, e)

    # ---------- Health ----------

    def health_check(self) -> Dict[str, Any]:
        return self._build_health().to_dict()

    def _build_health(self) -> MeshHealth:
        components = {
            "rasp": {
                "ok": True,
                "enforcer_actions": len(self.rasp_enforcer.actions()),
            },
            "attestation": {
                "ok": True,
                "keys": sum(1 for _ in [self.keystore]),
            },
            "ndr": {
                "ok": True,
                "events_buffered": self.bus.size(),
                "ndr_findings": len(self.ndr.all_findings()),
                "blocklist_size": len(self.ndr.blocklist()),
            },
            "ztna": {
                "ok": True,
                "bola_attempts": len(self.ztna.bola.attempts()),
                "active_tokens": self.ztna.issuer.active(),
            },
            "deception": {
                "ok": True,
                "decoy_token_attempts": len(self.decoy_token.usage_attempts()),
                "decoy_db_hits": len(self.decoy_db.hits()),
                "decoy_endpoint_hits": len(self.decoy_endpoint.hits()),
                "stix_iocs": self.stix.count(),
            },
            "xdr": {
                "ok": True,
                "events_in_bus": self.bus.size(),
                "incidents": self.incidents.count(),
            },
            "soar": {
                "ok": True,
                "playbooks": len(self.playbook_engine.list()),
                "playbook_runs": len(self.playbook_engine.runs()),
            },
        }
        return MeshHealth(
            status="active",
            components=components,
            uptime_seconds=round(time.time() - self._t0, 3),
        )

    # ---------- Simulate ----------

    def simulate(self, scenario: str = "compromised_device") -> Dict[str, Any]:
        """Corre una simulación end-to-end que ejercita todos los
        componentes. Retorna un dict con timeline + health post."""
        timeline: List[Dict[str, Any]] = []
        t0 = time.time()

        def log(stage: str, **details):
            entry = {"stage": stage, "ts": round(time.time() - t0, 3), **details}
            timeline.append(entry)
            return entry

        if scenario == "compromised_device":
            # 1) RASP detecta Frida + debugger
            self.rasp_probe.inject_loaded_lib("frida-agent-64.so")
            self.rasp_probe.inject_proc_status("12345")
            signals = self.ingest_threat_signals()
            log("rasp", signals=[s.to_dict() for s in signals])

            # 2) ZTNA emite JWT + se intenta BOLA
            ctx = ZTNAContext(
                device_id="dev-1", user_id="alice",
                posture_score=0.9, location_risk=0.1,
                time_of_day=10, network_trust=0.8,
            )
            tok = self.ztna.issue_token(ctx)
            d = self.ztna.authorize(
                ctx, "read", "order-1", {"id": "order-1", "owner_id": "bob"}
            )
            log("ztna", decision=d.to_dict(), token=bool(tok))

            # 3) NDR: beaconing
            base_t = time.time()
            for i in range(6):
                ev = FlowEvent(
                    endpoint_id="dev-1", timestamp=base_t + i * 30.0,
                    proto="tcp", direction="outbound", size=120,
                    dst="c2.evil.org",
                )
                self.ingest_flow(ev)
            log("ndr", findings=len(self.ndr.all_findings()))

            # 4) Deception: decoy endpoint hit
            hit = self.decoy_endpoint.handle("/admin-old", source_ip="1.2.3.4")
            self.ingest({"source": "deception", "category": "hit",
                         "severity": "high", "mitre_id": "T1078",
                         "summary": "decoy endpoint hit"})
            log("deception", hit=hit)

            # 5) XDR corre correlación
            time.sleep(0.05)
            incidents = self.correlator.incidents()
            log("xdr", incidents=incidents)

            # 6) SOAR dispara playbook
            if incidents:
                run = self.playbook_engine.run("pb_isolate_device", inputs={
                    "device_id": "dev-1",
                    "user_id": "alice",
                    "reason": "compromised_device simulation",
                })
                log("soar", run=run.to_dict())

        elif scenario == "credential_stuffing":
            ctx = ZTNAContext(
                device_id="dev-2", user_id="mallory",
                posture_score=0.3, location_risk=0.9,
                time_of_day=3, network_trust=0.2,
            )
            d = self.ztna.authorize(ctx, "login", "auth")
            log("ztna", decision=d.to_dict())
            # Decoy token usage
            dt = self.decoy_token.issue(scope="admin")
            self.decoy_token.record_usage(dt, "/api/v1/admin/orders")
            self.ingest({"source": "deception", "category": "canary_access",
                         "severity": "critical", "mitre_id": "T1078.004",
                         "summary": "canary token used"})
            time.sleep(0.05)
            run = self.playbook_engine.run("pb_revoke_jwt", inputs={
                "user_id": "mallory",
                "reason": "credential_stuffing simulation",
            })
            log("soar", run=run.to_dict())

        elif scenario == "data_exfil":
            base_t = time.time()
            for i in range(20):
                ev = FlowEvent(
                    endpoint_id="dev-3", timestamp=base_t + i * 12.0,
                    proto="dns", direction="outbound", size=180,
                    dst="dns.tunnel.evil",
                    extra={"qname": "a" * 30 + str(i) + ".tunnel.evil"},
                )
                self.ingest_flow(ev)
            log("ndr", findings=len(self.ndr.all_findings()))
            time.sleep(0.05)
            run = self.playbook_engine.run("pb_block_ioc", inputs={
                "ioc_type": "domain",
                "ioc_value": "dns.tunnel.evil",
                "source": "simulation",
            })
            log("soar", run=run.to_dict())

        else:
            log("error", message=f"unknown scenario {scenario}")

        # Health final
        health = self._build_health().to_dict()
        log("health", **health)
        return {"scenario": scenario, "timeline": timeline, "health": health}

    # ---------- Inspection ----------

    def events(self) -> List[Dict[str, Any]]:
        with self._lock_events:
            return list(self._events)

    def coverage(self) -> Dict[str, Any]:
        """Retorna la matriz de cobertura MITRE ATT&CK."""
        return {
            "techniques": self.mapper.techniques(),
            "by_tactic": self.mapper.coverage(),
            "playbooks": self.playbook_engine.list(),
        }

    def to_json(self) -> str:
        return json.dumps({
            "health": self.health_check(),
            "config_path": str(self.config_path),
            "mitre_path": str(self.mitre_path),
        }, indent=2, default=str)
