"""Regression tests for the additive, non-root SOL SuperGate fallback."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sol_rescate.sol_supergate import app


class SuperGateSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "SOL_API_KEY": "test-supergate-key",
                "SOL_KEY": "",
            },
            clear=False,
        )
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.env.stop()

    def test_health_is_public_but_context_requires_the_key(self) -> None:
        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Ejecutar barrido real", dashboard.text)
        self.assertNotIn("default-secure-sentinel-key", dashboard.text)

        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/sol/contexto").status_code, 403)
        self.assertEqual(
            self.client.get(
                "/sol/contexto",
                headers={"X-Sol-Key": "wrong-key"},
            ).status_code,
            403,
        )

        response = self.client.get(
            "/sol/contexto",
            headers={"X-Sol-Key": "test-supergate-key"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine"], "sol_supergate_nonroot")

    def test_missing_key_keeps_protected_routes_closed(self) -> None:
        with patch.dict(os.environ, {"SOL_API_KEY": "", "SOL_KEY": ""}):
            response = self.client.get("/sol/contexto")
        self.assertEqual(response.status_code, 503)

    def test_unknown_action_is_rejected_without_running_a_command(self) -> None:
        with patch("sol_rescate.sol_supergate.run_safe_command") as run_command:
            response = self.client.post(
                "/api/action/execute",
                headers={"X-Sol-Key": "test-supergate-key"},
                json={"action": "shell", "target": "127.0.0.1"},
            )

        self.assertEqual(response.status_code, 400)
        run_command.assert_not_called()

    def test_shell_metacharacters_are_rejected_before_execution(self) -> None:
        with patch("sol_rescate.sol_supergate.run_safe_command") as run_command:
            response = self.client.post(
                "/api/action/execute",
                headers={"X-Sol-Key": "test-supergate-key"},
                json={
                    "action": "ping",
                    "target": "127.0.0.1; touch /tmp/supergate-should-not-run",
                },
            )

        self.assertEqual(response.status_code, 400)
        run_command.assert_not_called()

    def test_allowed_action_uses_an_argument_vector(self) -> None:
        with patch(
            "sol_rescate.sol_supergate.run_safe_command",
            return_value=("pong", "", 0),
        ) as run_command:
            response = self.client.post(
                "/api/action/execute",
                headers={"X-Sol-Key": "test-supergate-key"},
                json={"action": "ping", "target": "127.0.0.1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["executed"])
        run_command.assert_called_once_with(
            ["ping", "-c", "3", "-W", "2", "127.0.0.1"]
        )


if __name__ == "__main__":
    unittest.main()