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

        # --- LIB-013B: regras direcionais de substituicao ---
        # ADITIVA. A tabela nasce em Base.metadata.create_all (models/exercise_substitution.py);
        # aqui migram as decisoes ja comprovadas na LIB-013A. Idempotente: ON CONFLICT DO NOTHING
        # sobre a UNIQUE(source, target). NENHUM DROP, NENHUMA perda de dado.
        # A coluna antiga exercises.approved_substitutions e PRESERVADA e deixa de ser lida:
        # vira projecao derivada desta tabela (services/substitution_rules.py).
        # ROLLBACK: DELETE FROM exercise_substitution_rules WHERE ...  (relacoes) e, se preciso,
        #           DROP TABLE IF EXISTS exercise_substitution_rules. A coluna legada continua
        #           intacta com o conteudo anterior, entao o estado antigo e recuperavel.
        _migrar_regras_de_substituicao(conn)

    logger.info("Migrations concluidas.")


# Decisoes da LIB-013A (source, target, relation_type, rationale, condition).
# Nenhuma relacao nova: apenas o que ja foi avaliado e provado naquela missao.
LIB_013A_RULES = [
    ("supino-reto", "supino-com-halteres", "direct",
     "Mesmo padrao motor (empurrar horizontal), mesmo musculo principal e mesma funcao no treino "
     "(composto de empurrar). Ambos sao peso livre: muda o implemento, nao a classe de estabilidade exigida.",
     None),
    ("supino-com-halteres", "supino-reto", "direct",
     "Simetria verificada caso a caso, nao assumida: nos dois sentidos a demanda de estabilidade e da "
     "mesma classe e a funcao no treino se mantem.",
     None),
    ("agachamento-livre", "leg-press", "acceptable",
     "Mesma funcao no treino (composto de membros inferiores) e a maquina reduz a demanda de estabilidade, "
     "o que respeita a hierarquia do Metodo Sotel (seguranca acima de intensidade). Nao e 'direct' porque "
     "mudam equipamento, padrao especifico e complexidade tecnica.",
     None),
    ("leg-press", "agachamento-livre", "contextual",
     "O sentido inverso nao herda a aprovacao: sair da maquina para o peso livre acrescenta demanda de "
     "estabilidade, mobilidade e tecnica que a origem nao exigia.",
     "Somente quando o aluno ja sustenta o padrao de agachamento com controle e coluna neutra na amplitude "
     "que vai usar; o alvo esta registrado como nivel avancado."),
    ("supino-maquina", "voador", "rejected",
     "Musculo principal, equipamento e nivel sao identicos e ainda assim nao se substituem: um e composto "
     "de empurrar, o outro e isolador de aducao. 'Mesmo musculo' nao e criterio de substituicao.",
     None),
    ("voador", "supino-maquina", "rejected",
     "Avaliado explicitamente tambem neste sentido: trocar um isolador de aducao por um composto de "
     "empurrar muda a funcao do exercicio dentro do treino.",
     None),
]


def _migrar_regras_de_substituicao(conn):
    """Semeia as regras da LIB-013A. Idempotente e nao destrutiva.

    Se a tabela ainda nao existe (create_all nao rodou) ou se algum exercicio do
    par nao existe, a linha e simplesmente pulada - a migration nunca derruba a
    startup por causa de dado de dominio.
    """
    inseridas = 0
    for source, target, relation_type, rationale, condition in LIB_013A_RULES:
        try:
            row = conn.execute(
                text("SELECT "
                     "(SELECT id FROM exercises WHERE slug = :s) AS sid, "
                     "(SELECT id FROM exercises WHERE slug = :t) AS tid")
            .bindparams(s=source, t=target)).fetchone()
            if not row or row[0] is None or row[1] is None:
                logger.warning(f"LIB-013B: regra {source}->{target} ignorada (exercicio ausente)")
                continue
            res = conn.execute(
                text("INSERT INTO exercise_substitution_rules "
                     "(source_exercise_id, target_exercise_id, relation_type, rationale, condition, is_active) "
                     "VALUES (:sid, :tid, :rt, :ra, :cond, TRUE) "
                     "ON CONFLICT (source_exercise_id, target_exercise_id) DO NOTHING")
                .bindparams(sid=row[0], tid=row[1], rt=relation_type, ra=rationale, cond=condition))
            conn.commit()
            inseridas += res.rowcount or 0
        except Exception as e:
            conn.rollback()
            logger.error(f"LIB-013B: falha ao migrar regra {source}->{target}: {e}")
    if inseridas:
        logger.info(f"LIB-013B: {inseridas} regras de substituicao migradas.")