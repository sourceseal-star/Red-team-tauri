# Commander — ejecución y sincronización

**Última actualización:** 2026-08-30

Este checkout contiene Commander y COM-LINK. El backend de Red-team-tauri no está incluido; el dashboard de Commander lo consume por `BACKEND_API`.

## Ejecución independiente en Termux

```bash
python3 commander.py --list
```

- CLI de auditoría: `python3 commander.py`
- Pruebas rápidas: `bash quickstart.sh --test-only`
- Informes: `~/storage/downloads/commander_reports`
- Base de datos: `~/commander.db`

## Ejecución conjunta recomendada

Desde la raíz de `Red-team-tauri`:

```bash
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
# Si ya está preparado y no quieres tocar Git:
bash arrancar_termux.sh
```

El dashboard unificado sirve Commander en `http://127.0.0.1:8001/api/commander/*`.
No arranques `arrancar_commander.sh` ni un servidor en `8003` para este flujo.

`nmap`, `whois` y el acceso de almacenamiento son necesarios para las funciones correspondientes. SMS, GPS y otros canales requieren Termux:API y configuración adicional.