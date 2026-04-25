"""
Clients Router
CRUD de clientes com autenticação JWT
Validação de permissões: cliente só acessa a si mesmo, admin acessa qualquer um
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import verify_jwt_only, verify_dual_auth
from models.client import Client
from schemas.client import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/clients", tags=["clients"])


# ============================================================================
# HELPER: Validar permissão de acesso
# ============================================================================

def check_client_access(client_id: int, auth_client_id: int):
    """
    Valida se auth_client_id tem permissão de acessar client_id.
    
    - client_id=0 é admin (pode acessar qualquer um)
    - client_id>0 é cliente (só acessa a si mesmo)
    """
    if auth_client_id != 0 and auth_client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para acessar este cliente"
        )


# ============================================================================
# ENDPOINTS COM AUTENTICAÇÃO E PERMISSÃO
# ============================================================================

@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Cliente",
    description="Cria novo cliente. Requer JWT ou x-api-key (admin)."
)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    """
    Criar novo cliente

    Autenticação: 
    - Header `Authorization: Bearer <jwt_token>` (cliente novo)
    - OU Header `x-api-key: <token>` (admin)

    Body:
```json
    {
      "name": "João",
      "email": "joao@example.com",
      "phone": "+5511999999999",
      "objective": "Ganhar massa",
      "difficulty": "avançado"
    }
```
    """

    # Validar se cliente já existe
    existing = db.query(Client).filter(Client.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cliente com este email já existe"
        )

    new_client = Client(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        objective=payload.objective,
        difficulty=payload.difficulty
    )

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return new_client


@router.get(
    "",
    response_model=List[ClientResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar Clientes",
    description="Lista todos os clientes (admin) ou retorna o cliente autenticado."
)
def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    """
    Listar clientes com paginação

    Autenticação: Header `Authorization: Bearer <jwt_token>` ou `x-api-key`

    Permissão:
    - Admin (x-api-key): lista TODOS os clientes
    - Cliente (JWT): lista apenas a si mesmo

    Query:
    - skip: quantos pular (padrão 0)
    - limit: quantos retornar (padrão 100, máx 500)
    """

    if auth_client_id == 0:
        # Admin: retorna todos
        clients = db.query(Client).offset(skip).limit(min(limit, 500)).all()
    else:
        # Cliente: retorna apenas a si mesmo
        client = db.query(Client).filter(Client.id == auth_client_id).first()
        clients = [client] if client else []

    return clients


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter Cliente",
    description="Obtém detalhes de um cliente. Requer autenticação."
)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    """
    Obter detalhes de um cliente

    Autenticação: Header `Authorization: Bearer <jwt_token>` ou `x-api-key`

    Permissão:
    - Admin (x-api-key): acessa qualquer cliente
    - Cliente (JWT): acessa apenas a si mesmo
    """

    # Validar permissão
    check_client_access(client_id, auth_client_id)

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado"
        )

    return client


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar Cliente",
    description="Atualiza dados de um cliente. Requer autenticação."
)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    """
    Atualizar cliente

    Autenticação: Header `Authorization: Bearer <jwt_token>` ou `x-api-key`

    Permissão:
    - Admin (x-api-key): edita qualquer cliente
    - Cliente (JWT): edita apenas a si mesmo

    Body (todos os campos opcionais):
```json
    {
      "name": "João Silva",
      "email": "joao@example.com",
      "phone": "+5511999999999",
      "objective": "Ganhar massa",
      "difficulty": "avançado"
    }
```
    """

    # Validar permissão
    check_client_access(client_id, auth_client_id)

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado"
        )

    # Atualizar apenas campos fornecidos
    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)

    return client


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar Cliente",
    description="Deleta um cliente. Apenas admin (x-api-key)."
)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    auth_client_id: int = Depends(verify_dual_auth)
):
    """
    Deletar cliente (apenas admin)

    Autenticação: Header `x-api-key` (admin only)

    Permissão: Apenas admin pode deletar
    """

    # Apenas admin pode deletar
    if auth_client_id != 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas admin pode deletar clientes"
        )

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente não encontrado"
        )

    db.delete(client)
    db.commit()

    return None
