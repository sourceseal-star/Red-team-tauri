import os
import time
import hmac
import hashlib
import sqlite3
import json
import re
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from enum import Enum

try:
    import stripe
    STRIPE_OK = True
except ImportError:
    STRIPE_OK = False
    print("[!] stripe no instalado. Pagos desactivados.")

try:
    import openai
    OPENAI_OK = True
except ImportError:
    OPENAI_OK = False
    print("[!] openai no instalado. NLP usará heurística.")

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ==========================================
# CONFIGURACIÓN
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("motor_cierre")

security = HTTPBearer(auto_error=False)

class Settings:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    API_KEY = os.getenv("API_KEY", "dev-key-cambiar-en-produccion")
    DB_PATH = os.getenv("DB_PATH", "./motor_cierre.db")
    DEFAULT_PRICE_USD = int(os.getenv("DEFAULT_PRICE_USD", "499"))
    CHECKOUT_EXPIRY_MINUTES = int(os.getenv("CHECKOUT_EXPIRY_MINUTES", "30"))

settings = Settings()

if STRIPE_OK:
    stripe.api_key = settings.STRIPE_SECRET_KEY
if OPENAI_OK:
    openai.api_key = settings.OPENAI_API_KEY

app = FastAPI(title="Motor de Cierre Autonomo v2.0", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DB
# ==========================================
@contextmanager
def get_db():
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                company TEXT,
                domain TEXT,
                status TEXT DEFAULT 'new',
                intent TEXT,
                score INTEGER DEFAULT 0,
                price_offered INTEGER,
                payment_link TEXT,
                stripe_session_id TEXT,
                payment_status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                archived INTEGER DEFAULT 0,
                source TEXT,
                metadata TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_email TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('inbound','outbound')),
                content TEXT,
                intent_detected TEXT,
                ai_model TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                leads_received INTEGER DEFAULT 0,
                ready_to_buy INTEGER DEFAULT 0,
                objections INTEGER DEFAULT 0,
                dropped INTEGER DEFAULT 0,
                payments_initiated INTEGER DEFAULT 0,
                payments_completed INTEGER DEFAULT 0,
                revenue_usd INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS processed_hashes (
                hash TEXT PRIMARY KEY,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("[+] Base de datos lista.")

init_db()

# ==========================================
# VALIDACIÓN MANUAL DE EMAIL (sin email-validator)
# ==========================================
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email(email: str) -> str:
    if not EMAIL_REGEX.match(email):
        raise ValueError("Email inválido")
    return email

# ==========================================
# MODELOS
# ==========================================
class LeadStatus(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    OBJECTION = "objection"
    READY = "ready_to_buy"
    CHECKOUT_SENT = "checkout_sent"
    PAID = "paid"
    DROPPED = "dropped"
    NURTURING = "nurturing"

class Intent(str, Enum):
    READY_TO_BUY = "READY_TO_BUY"
    OBJECTION = "OBJECTION"
    NOT_INTERESTED = "NOT_INTERESTED"
    UNCLEAR = "UNCLEAR"

class EmailReply(BaseModel):
    lead_email: str = Field(..., max_length=300)
    subject: str = Field(..., max_length=300)
    body_text: str = Field(..., max_length=10000)
    source: Optional[str] = "email_provider"
    campaign_id: Optional[str] = None

    @field_validator('lead_email')
    @classmethod
    def check_email(cls, v):
        return validate_email(v)

    @field_validator('body_text')
    @classmethod
    def sanitize_body(cls, v):
        v = re.sub(r'["\']?\s*ignore\s+previous\s+instructions?["\']?', '[REDACTED]', v, flags=re.I)
        v = re.sub(r'["\']?\s*system\s*:*\s*["\']?', '[REDACTED]', v, flags=re.I)
        return v[:5000]

class CheckoutRequest(BaseModel):
    lead_email: str = Field(..., max_length=300)
    service_name: str = "Auditoría Operativa Express"
    price_usd: int = Field(default=499, ge=49, le=50000)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('lead_email')
    @classmethod
    def check_email(cls, v):
        return validate_email(v)

class LeadUpdate(BaseModel):
    status: Optional[LeadStatus] = None
    price_offered: Optional[int] = None
    notes: Optional[str] = None

# ==========================================
# SERVICIOS
# ==========================================
class LeadService:
    @staticmethod
    def get_or_create_lead(email: str, company: Optional[str] = None, source: Optional[str] = None):
        domain = email.split("@")[1] if "@" in email else ""
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM leads WHERE email = ?", (email,))
            row = c.fetchone()
            if not row:
                c.execute("""
                    INSERT INTO leads (email, company, domain, source, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (email, company or domain.split(".")[0].capitalize(), domain, source, datetime.utcnow().isoformat()))
                conn.commit()
                c.execute("SELECT * FROM leads WHERE email = ?", (email,))
                row = c.fetchone()
                logger.info(f"[+] Nuevo lead: {email}")
            return row

    @staticmethod
    def update_lead(email: str, **kwargs):
        with get_db() as conn:
            c = conn.cursor()
            fields = []
            values = []
            for k, v in kwargs.items():
                fields.append(f"{k} = ?")
                values.append(v)
            values.append(email)
            c.execute(f"UPDATE leads SET {', '.join(fields)}, updated_at = ? WHERE email = ?",
                      [datetime.utcnow().isoformat()] + values)
            conn.commit()

    @staticmethod
    def log_conversation(email: str, direction: str, content: str, intent: Optional[str] = None, model: Optional[str] = None):
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO conversations (lead_email, direction, content, intent_detected, ai_model)
                VALUES (?, ?, ?, ?, ?)
            """, (email, direction, content, intent, model))
            conn.commit()

class MetricsService:
    @staticmethod
    def increment(date_str: str, field: str, amount: int = 1):
        with get_db() as conn:
            c = conn.cursor()
            c.execute(f"INSERT INTO metrics (date) VALUES (?) ON CONFLICT(date) DO UPDATE SET {field} = {field} + ?",
                      (date_str, amount))
            conn.commit()

class NLPService:
    INTENT_PATTERNS = {
        Intent.READY_TO_BUY: [
            r'\b(precio|cotizaci[oó]n|presupuesto|costo|cu[aá]nto|cuesta|pagar|comprar|adquirir|contratar|siguientes pasos|empezar|iniciar|proceder)\b',
            r'\b(me interesa|quiero|deseo|voy a|listo para|confirmar|cerrar|facturar)\b',
            r'\b(tarjeta|transferencia|pago|factura|recibo|link|enlace)\b'
        ],
        Intent.OBJECTION: [
            r'\b(duda|pregunta|informaci[oó]n|detalle|especificaci[oó]n|t[eé]cnico|caso de uso|ejemplo|referencia|demo|prueba)\b',
            r'\b(car[oó]|expensive|costoso|presupuesto limitado|reducir|descuento|oferta|promoci[oó]n)\b',
            r'\b(tiempo|plazo|duraci[oó]n|cu[aá]ndo|demora|urgencia|prisa)\b'
        ],
        Intent.NOT_INTERESTED: [
            r'\b(no estoy interesado|no gracias|rechazo|cancelar|eliminar|borrar|spam|no quiero|baja)\b',
            r'\b(no aplica|no necesito|ya tengo|otro proveedor|competencia|m[aá]s tarde|nunca)\b'
        ]
    }

    @staticmethod
    def heuristic_intent(text: str) -> Intent:
        text_lower = text.lower()
        for intent, patterns in NLPService.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        return Intent.UNCLEAR

    @classmethod
    def analyze_intent(cls, text: str):
        if not OPENAI_OK or not settings.OPENAI_API_KEY:
            return cls.heuristic_intent(text), "heuristic"
        try:
            safe_text = text.replace('"', '\\"').replace('\n', ' ')
            system_prompt = (
                "Eres un clasificador de intención de compra B2B. "
                "Analiza el texto del prospecto y clasifícalo EXACTAMENTE en una de estas categorías: "
                "READY_TO_BUY, OBJECTION, NOT_INTERESTED, UNCLEAR. "
                "Responde ÚNICAMENTE con la categoría en mayúsculas, sin explicaciones."
            )
            user_prompt = f'Texto del prospecto: "{safe_text}"\\nCategoría:'
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=10,
                timeout=15
            )
            raw = response.choices[0].message.content.strip().upper()
            for intent in Intent:
                if intent.value in raw:
                    return intent, "gpt-4o-mini"
            return Intent.UNCLEAR, "gpt-4o-mini"
        except Exception as e:
            logger.error(f"[!] OpenAI falló: {e}. Usando heurística.")
            return cls.heuristic_intent(text), "heuristic-fallback"

class PaymentService:
    @staticmethod
    def create_checkout(email: str, service_name: str, price_usd: int, metadata: Optional[Dict] = None):
        if not STRIPE_OK or not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe no configurado")
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=email,
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': service_name,
                        'description': 'Servicio contratado vía Motor de Cierre Autónomo'
                    },
                    'unit_amount': price_usd * 100,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"https://tudominio.com/onboarding?session_id={{CHECKOUT_SESSION_ID}}&email={email}",
            cancel_url=f"https://tudominio.com/re-engagement?email={email}",
            expires_at=int(time.time()) + (settings.CHECKOUT_EXPIRY_MINUTES * 60),
            metadata={"lead_email": email, "service": service_name, **(metadata or {})}
        )
        return {
            "url": session.url,
            "session_id": session.id,
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.CHECKOUT_EXPIRY_MINUTES)
        }

