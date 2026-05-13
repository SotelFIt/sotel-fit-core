"""
Backup manual do banco Postgres do Railway.
Uso: python backup.py
Gera um arquivo SQL na pasta backups/ com data e hora.
"""
import subprocess
import os
from datetime import datetime

# Pega a DATABASE_URL do Railway (copie do painel Variables)
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERRO: DATABASE_URL nao definida.")
    print("Uso: $env:DATABASE_URL='postgresql://...' ; python backup.py")
    exit(1)

# Cria pasta backups se nao existir
os.makedirs("backups", exist_ok=True)

# Nome do arquivo com timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"backups/sotel_fit_core_{timestamp}.sql"

print(f"Iniciando backup -> {filename}")

try:
    result = subprocess.run(
        ["pg_dump", "--no-password", "--clean", "--if-exists", DATABASE_URL],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERRO no pg_dump:\n{result.stderr}")
        exit(1)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(result.stdout)

    size = os.path.getsize(filename)
    print(f"Backup concluido: {filename} ({size} bytes)")

except FileNotFoundError:
    print("ERRO: pg_dump nao encontrado.")
    print("Instale o PostgreSQL client: https://www.postgresql.org/download/")