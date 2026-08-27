#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# RECON.SH — Reconocimiento, reconexión y registro de dispositivos
# Busca dispositivos en la red, compara con los conocidos, y permite
# reconectar o registrar nuevos. También revisa usuarios del Motor.
#
# Uso:
#   bash recon.sh                # escaneo completo (known + new + status)
#   bash recon.sh --scan          # solo escanear red, mostrar tabla
#   bash recon.sh --known        # solo listar dispositivos registrados
#   bash recon.sh --users        # listar usuarios/leads del Motor de Cierre
#   bash recon.sh --reconnect    # intentar reconectar dispositivos caídos
#   bash recon.sh --register IP  # registrar un dispositivo nuevo
#   bash recon.sh --cameras      # listar cámaras y streams RTSP activos
#   bash recon.sh --all          # todo lo anterior
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

DATA_DIR="$ROOT/redteam/scripts/data"
DEVICES_FILE="$DATA_DIR/rasp_devices.json"
MOTOR_DB="$ROOT/motor_cierre/backend/motor_cierre.db"

# Colors
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'
BOLD='\033[1m'

DASH_URL="http://127.0.0.1:8001"
MOTOR_URL="http://127.0.0.1:8000"

# ── HELPERS ──────────────────────────────────────────────────────
header() {
    echo ""
    echo -e "${B}╔══════════════════════════════════════════════╗${N}"
    echo -e "${B}║  $1${N}"
    echo -e "${B}╚══════════════════════════════════════════════╝${N}"
}

# Detect local IP range
get_local_subnet() {
    if command -v ip >/dev/null 2>&1; then
        LOCAL_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
    fi
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
    fi
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="192.168.1.100"
    fi
    SUBNET=$(echo "$LOCAL_IP" | cut -d. -f1-3)
    echo "${SUBNET}.0/24"
}

# Ping sweep a la red local
ping_sweep() {
    local subnet=$(echo "$1" | cut -d/ -f1 | cut -d. -f1-3)
    echo -e "${C}Escaneando ${subnet}.1-254...${N}"
    local found=""
    for i in $(seq 1 254); do
        ip="${subnet}.${i}"
        if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
            echo "$ip"
        fi
    done
}

# ── 1. DISPOSITIVOS CONOCIDOS ─────────────────────────────────────
show_known() {
    header "DISPOSITIVOS REGISTRADOS"
    if [ ! -f "$DEVICES_FILE" ] || [ ! -s "$DEVICES_FILE" ]; then
        echo -e "  ${Y}No hay dispositivos registrados aún.${N}"
        echo -e "  Usa: bash recon.sh --register <IP> para registrar uno nuevo"
        return
    fi

    python3 -c "
import json, sys
with open('$DEVICES_FILE') as f:
    devices = json.load(f)
if not devices:
    print('  No hay dispositivos registrados.')
    sys.exit(0)
print(f'  Total: {len(devices)} dispositivo(s)\n')
print(f'  {\"#\":<4} {\"IP\":<16} {\"Tipo\":<14} {\"Nombre\":<20} {\"Estado\"}')
print(f'  {\"─\"*4} {\"─\"*16} {\"─\"*14} {\"─\"*20} {\"─\"*10}')
for i, d in enumerate(devices):
    ip = d.get('ip', d.get('address', '?'))
    dtype = d.get('type', d.get('device_type', '?'))
    name = d.get('name', d.get('hostname', '?'))
    status = d.get('status', 'unknown')
    print(f'  {i+1:<4} {ip:<16} {dtype:<14} {name:<20} {status}')
"
}

