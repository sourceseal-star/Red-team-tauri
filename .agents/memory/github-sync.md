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
- Shell `git push/pull` works via credential helper; Replit gitPush callback may still fail (OAuth not linked) — use shell directly if needed

**How to apply:** If git push fails after a container restart, re-run:
```bash
git config credential.helper store
echo "https://sourceseal-star:$(printenv GITHUB_TOKEN)@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials
```

**History:** Initial push required creating an orphan branch to avoid GitHub push protection blocking a fake Stripe test placeholder key present in `redteam/tests/test_scenarios.py` and `build/tests/test_scenarios.py`. Key replaced with a non-secret placeholder string.
