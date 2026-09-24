---
name: GitHub publishing
description: Use the managed GitHub connection when the local Git credential helper is stale or rejected.
---

The local Git credential helper can remain invalid even when the Replit-managed GitHub integration is installed. For repository writes, use the managed `github` connector and its authenticated Git data API instead of asking for or exposing a token.

**Why:** A local `git push` failed with an authentication error while the managed connection could be reauthorized and publish the same repository safely.

**How to apply:** If GitHub returns a 401 through the connector, inspect the reauthorization context and offer one OAuth reauthorization. After it succeeds, retry the failed connector operation once; do not loop.