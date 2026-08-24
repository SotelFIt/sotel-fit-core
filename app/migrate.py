"""
migrate.py - Migrations inline do Sotel Fit Core.
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
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_workout_reminder_sent TIMESTAMP DEFAULT NULL",
            # Subscriptions
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS notes VARCHAR",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS manual_payment_method VARCHAR",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_type VARCHAR",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS payment_status VARCHAR DEFAULT 'pending'",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS start_date DATE",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS end_date DATE",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_payment_date DATE",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS next_payment_date DATE",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'lead'",
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS client_id INTEGER",
            "ALTER TABLE client_plans ADD COLUMN IF NOT EXISTS published_content TEXT",
            "ALTER TABLE client_diets ADD COLUMN IF NOT EXISTS published_content TEXT",
            # LIB-005 Parte A: aliases na Biblioteca (dominio da Biblioteca).
            "ALTER TABLE exercises ADD COLUMN IF NOT EXISTS aliases JSON DEFAULT '[]'",
            # LIB-005 Parte B: enriquecimento paralelo do plano (NAO altera published_content).
            # Serializado como JSON em TEXT (portavel); idempotencia via source_hash.
            "ALTER TABLE client_plans ADD COLUMN IF NOT EXISTS enrichment_json TEXT",
            "ALTER TABLE client_plans ADD COLUMN IF NOT EXISTS enrichment_source_hash TEXT",
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
            )""",
            """CREATE TABLE IF NOT EXISTS stripe_events (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR UNIQUE NOT NULL,
                event_type VARCHAR,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS admin_audit_log (
                id SERIAL PRIMARY KEY,
                action VARCHAR NOT NULL,
                admin_id INTEGER,
                client_id INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS whatsapp_events (
                id SERIAL PRIMARY KEY,
                client_id INTEGER,
                message_sid VARCHAR,
                status VARCHAR,
                error_code VARCHAR,
                to_phone VARCHAR,
                context VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL UNIQUE,
                status VARCHAR NOT NULL DEFAULT 'lead',
                plan_type VARCHAR,
                payment_status VARCHAR NOT NULL DEFAULT 'pending',
                start_date DATE,
                end_date DATE,
                last_payment_date DATE,
                next_payment_date DATE,
                manual_payment_method VARCHAR,
                notes VARCHAR,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
        """CREATE TABLE IF NOT EXISTS timeline_events (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                event_type VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                description TEXT,
                metadata TEXT,
                icon VARCHAR DEFAULT '⚡',
                visibility VARCHAR DEFAULT 'private',
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


        # --- WORKOUT-DATA-001: conclusao canonica de treino ---
        # A tabela nasce via Base.metadata.create_all(); este CREATE IF NOT
        # EXISTS existe para bases onde o create_all nao alcancou. Aditivo e
        # idempotente: nao toca em timeline_events nem em dado existente.
        workout_completions = [
            """CREATE TABLE IF NOT EXISTS workout_completions (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL,
                client_plan_id INTEGER NOT NULL DEFAULT 0,
                workout_key VARCHAR(32) NOT NULL,
                completed_date DATE NOT NULL,
                completed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                idempotency_key VARCHAR(128) NOT NULL,
                timeline_event_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE workout_completions ADD COLUMN IF NOT EXISTS client_plan_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE workout_completions ADD COLUMN IF NOT EXISTS timeline_event_id INTEGER",
        ]
        for sql in workout_completions:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

        # --- INDEX migrations ---
        index_sqls = [
            "CREATE INDEX IF NOT EXISTS idx_timeline_client_id ON timeline_events (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_event_type ON timeline_events (event_type)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_created_at ON timeline_events (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_checkins_client_id ON client_checkins (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_checkins_created_at ON client_checkins (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_plans_client_id ON client_plans (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_diets_client_id ON client_diets (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients (phone)",
            "CREATE INDEX IF NOT EXISTS idx_clients_status ON clients (status)",
            "CREATE INDEX IF NOT EXISTS idx_wa_events_message_sid ON whatsapp_events (message_sid)",
            "CREATE INDEX IF NOT EXISTS idx_wa_events_client_id ON whatsapp_events (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_wa_events_status ON whatsapp_events (status)",
            # WORKOUT-DATA-001 — as DUAS garantias de unicidade.
            # (1) a intencao: mesma chave reenviada = uma conclusao so.
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_workout_completion_idem ON workout_completions (idempotency_key)",
            # (2) a ocorrencia: protege quem PERDEU a chave (storage limpo,
            #     outro aparelho) de concluir o mesmo treino do mesmo plano
            #     no mesmo dia duas vezes.
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_workout_completion_ocorrencia ON workout_completions (client_id, client_plan_id, workout_key, completed_date)",
            "CREATE INDEX IF NOT EXISTS idx_workout_completions_client ON workout_completions (client_id)",
            "CREATE INDEX IF NOT EXISTS idx_workout_completions_date ON workout_completions (completed_date DESC)",
        ]
        for sql in index_sqls:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()

        # --- LIB-002: imutabilidade do slug em exercises (garantia no banco) ---
        # Especifico desta tabela e idempotente (CREATE OR REPLACE / DROP IF EXISTS).
        # Roda SOMENTE em PostgreSQL: plpgsql nao existe em SQLite; a protecao
        # equivalente no ambiente local/dev fica no listener ORM do model.
        if engine.dialect.name == "postgresql":
            exercises_slug_guard = [
                """CREATE OR REPLACE FUNCTION exercises_slug_immutable() RETURNS trigger AS $$
                BEGIN
                    IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                        RAISE EXCEPTION 'exercises.slug e imutavel';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql""",
                "DROP TRIGGER IF EXISTS trg_exercises_slug_immutable ON exercises",
                """CREATE TRIGGER trg_exercises_slug_immutable
                    BEFORE UPDATE OF slug ON exercises
                    FOR EACH ROW EXECUTE FUNCTION exercises_slug_immutable()""",
            ]
            for sql in exercises_slug_guard:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Erro no guard de slug de exercises: {e}")
    logger.info("Migrations concluidas.")