"""
Editor backend — descarga el frontend de un Repl (o cualquier sitio) y lo
empaqueta como JSON para edición local + descarga de patches.

Sin token: solo lectura + diff manual + descarga de bundle.
Con REPLIT_TOKEN: además permite POST /api/site/publish para escribir de
vuelta al Repl vía Replit API v2.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple


# Lista conservadora de extensiones a intentar descargar desde un index HTML.
DEFAULT_ASSET_EXT = (".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp",
                     ".ico", ".json", ".txt", ".woff", ".woff2")
MAX_FILE_BYTES = 2_000_000  # 2 MB por archivo, por seguridad
MAX_FILES = 60
MAX_TOTAL_BYTES = 8_000_000


class _LinkExtractor(HTMLParser):
    """Extrae <link href>, <script src>, y rutas relativas del HTML."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base = urllib.parse.urlparse(base_url)
        self.refs: List[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        for key in ("href", "src"):
            v = d.get(key)
            if v and not v.startswith(("data:", "javascript:", "mailto:", "#")):
                self.refs.append(v)

    def resolve(self) -> List[str]:
        out: List[str] = []
        for r in self.refs:
            if r.startswith(("http://", "https://")):
                out.append(r)
            elif r.startswith("//"):
                out.append(f"{self.base.scheme}:{r}")
            elif r.startswith("/"):
                out.append(f"{self.base.scheme}://{self.base.netloc}{r}")
            else:
                base_dir = "/".join(self.base.path.split("/")[:-1])
                out.append(f"{self.base.scheme}://{self.base.netloc}{base_dir}/{r}")
        # dedup preservando orden
        seen, uniq = set(), []
        for u in out:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq


def fetch_site(url: str, max_files: int = MAX_FILES,
               max_total: int = MAX_TOTAL_BYTES,
               timeout: float = 8.0) -> Dict[str, Any]:
    """Descarga un sitio y devuelve un dict {ok, files, bytes, error}."""
    out_files: List[Dict[str, Any]] = []
    total = 0
    try:
        ctx_headers = {"User-Agent": "SOURCESEAL-Editor/1.0"}
        # 1) HTML principal
        html = _http_get(url, timeout=timeout, headers=ctx_headers)
        if not html:
            return {"ok": False, "error": "no se pudo descargar HTML principal"}
        out_files.append(_file_obj(url, html, "utf-8"))
        total += len(html)

        # 2) extraer assets
        parser = _LinkExtractor(url)
        try:
            parser.feed(html.decode("utf-8", errors="replace"))
        except Exception:
            pass
        for ref in parser.resolve():
            if len(out_files) >= max_files or total >= max_total:
                break
            path = urllib.parse.urlparse(ref).path
            if not any(path.lower().endswith(ext) for ext in DEFAULT_ASSET_EXT):
                continue
            try:
                body = _http_get(ref, timeout=timeout, headers=ctx_headers)
            except Exception:
                continue
            if body is None or len(body) > MAX_FILE_BYTES:
                continue
            out_files.append(_file_obj(ref, body, _guess_encoding(path)))
            total += len(body)
        return {"ok": True, "files": out_files, "bytes": total}
    except Exception as e:
        return {"ok": False, "error": str(e), "files": out_files, "bytes": total}


def _http_get(url: str, timeout: float, headers: Dict[str, str]) -> Optional[bytes]:
    import ssl
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status >= 400:
                return None
            return resp.read()
    except Exception:
        return None


def _file_obj(url: str, body: bytes, encoding: str) -> Dict[str, Any]:
    path = urllib.parse.urlparse(url).path or "/"
    if path == "/":
        path = "/index.html"
    sha = hashlib.sha256(body).hexdigest()
    try:
        text = body.decode(encoding, errors="replace")
    except Exception:
        text = body.decode("utf-8", errors="replace")
    return {"path": path.lstrip("/"), "url": url, "content": text,
            "bytes": len(body), "sha": sha, "encoding": encoding}


def _guess_encoding(path: str) -> str:
    p = path.lower()
    if p.endswith((".css", ".js", ".html", ".htm", ".svg", ".json", ".txt", ".xml")):
        return "utf-8"
    return "latin-1"


# ---------------------------------------------------------------------------
# Replit publish (opcional, requiere REPLIT_TOKEN)
# ---------------------------------------------------------------------------
class ReplitPublisher:
    """Cliente mínimo de la Replit API v2 para escribir archivos en un Repl.

    Endpoints usados:
      GET  https://replit.com/data/repls/{owner}/{slug}/files  -> index
      GET  https://replit.com/data/repls/{owner}/{slug}/files/{path...}
      POST https://replit.com/data/repls/{owner}/{slug}/files/{path...}
            body: { "files": [ { "path": "...", "content": "..." } ] }
    """

    BASE = "https://replit.com"

    def __init__(self, token: str) -> None:
        self.token = token.strip()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

    def list_files(self, owner: str, slug: str) -> Dict[str, Any]:
        url = f"{self.BASE}/data/repls/{owner}/{slug}/files"
        try:
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def write_files(self, owner: str, slug: str, files: List[Dict[str, str]]) -> Dict[str, Any]:
        # Replit acepta hasta N archivos por request; mandamos en grupos de 10
        results = []
        for i in range(0, len(files), 10):
            batch = files[i:i + 10]
            url = f"{self.BASE}/data/repls/{owner}/{slug}/files"
            try:
                req = urllib.request.Request(
                    url, data=json.dumps({"files": batch}).encode(),
                    headers=self._headers(), method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    results.append({"ok": True, "status": resp.status})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        return {"ok": all(r.get("ok") for r in results), "batches": results}


def parse_repl_url(url: str) -> Optional[Tuple[str, str]]:
    """Devuelve (owner, slug) si la URL es un Repl público, si no None."""
    m = re.match(r"https?://([\w\-]+)\.repl\.co/?$", url.strip())
    if m:
        # .repl.co no expone owner; necesitamos otra URL.
        return None
    m = re.match(r"https?://replit\.com/@([\w\-]+)/([\w\-]+)/?.*", url.strip())
    if m:
        return m.group(1), m.group(2)
    return None
