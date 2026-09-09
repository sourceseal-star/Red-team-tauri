# Verificación de fuentes del OSINT — 2026-09-08

Pedido de Harold: confirmar que los datos del OSINT son REALES y hacerlo visible.

## Veredicto

TODAS las fuentes del OSINT son APIs reales o consultas de red activas:

| Fuente | Tipo | API |
|---|---|---|
| Shodan | API con key | api.shodan.io |
| VirusTotal | API con key | virustotal.com/api/v3 |
| Censys | API con key | search.censys.io |
| Hunter.io | API con key | api.hunter.io/v2 |
| Google CSE | API con key | programmablesearchengine |
| GitHub | API con token | api.github.com |
| crt.sh | API pública, sin key | crt.sh |
| RDAP/WHOIS | API pública, sin key | rdap.org + python-whois |
| DNS | consulta de red real | resolución activa |
| ThreatFox | API pública, sin key | threatfox.abuse.ch |

Sin key configurada los endpoints devuelven error honesto
("SHODAN_API_KEY not configured" HTTP 503) — NUNCA datos inventados.
La auditoría del 2026-09-08 (commit f95b1ec) ya había eliminado la última
confusión de "demo data" con red real en topología.

## Cambios de esta sesión (dentro del commit 1f01c3c, que quedó con el
mensaje auto "Published your App" por un accidente de rebase — los
cambios son EXACTAMENTE estos)

1. `backend/modules/osint_advanced.py`: `/api/osint/full/{domain}` ahora
   incluye bloque `fuentes` — de dónde salió CADA dato y qué fuentes de
   intel NO se consultaron y por qué (falta tal key).
2. `tauri-frontend/src/components/OSINTAdvancedPanel.tsx`: banner
   permanente con el estado real de las fuentes (X/8 activas, chips
   ✓/✗ por fuente), tomado de `/api/ops/intel-status` (ya existía).
3. Frontend recompilado: `index-1VjHtiuU.js` +
   `TopologyMap-w3iguvTb.js`.

Aditivo total: cero rutas eliminadas, cero respuestas cambiadas.
Verificado: 16 rutas del router OSINT montadas, banner dentro del
bundle, sintaxis Python OK, build vite OK.
