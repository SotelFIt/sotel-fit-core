"""
migrate.py — Migrations inline do Sotel Fit Core.
Executado uma vez na startup via main.py.
Todas as alteracoes de schema ficam aqui, nao no main.py.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def run_migrations(engine):
    logger.info("Executando migrations...")

    with engine.connect() as conn:

        # --- ALTER TABLE migrations ---
        alterations = [
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

        for sql in alterations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

        # --- CREATE TABLE migrations ---
        tables = [
            """CREATE TABLE IF NOT EXISTS client_plans (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                content TEXT,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS client_diets (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                content TEXT,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS client_checkins (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                treinou VARCHAR,
                seguiu_dieta VARCHAR,
                peso FLOAT,
                energia VARCHAR,
                dificuldade TEXT,
                observacoes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )"""
	    """CREATE TABLE IF NOT EXISTS stripe_events (
            id SERIAL PRIMARY KEY,
            event_id VARCHAR UNIQUE NOT NULL,
            event_type VARCHAR,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        ]

        for sql in tables:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao criar tabela: {e}")

    logger.info("Migrations concluidas.")