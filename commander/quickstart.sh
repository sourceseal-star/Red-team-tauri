#!/usr/bin/env bash
# =====================================================================
# COMMANDER — Quickstart + Smoke Tests
# Verifica que todo está listo para auditar
# Uso:
#   bash quickstart.sh            # Verificar deps + smoke tests
#   bash quickstart.sh --test-only # Solo tests (sin instalar nada)
# =====================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; N='\033[0m'
PASS=0; FAIL=0; WARN=0

banner() {
  echo ""
  echo -e "${C}════════════════════════════════════════════════════${N}"
  echo -e "${G}  $1${N}"
  echo -e "${C}════════════════════════════════════════════════════${N}"
}
ok()   { echo -e "  ${G}✓${N} $1"; PASS=$((PASS+1)); }
fail() { echo -e "  ${R}✗${N} $1"; FAIL=$((FAIL+1)); }
warn() { echo -e "  ${Y}⚠${N} $1"; WARN=$((WARN+1)); }

TEST_ONLY=0
[ "$1" = "--test-only" ] && TEST_ONLY=1

if [ "$TEST_ONLY" -eq 0 ]; then
  banner "🔱 COMMANDER v3.6.0 — Quickstart"

  # 1. Detectar entorno
  echo -e "${C}[1/4] Detectando entorno...${N}"
  echo -e "  OS: $(uname -s) $(uname -m)"

  if command -v python3 >/dev/null 2>&1; then
    ok "Python: $(python3 --version 2>&1)"
  else
    fail "Python3 no encontrado"
    if command -v pkg >/dev/null 2>&1; then
      warn "Instalando Python..."
      pkg install -y python 2>&1 | tail -2
    else
      echo -e "${R}Instala Python 3.10+ manualmente${N}"
      exit 1
    fi
  fi

  # 2. Dependencias del sistema
  echo -e "${C}[2/4] Verificando dependencias del sistema...${N}"
  if command -v nmap >/dev/null 2>&1; then
    ok "nmap: $(nmap --version 2>&1 | head -1)"
  else
    fail "nmap no encontrado"
    if command -v pkg >/dev/null 2>&1; then
      warn "Instalando nmap..."
      pkg install -y nmap 2>&1 | tail -2
      ok "nmap instalado"
    else
      echo -e "${R}Instala: sudo apt install nmap (Linux) o pkg install nmap (Termux)${N}"
    fi
  fi

  if command -v whois >/dev/null 2>&1; then
    ok "whois: $(whois --version 2>&1 | head -1)"
  else
    warn "whois no encontrado (OSINT limitado)"
    if command -v pkg >/dev/null 2>&1; then
      warn "Instalando whois..."
      pkg install -y whois 2>&1 | tail -2
      ok "whois instalado"
    fi
  fi

  # 3. Permisos de almacenamiento (Termux)
  if command -v termux-setup-storage >/dev/null 2>&1; then
    echo -e "${C}[3/4] Verificando almacenamiento...${N}"
    if [ -d ~/storage/downloads ]; then
      ok "Almacenamiento accesible"
    else
      warn "Ejecuta: termux-setup-storage (y acepta el permiso)"
    fi
  else
    echo -e "${C}[3/4] No es Termux — saltando permisos${N}"
  fi

  # 4. Dependencias Python
  echo -e "${C}[4/4] Verificando dependencias Python...${N}"
  python3 -c "from cryptography.fernet import Fernet" 2>/dev/null && {
    ok "cryptography instalado"
  } || {
    warn "Instalando cryptography..."
    pip install cryptography 2>&1 | tail -3
    python3 -c "from cryptography.fernet import Fernet" 2>/dev/null && ok "cryptography instalado" || fail "cryptography falló"
  }

  python3 -c "import sqlite3" 2>/dev/null && ok "sqlite3 (stdlib) OK" || fail "sqlite3 no disponible"
  python3 -c "import json, hashlib, argparse, logging" 2>/dev/null && ok "stdlib core OK" || fail "stdlib core incompleto"
fi

# ════════════════════════════════════════════════════════════════════
# SMOKE TESTS
# ════════════════════════════════════════════════════════════════════
banner "🔱 Smoke Tests"

echo -e "${B}── CLI ──${N}"
# Test 1: --help
if python3 commander.py --help 2>&1 | grep -q "usage: commander.py"; then
  ok "CLI --help funciona"
else
  fail "CLI --help no responde"
fi

# Test 2: --list (no debe crashear)
OUTPUT=$(python3 commander.py --list 2>&1)
if echo "$OUTPUT" | grep -qE "auditorías|Auditorías|auditor|empty|vacío|pending"; then
  ok "CLI --list funciona"
else
  warn "CLI --list responde pero formato inesperado"
fi

echo ""
echo -e "${B}── Cifrado Fernet ──${N}"
# Test 3: Cifrado/descifrado
if python3 -c "
from cryptography.fernet import Fernet
key = Fernet.generate_key()
f = Fernet(key)
enc = f.encrypt(b'SourceSeal test')
dec = f.decrypt(enc)
assert dec == b'SourceSeal test'
print('OK')
" 2>/dev/null | grep -q "OK"; then
  ok "Cifrado/descifrado Fernet OK"
else
  fail "Cifrado Fernet falló"
fi