# ── 2. ESCANEAR RED ──────────────────────────────────────────────
scan_network() {
    header "ESCANEO DE RED LOCAL"
    local subnet=$(get_local_subnet)
    echo -e "  Red local: ${C}$subnet${N}"
    echo ""

    # Intentar usar el endpoint del dashboard primero
    local dash_resp
    dash_resp=$(curl -s -m 10 "$DASH_URL/api/scan" -X POST -H "Content-Type: application/json" -d "{\"target\": \"$subnet\", \"scan_type\": \"quick\"}" 2>/dev/null || echo "")

    if [ -n "$dash_resp" ] && echo "$dash_resp" | python3 -c "import sys,json;json.load(sys.stdin)" 2>/dev/null; then
        echo -e "  ${G}Vía Dashboard API (:8001)${N}"
        echo "$dash_resp" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if 'devices' in data:
        for d in data['devices']:
            ip = d.get('ip', '?')
            dtype = d.get('type', d.get('device_type', '?'))
            name = d.get('hostname', d.get('name', '?'))
            vendor = d.get('vendor', '')
            print(f'  {ip:<16} {dtype:<14} {name:<20} {vendor}')
    elif 'hosts' in data:
        for h in data['hosts']:
            print(f'  {h}')
    else:
        print(json.dumps(data, indent=2)[:500])
except:
    print('  (respuesta no parseable)')
"
    else
        echo -e "  ${Y}Dashboard no responde — fallback a ping sweep${N}"
        echo ""
        ping_sweep "$subnet" | while read -r ip; do
            # Intentar identificar el dispositivo
            hostname=$(ping -c 1 -W 1 "$ip" 2>/dev/null | grep -oP '(?<=from ).*?(?=:)' | head -1)
            echo -e "  ${G}●${N} $ip  ${C}${hostname:-?}${N}"
        done
    fi

    echo ""
    echo -e "  Para registrar uno nuevo: bash recon.sh --register <IP>"
}

# ── 3. RECONectar dispositivos caídos ───────────────────────────
reconnect_all() {
    header "RECONEXIÓN DE DISPOSITIVOS"
    if [ ! -f "$DEVICES_FILE" ] || [ ! -s "$DEVICES_FILE" ]; then
        echo -e "  ${Y}No hay dispositivos registrados para reconectar.${N}"
        return
    fi

    python3 -c "
import json, subprocess, sys
with open('$DEVICES_FILE') as f:
    devices = json.load(f)
if not devices:
    print('  Sin dispositivos registrados.')
    sys.exit(0)
print(f'  Revisando {len(devices)} dispositivo(s)...\n')
for d in devices:
    ip = d.get('ip', d.get('address', ''))
    name = d.get('name', d.get('hostname', '?'))
    dtype = d.get('type', d.get('device_type', '?'))
    port = d.get('port', 80)
    if not ip:
        continue
    # Ping check
    ping_ok = subprocess.run(['ping', '-c', '1', '-W', '1', ip], capture_output=True)
    online = ping_ok.returncode == 0
    # Port check
    port_ok = False
    if online:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        try:
            s.connect((ip, int(port)))
            port_ok = True
        except:
            port_ok = False
        finally:
            s.close()
    status = 'ONLINE' if online else 'OFFLINE'
    port_status = f':{port} OK' if port_ok else f':{port} CLOSED'
    icon = '✓' if online else '✗'
    color = '\033[32m' if online else '\033[31m'
    reset = '\033[0m'
    print(f'  {color}{icon}{reset} {ip:<16} {name:<20} {dtype:<14} {status:<8} {port_status}')
    if not online:
        print(f'     → Sin respuesta de {ip}. Verifica que el dispositivo esté encendido y en la misma red.')
    elif not port_ok:
        print(f'     → Responde a ping pero puerto {port} cerrado. ¿Servicio caído?')
"
}

# ── 4. REGISTRAR DISPOSITIVO NUEVO ───────────────────────────────
register_device() {
    local ip="$1"
    if [ -z "$ip" ]; then
        echo -e "${R}Uso: bash recon.sh --register <IP>${N}"
        exit 1
    fi

    header "REGISTRAR DISPOSITIVO: $ip"

    # Detectar tipo de dispositivo
    echo -e "  ${C}Probando $ip...${N}"

    local dtype="unknown"
    local name=""
    local port=""

    # Probar puertos comunes
    for p in 80 443 554 8000 8080 8001 8888 22 23; do
        if echo -n "" | timeout 2 bash -c "echo > /dev/tcp/$ip/$p" 2>/dev/null; then
            port="$p"
            case $p in
                554)  dtype="camera_rtsp"; name="Camara-RTSP" ;;
                80|8080|8888) dtype="web_device"; name="Device-Web" ;;
                8000) dtype="motor_cierre"; name="Motor-Cierre" ;;
                8001) dtype="dashboard"; name="Dashboard" ;;
                443)  dtype="web_device_tls"; name="Device-TLS" ;;
                22)   dtype="ssh_host"; name="Host-SSH" ;;
                23)   dtype="telnet_host"; name="Host-Telnet" ;;
            esac
            echo -e "  ${G}✓${N} Puerto $p abierto → tipo: $dtype"
            break
        fi
    done

    if [ -z "$port" ]; then
        echo -e "  ${Y}⚠ Sin puertos abiertos conocidos. Registrar como genérico.${N}"
        dtype="generic"
        name="Device-Generic"
        port="0"
    fi

    # Ping check
    if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
        echo -e "  ${G}✓ Responde a ping${N}"
    else
        echo -e "  ${R}✗ No responde a ping — ¿está en la misma red?${N}"
        read -p "  ¿Registrar de todos modos? (s/n): " confirm
        [ "$confirm" != "s" ] && exit 0
    fi

    # Intentar hostname
    hostname=$(ping -c 1 -W 1 "$ip" 2>/dev/null | grep -oP '(?<=from ).*?(?=\s*\()' | head -1)
    [ -n "$hostname" ] && name="$hostname"

    # Guardar en rasp_devices.json
    python3 -c "
