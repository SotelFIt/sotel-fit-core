from sqlalchemy import create_engine, text, inspect
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL)

print("=" * 70)
print("AUDITORIA DE LIMPEZA — SOTEL FIT CORE")
print("=" * 70)

inspector = inspect(engine)
tables = inspector.get_table_names()

with engine.connect() as conn:
    print("\n[CONTAGEM DE REGISTROS POR TABELA]")
    for table in tables:
        try:
            total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            status = "✓ LIMPO" if total == 0 else f"⚠️ {total} registros"
            print(f"  {table:25} → {status}")
        except Exception as e:
            print(f"  {table:25} → ❌ Erro")
    
    # Verificar dados em plans
    print("\n[PLANS - ESTRUTURA]")
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM plans")).scalar()
        print(f"  Total: {result}")
        cols = inspector.get_columns('plans')
        print("  Colunas:", [c['name'] for c in cols])
    except Exception as e:
        print(f"  Erro: {str(e)[:60]}")
    
    # Verificar dados em diets
    print("\n[DIETS - ESTRUTURA]")
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM diets")).scalar()
        print(f"  Total: {result}")
        cols = inspector.get_columns('diets')
        print("  Colunas:", [c['name'] for c in cols])
    except Exception as e:
        print(f"  Erro: {str(e)[:60]}")

print("\n" + "=" * 70)