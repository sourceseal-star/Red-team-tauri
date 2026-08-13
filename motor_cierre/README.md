# Motor de Cierre Autónomo v2.0

Sistema independiente de pipeline de ventas con NLP + Stripe + dashboard.

## Arquitectura — 100% independiente

```
motor_cierre/              ← Módulo aislado (NO toca el dashboard principal)
├── backend/
│   ├── main.py            ← FastAPI :8000 (puerto separado de :8001)
│   ├── requirements.txt  ← Dependencias Python propias
│   └── .env.example      ← Config (Stripe, OpenAI, API_KEY)
├── start.sh              ← Arranque independiente
└── README.md
```

Frontend: `tauri-frontend/src/routes/SalesCommandCenter.tsx`
Ruta: `/ventas` en el sidebar

## Arranque

### Backend (puerto 8000)
```bash
cd motor_cierre
bash start.sh
```

### Frontend
```bash
cd tauri-frontend
cp .env.motor_cierre.example .env.local  # editar valores
npm run dev
# → Navegar a /ventas en el sidebar
```

## Endpoints
- `POST /webhook/email-reply` — NLP + Stripe
- `POST /checkout/manual` — Checkout manual
- `GET /leads` — Lista leads
- `GET /leads/{email}` — Detalle lead
- `PATCH /leads/{email}` — Actualizar lead
- `GET /metrics/dashboard` — Dashboard métricas
- `POST /stripe/webhook` — Webhook Stripe
- `GET /health` — Health check

## Puertos
| Puerto | Servicio |
|--------|----------|
| 8000   | Motor de Cierre (este módulo) |
| 8001   | Dashboard principal (Red-Team-Tauri) |
