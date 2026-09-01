#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# KRAKEN v3.0 — Instalación ligera para Termux (solo core + CLI)
# No instala weasyprint, streamlit, sklearn (muy pesados para Android)
# El dashboard y reportes PDF se manejan desde el backend principal
# =====================================================================
set -e

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; N='\033[0m'

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo -e "${Y}🔧 KRAKEN v3.0 — Instalación Termux (modo ligero)${N}"

# Dependencias del sistema
echo -e "${Y}📦 Instalando dependencias del sistema...${N}"
pkg install -y nmap sshpass curl python 2>/dev/null || true

# Dependencias Python (solo lo que funciona en Termux)
echo -e "${Y}🐍 Instalando dependencias Python...${N}"
pip install --upgrade pip
pip install \
  click>=8.0 \
  fastapi>=0.95 \
  uvicorn>=0.22 \
  sqlalchemy>=2.0 \
  python-nmap>=0.7 \
  requests>=2.28 \
  python-json-logger>=2.0 \
  pydantic>=2.0 \
  python-dotenv>=1.0 \
  pyyaml>=6.0 \
  pycryptodome>=3.19

# Estas son opcionales — si fallan, KRAKEN sigue funcionando
echo -e "${Y}📦 Dependencias opcionales (pueden fallar en Termux)...${N}"
pip install passlib 2>/dev/null || echo -e "${R}  passlib no instalado (auth API deshabilitada)${N}"
pip install scikit-learn 2>/dev/null || echo -e "${R}  sklearn no instalado (IA deshabilitada)${N}"

# Verificar instalación
echo -e "${Y}✅ Verificando...${N}"
python3 -c "
import sys
sys.path.insert(0, '$ROOT/src')
try:
    from kraken.config.settings import settings
    print(f'  Config: OK (DB={settings.DB_TYPE})')
except Exception as e:
    print(f'  Config: {e}')
try:
    from kraken.core.utils import get_ips_from_cidr
    ips = get_ips_from_cidr('192.168.1.0/30')
    print(f'  Utils: OK ({len(ips)} IPs en /30)')
except Exception as e:
    print(f'  Utils: {e}')
try:
    from kraken.core.cache import cache
    c = cache('memory')
    c.set('test', 1)
    print(f'  Cache: OK (memory mode)')
except Exception as e:
    print(f'  Cache: {e}')
"

echo ""
echo -e "${G}✅ KRAKEN instalado en: $ROOT${N}"
echo -e "${G}📌 CLI:  python3 -m kraken.cli.commands --help${N}"
echo -e "${G}📌 API:  python3 -m kraken.api.app${N}"
echo -e "${Y}⚠️  Web dashboard (streamlit) y PDF (weasyprint) no instalados${N}"
echo -e "${Y}    Usa el dashboard principal en http://localhost:8001${N}"
