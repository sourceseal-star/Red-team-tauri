#!/usr/bin/env python3
"""
STIX 2.1 Exporter — Convierte IoCs del TIP a formato STIX 2.1.
Compatible con MISP, OpenCTI, ThreatConnect.
No usa librería stix2 — construye el JSON manualmente.
"""
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from tip.platform import IoC


def _stix_id(prefix: str, seed: str = "") -> str:
    """Genera un STIX ID único."""
    h = hashlib.sha256((seed + str(uuid.uuid4())).encode()).hexdigest()[:16]
    return f"{prefix}--{h}"


def _stix_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class StixExporter:
    """Exporta IoCs a STIX 2.1 bundles."""

    STIX_PATTERN_MAP = {
        "ip": "ipv4-addr:value",
        "domain": "domain-name:value",
        "url": "url:value",
        "hash": "file:hashes.'SHA-256'",
        "email": "email-addr:value",
    }

    STIX_TYPE_MAP = {
        "ip": "ipv4-addr",
        "domain": "domain-name",
        "url": "url",
        "hash": "file",
        "email": "email-addr",
    }

    def __init__(self):
        self.bundle: Dict[str, Any] = {
            "type": "bundle",
            "id": _stix_id("bundle"),
            "spec_version": "2.1",
            "objects": [],
        }

    def add_indicator(self, ioc: IoC) -> Dict:
        """Crea un STIX Indicator object desde un IoC."""
        pattern_field = self.STIX_PATTERN_MAP.get(ioc.type, "x-unknown:value")
        pattern = f"[{pattern_field} = '{ioc.value}']"

        labels = []
        if ioc.source == "soar":
            labels.append("malicious-activity")
        elif ioc.source == "probe":
            labels.append("anomalous-activity")
        else:
            labels.append("suspicious-activity")

        ext_refs = []
        if ioc.tags:
            for tag in ioc.tags:
                ext_refs.append({"source_name": "source-tag", "external_id": tag})

        indicator = {
            "type": "indicator",
            "spec_version": "2.1",
            "id": _stix_id("indicator", ioc.value),
            "created": _stix_timestamp(),
            "modified": _stix_timestamp(),
            "pattern": pattern,
            "pattern_type": "stix",
            "valid_from": _stix_timestamp(),
            "valid_until": datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59.000000Z"),
            "labels": labels,
            "confidence": int(ioc.confidence * 100),
            "external_references": ext_refs,
        }
        self.bundle["objects"].append(indicator)
        return indicator

    def add_observable(self, ioc: IoC) -> Dict:
        """Crea un STIX Observed Data object."""
        stix_type = self.STIX_TYPE_MAP.get(ioc.type, "x-unknown")
        observable = {
            "type": stix_type,
            "spec_version": "2.1",
            "id": _stix_id(stix_type, ioc.value),
            "value": ioc.value,
        }
        self.bundle["objects"].append(observable)
        return observable

    def add_threat_report(self, title: str, description: str, findings: List[Dict]) -> Dict:
        """Crea un STIX Report object que resume todos los hallazgos."""
        report_refs = []
        for obj in self.bundle["objects"]:
            if obj["type"] in ("indicator", "observed-data"):
                report_refs.append({"id": obj["id"], "type": obj["type"]})

        report = {
            "type": "report",
            "spec_version": "2.1",
            "id": _stix_id("report"),
            "created": _stix_timestamp(),
            "modified": _stix_timestamp(),
            "name": title,
            "description": description,
            "published": _stix_timestamp(),
            "object_refs": report_refs,
            "labels": ["threat-report"],
            "confidence": 80,
        }
        self.bundle["objects"].append(report)
        return report

    def export_iocs(self, iocs: List[IoC]) -> Dict:
        """Exporta una lista de IoCs a un STIX 2.1 bundle."""
        self.bundle = {
            "type": "bundle",
            "id": _stix_id("bundle"),
            "spec_version": "2.1",
            "objects": [],
        }
        for ioc in iocs:
            self.add_observable(ioc)
            self.add_indicator(ioc)
        self.add_threat_report(
            "SourceSeal Red Team — Threat Report",
            f"Generated from {len(iocs)} IoCs detected by Red Team Enterprise scan",
            [],
        )
        return self.bundle

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.bundle, indent=indent, default=str)

    def save(self, filepath: str) -> str:
        with open(filepath, "w") as f:
            f.write(self.to_json())
        return filepath

    def validate(self) -> bool:
        """Validación básica del schema STIX 2.1."""
        if self.bundle.get("type") != "bundle":
            return False
        if self.bundle.get("spec_version") != "2.1":
            return False
        if "id" not in self.bundle:
            return False
        if "objects" not in self.bundle:
            return False
        for obj in self.bundle["objects"]:
            if "type" not in obj or "id" not in obj:
                return False
            if obj.get("spec_version") and obj["spec_version"] != "2.1":
                return False
        return True

    def to_misp_event(self, iocs: List[IoC], event_info: str = "Red Team Findings") -> Dict:
        """Convierte IoCs a formato MISP event para importación directa."""
        attributes = []
        misp_type_map = {
            "ip": "ip-dst", "domain": "domain", "url": "url",
            "hash": "sha256", "email": "email-dst",
        }
        for ioc in iocs:
            attr_type = misp_type_map.get(ioc.type, "text")
            attributes.append({
                "category": "Network activity" if ioc.type in ("ip", "domain", "url") else "Payload delivery",
                "type": attr_type,
                "value": ioc.value,
                "comment": f"Source: {ioc.source}, Confidence: {ioc.confidence}",
                "to_ids": ioc.confidence >= 0.7,
            })
        threat_level = 1
        if any(i.confidence >= 0.9 for i in iocs):
            threat_level = 1  # high
        elif any(i.confidence >= 0.7 for i in iocs):
            threat_level = 2  # medium
        else:
            threat_level = 3  # low
        return {
            "Event": {
                "uuid": str(uuid.uuid4()),
                "info": event_info,
                "threat_level_id": str(threat_level),
                "analysis": "2",  # completed
                "date": datetime.now().strftime("%Y-%m-%d"),
                "Attribute": attributes,
            }
        }
