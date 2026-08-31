---
name: GitHub sync setup
description: How git auth is configured and which repo to use for this project
---

# GitHub Sync

**Repo:** `https://github.com/sourceseal-star/Red-team-tauri`  
**Account:** `sourceseal-star`

**Why:** The original remote (`sourceseal/Red-team-main`) was inaccessible from the connected GitHub account. The user chose `Red-team-tauri` under `sourceseal-star`.

**How auth works:**
- `GITHUB_TOKEN` secret holds a Personal Access Token with `repo` scope
- Git credential helper: `git config credential.helper store` → `~/.git-credentials` holds `https://sourceseal-star:TOKEN@github.com`
- Remote URL is clean (no token embedded): `https://github.com/sourceseal-star/Red-team-tauri.git`
- Shell `git push/pull` may depend on the current credential-helper state; do not assume it is available after reconnecting GitHub. A healthy Replit connection can coexist with a rejected local HTTPS push.
- Verify the remote URL includes `github.com`; an imported workspace may retain a malformed `https://owner/repo.git` URL and surface `UNAUTHENTICATED` before credentials are even evaluated.

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

**How to apply:** If git push fails after a container restart, re-run:
```bash
git config credential.helper store
echo "https://sourceseal-star:$(printenv GITHUB_TOKEN)@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
```

**History:** Initial push required creating an orphan branch to avoid GitHub push protection blocking a fake Stripe test placeholder key present in `redteam/tests/test_scenarios.py` and `build/tests/test_scenarios.py`. Key replaced with a non-secret placeholder string.
