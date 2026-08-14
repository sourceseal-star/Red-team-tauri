#!/usr/bin/env python3
"""
Threat Intelligence Platform (TIP)
Centraliza IoCs detectados por todos los módulos y los distribuye como blocklists.
"""
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class IoC:
    type: str        # ip, domain, hash, url
    value: str
    source: str      # módulo que lo detectó
    confidence: float
    first_seen: datetime = field(default_factory=datetime.utcnow)
    tags: list = field(default_factory=list)


class ThreatIntelPlatform:
    def __init__(self):
        self.iocs = []
        self.blocklist = set()

    def add_ioc(self, ioc: IoC):
        self.iocs.append(ioc)
        if ioc.confidence >= 0.7:
            self.blocklist.add(ioc.value)

    def get_blocklist(self):
        return sorted(self.blocklist)

    def get_summary(self):
        by_type = defaultdict(int)
        by_source = defaultdict(int)
        for ioc in self.iocs:
            by_type[ioc.type] += 1
            by_source[ioc.source] += 1
        return {
            "total_iocs": len(self.iocs),
            "blocklist_size": len(self.blocklist),
            "by_type": dict(by_type),
            "by_source": dict(by_source),
        }
