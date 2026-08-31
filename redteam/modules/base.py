"""Clase base para módulos autorizados de evaluación y evidencia."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redteam.runner.engagement_guard import require_authorization


EVIDENCE_DIR = Path(
    os.environ.get(
        "SOURCESEAL_EVIDENCE_DIR",
        str(Path.home() / ".sourceseal" / "evidence" / "findings"),
    )
).expanduser()


class BaseModule:
    name = "base"
    description = ""
    version = "1.0"

    def __init__(self, engagement_id: str):
        self.engagement_id = engagement_id
        self.start_time: datetime | None = None
        self.findings: list[dict[str, Any]] = []

    def authorize_target(self, target: str) -> bool:
        return require_authorization(target, self.engagement_id)

    def run(self, target: str, **kwargs: Any) -> dict[str, Any]:
        self.start_time = datetime.now(timezone.utc)
        self.authorize_target(target)
        result = self._execute(target, **kwargs)
        self._seal_finding(target, result)
        return result

    def _execute(self, target: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def _seal_finding(self, target: str, result: dict[str, Any]) -> None:
        started = self.start_time or datetime.now(timezone.utc)
        finding = {
            "module": self.name,
            "version": self.version,
            "engagement_id": self.engagement_id,
            "target": target,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_sec": (datetime.now(timezone.utc) - started).total_seconds(),
            "result": result,
        }
        canonical = json.dumps(finding, sort_keys=True, ensure_ascii=False)
        finding["finding_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        output = EVIDENCE_DIR / f"{self.name}_{int(time.time())}_{finding['finding_hash'][:8]}.json"
        output.write_text(json.dumps(finding, indent=2, ensure_ascii=False), encoding="utf-8")
        self.findings.append(finding)