# Commander — ejecución y sincronización

Este checkout contiene Commander y COM-LINK. El backend de Red-team-tauri no está incluido; el dashboard de Commander lo consume por `BACKEND_API`.

## Termux

```bash
bash termux_setup.sh
python3 commander.py --list
BACKEND_API=http://127.0.0.1:8001 bash arrancar_commander.sh
```

- CLI de auditoría: `python3 commander.py`
- Dashboard de Commander: `http://127.0.0.1:8003`
- Red-team-tauri esperado: `http://127.0.0.1:8001`
- Pruebas rápidas: `bash quickstart.sh --test-only`
- Informes: `~/storage/downloads/commander_reports`
- Base de datos: `~/commander.db`

`nmap`, `whois` y el acceso de almacenamiento son necesarios para las funciones correspondientes. SMS, GPS y otros canales requieren Termux:API y configuración adicional.