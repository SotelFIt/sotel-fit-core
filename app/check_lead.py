from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 70)
    print("[LEAD ONBOARDINGS - DADOS]")
    print("=" * 70)
    
    result = conn.execute(text("SELECT * FROM lead_onboardings LIMIT 10"))
    for row in result:
        print(f"\nRegistro:")
        for col_name, value in zip(result.keys(), row):
            print(f"  {col_name}: {value}")