echo ""
echo -e "${B}── SQLite ──${N}"
# Test 4: SQLite + checkpoints
if python3 -c "
import sqlite3, json, os
db = os.path.expanduser('~/.commander_tmp/commander_test.db')
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT, scan_type TEXT, timestamp TEXT,
    data_json TEXT, hash TEXT, status TEXT, checkpoint_data TEXT
)''')
c.execute('INSERT INTO audits VALUES (NULL,?,?,?,?,?,?,?)',
    ('192.168.1.0/24', 'test', '2026-01-01T00:00:00Z',
     '{}', 'abc123def', 'running', json.dumps({'phase':'start'})))
conn.commit()
row = c.execute('SELECT id, target, status, checkpoint_data FROM audits').fetchone()
assert row[1] == '192.168.1.0/24'
assert row[2] == 'running'
cp = json.loads(row[3])
assert cp['phase'] == 'start'
print('OK')
conn.close()
os.remove(db)
" 2>/dev/null | grep -q "OK"; then
  ok "SQLite + checkpoints OK"
else
  fail "SQLite falló"
fi

echo ""
echo -e "${B}── Hash SHA-256 ──${N}"
# Test 5: Hash SHA-256
if python3 -c "
import hashlib, json
data = {'network': {'hosts': []}, 'cameras': {'cameras': []}, 'osint': []}
h = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
assert len(h) == 64
assert all(c in '0123456789abcdef' for c in h)
print('OK')
" 2>/dev/null | grep -q "OK"; then
  ok "Hash SHA-256 OK"
else
  fail "Hash SHA-256 falló"
fi

echo ""
echo -e "${B}── Logging dual ──${N}"
# Test 6: Logger (archivo + consola)
if python3 -c "
import logging, sys, os
log = logging.getLogger('TEST')
log.setLevel(logging.INFO)
log.handlers.clear()
fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
ch = logging.StreamHandler(sys.stdout); ch.setFormatter(fmt); log.addHandler(ch)
fh = logging.FileHandler(os.path.expanduser('~/.commander_tmp/commander_test.log'), encoding='utf-8')
fh.setFormatter(fmt); log.addHandler(fh)
log.info('Test message')
assert os.path.exists(os.path.expanduser('~/.commander_tmp/commander_test.log'))
with open(os.path.expanduser('~/.commander_tmp/commander_test.log')) as f:
    assert 'Test message' in f.read()
os.remove(os.path.expanduser('~/.commander_tmp/commander_test.log'))
print('OK')
" 2>/dev/null | grep -q "OK"; then
  ok "Logging dual (consola + archivo) OK"
else
  fail "Logging dual falló"
fi

echo ""
echo -e "${B}── Directorios ──${N}"
# Test 7: Directorios temporales (NO /tmp)
if python3 -c "
import os
from pathlib import Path
temp_dir = os.path.expanduser('~/.commander_tmp')
report_dir = os.path.expanduser('~/storage/downloads/commander_reports')
os.makedirs(temp_dir, exist_ok=True)
assert os.path.isdir(temp_dir)
# report_dir puede no existir en no-Termux, solo verificar que el código no crashee
print('OK')
" 2>/dev/null | grep -q "OK"; then
  ok "Directorios temporales OK (~/.commander_tmp)"
else
  fail "Directorios temporales falló"
fi

echo ""
echo -e "${B}── Red (opcional) ──${N}"
# Test 8: nmap disponible
if command -v nmap >/dev/null 2>&1; then
  ok "nmap disponible para escaneo"
else
  warn "nmap no instalado (escaneo no disponible)"
fi

# Test 9: whois disponible
if command -v whois >/dev/null 2>&1; then
  ok "whois disponible para OSINT"
else
  warn "whois no instalado (OSINT limitado)"
fi

# Test 10: ip-api.com reachable
if python3 -c "
import urllib.request, json
try:
    req = urllib.request.urlopen('http://ip-api.com/json/8.8.8.8?fields=status', timeout=5)
    data = json.loads(req.read().decode())
    assert data.get('status') == 'success'
    print('OK')
except:
    print('SKIP')
" 2>/dev/null | grep -q "OK"; then
  ok "ip-api.com reachable (Geo-IP OK)"
elif python3 -c "
import urllib.request
try:
    urllib.request.urlopen('http://ip-api.com/json/8.8.8.8', timeout=3)
except:
    pass
" 2>/dev/null; then
  warn "ip-api.com no responde (Geo-IP offline)"
else
  warn "Sin red — OSINT limitado"
fi

# ─── RESUMEN ──────────────────────────────────────────────────────────
echo ""
echo -e "${C}════════════════════════════════════════════════════${N}"
echo -e "${G}  RESULTADOS: ${PASS} OK · ${FAIL} FAIL · ${WARN} WARN · $((PASS+FAIL+WARN)) TOTAL${N}"
echo -e "${C}════════════════════════════════════════════════════${N}"

if [ "$FAIL" -eq 0 ]; then
  echo -e "${G}  ✅ COMMANDER LISTO PARA AUDITAR${N}"
  echo ""
  echo -e "  ${C}Comandos rápidos:${N}"
  echo -e "    ${G}python3 commander.py${N}                    # Menú interactivo"
  echo -e "    ${G}python3 commander.py --auto 192.168.1.0/24${N}  # Auditoría automática"
  echo -e "    ${G}python3 commander.py --list${N}              # Listar auditorías"
  echo -e "    ${G}python3 commander.py --resume 1${N}           # Reanudar por ID"
else
  echo -e "${R}  ❌ $FAIL test(s) fallaron — revisa arriba${N}"
fi
