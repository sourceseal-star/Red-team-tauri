# SOL 2.0 — Núcleo de Autonomía y Auto-Evolución (2026-09-08)

**Estado: FASE 1 (aditiva, NO cableada al dashboard — riesgo cero).**

## Qué es
Paquete `sol_autonomy/` + script `sol_awakening.py`: memoria operativa SQLite,
metas, reflexión, evolución de estrategias y aprendizaje continuo para Sol.

## Por qué "sol_autonomy" y no "sol_core/" (regla #3)
El diseño original creaba un paquete `sol_core/` — pero `sol_core.py` YA existe
como módulo en la raíz y Python daría prioridad al paquete, secuestrando todos
los imports existentes (sol_core, sol_tools, sol_api). Igual con `sol_memory/`
(ya existe `sol_memory.py`). Nombre nuevo = cero colisiones.

## Las tres memorias de Sol (no se pisan)
| Sistema | Papel | Formato |
|---|---|---|
| `memory.jsonl` | recuerdos conversacionales | JSONL + backup AES cada 6h |
| `libro_vida.json` | hechos duraderos sobre Harold (regla #56) | JSON destilado por LLM |
| `sol_brain.db` (NUEVO) | experiencias OPERATIVAS: qué hice, si funcionó, qué aprendí | SQLite WAL |

Todo vive en `~/.sol/` (o sobreescribir con `SOL_BRAIN_DB`, `SOL_GOALS`, `SOL_STRATEGIES`).

## Bugs del diseño original corregidos aquí
1. `reflection.py` usaba `sqlite3` sin importarlo → NameError.
2. Metas nunca progresaban: `f"master_{task_name}"` no coincidía con ningún id → registro TASK_GOAL_REGISTRY.
3. Banco de estrategias vivía solo en RAM (se perdía al reiniciar) → persiste en `sol_strategies.json`.
4. Mezcla de unidades 0-1 vs 0-100 en success_rate/confianza → escala 0-100 única.
5. `db_path="sol_brain.db"` relativo al cwd (omni.sh cambia de directorio) → anclado a `~/.sol/`.
6. El ejemplo "Cómo usar" REEMPLAZABA `/api/scan/topology` → PROHIBIDO (regla #1): la instrumentación es pre_task/post_task en los call-sites, nunca sustituyendo rutas.

## Uso (standalone, ya funciona)
```bash
python3 sol_awakening.py          # briefing matutino
python3 sol_awakening.py --evolve # ciclo de evolución
python3 sol_awakening.py --health # salud JSON
```

## FASE 2 (pendiente confirmación de Harold) — instrumentar sin reemplazar
Añadir en `redteam/scripts/dashboard_server.py`, dentro de las funciones
EXISTENTES (3 líneas por sitio, en try/except para que nunca tumbe el scan):
```python
_SOL = None  # import perezoso con try/except — si falla, todo sigue igual
def _sol():  # singleton
    global _SOL
    if _SOL is None:
        from sol_autonomy import AutonomousSol; _SOL = AutonomousSol()
    return _SOL
# en scan_topology, tras obtener hosts (try/except alrededor):
#   prep = _sol().pre_task("network_scan", {...}); ... _sol().post_task(...)
```
Sitios: `scan_topology`, `scan_cameras`, GPS. El `post_task` ya devuelve la
mini-reflexión cada 10 tareas del día.

## FASE 3 (después) — panel y cron
- Endpoints nuevos `/api/sol-autonomy/health|briefing|evolve` (solo lectura + POST).
- Cron de Termux: `0 9 * * * python3 sol_awakening.py --evolve`.
- Seeding opcional: cargar SIL/tutor stats como skills iniciales.
