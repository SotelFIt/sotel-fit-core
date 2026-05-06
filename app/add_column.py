import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE conversation_states 
        ADD COLUMN IF NOT EXISTS onboarding_link_sent BOOLEAN DEFAULT FALSE
    """))
    conn.commit()
    print("Coluna adicionada com sucesso!")