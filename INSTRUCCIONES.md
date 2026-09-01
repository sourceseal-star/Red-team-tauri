# SourceSeal Red-team-tauri — Instrucciones Operativas

**Versión:** 7.0-TACTICAL-HOTRELOAD
**Última actualización:** 2026-09-01

---

## 📋 TABLA DE COMANDOS RÁPIDOS

### Actualizar y sincronizar
```bash
# Traer cambios del remote
cd ~/Red-team-tauri
git stash
git pull origin main
git stash pop
```

### Levantar el sistema completo
```bash
# Termux
bash arrancar.sh

# Replit
bash replit_start.sh
```

### Hot-reload (nuevo)
```bash
# Iniciar watcher en background
python3 watcher.py &

# El watcher monitorea redteam/modules/ cada 2s
# Al editar un módulo, recarga automáticamente sin reiniciar
```

### Parar todo
```bash
# Parar dashboard
pkill -f dashboard_server

# Parar watcher
pkill -f watcher.py
```

---

## 🔧 INSTALACIÓN INICIAL (Termux)

```bash
# 1. Clonar repo
git clone https://github.com/sourceseal-star/Red-team-tauri.git ~/Red-team-tauri
cd ~/Red-team-tauri

# 2. Instalar dependencias Python
pkg install python nmap
pip install fastapi uvicorn pydantic httpx requests psutil

# 3. Instalar dependencias Node
cd tauri-frontend
npm install
npm run build
cp -r dist/. ../public/
cd ..

# 4. (Opcional) Herramientas de escaneo
pkg install masscan subfinder nikto
pip install nuclei sslscan

# 5. Arrancar
bash arrancar.sh
```

---

## 🎯 EJECUTAR AUDITORÍA TÁCTICA

### Desde el dashboard
1. Abrir `http://localhost:8001`
2. Sidebar → **Auditoría Táctica** (icono de mira roja)
3. Ingresar subnet (o dejar vacío para auto-detectar)
4. Clic en **Ejecutar Auditoría**
5. Ver log en vivo, hallazgos y reporte sellado

### Desde la API
```bash
# Auto-detectar red
curl -X POST http://localhost:8001/api/tactical/scan

# Especificar subnet
curl -X POST http://localhost:8001/api/tactical/scan \
  -H "Content-Type: application/json" \
  -d '{"subnet": "192.168.1.0/24"}'

# Ver credenciales del diccionario
curl http://localhost:8001/api/tactical/credentials

# Ver puertos escaneados
curl http://localhost:8001/api/tactical/ports

# Descargar reporte
curl -O http://localhost:8001/api/tactical/report/RPT-1234567890-a1b2c3d4.html
```

---

## 🛠️ DESARROLLO DE MÓDULOS

### Crear un módulo nuevo
```bash
nano redteam/modules/mi_modulo.py
```

```python
from redteam.modules.base import BaseModule

class MiModulo(BaseModule):
    name = "mi_modulo"
    description = "Descripción del módulo"
    version = "1.0"

    def _execute(self, target: str, **kwargs):
        # Validar engagement (automático en run())
        # Tu lógica aquí
        return {"resultado": "..."}
```

### Recargar en caliente
Con el watcher corriendo, editar el archivo y guardar. El watcher detecta el cambio automáticamente:
```
🔄 MODIFIED: mi_modulo.py
🔗 Sellado en ledger SourceSeal
📡 Señal reload enviada al dashboard
```

---

## 🔐 CONFIGURACIÓN DE ENGAGEMENTS

Editar `config/engagements.json`:
```json
{
  "engagements": [
    {
      "id": "ENG-CLIENTE-001",
      "client": "Nombre del Cliente",
      "start_date": "2026-09-01T00:00:00Z",
      "end_date": "2026-12-31T23:59:59Z",
      "authorization_signed": true,
      "scope": ["192.168.1.0/24", "*.cliente.com"],
      "excluded": ["192.168.1.1"]
    }
  ]
}
```

⚠️ `authorization_signed: false` bloquea toda acción. Debe ser `true` para operar.

---

## 📂 ESTRUCTURA DE EVIDENCIA

```
evidence/
├── findings/         # JSON de hallazgos sellados con SHA-256
└── sealed/           # Informes sellados finalizados

reports/
└── templates/        # Plantillas HTML de reportes

~/.c2/
├── evidence_ledger.json    # Ledger SourceSeal con chain hash
├── module_state.json       # Estado del watcher
├── pids/dashboard.pid      # PID del dashboard
└── logs/
    ├── watcher.log         # Log del watcher
    └── engagement_audit.log  # Audit de autorizaciones
```

---

## 🚨 SOLUCIÓN DE PROBLEMAS

### El frontend no compila en Termux
```bash
# El build es no-fatal: si falla, usa dist/ existente
bash arrancar.sh
# Si necesitas recompilar manual:
cd tauri-frontend && npm run build && cp -r dist/. ../public/
```

### El watcher no detecta cambios
```bash
# Verificar que esté corriendo
ps aux | grep watcher

# Ver log
cat ~/.c2/logs/watcher.log

# Reiniciar
pkill -f watcher.py
python3 watcher.py &
```

### El dashboard no recibe señales del watcher
```bash
# Verificar PID del dashboard
cat ~/.c2/pids/dashboard.pid

# Verificar que el proceso existe
ps aux | grep dashboard_server

# Forzar recarga manual
kill -USR1 $(cat ~/.c2/pids/dashboard.pid)
```

### Puerto 8001 ocupado
```bash
# Ver qué lo usa
lsof -i :8001

# Matar proceso
pkill -f dashboard_server

# Reinciar
bash arrancar.sh
```

### Git pull con conflictos
```bash
git stash
git pull origin main
git stash pop
# Si sigue fallando:
git checkout .
git pull origin main
```

---

## ✅ CHECKLIST DE VERIFICACIÓN

```bash
# 1. Dashboard arriba
curl http://localhost:8001/api/health | jq .

# 2. Módulos disponibles
curl http://localhost:8001/api/tactical/ports | jq .

# 3. Diccionario de credenciales
curl http://localhost:8001/api/tactical/credentials | jq .

# 4. Watcher activo
ps aux | grep "watcher.py" | grep -v grep

# 5. Ledger SourceSeal
cat ~/.c2/evidence_ledger.json | jq .chain_hash

# 6. Frontend sirve
curl -s http://localhost:8001/ | head -5
```