import json, os
path = '$DEVICES_FILE'
os.makedirs(os.path.dirname(path), exist_ok=True)
devices = []
if os.path.exists(path):
    with open(path) as f:
        try: devices = json.load(f)
        except: devices = []
# Verificar si ya existe
for d in devices:
    if d.get('ip') == '$ip' or d.get('address') == '$ip':
        print(f'  Ya estaba registrado: {d.get(\"name\", \"?\")}')
        exit(0)
devices.append({
    'ip': '$ip',
    'type': '$dtype',
    'name': '$name',
    'port': int('$port'),
    'status': 'registered',
    'registered_at': __import__('datetime').datetime.now().isoformat()
})
with open(path, 'w') as f:
    json.dump(devices, f, indent=2, default=str)
print(f'  Registrado: $ip ($dtype) → $name')
print(f'  Total dispositivos: {len(devices)}')
"

    # También intentar registrar vía API del dashboard
    curl -s -m 5 "$DASH_URL/api/rasp/devices" -X POST \
        -H "Content-Type: application/json" \
        -d "{\"ip\": \"$ip\", \"type\": \"$dtype\", \"name\": \"$name\"}" >/dev/null 2>&1 && \
        echo -e "  ${G}✓ También registrado en el dashboard${N}" || true
}

# ── 5. USUARIOS / LEADS del Motor de Cierre ──────────────────────
show_users() {
    header "USUARIOS / LEADS — MOTOR DE CIERRE"

    # Intentar vía API primero
    local resp
    resp=$(curl -s -m 5 "$MOTOR_URL/leads" 2>/dev/null || echo "")
    if [ -n "$resp" ] && echo "$resp" | python3 -c "import sys,json;json.load(sys.stdin)" 2>/dev/null; then
        echo -e "  ${G}Vía Motor API (:8000)${N}"
        echo "$resp" | python3 -c "
import json, sys
data = json.load(sys.stdin)
leads = data if isinstance(data, list) else data.get('leads', data.get('data', []))
if not leads:
    print('  Sin usuarios registrados.')
    sys.exit(0)
print(f'  Total: {len(leads)} usuario(s)\n')
print(f'  {\"Email\":<30} {\"Empresa\":<20} {\"Producto\":<12} {\"Última actualización\"}')
print(f'  {\"─\"*30} {\"─\"*20} {\"─\"*12} {\"─\"*20}')
for l in leads:
    email = l.get('email', '?')
    company = l.get('company', '-')
    product = l.get('product_id', '-')
    updated = l.get('updated_at', '?')[:19]
    print(f'  {email:<30} {company:<20} {product:<12} {updated}')
"
    elif [ -f "$MOTOR_DB" ]; then
        echo -e "  ${Y}Motor API no responde — leyendo SQLite directo${N}"
        python3 -c "
import sqlite3, os
db = '$MOTOR_DB'
if not os.path.exists(db):
    print('  BD no encontrada.')
    exit(0)
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute('SELECT email, company, domain, source, product_id, updated_at FROM leads ORDER BY updated_at DESC').fetchall()
except:
    print('  No se pudo leer la tabla leads.')
    exit(0)
if not rows:
    print('  Sin usuarios registrados.')
else:
    print(f'  Total: {len(rows)} usuario(s)\n')
    print(f'  {\"Email\":<30} {\"Empresa\":<20} {\"Producto\":<12} {\"Última actualización\"}')
    print(f'  {\"─\"*30} {\"─\"*20} {\"─\"*12} {\"─\"*20}')
    for r in rows:
        print(f'  {r[\"email\"]:<30} {r[\"company\"] or \"-\":<20} {r[\"product_id\"] or \"-\":<12} {(r[\"updated_at\"] or \"?\")[:19]}')
conn.close()
"
    else
        echo -e "  ${R}Motor de Cierre no está corriendo y no se encontró la BD.${N}"
        echo -e "  Arranca con: bash update.sh --all && bash update.sh --watch"
    fi
}

