# Campo: integración aditiva en el servidor vivo

El servidor que corre en Termux y Replit es `redteam/scripts/dashboard_server.py`
(Regla #43). No se reemplaza por un segundo `FastAPI()`: eso perdería cientos
de rutas, autenticación y middleware existentes.

- `POST /api/scan/topology`: conserva `results`, `hosts_up`, `subnet`,
  `local_ip` y `method`. Nmap ya corre en un thread con timeout y TCP es el
  fallback sin root. Se rechazan rangos fuera de RFC1918 y mayores de /24
  antes de iniciar un proceso o socket. Nunca escanea al montar la War Room.
- `GET/POST /api/scan/cameras`: mantiene `results`, `count` y
  `elapsed_seconds`, incluida la ruta `?target=IP` que usa GeoIntel. El barrido
  local sin target se limita a la LAN detectada, con máximo 24 conexiones RTSP
  concurrentes; un puerto abierto no proporciona por sí solo marca/modelo.
- `redteam/scripts/android_field.py` es la pasarela real Termux:API y ya
  implementa `/api/android/location`, `/api/android/wifi`, estado, permisos
  e intents OsmAnd/NetGuard. `/api/android/gps` es alias del GPS existente;
  `/api/android/wifi-scan` devuelve datos reales o 503 con el error, no mocks.
  No hace falta crear otra `sol_body.py` ni cambiar a 0 las coordenadas GPS
  ausentes: 0 sería una posición falsa.
- `sol_security.py` (repo `sol`) y SOL GATE (`sol_portero.py` en :8012) siguen
  siendo fronteras separadas. El JSON editable del panel SuperGate NO es una
  autorización para desactivar el middleware ni abrir `skip_authorization`,
  escritura/borrado, comandos arbitrarios o escaneo de IPs externas.

Verificación sin tocar redes/hardware:

```sh
PYTHONPATH=. python3 -m unittest -q redteam.tests.test_field_contracts
python3 -m py_compile redteam/scripts/dashboard_server.py redteam/scripts/android_field.py
python3 redteam/scripts/validate_frontend_dist.py
```

Para comprobar el hardware real falta ejecutar en el teléfono (no en Replit)
los endpoints con la autenticación existente y permisos Termux:API concedidos.
No se instala ningún paquete ni se inicia ningún barrido automáticamente.
