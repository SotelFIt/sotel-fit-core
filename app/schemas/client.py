"""
schemas/client.py
Schemas para CRUD de clientes
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field

# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class ClientCreate(BaseModel):
    """Criar novo cliente"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    objective: str = Field(..., min_length=1, max_length=255)
    difficulty: str = Field(..., min_length=1, max_length=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "+5511999999999",
                "objective": "Perder peso",
                "difficulty": "iniciante"
            }
        }


class ClientUpdate(BaseModel):
    """Atualizar cliente (todos os campos opcionais)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    objective: Optional[str] = Field(None, min_length=1, max_length=255)
    difficulty: Optional[str] = Field(None, min_length=1, max_length=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "João Silva Updated"
            }
        }


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class ClientResponse(BaseModel):
    """Resposta: cliente"""
    id: int
    name: str
    email: str
    phone: str
    objective: str
    difficulty: str
    
    class Config:
        from_attributes = True  # Pydantic v2
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "+5511999999999",
                "objective": "Perder peso",
                "difficulty": "iniciante"
            }
        }


class ClientWithTokenResponse(ClientResponse):
    """Resposta: cliente + tokens JWT"""
    access_token: str = Field(..., description="JWT access token (24h)")
    refresh_token: str = Field(..., description="JWT refresh token (7 dias)")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Segundos até expiração do access token")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "+5511999999999",
                "objective": "Perder peso",
                "difficulty": "iniciante",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 86400
            }
        }