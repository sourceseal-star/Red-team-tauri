#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# RED TEAM ENTERPRISE — Quickstart para Termux
# Ejecuta esto UNA vez y queda todo listo:
#
#   pkg install git -y
#   git clone https://github.com/sourceseal-star/Red-team.git
#   cd Red-team/redteam
#   bash scripts/termux_quickstart.sh
#
# ============================================================
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  RED TEAM ENTERPRISE — Quickstart Termux     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Paquetes del sistema
echo "[1/6] Instalando paquetes..."
pkg update -y 2>/dev/null || true
pkg install -y python git openssl curl termux-api 2>/dev/null || true

# 2. Python deps
echo "[2/6] Instalando dependencias Python..."
pip install --upgrade pip 2>/dev/null || true
pip install requests pycryptodome pyOpenSSL pytz 2>/dev/null || true
pip install stix2 2>/dev/null || echo "  stix2 opcional — sin bundle STIX"

# 3. Directorios
echo "[3/6] Preparando directorios..."
mkdir -p reports evidence
[ ! -f evidence/dummy.apk ] && echo "PK" > evidence/dummy.apk

# 4. Verificar imports
echo "[4/6] Verificando módulos..."
python3 -c "
import sys; sys.path.insert(0, '.')
mods = [
    ('RASP', 'rasp.agent', 'RASPAgent'),
    ('NDR', 'ndr.engine', 'NDREngine'),
    ('ZTNA', 'ztna.gateway', 'ZTNAGateway'),
    ('XDR', 'xdr.correlator', 'XDRCorrelator'),
    ('SOAR', 'soar.engine', 'SOAREngine'),
    ('Deception', 'deception.mesh', 'DeceptionMesh'),
    ('TLS Proxy', 'tlsproxy.interceptor', 'TLSProxy'),
    ('TIP', 'tip.platform', 'ThreatIntelPlatform'),
    ('Integrity', 'integrity.seal_manager', 'SealManager'),
]
ok = 0
for name, mod, cls in mods:
    try:
        m = __import__(mod, fromlist=[cls])
        getattr(m, cls)
        print(f'  ✅ {name}')
        ok += 1
    except Exception as e:
        print(f'  ❌ {name}: {e}')
print(f'\n  {ok}/{len(mods)} módulos OK')
"

# 5. Sellar el sistema
echo ""
echo "[5/6] Sellando archivos críticos..."
python3 scripts/termux_run.py seal 2>&1 | grep -E "sellados|protegidos|🔒"

# 6. Tests enterprise
echo ""
echo "[6/6] Ejecutando tests enterprise..."
python3 tests/test_enterprise.py 2>&1

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅ INSTALACIÓN COMPLETA                      ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║  Comandos para usar:                         ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py verify         ║"
echo "║    → Verificar que nadie modificó nada       ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py status        ║"
echo "║    → Estado de todos los módulos             ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py ztna          ║"
echo "║    → Test ZTNA (permisos y bloqueos)         ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py rasp          ║"
echo "║    → Test RASP (atestación de dispositivo)   ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py ndr           ║"
echo "║    → Test NDR (detecta C2 beaconing + DNS)   ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py deception      ║"
echo "║    → Test Deception Mesh (honeypots)         ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py scan          ║"
echo "║    → Scan enterprise completo (7 módulos)    ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py dashboard     ║"
echo "║    → Dashboard web en localhost:8000         ║"
echo "║                                              ║"
echo "║  python3 scripts/termux_run.py seal          ║"
echo "║    → Re-sellar después de cambios (git pull) ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
