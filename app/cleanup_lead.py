from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 70)
    print("[DELETANDO REGISTRO DE TESTE]")
    print("=" * 70)
    
    # Verificar antes
    before = conn.execute(text("SELECT COUNT(*) FROM lead_onboardings")).scalar()
    print(f"\nAntes: {before} registros")
    
    # Deletar
    conn.execute(text("DELETE FROM lead_onboardings WHERE id = 1"))
    conn.commit()
    
    # Verificar depois
    after = conn.execute(text("SELECT COUNT(*) FROM lead_onboardings")).scalar()
    print(f"Depois: {after} registros")
    print("\n✅ Registro deletado com sucesso!")
    
print("=" * 70)