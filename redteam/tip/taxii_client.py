#!/usr/bin/env python3
"""
TAXII 2.1 Client — Push STIX bundles a un servidor TAXII.
Si no hay servidor configurado, exporta a archivo local.
"""
import json
import os
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional


class TaxiiClient:
    """Cliente TAXII 2.1 para enviar STIX bundles."""

    def __init__(
        self,
        server_url: str = "",
        api_key: str = "",
        collection_id: str = "",
        timeout: int = 30,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.collection_id = collection_id
        self.timeout = timeout
        self._headers = {
            "Accept": "application/taxii+json;version=2.1",
            "Content-Type": "application/taxii+json;version=2.1",
        }
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def discover_collections(self) -> List[Dict]:
        """Descubre colecciones disponibles en el servidor TAXII."""
        if not self.server_url:
            return []
        try:
            resp = requests.get(
                f"{self.server_url}/taxii2/api/v21/collections/",
                headers=self._headers,
                timeout=self.timeout,
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json().get("collections", [])
        except Exception:
            pass
        return []

    def push_to_collection(self, stix_bundle: Dict) -> Dict:
        """Envía un STIX bundle a la colección configurada."""
        if not self.server_url or not self.collection_id:
            return self._export_local(stix_bundle)

        url = f"{self.server_url}/taxii2/api/v21/collections/{self.collection_id}/objects/"
        try:
            resp = requests.post(
                url,
                json=stix_bundle,
                headers=self._headers,
                timeout=self.timeout,
                verify=False,
            )
            return {
                "status": "pushed" if resp.status_code in (200, 201, 202) else "failed",
                "status_code": resp.status_code,
                "response": resp.text[:500],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_collections(self) -> List[Dict]:
        """Obtiene la lista de colecciones."""
        return self.discover_collections()

    def _export_local(self, stix_bundle: Dict) -> Dict:
        """Fallback: exporta a archivo local si no hay servidor."""
        export_dir = "reports"
        os.makedirs(export_dir, exist_ok=True)
        filename = f"stix-bundle-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
        filepath = os.path.join(export_dir, filename)
        with open(filepath, "w") as f:
            json.dump(stix_bundle, f, indent=2, default=str)
        return {
            "status": "exported_local",
            "file": filepath,
            "message": "No TAXII server configured — exported to local file",
        }
