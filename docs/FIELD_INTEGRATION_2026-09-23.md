# Campo: integración aditiva en el servidor vivo

El servidor que corre en Termux y Replit es `redteam/scripts/dashboard_server.py`
(Regla #43). No se reemplaza por un segundo `FastAPI()`: eso perdería cientos
de rutas, autenticación y middleware existentes.

- `POST /api/scan/topology`: conserva `results`, `hosts_up`, `subnet`,
  `local_ip` y `method`, y añade `subnets` cuando se solicitan varias redes.
  Los CIDR se normalizan y deduplican; solo se aceptan redes IPv4 RFC1918.
  Ya no existe el límite rígido de `/24`: cada red puede llegar al límite
  operativo configurable `SOURCESEAL_SCAN_MAX_HOSTS` (65536 por defecto), y
  los rangos grandes usan descubrimiento TCP por lotes para no cargar nmap ni
  miles de conexiones simultáneas. Nunca escanea al montar la War Room.
- `GET/POST /api/scan/cameras`: mantiene `results`, `count` y
  `elapsed_seconds`, incluida la ruta `?target=IP` que usa GeoIntel. Acepta
  `subnets` en query o JSON y devuelve la lista normalizada. El barrido se
  procesa por lotes de hosts y con concurrencia acotada por
  `SOURCESEAL_CAMERA_CONNECTIONS` (48 por defecto). Las sondas envían
  OPTIONS RTSP y una solicitud ONVIF/HTTP de solo lectura; solo clasifican una
  cámara cuando hay evidencia RTSP/ONVIF o una marca/identificador de cámara.
  Un puerto abierto genérico no basta. `target` también debe ser una IP
  RFC1918.
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

## Operación en Termux

La actualización separa la sincronización del arranque y conserva los cambios
locales del operador:

```bash
cd ~/Red-team-tauri
bash omni.sh sync
bash omni.sh restart
bash omni.sh status
```

El dashboard sigue en `:8001`; el portero SOL GATE/SuperGate sigue separado en
`:8012`. No se lanza un segundo servidor FastAPI ni se publica `:8012`.
Abre la War Room y pulsa el botón de escaneo de forma manual. En el campo
`CIDR(s), opcional` se pueden introducir varias redes separadas por espacios,
comas o punto y coma, por ejemplo:

```text
192.168.1.0/24 10.20.0.0/16
```

Para un Moto se puede reducir la presión sin cambiar el alcance autorizado:

```bash
export SOURCESEAL_CAMERA_CONNECTIONS=24
export SOURCESEAL_CAMERA_HOST_BATCH=24
```

No aumentes `SOURCESEAL_SCAN_MAX_HOSTS` sin autorización operativa. El
middleware y la autenticación existentes siguen aplicándose a todas las rutas;
estas variables solo controlan recursos, no autorizan redes públicas ni
desactivan SOL GATE.
