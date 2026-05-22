from sqlalchemy import create_engine, text

PROD_DB = "postgresql://postgres:UDTvvLDXJuMXNDvFGBKIOyEzCuqfCEmi@postgres.railway.internal:5432/railway"

# Para usar apenas localmente via SSH ou tunnel
# Por agora, vamos apenas documentar

print("=" * 70)
print("AUDITORIA DE LEADS EM PRODUÇÃO")
print("=" * 70)
print("\n⚠️ Há 3 lead_onboardings em produção")
print("\nPróximo passo: verificar via Railway UI quais são")
print("  - Se contêm dados de teste → deletar")
print("  - Se contêm dados reais → manter")
print("\n" + "=" * 70)