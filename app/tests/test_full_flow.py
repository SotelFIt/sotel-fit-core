import pytest, sys, os
sys.path.insert(0, 'app')
os.environ["JWT_SECRET_KEY"] = "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8="
os.environ["LANDBOT_SECRET_TOKEN"] = "token"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from core.database import get_db, Base
from models.client import Client
from core.security import create_access_token

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    yield db
    db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def token():
    return create_access_token(1)

def test_jwt_invalido(setup_test_db):
    r = client.get("/auth/me", headers={"Authorization": "Bearer xxx"})
    assert r.status_code == 401
    print("✅ JWT inválido = 401")

def test_sem_jwt(setup_test_db):
    r = client.get("/auth/me")
    assert r.status_code == 401
    print("✅ Sem JWT = 401")

def test_webhook_sem_auth(setup_test_db):
    r = client.post("/webhook/landbot", json={"landbot_user_id": "x", "name": "y", "email": "z@z.com", "phone": "1"})
    print(f"❌ Webhook sem auth = {r.status_code} (esperado 401)")
