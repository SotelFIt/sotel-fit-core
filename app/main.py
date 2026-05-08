import logging
import sys
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
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
            FROM conversation_