# ==========================================
# AUTH
# ==========================================
def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="API Key requerida. Header: Authorization: Bearer <key>")
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
    return credentials.credentials

# ==========================================
# ENDPOINTS
# ==========================================
@app.post("/webhook/email-reply", status_code=200)
async def handle_email_reply(
    reply: EmailReply,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Idempotencia
    content_hash = hashlib.sha256(f"{reply.lead_email}:{reply.subject}:{reply.body_text[:100]}".encode()).hexdigest()[:32]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (content_hash,))
        if c.fetchone():
            return {"status": "duplicate", "message": "Este mensaje ya fue procesado."}
        c.execute("INSERT INTO processed_hashes (hash) VALUES (?)", (content_hash,))
        conn.commit()

    lead = LeadService.get_or_create_lead(reply.lead_email, source=reply.source)
    LeadService.log_conversation(reply.lead_email, "inbound", reply.body_text)
    MetricsService.increment(today, "leads_received")

    intent, model_used = NLPService.analyze_intent(reply.body_text)
    LeadService.log_conversation(reply.lead_email, "system", f"Intent detectado: {intent.value}", intent.value, model_used)
    logger.info(f"[>] {reply.lead_email} | Intent: {intent.value} | Model: {model_used}")

    if intent == Intent.READY_TO_BUY:
        price = lead["price_offered"] or settings.DEFAULT_PRICE_USD
        try:
            checkout = PaymentService.create_checkout(
                reply.lead_email, "Auditoría Operativa Express", price,
                metadata={"campaign_id": reply.campaign_id, "intent": intent.value}
            )
            LeadService.update_lead(
                reply.lead_email, status=LeadStatus.READY, intent=intent.value,
                score=min(lead["score"] + 30, 100), price_offered=price,
                payment_link=checkout["url"], stripe_session_id=checkout["session_id"]
            )
            LeadService.log_conversation(reply.lead_email, "outbound", f"Checkout enviado: {checkout['url']}")
            MetricsService.increment(today, "ready_to_buy")
            MetricsService.increment(today, "payments_initiated")
            return {
                "status": "success", "action": "checkout_sent", "lead_status": LeadStatus.READY,
                "intent": intent.value, "payment_link": checkout["url"],
                "expires_at": checkout["expires_at"].isoformat(), "model_used": model_used
            }
        except Exception as e:
            logger.error(f"[!] Error checkout: {e}")
            LeadService.update_lead(reply.lead_email, status=LeadStatus.NURTURING, intent=intent.value)
            raise HTTPException(status_code=502, detail=f"Error de pasarela: {str(e)}")

    elif intent == Intent.OBJECTION:
        LeadService.update_lead(reply.lead_email, status=LeadStatus.OBJECTION, intent=intent.value, score=min(lead["score"] + 10, 100))
        MetricsService.increment(today, "objections")
        return {"status": "pending", "action": "objection_handling_triggered", "lead_status": LeadStatus.OBJECTION, "intent": intent.value, "model_used": model_used}

    elif intent == Intent.NOT_INTERESTED:
        LeadService.update_lead(reply.lead_email, status=LeadStatus.DROPPED, intent=intent.value, archived=1)
        MetricsService.increment(today, "dropped")
        return {"status": "dropped", "action": "lead_archived", "lead_status": LeadStatus.DROPPED, "intent": intent.value}

    else:
        LeadService.update_lead(reply.lead_email, status=LeadStatus.NURTURING, intent=intent.value)
        return {"status": "needs_review", "action": "manual_qualification_required", "lead_status": LeadStatus.NURTURING, "intent": intent.value, "model_used": model_used}

