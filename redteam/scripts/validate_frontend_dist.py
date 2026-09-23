#!/usr/bin/env python3
"""Validate that the tracked frontend bundle is internally complete.

The dashboard can return HTTP 200 while a stale or partial Vite dist leaves
the browser with a blank page. Keep this check dependency-free so both Replit
and Termux can run it before starting the backend.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST = PROJECT_ROOT / "tauri-frontend" / "dist"
INDEX_ASSET_RE = re.compile(r"""(?:src|href)=["'](/assets/[^"']+)["']""")
JS_ASSET_RE = re.compile(
    r"""["'`](?:/assets/|assets/|\./)
    ([A-Za-z0-9][A-Za-z0-9._-]+\.(?:js|css|png|jpe?g|svg|woff2?))["'`]""",
    re.VERBOSE,
)


def validate(dist: Path = DIST) -> list[str]:
    errors: list[str] = []
    index = dist / "index.html"
    if not index.is_file():
        return [f"missing {index}"]

    text = index.read_text(encoding="utf-8")
    if 'id="root"' not in text:
        errors.append("index.html has no #root mount")

    assets = sorted(set(INDEX_ASSET_RE.findall(text)))
    if not assets:
        errors.append("index.html references no /assets/ bundle")

    referenced_files = {
        Path(asset.lstrip("/"))
        for asset in assets
    }
    for script in sorted((dist / "assets").glob("*.js")):
        for asset_name in JS_ASSET_RE.findall(
            script.read_text(encoding="utf-8", errors="replace")
        ):
            referenced_files.add(Path("assets") / asset_name)

    tracked = set()
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "tauri-frontend/dist"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        prefix = Path("tauri-frontend/dist")
        tracked = {
            Path(path).relative_to(prefix)
            for path in result.stdout.splitlines()
            if Path(path).is_relative_to(prefix)
        }
    except OSError:
        errors.append("git is unavailable; cannot verify tracked dist")

    for relative in sorted(referenced_files):
        candidate = dist / relative
        if not candidate.is_file():
            errors.append(f"missing referenced asset /{relative.as_posix()}")
        if tracked and relative not in tracked:
            errors.append(f"asset is not tracked by Git /{relative.as_posix()}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("frontend_dist=fail")
        for error in errors:
            print(f"  - {error}")
        return 1

    index = DIST / "index.html"
    assets = sorted(set(INDEX_ASSET_RE.findall(index.read_text(encoding="utf-8"))))
    print(f"frontend_dist=ok assets={len(assets)} path={DIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())