---
name: Android field integrations
description: Termux and Android app integrations remain optional, feature-detected, and operator-triggered.
---

Termux:API, OsmAnd, and NetGuard are device-local capabilities rather than server dependencies. The Dashboard must detect their availability, expose honest fallback states, and keep location reads and network discovery under explicit operator action.

**Why:** Replit cannot execute Android intents or Termux commands, and NetGuard does not expose a public API for remotely changing firewall rules.

**How to apply:** Keep Android endpoints optional and authenticated; use relative Dashboard routes; require an explicit target and confirmation for manual TCP scans; keep automatic discovery as a separate button rather than an on-load action.