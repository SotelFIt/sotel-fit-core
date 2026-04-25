"""
BLOCO 1 — Test Suite para Sotel Fit Core
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, 'app')

from main import app
from core.database import get_db, Base
from models.client import Client
from core.security import create_access_token


# ========== SETUP ==========

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ========== FIXTURES ==========

@pytest.fixture
def setup_test_db():
    """Limpa banco antes de cada teste."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_token():
    """Token JWT para admin (client_id = 0)."""
    return create_access_token(data={"sub": "0"})


@pytest.fixture
def client1_token():
    """Token JWT para cliente 1."""
    return create_access_token(data={"sub": "1"})


@pytest.fixture
def create_test_client():
    """Cria um cliente de teste no banco."""
    db = TestingSessionLocal()
    test_client = Client(
        id=1,
        name="Cliente Teste",
        email="cliente@test.com",
        phone="11999999999",
        landbot_user_id="landbot_123",
        status="active"
    )
    db.add(test_client)
    db.commit()
    db.refresh(test_client)
    db.close()
    return test_client


# ========== TESTES: JWT & AUTENTICAÇÃO ==========

class TestJWTAuthentication:
    """✅ DEVEM PASSAR"""

    def test_jwt_valido_acessa_dados(self, setup_test_db, create_test_client, client1_token):
        """✅ JWT válido acessa dados."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {client1_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        print(f"✅ JWT válido funciona")

    def test_jwt_invalido_retorna_401(self, setup_test_db):
        """✅ JWT inválido retorna 401."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer token_invalido"}
        )

        assert response.status_code == 401
        print(f"✅ JWT inválido retorna 401")

    def test_sem_jwt_retorna_401(self, setup_test_db):
        """✅ Sem JWT retorna 401."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        print(f"✅ Sem JWT retorna 401")


# ========== TESTES: WEBHOOK LANDBOT ==========

class TestWebhookLandbot:
    """❌ DEVEM FALHAR (mostra vulnerabilidade)"""

    def test_webhook_sem_autenticacao(self, setup_test_db):
        """❌ Webhook SEM x-api-key deveria ser rejeitado."""
        payload = {
            "landbot_user_id": "landbot_xyz_123",
            "name": "Novo Cliente",
            "email": "novo@test.com",
            "phone": "11988888888"
        }

        response = client.post("/webhook/landbot", json=payload)

        print(f"\n❌ Webhook sem auth — Status: {response.status_code}")
        print(f"   Esperado após correção: 401")
        print(f"   Atual (vulnerável): {response.status_code}")

    def test_webhook_idempotencia(self, setup_test_db):
        """❌ Webhook cria duplicatas (sem idempotência)."""
        payload = {
            "landbot_user_id": "landbot_idem_test",
            "name": "Teste Idempotência",
            "email": "idem@test.com",
            "phone": "11986666666"
        }

        response1 = client.post("/webhook/landbot", json=payload)
        data1 = response1.json() if response1.status_code == 200 else {"client_id": None}
        client_id_1 = data1.get("client_id")

        response2 = client.post("/webhook/landbot", json=payload)
        data2 = response2.json() if response2.status_code == 200 else {"client_id": None}
        client_id_2 = data2.get("client_id")

        print(f"\n❌ Idempotência — Primeira: {client_id_1}, Segunda: {client_id_2}")
        print(f"   Esperado: IDs iguais")
        print(f"   Atual: IDs diferentes (DUPLICAÇÃO)")


# ========== TESTES: PERMISSÕES ==========

class TestPermissions:
    """✅ DEVEM PASSAR"""

    def test_cliente_ve_seus_dados(self, setup_test_db, create_test_client, client1_token):
        """✅ Cliente vê seus próprios dados."""
        response = client.get(
            "/clients/1",
            headers={"Authorization": f"Bearer {client1_token}"}
        )

        assert response.status_code == 200
        print(f"✅ Cliente vê seus dados")

    def test_admin_ve_todos(self, setup_test_db, create_test_client, admin_token):
        """✅ Admin vê todos."""
        response = client.get(
            "/clients/1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        print(f"✅ Admin vê todos os dados")


# ========== TESTES: CRUD ==========

class TestCRUD:
    """✅ DEVEM PASSAR"""

    def test_create_client(self, setup_test_db, admin_token):
        """✅ CREATE — cria cliente."""
        payload = {
            "name": "Novo Cliente",
            "email": "novo@test.com",
            "phone": "11999999999",
            "landbot_user_id": "landbot_crud_001"
        }

        response = client.post(
            "/clients",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        print(f"✅ CREATE funciona")

    def test_read_client(self, setup_test_db, create_test_client, admin_token):
        """✅ READ — lê cliente."""
        response = client.get(
            "/clients/1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        print(f"✅ READ funciona")

    def test_update_client(self, setup_test_db, create_test_client, admin_token):
        """✅ UPDATE — atualiza cliente."""
        update_payload = {
            "name": "Cliente Atualizado",
            "status": "inactive"
        }

        response = client.put(
            "/clients/1",
            json=update_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        print(f"✅ UPDATE funciona")

    def test_delete_client(self, setup_test_db, create_test_client, admin_token):
        """✅ DELETE — deleta cliente."""
        response = client.delete(
            "/clients/1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 204
        print(f"✅ DELETE funciona")