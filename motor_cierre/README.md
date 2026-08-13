# Motor de Cierre Autónomo v2.1 — Multi-Producto

Sistema independiente de pipeline de ventas con NLP + Stripe + dashboard. **Funciona con cualquier producto actual o futuro.**

## Arquitectura — 100% independiente

```
motor_cierre/              ← Módulo aislado (NO toca el dashboard principal)
├── backend/
│   ├── main.py            ← FastAPI :8000 (puerto separado de :8001)
│   ├── requirements.txt   ← Dependencias Python propias
│   └── .env.example       ← Config (Stripe, OpenAI, API_KEY)
├── start.sh              ← Arranque independiente
└── README.md
```

Frontend: `tauri-frontend/src/routes/SalesCommandCenter.tsx`
Ruta: `/ventas` en el sidebar

## Multi-Producto

El motor tiene un **catálogo de productos dinámico** (tabla `products` en SQLite). Cualquier producto actual o futuro puede registrarse vía API o desde el tab "Productos" del dashboard.

### Productos pre-configurados
| ID | Nombre | Precio |
|----|--------|--------|
| `sourceseal-console` | SourceSeal Console | $499 |
| `origenprogreso` | OrigenProgreso | $299 |
| `sourceseal-audit` | Auditoría Operativa Express | $999 |
| `generic-product` | Producto Genérico | $199 |

### Registrar un producto nuevo
```bash
curl -X POST http://localhost:8000/products \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":"mi-nuevo-producto","name":"Mi Producto","default_price_usd":299}'
```

O desde el dashboard → tab Productos → "Registrar Nuevo Producto".

### Usar un producto en el webhook
```bash
curl -X POST http://localhost:8000/webhook/email-reply \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"lead_email":"cliente@test.com","subject":"Hola","body_text":"Quiero comprar","product_id":"origenprogreso"}'
```

El motor usa el nombre, precio y URLs de redirección del producto automáticamente.

## Endpoints

### Productos
- `GET /products` — Lista productos activos
- `GET /products/{id}` — Detalle de producto
- `POST /products` — Crear producto
- `PATCH /products/{id}` — Actualizar producto
- `DELETE /products/{id}` — Desactivar producto

### Ventas
- `POST /webhook/email-reply` — Procesa respuestas (NLP + Stripe) — acepta `product_id`
- `POST /checkout/manual` — Checkout manual — acepta `product_id`
- `GET /leads` — Lista leads (filtra por `product_id` y `status`)
- `GET /leads/{email}` — Detalle de lead
- `PATCH /leads/{email}` — Actualizar lead
- `GET /metrics/dashboard` — Métricas (filtra por `product_id`, incluye `by_product`)
- `POST /stripe/webhook` — Webhook de Stripe
- `GET /health` — Health check

## Arranque

### Backend (puerto 8000)
```bash
cd motor_cierre && bash start.sh
```

### Frontend
```bash
cd tauri-frontend
cp .env.motor_cierre.example .env.local  # editar valores
npm run dev
# → Navegar a /ventas en el sidebar
```

## Puertos
| Puerto | Servicio |
|--------|----------|
| 8000   | Motor de Cierre (este módulo) |
| 8001   | Dashboard principal (Red-Team-Tauri) |
