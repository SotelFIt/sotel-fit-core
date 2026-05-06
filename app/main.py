import logging
import sys
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

from core.database import Base, engine
from routers import landbot, clients, auth
from routers.admin import router as admin_router
from routers.cron import router as cron_router
from routers.twilio_webhook import router as twilio_router
from routers.stripe_webhook import router as stripe_router
from routers.lead_onboarding import router as lead_onboarding_router
from models import *  # noqa

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger.info("Importando routers...")

try:
    Base.metadata.create_all(bind=engine)
    logger.info("Banco de dados inicializado")
except Exception as e:
    logger.warning(f"Banco de dados nao disponivel: {e}")

from sqlalchemy import text

with engine.connect() as conn:
    migrations = [
        "ALTER TABLE conversation_states ADD COLUMN IF NOT EXISTS onboarding_link_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS objective VARCHAR",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'lead'",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS age INTEGER",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS weight FLOAT",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS height FLOAT",
        "ALTER TABLE clients ALTER COLUMN email DROP NOT NULL",
        "ALTER TABLE clients ALTER COLUMN name DROP NOT NULL",
        "ALTER TABLE clients ALTER COLUMN objective DROP NOT NULL",
        "ALTER TABLE clients ALTER COLUMN difficulty DROP NOT NULL",
        "ALTER TABLE clients ALTER COLUMN updated_at DROP NOT NULL",
        "ALTER TABLE clients ALTER COLUMN updated_at SET DEFAULT NOW()",
	"ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_checkin_reminder_sent TIMESTAMP DEFAULT NULL",
        "DROP INDEX IF EXISTS ix_clients_email",
    ]
    for sql in migrations:
        try:
            conn.execute(text(sql))
            conn.commit()
        except Exception:
            conn.rollback()

    for sql in [
        """
        CREATE TABLE IF NOT EXISTS client_plans (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            content TEXT,
            status VARCHAR DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS client_diets (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            content TEXT,
            status VARCHAR DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS client_checkins (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            treinou VARCHAR,
            seguiu_dieta VARCHAR,
            peso FLOAT,
            energia VARCHAR,
            dificuldade TEXT,
            observacoes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
    ]:
        try:
            conn.execute(text(sql))
            conn.commit()
            logger.info("Tabela criada/verificada com sucesso")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao criar tabela: {e}")

    try:
        result = conn.execute(text("""
            INSERT INTO clients (name, phone, status, email, objective, created_at, updated_at)
            SELECT COALESCE(cs.name, 'Lead WhatsApp'), cs.phone, 'lead', NULL, NULL, cs.created_at, NOW()
            FROM conversation_states cs
            WHERE cs.phone IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.phone = cs.phone)
        """))
        conn.commit()
        if result.rowcount > 0:
            logger.info(f"Clientes criados a partir de leads: {result.rowcount}")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Sync clients erro: {e}")

logger.info("Migracoes executadas")

app = FastAPI(title="Sotel Fit Core", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def scheduled_checkin_reminders():
    """Task agendada para enviar lembretes."""
    try:
        from services.checkin_reminder import send_checkin_reminders
        result = send_checkin_reminders()
        logger.info(f"Checkin reminders job executado: {result}")
    except Exception as e:
        logger.error(f"Erro em scheduled_checkin_reminders: {e}")

scheduler = BackgroundScheduler()

@app.on_event("startup")
async def startup_event():
    logger.info("STARTUP OK")
    
    # Agenda lembretes de check-in
    # Roda de segunda a sexta às 8h
    scheduler.add_job(
        scheduled_checkin_reminders,
        CronTrigger(day_of_week="0-4", hour=8, minute=0),
        id="checkin_reminders",
        name="Checkin Reminders",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler iniciado - Lembretes agendados para seg-sex 8h")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SHUTDOWN OK")


app.include_router(landbot.router)
app.include_router(clients.router)
app.include_router(auth.router)
app.include_router(admin_router)
app.include_router(cron_router)
app.include_router(twilio_router)
app.include_router(stripe_router)
app.include_router(lead_onboarding_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Sotel Fit Core API"}
