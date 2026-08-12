#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# TRIAGE KIT v1.0 -- Auditoria de dispositivo Android via Termux
# Detecta signos de compromiso: spyware, implants, vigilancia
# Sin root. Solo herramientas disponibles en Termux.
# =====================================================================
set -e

REPORT_DIR="$HOME/triage-reports"
REPORT_FILE="$REPORT_DIR/report-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$REPORT_DIR"

echo "============================================================"
echo "  TRIAGE KIT v1.0 -- Dispositivo: $(getprop ro.product.model)"
echo "  Fecha: $(date)"
echo "  Usuario: $(whoami)"
echo "============================================================"

exec > >(tee "$REPORT_FILE") 2>&1

echo ""
echo "+============================================================+"
echo "|  SECCION 1: PROCESOS SOSPECHOSOS                         |"
echo "+============================================================+"

# Procesos que consumen CPU constantemente (posible implant)
echo "[+] Top 15 procesos por uso de CPU:"
ps -eo pid,ppid,%cpu,%mem,args 2>/dev/null | sort -k3 -rn | head -15 || echo "    (ps no disponible)"

echo ""
echo "[+] Procesos sin nombre legible o con nombres genericos:"
ps -eo args 2>/dev/null | grep -E "^[a-z]{1,4}$|^[0-9]+$|\.tmp$|\.bin$" | head -10 || echo "    Ninguno detectado"

echo ""
echo "[+] Procesos del sistema con acceso a internet:"
for pid in $(ls /proc 2>/dev/null | grep -E "^[0-9]+$" | head -50); do
    if [ -f "/proc/$pid/net/tcp" ] 2>/dev/null; then
        conns=$(wc -l < "/proc/$pid/net/tcp" 2>/dev/null)
        if [ "$conns" -gt 2 ]; then
            cmdline=$(cat "/proc/$pid/cmdline" 2>/dev/null | tr '\0' ' ' | head -c 60)
            echo "    PID $pid ($cmdline) -- $conns conexiones"
        fi
    fi
done

echo ""
echo "+============================================================+"
echo "|  SECCION 2: CONEXIONES DE RED ACTIVAS                    |"
echo "+============================================================+"

echo "[+] Conexiones TCP/UDP establecidas:"
if command -v ss >/dev/null 2>&1; then
    ss -tunap 2>/dev/null | grep ESTAB | head -20 || echo "    Ninguna activa"
elif command -v netstat >/dev/null 2>&1; then
    netstat -tunap 2>/dev/null | grep ESTABLISHED | head -20 || echo "    Ninguna activa"
else
    echo "    (ni ss ni netstat disponibles)"
fi

echo ""
echo "[+] Interfaces de red activas:"
ip addr show 2>/dev/null | grep -E "inet |UP|DOWN" || ifconfig 2>/dev/null | grep -E "inet |UP|DOWN" || echo "    No disponible"

echo ""
echo "[+] Tabla de rutas (posible VPN o redireccion):"
ip route 2>/dev/null | head -10 || echo "    No disponible"

echo ""
echo "+============================================================+"
echo "|  SECCION 3: TEMPERATURA Y BATERIA                        |"
echo "+============================================================+"

echo "[+] Temperatura del dispositivo:"
for zone in /sys/class/thermal/thermal_zone*/temp; do
    if [ -f "$zone" ]; then
        temp_raw=$(cat "$zone" 2>/dev/null)
        type=$(cat "${zone%/*}/type" 2>/dev/null || echo "unknown")
        if [ -n "$temp_raw" ] && [ "$temp_raw" != "0" ]; then
            temp_c=$((temp_raw / 1000))
            echo "    $type: ${temp_c} deg C"
        fi
    fi
done

echo ""
echo "[+] Estado de bateria:"
if [ -f /sys/class/power_supply/battery/capacity ]; then
    echo "    Nivel: $(cat /sys/class/power_supply/battery/capacity 2>/dev/null)%"
fi
if [ -f /sys/class/power_supply/battery/status ]; then
    echo "    Estado: $(cat /sys/class/power_supply/battery/status 2>/dev/null)"
fi
if [ -f /sys/class/power_supply/battery/current_now ]; then
    current=$(cat /sys/class/power_supply/battery/current_now 2>/dev/null)
    if [ -n "$current" ] && [ "$current" != "0" ]; then
        echo "    Corriente: ${current} uA (negativo=descargando)"
    fi
fi

echo ""
echo "+============================================================+"
echo "|  SECCION 4: APPS Y PERMISOS SOSPECHOSOS                  |"
echo "+============================================================+"

echo "[+] Lista de paquetes instalados (primeros 30):"
if command -v pm >/dev/null 2>&1; then
    pm list packages 2>/dev/null | head -30 || echo "    pm no disponible"
else
    echo "    (pm no disponible sin root/shell de sistema)"
fi

echo ""
echo "[+] Apps con permiso de administrador de dispositivo:"
if command -v dpm >/dev/null 2>&1; then
    dpm list-active-admins 2>/dev/null || echo "    Ninguna o no disponible"
else
    echo "    (dpm no disponible)"
fi

