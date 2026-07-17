"""
Schemas de dominio da Biblioteca de Exercicios V1 (LIB-002).
Validacao dos campos da tabela exercises. Sem endpoints nesta missao.
"""
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ExerciseLevel = Literal["iniciante", "intermediario", "avancado"]


class ExerciseMedia(BaseModel):
    """Item de midia futura: {type, url, alt?}."""
    type: str = Field(min_length=1)
    url: str = Field(min_length=1)
    alt: Optional[str] = None


class ExerciseBase(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    primary_muscle: str = Field(min_length=1)
    secondary_muscles: List[str] = Field(default_factory=list)
    equipment: str = Field(min_length=1)
    level: ExerciseLevel
    instructions: Optional[str] = None
    common_errors: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    approved_substitutions: List[str] = Field(default_factory=list)
    media: List[ExerciseMedia] = Field(default_factory=list)
    is_active: bool = True


class ExerciseResponse(ExerciseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
