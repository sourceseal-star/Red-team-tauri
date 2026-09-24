"""Regresiones aisladas para el router SOL Universe v4 (estado real + medios)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from redteam.modules import universe


class UniverseV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        # HOME aislado: no tocar ~/warroom real del entorno de pruebas
        self._tmp = tempfile.TemporaryDirectory()
        self._home = patch("redteam.modules.universe.Path.home",
                           return_value=Path(self._tmp.name))
        self._home.start()
        # Reinicializar rutas y estado del módulo bajo el HOME aislado
        universe.WR = Path(self._tmp.name) / "warroom"
        universe.MEDIA_DIR = universe.WR / "media"
        universe.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        universe._MEDIA_ROOT = universe.MEDIA_DIR.resolve()
        universe.STATE_F = universe.WR / "universe_state.json"
        universe.universe_state.update({
            "started": None, "net": None, "fd_count": 0, "nodes": {},
            "last_purge": None, "purges": 0,
            "media": {"count": 0, "bytes": 0, "last_index": None},
        })
        self.app = FastAPI()
        self.app.include_router(universe.router)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self._home.stop()
        self._tmp.cleanup()

    def test_status_reports_real_userland_context(self) -> None:
        with patch("redteam.modules.universe._local_ip", return_value="192.168.43.1"):
            response = self.client.get("/api/universe/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # El estado v4 viaja plano: started/net/fd_count/media son reales
        self.assertIn("fd_now", body)
        self.assertIn("net", body)
        self.assertIn("media", body)

    def test_sync_accepts_only_declared_actions(self) -> None:
        ok = self.client.post("/api/universe/sync", json={"action": "net_inspect"})
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["ok"])
        bad = self.client.post("/api/universe/sync", json={"action": "shell"})
        self.assertEqual(bad.status_code, 422)  # pydantic rechaza la acción

    def test_mesh_sync_records_timestamp(self) -> None:
        before = universe.universe_state.get("last_mesh")
        response = self.client.post("/api/universe/sync", json={"action": "mesh_sync"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertNotEqual(before, universe.universe_state.get("last_mesh"))

    # ── Medios: seguridad de nombres y allowlist ──────────────────────────────
    def test_media_upload_and_view_roundtrip(self) -> None:
        upload = self.client.post(
            "/api/universe/media/upload",
            files={"file": ("holo_sol.png", b"\x89PNG-fake", "image/png")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["type"], "image")

        viewed = self.client.get("/api/universe/media/view/holo_sol.png")
        self.assertEqual(viewed.status_code, 200)
        self.assertEqual(viewed.headers["content-type"].split(";")[0], "image/png")
        self.assertEqual(viewed.content, b"\x89PNG-fake")

        listing = self.client.get("/api/universe/media/list")
        self.assertEqual(listing.status_code, 200)
        media = listing.json()["media"]
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["filename"], "holo_sol.png")

    def test_media_upload_rejects_disallowed_extension(self) -> None:
        upload = self.client.post(
            "/api/universe/media/upload",
            files={"file": ("exploito.html", b"<script>", "text/html")},
        )
        self.assertEqual(upload.status_code, 415)

    def test_media_view_blocks_path_traversal(self) -> None:
        for hostile in ("../../etc/passwd", "universe_state.json", "..%2F..%2Fsecreto"):
            response = self.client.get(f"/api/universe/media/view/{hostile}")
            self.assertIn(response.status_code, (404, 415),
                          f"no debía servirse: {hostile}")

    def test_media_view_never_serves_html(self) -> None:
        # Aunque exista un .html en el directorio, el endpoint no lo sirve
        (universe.MEDIA_DIR / "x.html").write_text("<script>bad()</script>")
        response = self.client.get("/api/universe/media/view/x.html")
        self.assertEqual(response.status_code, 415)
        (universe.MEDIA_DIR / "x.html").unlink()
