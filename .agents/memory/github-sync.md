---
name: GitHub sync setup
description: How git auth is configured and which repo to use for this project
---

# GitHub Sync

**Repo:** `https://github.com/sourceseal-star/Red-team-tauri`  
**Account:** `sourceseal-star`

**Why:** The original remote (`sourceseal/Red-team-main`) was inaccessible from the connected GitHub account. The user chose `Red-team-tauri` under `sourceseal-star`.

**How auth works:**
- Prefer the connected Replit GitHub integration (`github`) for authenticated API operations; it injects credentials without exposing them to the workspace.
- `GITHUB_TOKEN` and the local credential helper may be absent or stale after reconnecting the workspace; do not assume shell `git push/pull` is available.
- Remote URL is clean (no token embedded): `https://github.com/sourceseal-star/Red-team-tauri.git`
- Verify the remote URL includes `github.com`; an imported workspace may retain a malformed `https://owner/repo.git` URL and surface `UNAUTHENTICATED` before credentials are evaluated.

**Publishing through the connected integration:**
- Read `GET /repos/{owner}/{repo}/git/ref/heads/main` to obtain the current commit.
- Update with `PATCH /repos/{owner}/{repo}/git/refs/heads/main` (the update path is plural `refs`).
- Check the branch SHA immediately before the update and use `force: false` so a concurrent remote change is never overwritten.

**Why:** GitHub's read-reference and update-reference REST endpoints use different
path forms, and the workspace credential helper can be stale even when the
integration is connected.

**How to apply:** Prefer the connected integration for authenticated publishing.
Build blobs/tree/commit from the local diff, verify the expected parent SHA, then
advance `main` through the plural `refs` endpoint.

**How to apply:** After publishing through the integration, verify both the remote
ref SHA and tree SHA; the local tracking ref may still describe the pre-publish
commit even when the remote is correct.

**History:** Initial push required creating an orphan branch to avoid GitHub push protection blocking a fake Stripe test placeholder key present in `redteam/tests/test_scenarios.py` and `build/tests/test_scenarios.py`. Key replaced with a non-secret placeholder string.
