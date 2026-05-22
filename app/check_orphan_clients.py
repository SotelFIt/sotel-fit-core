from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 70)
    print("[CLIENTES SEM SUBSCRIPTION]")
    print("=" * 70)
    
    result = conn.execute(text("""
        SELECT c.id, c.name, c.status, c.created_at 
        FROM clients c 
        WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.client_id = c.id)
        LIMIT 10
    """))
    
    for row in result:
        print(f"ID: {row[0]}, Nome: {row[1]}, Status: {row[2]}, Data: {row[3]}")