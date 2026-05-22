from sqlalchemy import create_engine, text, inspect
import os

# DATABASE_URL de produção
PROD_DB = "postgresql://postgres:UDTvvLDXJuMXNDvFGBKIOyEzCuqfCEmi@postgres.railway.internal:5432/railway"

try:
    engine = create_engine(PROD_DB)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("=" * 70)
    print("AUDITORIA DE LIMPEZA — BANCO DE PRODUÇÃO (RAILWAY)")
    print("=" * 70)

    with engine.connect() as conn:
        print("\n[CONTAGEM DE REGISTROS POR TABELA]")
        for table in sorted(tables):
            try:
                total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                status = "✓ LIMPO" if total == 0 else f"⚠️ {total} registros"
                print(f"  {table:25} → {status}")
            except Exception as e:
                print(f"  {table:25} → ❌ Erro")

    print("\n" + "=" * 70)
    print("✅ Conexão com produção bem-sucedida!")
    print("=" * 70)

except Exception as e:
    print(f"❌ Erro ao conectar: {e}")