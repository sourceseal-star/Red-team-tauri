# SourceSeal Console — Guía de Arranque Rápido
# Moto Edge 50 Fusion + Termux

## ━━━━ PASO 1: Configurar API Keys (una sola vez) ━━━━

### AbuseIPDB (gratis — reputación de IPs)
1. Ve a https://www.abuseipdb.com/account/api
2. Regístrate (gratis) o inicia sesión
3. Copia tu API key
4. En Termux:
   ```bash
   cd ~/Red-team-tauri
   echo 'ABUSEIPDB_KEY=tu-key-aqui' >> .env
   ```

### Shodan (gratis — puertos, servicios, vulnerabilidades)
1. Ve a https://www.shodan.io/dashboard
2. Crea cuenta gratis
3. Copia tu API key
4. En Termux:
   ```bash
   echo 'SHODAN_API_KEY=tu-key-aqui' >> .env
   ```

## ━━━━ PASO 2: Arrancar todo (un comando) ━━━━

```bash
cd ~/Red-team-tauri
bash arrancar.sh
```

Eso hace todo automáticamente:
- git pull (sincroniza)
- Instala deps (python, node, nmap, whois, dig)
- Verifica/crea .env
- Compila frontend
- Levanta backend en puerto 8001
- Muestra tu IP local para acceso desde otros dispositivos

## ━━━━ PASO 3: Abrir el dashboard ━━━━

En Chrome del celular:
```
http://localhost:8001
```

Desde otro dispositivo en la misma WiFi:
```
http://TU_IP_LOCAL:8001
```

## ━━━━ ENDPOINTS PARA INVESTIGAR CCTV ━━━━

### Investigar una IP (due diligence completo)
```bash
curl http://localhost:8001/api/investigate/ip/190.1.2.3
```
Combina: geo + threat intel + abuseipdb + shodan + rdns + blocklist
Devuelve: score de riesgo, veredicto (LIMPIO/MEDIO/ALTO), recomendaciones

### Investigar una cámara específica
```bash
curl http://localhost:8001/api/investigate/camera/190.1.2.3
```
Combina: investigación de IP + marca detectada + puertos + streams + SSL

### Check masivo de IPs
```bash
curl -X POST http://localhost:8001/api/intel/bulk-check \
  -H "Content-Type: application/json" \
  -d '["190.1.2.3","200.5.6.7","190.8.9.10"]'
```

### Geo-localización
```bash
curl http://localhost:8001/api/geo?ip=190.1.2.3
```

### Threat Intel (scoring + blocklist)
```bash
curl http://localhost:8001/api/intel?ip=190.1.2.3
```

### WHOIS de dominio
```bash
curl http://localhost:8001/api/osint/whois/dominio.com
```

### Subdominios (crt.sh + brute force)
```bash
curl http://localhost:8001/api/osint/subdomains/dominio.com?brute=true
```

### Emails asociados a dominio
```bash
curl http://localhost:8001/api/osint/emails/dominio.com
```

### Escanear red CCTV completa
```bash
# Topología de red
curl -X POST http://localhost:8001/api/scan/topology

# Detectar cámaras por RTSP/ONVIF
curl -X POST http://localhost:8001/api/scan/cameras

# Descubrimiento completo (ONVIF + SSDP + mDNS + SNMP)
curl -X POST http://localhost:8001/api/enhanced/discover/all

# Cámaras guardadas en DB
curl http://localhost:8001/api/enhanced/cameras

# Hosts descubiertos
curl http://localhost:8001/api/enhanced/hosts

# Escanear red CIDR específica
curl -X POST http://localhost:8001/api/iot/scan-network \
  -H "Content-Type: application/json" \
  -d '{"cidr":"192.168.1.0/24"}'
```

## ━━━━ EN REPLIT ━━━━

```bash
bash replit_start.sh
```

El backend se levanta en :8001 automáticamente.

## ━━━━ FLUJO DE TRABAJO CCTV ━━━━

1. MONTAR: Conectar cámaras a la red
2. ESCANEAR: POST /api/scan/topology + POST /api/enhanced/discover/all
3. REGISTRAR: GET /api/enhanced/cameras (ver cámaras detectadas)
4. INVESTIGAR: GET /api/investigate/camera/{ip} por cada cámara
5. BLINDAR: Verificar puertos abiertos, cambiar passwords, cerrar RTSP público
6. EVIDENCIA: Documentar con WHOIS + threat intel de cada IP

## ━━━━ SI ALGO FALLA ━━━━

Verificar que el backend está vivo:
```bash
curl http://localhost:8001/api/health
```

Ver logs del backend:
```bash
# Si usaste start_all.sh:
tail -50 backend.log
```

Reinstalar dependencias:
```bash
bash termux_setup.sh
```
