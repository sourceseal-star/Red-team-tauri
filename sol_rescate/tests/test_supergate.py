"""Regression tests for the additive, non-root SOL SuperGate fallback."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sol_rescate import sol_supergate
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

    def test_active_interfaces_expose_all_private_ipv4_networks(self) -> None:
        ip_output = "\n".join(
            [
                "2: eth0    inet 172.22.5.8/24 brd 172.22.5.255 scope global eth0",
                "3: wlan0   inet 10.20.0.4/24 brd 10.20.0.255 scope global wlan0",
                "4: wan0    inet 8.8.8.8/24 brd 8.8.8.255 scope global wan0",
                "1: lo      inet 127.0.0.1/8 scope host lo",
            ]
        )
        with patch(
            "sol_rescate.sol_supergate.run_safe_command",
            return_value=(ip_output, "", 0),
        ):
            interfaces = sol_supergate.obtener_interfaces_activas()

        self.assertEqual(
            [item["network_cidr"] for item in interfaces],
            ["172.22.5.0/24", "10.20.0.0/24"],
        )
        self.assertEqual([item["type_hint"] for item in interfaces], ["ethernet", "wifi"])


if __name__ == "__main__":
    unittest.main()