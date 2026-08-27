# Motor de Cierre — Sistema de Ventas (Separado)

Modulo separado del dashboard Red-Team Tauri.

## Despliegue

```bash
cd motor_cierre/backend
pip install -r requirements.txt
export API_KEY="tu-clave"
uvicorn main:app --host 0.0.0.0 --port 8000
```

Funciona en cualquier servidor con Python 3.10+. No requiere Termux.
