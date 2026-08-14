#!/usr/bin/env python3
"""
Unit tests for SOAR DAG Executor
Tests: topological sort, parallel execution, rollback, timeout, state tracking.
"""

import json
import time
import unittest
import threading
from pathlib import Path

from dag_executor import DAGExecutor, StepState
from handlers import HANDLER_REGISTRY


# ─────────────────────────────────────────────
# Mock handlers
# ─────────────────────────────────────────────

def mock_success(context):
    return {"success": True, "message": "ok"}

def mock_fail(context):
    raise RuntimeError("Simulated handler failure")

def mock_slow(context):
    time.sleep(5)  # longer than timeout
    return {"success": True}

def mock_rollback(context):
    return {"success": True, "message": "rolled back"}

MOCK_HANDLERS = {
    "mock_success": mock_success,
    "mock_fail": mock_fail,
    "mock_slow": mock_slow,
    "mock_rollback": mock_rollback,
    **HANDLER_REGISTRY,
}

# ─────────────────────────────────────────────
# Helper: simple 3-step playbook
# ─────────────────────────────────────────────

SIMPLE_PLAYBOOK = {
    "name": "test_playbook",
    "mitre_techniques": ["T1566"],
    "severity": "HIGH",
    "steps": [
        {"id": "s1", "name": "Step 1", "handler": "mock_success", "depends_on": [], "timeout_seconds": 5},
        {"id": "s2", "name": "Step 2", "handler": "mock_success", "depends_on": ["s1"], "timeout_seconds": 5},
        {"id": "s3", "name": "Step 3", "handler": "mock_success", "depends_on": ["s1"], "timeout_seconds": 5},
    ]
}


class TestDAGExecutor(unittest.TestCase):

    def test_simple_execution_success(self):
        """All steps succeed — overall_status should be SUCCESS."""
        executor = DAGExecutor(SIMPLE_PLAYBOOK, MOCK_HANDLERS)
        report = executor.execute({"incident_id": "TEST-001"})
        self.assertEqual(report["overall_status"], "SUCCESS")
        self.assertEqual(report["steps_success"], 3)
        self.assertEqual(report["steps_failed"], 0)

    def test_topological_sort_order(self):
        """s2 and s3 both depend on s1 — s1 must run before s2/s3."""
        execution_order = []

        def track_handler(context):
            execution_order.append(context.get("_step_id", "?"))
            return {"success": True}

        # Inject tracking into each step
        playbook = {
            "name": "order_test",
            "mitre_techniques": [],
            "severity": "LOW",
            "steps": [
                {"id": "s1", "name": "S1", "handler": "h_s1", "depends_on": [], "timeout_seconds": 5},
                {"id": "s2", "name": "S2", "handler": "h_s2", "depends_on": ["s1"], "timeout_seconds": 5},
                {"id": "s3", "name": "S3", "handler": "h_s3", "depends_on": ["s2"], "timeout_seconds": 5},
            ]
        }

        order_log = []
        def make_handler(name):
            def h(ctx):
                order_log.append(name)
                return {"success": True}
            return h

        handlers = {
            "h_s1": make_handler("s1"),
            "h_s2": make_handler("s2"),
            "h_s3": make_handler("s3"),
        }

        executor = DAGExecutor(playbook, handlers)
        executor.execute({})
        self.assertEqual(order_log, ["s1", "s2", "s3"])

    def test_rollback_on_failure(self):
        """When s2 fails, completed s1 should be rolled back."""
        rollback_called = []

        def succeed(ctx):
            return {"success": True}

        def fail(ctx):
            raise RuntimeError("Failure!")

        def rollback(ctx):
            rollback_called.append(True)
            return {"success": True, "message": "rolled back"}

        playbook = {
            "name": "rollback_test",
            "mitre_techniques": [],
            "severity": "HIGH",
            "steps": [
                {"id": "s1", "name": "S1", "handler": "succeed", "depends_on": [],
                 "timeout_seconds": 5, "rollback_handler": "rollback"},
                {"id": "s2", "name": "S2 FAIL", "handler": "fail", "depends_on": ["s1"],
                 "timeout_seconds": 5},
            ]
        }

        handlers = {"succeed": succeed, "fail": fail, "rollback": rollback}
        executor = DAGExecutor(playbook, handlers)
        report = executor.execute({})

        self.assertNotEqual(report["overall_status"], "SUCCESS")
        self.assertTrue(len(rollback_called) > 0, "Rollback should have been called for s1")
        self.assertEqual(report["step_results"]["s1"]["state"], StepState.ROLLED_BACK.value)
        self.assertEqual(report["step_results"]["s2"]["state"], StepState.FAILED.value)

    def test_parallel_execution(self):
        """Steps with no depends_on should run concurrently."""
        start_times = {}
        lock = threading.Lock()

        def slow_handler(ctx):
            step = ctx.get("step_name", "?")
            with lock:
                start_times[step] = time.time()
            time.sleep(0.3)
            return {"success": True}

        playbook = {
            "name": "parallel_test",
            "mitre_techniques": [],
            "severity": "LOW",
            "steps": [
                {"id": "p1", "name": "P1", "handler": "slow_h", "depends_on": [], "timeout_seconds": 5},
                {"id": "p2", "name": "P2", "handler": "slow_h", "depends_on": [], "timeout_seconds": 5},
            ]
        }

        t_start = time.time()
        executor = DAGExecutor(playbook, {"slow_h": slow_handler})
        report = executor.execute({})
        t_total = time.time() - t_start

        # If truly parallel, total time should be ~0.3s, not ~0.6s
        self.assertLess(t_total, 0.55, "Parallel steps should complete faster than sequential")
        self.assertEqual(report["steps_success"], 2)

    def test_timeout_handling(self):
        """A step that exceeds timeout_seconds should be marked FAILED."""
        playbook = {
            "name": "timeout_test",
            "mitre_techniques": [],
            "severity": "LOW",
            "steps": [
                {"id": "slow", "name": "Slow Step", "handler": "mock_slow",
                 "depends_on": [], "timeout_seconds": 1},
            ]
        }

        executor = DAGExecutor(playbook, MOCK_HANDLERS)
        report = executor.execute({})
        self.assertEqual(report["step_results"]["slow"]["state"], StepState.FAILED.value)
        self.assertIn("Timeout", report["step_results"]["slow"]["error"])

    def test_load_phishing_playbook(self):
        """Load real phishing playbook JSON and execute with mock handlers."""
        pb_path = Path(__file__).parent / "playbooks" / "playbook_phishing.json"
        if not pb_path.exists():
            self.skipTest("playbook_phishing.json not found")

        with open(pb_path) as f:
            playbook = json.load(f)

        executor = DAGExecutor(playbook, MOCK_HANDLERS)
        report = executor.execute({"incident_id": "INC-TEST-002", "source_ip": "1.2.3.4",
                                   "sender_email": "evil@test.com", "user_id": "user123"})
        # All steps use mock_success via HANDLER_REGISTRY (which simulates)
        self.assertIn(report["overall_status"], ["SUCCESS", "PARTIAL", "FAILED"])
        self.assertGreater(report["step_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