@app.post("/checkout/manual", status_code=200)
async def manual_checkout(req: CheckoutRequest, api_key: str = Depends(verify_api_key)):
    checkout = PaymentService.create_checkout(req.lead_email, req.service_name, req.price_usd, req.metadata)
    LeadService.update_lead(req.lead_email, payment_link=checkout["url"], stripe_session_id=checkout["session_id"], price_offered=req.price_usd, status=LeadStatus.CHECKOUT_SENT)
    return {"payment_link": checkout["url"], "session_id": checkout["session_id"], "expires_at": checkout["expires_at"].isoformat()}

@app.get("/leads", status_code=200)
async def list_leads(status: Optional[LeadStatus] = None, limit: int = 50, offset: int = 0, api_key: str = Depends(verify_api_key)):
    with get_db() as conn:
        c = conn.cursor()
        if status:
            c.execute("SELECT * FROM leads WHERE status = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (status.value, limit, offset))
        else:
            c.execute("SELECT * FROM leads ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = c.fetchall()
    return {"total": len(rows), "leads": [dict(r) for r in rows]}

@app.get("/leads/{email}", status_code=200)
async def get_lead_detail(email: str, api_key: str = Depends(verify_api_key)):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM leads WHERE email = ?", (email,))
        lead = c.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead no encontrado")
        c.execute("SELECT * FROM conversations WHERE lead_email = ? ORDER BY created_at DESC", (email,))
        conversations = c.fetchall()
    return {"lead": dict(lead), "conversation_history": [dict(c) for c in conversations]}

@app.patch("/leads/{email}", status_code=200)
async def update_lead_manual(email: str, update: LeadUpdate, api_key: str = Depends(verify_api_key)):
    updates = {}
    if update.status:
        updates["status"] = update.status.value
    if update.price_offered:
        updates["price_offered"] = update.price_offered
    if update.notes:
        updates["metadata"] = json.dumps({"notes": update.notes})
    if updates:
        LeadService.update_lead(email, **updates)
    return {"status": "updated", "email": email}

@app.get("/metrics/dashboard", status_code=200)
async def get_metrics(days: int = 30, api_key: str = Depends(verify_api_key)):
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT SUM(leads_received) as total_leads,
                   SUM(ready_to_buy) as hot_leads,
                   SUM(objections) as objections,
                   SUM(dropped) as dropped,
                   SUM(payments_initiated) as checkouts,
                   SUM(payments_completed) as paid,
                   SUM(revenue_usd) as revenue
            FROM metrics WHERE date >= ?
        """, (since,))
        row = c.fetchone()

    total_leads = row["total_leads"] or 0
    hot_leads = row["hot_leads"] or 0
    objections = row["objections"] or 0
    checkouts = row["checkouts"] or 0
    paid = row["paid"] or 0
    revenue = row["revenue"] or 0

    return {
        "period_days": days,
        "funnel": {
            "leads_received": total_leads,
            "qualified": hot_leads + objections,
            "ready_to_buy": hot_leads,
            "checkouts_sent": checkouts,
            "payments_completed": paid,
            "revenue_usd": revenue
        },
        "conversion_rates": {
            "lead_to_qualified": round((hot_leads / total_leads * 100), 2) if total_leads else 0,
            "qualified_to_checkout": round((checkouts / hot_leads * 100), 2) if hot_leads else 0,
            "checkout_to_paid": round((paid / (checkouts or 1) * 100), 2)
        }
    }

@app.post("/stripe/webhook", status_code=200)
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.STRIPE_WEBHOOK_SECRET:
        event = json.loads(payload)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except ValueError:
            raise HTTPException(status_code=400, detail="Payload inválido")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Firma inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("metadata", {}).get("lead_email")
        if email:
            LeadService.update_lead(email, status=LeadStatus.PAID, payment_status="completed")
            today = datetime.utcnow().strftime("%Y-%m-%d")
            amount = session.get("amount_total", 0) // 100
            MetricsService.increment(today, "payments_completed")
            MetricsService.increment(today, "revenue_usd", amount)
            logger.info(f"[$] Pago completado: {email} ${amount}")

    return {"status": "received"}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "stripe_configured": bool(STRIPE_OK and settings.STRIPE_SECRET_KEY),
        "openai_configured": bool(OPENAI_OK and settings.OPENAI_API_KEY),
        "db_path": settings.DB_PATH
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