# ── 6. CÁMARAS Y STREAMS ACTIVOS ────────────────────────────────
show_cameras() {
    header "CÁMARAS Y STREAMS"

    # RTSP activos
    local resp
    resp=$(curl -s -m 5 "$DASH_URL/api/iot/rtsp-active" 2>/dev/null || echo "")
    if [ -n "$resp" ] && echo "$resp" | python3 -c "import sys,json;json.load(sys.stdin)" 2>/dev/null; then
        echo -e "  ${G}Streams RTSP activos:${N}"
        echo "$resp" | python3 -c "
import json, sys
data = json.load(sys.stdin)
sessions = data if isinstance(data, list) else data.get('sessions', data.get('data', []))
if not sessions:
    print('  Sin streams activos.')
else:
    for s in sessions:
        sid = s.get('session_id', '?')
        url = s.get('rtsp_url', s.get('url', '?'))
        status = s.get('status', '?')
        print(f'  {sid:<12} {url:<40} {status}')
"
    else
        echo -e "  ${Y}Dashboard no responde para RTSP activos.${N}"
    fi

    echo ""

    # Cámaras conocidas en devices
    if [ -f "$DEVICES_FILE" ]; then
        echo -e "  ${C}Cámaras registradas:${N}"
        python3 -c "
import json
with open('$DEVICES_FILE') as f:
    devices = json.load(f)
cams = [d for d in devices if 'camera' in str(d.get('type', '')).lower() or 'rtsp' in str(d.get('type', '')).lower()]
if not cams:
    print('  Sin cámaras registradas.')
else:
    for c in cams:
        ip = c.get('ip', '?')
        name = c.get('name', '?')
        port = c.get('port', 554)
        print(f'  {ip:<16} {name:<20} :{port}')
"
    fi
}

# ── 7. ESTADO GENERAL DEL SISTEMA ────────────────────────────────
system_status() {
    header "ESTADO DEL SISTEMA"

    # Servicios
    for svc in "Dashboard:8001:dashboard_server.py" "Motor:8000:uvicorn.*main:app.*8000" "Vite:5173:vite"; do
        name=$(echo "$svc" | cut -d: -f1)
        port=$(echo "$svc" | cut -d: -f2)
        pattern=$(echo "$svc" | cut -d: -f3)
        if pgrep -f "$pattern" >/dev/null 2>&1; then
            echo -e "  ${G}✓${N} $name (:$port) — corriendo"
        else
            echo -e "  ${R}✗${N} $name (:$port) — detenido"
        fi
    done

    echo ""

    # Conectividad
    local subnet
    subnet=$(get_local_subnet)
    echo -e "  Red local: ${C}$subnet${N}"

    local online_count=0
    for i in $(seq 1 254); do
        ping -c 1 -W 1 "$(echo $subnet | cut -d/ -f1 | cut -d. -f1-3).$i" >/dev/null 2>&1 && online_count=$((online_count + 1))
    done
    echo -e "  Dispositivos en red: ${G}$online_count${N} activos de 254"
}

# ── MAIN ─────────────────────────────────────────────────────────
MODE="${1:-all}"
[ -z "$1" ] && MODE="all"

case "$1" in
    --scan)       scan_network ;;
    --known)      show_known ;;
    --users)      show_users ;;
    --reconnect)  reconnect_all ;;
    --register)   register_device "$2" ;;
    --cameras)    show_cameras ;;
    --status)     system_status ;;
    --all)
        system_status
        show_known
        scan_network
        reconnect_all
        show_cameras
        show_users
        ;;
    --help|-h|"")
        echo "Uso: bash recon.sh [modo]"
        echo ""
        echo "  (sin args)  --all  → estado + known + scan + reconnect + cameras + users"
        echo "  --scan       Escanea la red local y muestra dispositivos encontrados"
        echo "  --known      Lista dispositivos previamente registrados"
        echo "  --users      Lista usuarios/leads del Motor de Cierre"
        echo "  --reconnect  Verifica y reconecta dispositivos registrados"
        echo "  --register IP  Registra un dispositivo nuevo por IP"
        echo "  --cameras    Muestra cámaras y streams RTSP activos"
        echo "  --status     Estado general del sistema y servicios"
        echo ""
        ;;
    *)
        echo "Opción no reconocida: $1"
        echo " Usa: bash recon.sh --help"
        exit 1
        ;;
esac

echo ""
echo -e "${B}══════════════════════════════════════════════${N}"
echo ""
