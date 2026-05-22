from datetime import datetime, timedelta
import jwt
import os

# Usar mesma SECRET de produção
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ec/hBUFhntUNSkRbbVVo6CnWDokXV2b8TMLI5VmcFd8=")

# Gerar token com timestamps atuais (sincronizados com UTC)
now = datetime.utcnow()
payload = {
    "sub": 2,
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(hours=24)).timestamp()),
    "type": "access"
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print("Token novo:")
print(token)
print("\nUse este token para testes em produção.")