#!/usr/bin/env python3
"""
SOAR DAG Executor — Directed Acyclic Graph playbook execution engine
=====================================================================
Executes SOAR playbooks as DAGs with:
  - Topological sort of steps based on depends_on
  - Parallel execution of independent steps (ThreadPoolExecutor)
  - Rollback on failure (reverse order of completed steps)
  - Per-step state tracking and timeout handling
  - MITRE ATT&CK technique tagging in execution reports
"""

import json
import time
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque


class StepState(Enum):
    PENDING     = "PENDING"
    RUNNING     = "RUNNING"
    SUCCESS     = "SUCCESS"
    FAILED      = "FAILED"
    SKIPPED     = "SKIPPED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class StepResult:
    step_id: str
    step_name: str
    handler: str
    state: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[float] = None
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    mitre_technique: Optional[str] = None
    rollback_result: Optional[Dict] = None


class DAGExecutor:
    """
    Executes a SOAR playbook as a DAG.

    Usage:
        executor = DAGExecutor(playbook_dict, handlers_dict)
        result = executor.execute(context={"incident_id": "INC-001"})
        report = executor.get_execution_report()
    """

    def __init__(self, playbook: Dict[str, Any], handlers: Dict[str, Callable]):
        self.playbook = playbook
        self.handlers = handlers
        self.step_results: Dict[str, StepResult] = {}
        self.context: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._execution_start: Optional[str] = None
        self._execution_end: Optional[str] = None

    def _topological_sort(self, steps: List[Dict]) -> List[List[Dict]]:
        """Returns steps grouped in execution waves (parallel groups)."""
        step_map = {s["id"]: s for s in steps}
        in_degree = {s["id"]: 0 for s in steps}
        graph = defaultdict(list)

        for step in steps:
            for dep in step.get("depends_on", []):
                graph[dep].append(step["id"])
                in_degree[step["id"]] += 1

        # BFS wave generation
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        waves = []
        visited = set()

        while queue:
            wave_size = len(queue)
            wave = []
            for _ in range(wave_size):
                sid = queue.popleft()
                wave.append(step_map[sid])
                visited.add(sid)
                for neighbor in graph[sid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            waves.append(wave)

        if len(visited) != len(steps):
            raise ValueError("Playbook has a circular dependency in steps")

        return waves

    def _run_step(self, step: Dict, context: Dict) -> StepResult:
        """Executes a single step with timeout handling."""
        step_id = step["id"]
        handler_name = step["handler"]
        timeout = step.get("timeout_seconds", 30)
        mitre = step.get("mitre_technique") or (self.playbook.get("mitre_techniques") or [None])[0] if (self.playbook.get("mitre_techniques") or []) else None

        result = StepResult(
            step_id=step_id,
            step_name=step.get("name", step_id),
            handler=handler_name,
            state=StepState.RUNNING.value,
            started_at=datetime.datetime.utcnow().isoformat() + "Z",
            mitre_technique=mitre,
        )

        with self._lock:
            self.step_results[step_id] = result

        start_ts = time.time()

        try:
            handler_fn = self.handlers.get(handler_name)
            if not handler_fn:
                raise ValueError(f"Handler '{handler_name}' not registered")

            # Run handler with timeout via thread
            output = [None]
            exc = [None]

            def run():
                try:
                    output[0] = handler_fn({**context, **step.get("params", {})})
                except Exception as e:
                    exc[0] = e

            t = threading.Thread(target=run)
            t.start()
            t.join(timeout=timeout)

            if t.is_alive():
                result.state = StepState.FAILED.value
                result.error = f"Timeout after {timeout}s"
            elif exc[0]:
                raise exc[0]
            else:
                result.state = StepState.SUCCESS.value
                result.output = output[0] or {}
                # Merge step output into shared context
                with self._lock:
                    self.context.update(result.output)

        except Exception as e:
            result.state = StepState.FAILED.value
            result.error = str(e)

        finally:
            elapsed = time.time() - start_ts
            result.finished_at = datetime.datetime.utcnow().isoformat() + "Z"
            result.duration_ms = round(elapsed * 1000, 2)
            with self._lock:
                self.step_results[step_id] = result

        return result

    def _rollback_step(self, step: Dict, context: Dict) -> Optional[Dict]:
        """Executes rollback handler for a completed step."""
        rollback_handler = step.get("rollback_handler")
        if not rollback_handler:
            return None
        handler_fn = self.handlers.get(rollback_handler)
        if not handler_fn:
            return {"success": False, "error": f"Rollback handler '{rollback_handler}' not found"}
        try:
            return handler_fn({**context, **step.get("params", {})})
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute(self, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute the playbook DAG.
        Returns a summary dict with overall status and per-step results.
        """
        self.context = context or {}
        self._execution_start = datetime.datetime.utcnow().isoformat() + "Z"
        steps = self.playbook.get("steps", [])
        completed_steps: List[Dict] = []
        overall_success = True

        try:
            waves = self._topological_sort(steps)
        except ValueError as e:
            return {"success": False, "error": str(e), "step_results": {}}

        for wave in waves:
            if not overall_success:
                # Mark remaining steps as SKIPPED
                for step in wave:
                    self.step_results[step["id"]] = StepResult(
                        step_id=step["id"],
                        step_name=step.get("name", step["id"]),
                        handler=step["handler"],
                        state=StepState.SKIPPED.value,
                    )
                continue

            # Execute wave steps in parallel
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {pool.submit(self._run_step, step, dict(self.context)): step for step in wave}
                for future in as_completed(futures):
                    step = futures[future]
                    result = future.result()
                    if result.state == StepState.SUCCESS.value:
                        completed_steps.append(step)
                    elif not step.get("continue_on_failure", False):
                        overall_success = False

        # Rollback if failed
        if not overall_success:
            for step in reversed(completed_steps):
                rollback_result = self._rollback_step(step, self.context)
                if step["id"] in self.step_results:
                    self.step_results[step["id"]].state = StepState.ROLLED_BACK.value
                    self.step_results[step["id"]].rollback_result = rollback_result

        self._execution_end = datetime.datetime.utcnow().isoformat() + "Z"
        return self.get_execution_report()

    def get_execution_report(self) -> Dict[str, Any]:
        """Returns the full execution report."""
        results = {sid: asdict(r) for sid, r in self.step_results.items()}
        states = [r.state for r in self.step_results.values()]
        overall = "SUCCESS" if all(s == StepState.SUCCESS.value for s in states) else \
                  "PARTIAL" if any(s == StepState.SUCCESS.value for s in states) else "FAILED"
        return {
            "playbook": self.playbook.get("name", "unknown"),
            "mitre_techniques": self.playbook.get("mitre_techniques", []),
            "severity": self.playbook.get("severity", "UNKNOWN"),
            "overall_status": overall,
            "started_at": self._execution_start,
            "finished_at": self._execution_end,
            "step_count": len(self.step_results),
            "steps_success": sum(1 for s in states if s == StepState.SUCCESS.value),
            "steps_failed": sum(1 for s in states if s == StepState.FAILED.value),
            "steps_rolled_back": sum(1 for s in states if s == StepState.ROLLED_BACK.value),
            "steps_skipped": sum(1 for s in states if s == StepState.SKIPPED.value),
            "step_results": results,
            "final_context": self.context,
        }
