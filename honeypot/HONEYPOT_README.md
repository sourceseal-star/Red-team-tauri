# 🐝 SourceSeal Honeypot

Honeypot HTTP funcional para captura y análisis de ataques reales contra sourceseal.co.

## Inicio rápido

```bash
cd honeypot
npm install
node start-honeypot.js
```

Output:
```
[HONEYPOT] ✅ Active! Token: ss_hp_a1b2c3d4_1234567890
[HONEYPOT] Listening on port 8080
[HONEYPOT] Capturing attacks in real-time...

━━━ READY TO USE IN TERMUX ━━━
curl http://localhost:8080/api/honeypot/status
curl "http://localhost:8080/api/honeypot/attacks?token=ss_hp_a1b2c3d4_1234567890"
curl "http://localhost:8080/api/honeypot/attacks/export?format=csv&token=ss_hp_a1b2c3d4_1234567890" > attacks.csv
curl "http://localhost:8080/api/honeypot/stats?token=ss_hp_a1b2c3d4_1234567890"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/honeypot/activate` | Activa honeypot, genera token |
| POST | `/api/honeypot/deactivate` | Desactiva honeypot |
| GET | `/api/honeypot/status` | Estado actual |
| GET | `/api/honeypot/attacks?token=XXX` | Últimos ataques |
| GET | `/api/honeypot/attacks/top-ips?hours=24` | IPs más activas |
| GET | `/api/honeypot/attacks/export?format=csv` | Exportar CSV/JSON/TXT |
| GET | `/api/honeypot/stats?token=XXX` | Estadísticas completas |
| GET | `/api/honeypot/attacks/by-country` | Distribución geográfica |
| DELETE | `/api/honeypot/attacks?token=XXX` | Limpiar ataques |
| GET | `/api/honeypot/docs` | Documentación automática |

## Clasificación de severidad

| Nivel | Patrones |
|-------|----------|
| 🔴 CRITICAL | /admin, /.env, /.git, /backup, /phpmyadmin, /shell |
| 🟠 HIGH | SQL injection, XSS, path traversal, RCE |
| 🟡 MEDIUM | Reconocimiento (wp-login, scanners) |
| 🟢 LOW | Probes genéricos |

## Endpoints falsos (atraen atacantes)

- `/admin/login`
- `/wp-login.php`
- `/phpmyadmin`
- `/.env`
- `/.git/config`
- `/api/v1/users`
- `/backup.sql`
- `/robots.txt`

## Base de datos

SQLite en `data/honeypot.db`:
- Tabla `honeypot_attacks` con índices en IP, token, timestamp, severity
- Persistente entre reinicios
- Exportable a CSV/JSON/TXT

## GeoIP

- Primario: `geoip-lite` (offline, instalar con `npm install geoip-lite`)
- Fallback: `ipapi.co` (API gratuita, sin API key)
- Cache de 1 hora por IP

## WebSocket (tiempo real)

```javascript
const socket = io('http://localhost:8080');
socket.on('honeypot.attack', (attack) => {
  console.log(`ATAQUE! ${attack.ip} → ${attack.path} [${attack.severity}]`);
});
```

## Comandos Termux

```bash
# Activar
curl -X POST http://sourceseal.co:8080/api/honeypot/activate

# Ver estado
curl http://sourceseal.co:8080/api/honeypot/status

# Ver últimos 50 ataques
curl "http://sourceseal.co:8080/api/honeypot/attacks?token=ss_hp_XXX&limit=50" | jq .

# Top IPs en últimas 24h
curl "http://sourceseal.co:8080/api/honeypot/attacks/top-ips?hours=24" | jq .

# Exportar a CSV
curl "http://sourceseal.co:8080/api/honeypot/attacks/export?format=csv&token=ss_hp_XXX" > attacks.csv

# Analizar en Termux
cat attacks.csv | grep "192.168" | sort | uniq -c | sort -rn

# Estadísticas
curl "http://sourceseal.co:8080/api/honeypot/stats?token=ss_hp_XXX" | jq .

# Por país
curl "http://sourceseal.co:8080/api/honeypot/attacks/by-country?token=ss_hp_XXX" | jq .

# Limpiar
curl -X DELETE "http://sourceseal.co:8080/api/honeypot/attacks?token=ss_hp_XXX"

# Documentación
curl http://sourceseal.co:8080/api/honeypot/docs | jq .
```

## Arquitectura

```
start-honeypot.js (Express + Socket.io)
├── src/honeypot/server.js    (HTTP honeypot en :8080)
├── src/honeypot/database.js  (SQLite operations)
├── src/api/routes.js        (REST API endpoints)
├── src/utils/geoip.js       (Geolocalización)
└── src/utils/classifier.js  (Severidad automática)
```

## Dependencias

```bash
npm install express socket.io sqlite3 uuid cors helmet
npm install geoip-lite  # Opcional, para GeoIP offline
```