echo ""
echo "[+] Servicios en ejecucion (primeros 30):"
if command -v am >/dev/null 2>&1; then
    am list running-services 2>/dev/null | head -30 || echo "    No disponible"
else
    echo "    (am no disponible)"
fi

echo ""
echo "+============================================================+"
echo "|  SECCION 5: ARCHIVOS RECIENTES Y DIRECTORIOS             |"
echo "+============================================================+"

echo "[+] Archivos modificados en las ultimas 24h en /sdcard:"
find /sdcard -mtime -1 -type f 2>/dev/null | head -20 || echo "    Ninguno o sin permiso"

echo ""
echo "[+] Archivos recientes en directorios de apps sospechosas:"
for dir in /data/data/com.* /data/data/android.*; do
    if [ -d "$dir" ]; then
        recent=$(find "$dir" -mtime -1 -type f 2>/dev/null | head -5)
        if [ -n "$recent" ]; then
            echo "    $dir:"
            echo "$recent" | sed 's/^/      /'
        fi
    fi
done 2>/dev/null | head -40

echo ""
echo "[+] Archivos ocultos en home de Termux:"
ls -la "$HOME" 2>/dev/null | grep "^\." | head -20 || echo "    Ninguno"

echo ""
echo "+============================================================+"
echo "|  SECCION 6: INFORMACION DEL SISTEMA                      |"
echo "+============================================================+"

echo "[+] Propiedades del sistema (filtradas):"
getprop | grep -E "ro.product|ro.build|ro.bootloader|ro.hardware|persist" | head -20 || echo "    No disponible"

echo ""
echo "[+] Kernel y version de Android:"
echo "    Kernel: $(uname -r 2>/dev/null || echo 'N/A')"
echo "    Android: $(getprop ro.build.version.release 2>/dev/null || echo 'N/A')"
echo "    SDK: $(getprop ro.build.version.sdk 2>/dev/null || echo 'N/A')"

echo ""
echo "[+] SELinux estado:"
getenforce 2>/dev/null || echo "    No disponible"

echo ""
echo "[+] Usuarios y grupos:"
id 2>/dev/null || echo "    No disponible"

echo ""
echo "+============================================================+"
echo "|  SECCION 7: INDICADORES DE COMPROMISO (IOCs)             |"
echo "+============================================================+"

echo "[+] Buscando nombres de procesos conocidos de spyware comercial:"
SPYWARE_PATTERNS="mSpy|FlexiSpy|Hoverwatch|Cerberus|Spyera|Highster|TruthSpy|Spyzie|Cocospy|uMobix|XNSpy|iKeyMonitor|Mobistealth|TeenSafe|PhoneSheriff|Pegasus|NSO|FinSpy|HackingTeam|RCS|Candiru|Sourgum|DevilsTongue"
ps -eo args 2>/dev/null | grep -iE "$SPYWARE_PATTERNS" | head -10 || echo "    Ninguno detectado"

echo ""
echo "[+] Buscando archivos relacionados con spyware:"
find /sdcard /data/local/tmp /data/data 2>/dev/null | grep -iE "spy|track|monitor|keylog|screenrec|screenshot|callrec" | head -15 || echo "    Ninguno detectado"

echo ""
echo "[+] Verificando acceso root (el dispositivo no deberia estar rooteado):"
if [ -f /system/bin/su ] || [ -f /system/xbin/su ] || [ -f /sbin/su ] || [ -f /su/bin/su ]; then
    echo "    ??  ARCHIVO SU DETECTADO -- El dispositivo podria estar rooteado o tener root escondido"
else
    echo "    No se detecto acceso root (bueno para stealth, malo para auditoria profunda)"
fi

echo ""
echo "+============================================================+"
echo "|  SECCION 8: REDES WIFI Y BLUETOOTH                       |"
echo "+============================================================+"

echo "[+] Redes WiFi guardadas:"
if [ -f /data/misc/wifi/wpa_supplicant.conf ]; then
    grep -E "ssid|psk" /data/misc/wifi/wpa_supplicant.conf 2>/dev/null | head -10 || echo "    No disponible"
else
    echo "    (requiere root para leer wpa_supplicant.conf)"
fi

echo ""
echo "[+] Estado WiFi actual:"
dumpsys wifi 2>/dev/null | grep -E "mWifiInfo|SSID|BSSID|ipaddress" | head -10 || echo "    No disponible"

echo ""
echo "============================================================"
echo "  REPORTE GUARDADO EN: $REPORT_FILE"
echo "============================================================"
echo ""
echo "INTERPRETACION RAPIDA:"
echo "  ? Temperatura > 45 deg C en reposo = posible actividad oculta"
echo "  ? Corriente de bateria muy negativa en standby = posible beacon"
echo "  ? Procesos sin nombre + conexiones = MUY SOSPECHOSO"
echo "  ? Apps con admin de dispositivo que no reconoces = REVISAR"
echo "  ? Archivos .apk recientes desconocidos = posible sideload"
echo ""
echo "Si encuentras algo sospechoso: NO LO BORRES. Documentalo."
echo "Borrar destruye evidencia. Documentar preserva la verdad."
echo ""
