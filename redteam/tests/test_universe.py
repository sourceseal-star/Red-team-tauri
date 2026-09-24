"""Regresiones aisladas para el router aditivo SOL Universe."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from fastapi import FastAPI
from redteam.modules.universe import router, universe_state


class UniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        universe_state["last_synchronization"] = None
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()

    def test_status_is_read_only_and_reports_userland_context(self) -> None:
        with patch(
            "redteam.modules.universe.socket.gethostname",
            return_value="termux-node",
        ), patch(
            "redteam.modules.universe.socket.gethostbyname",
            return_value="10.20.0.4",
        ):
            response = self.client.get("/api/universe/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["module"], "universe.py")
        self.assertEqual(body["network_context"]["local_ip"], "10.20.0.4")
        self.assertEqual(body["network_context"]["privilege"], "userland (no-root)")
        self.assertIsNone(body["state"]["last_synchronization"])
        self.assertIn("observed_at", body)

    def test_sync_accepts_only_declared_actions(self) -> None:
        response = self.client.post(
            "/api/universe/sync",
            json={"action": "mesh_sync", "target_subnet": "10.20.0.0/24"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subnet"], "10.20.0.0/24")

        invalid = self.client.post(
            "/api/universe/sync",
            json={"action": "shell", "target_subnet": "10.20.0.0/24"},
        )
        self.assertEqual(invalid.status_code, 400)
