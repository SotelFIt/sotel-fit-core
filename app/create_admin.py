import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from core.database import SessionLocal
from models.admin import Admin
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()
admin = Admin(
    email="sotel@admin.com",
    hashed_password=pwd_context.hash("admin123"),
    name="Sotel"
)
db.add(admin)
db.commit()
print("Admin criado com sucesso!")
db.close()
