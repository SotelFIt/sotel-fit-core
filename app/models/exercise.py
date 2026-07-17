"""
Exercise - Biblioteca de Exercicios V1 (LIB-002).
Fundacao tecnica: somente a tabela. Sem endpoints, sem CRUD, sem integracao
com os planos texto atuais. Contrato aprovado pelo Proprietario em 2026-07-17.
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func, event
from sqlalchemy import Enum as SAEnum, JSON
from sqlalchemy.orm.attributes import NO_VALUE
from core.database import Base

EXERCISE_LEVELS = ("iniciante", "intermediario", "avancado")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    # slug: identificador estavel, unico e IMUTAVEL (ver listener abaixo)
    slug = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    primary_muscle = Column(String, nullable=False)
    secondary_muscles = Column(JSON, nullable=False, default=list)
    equipment = Column(String, nullable=False)
    level = Column(
        SAEnum(*EXERCISE_LEVELS, name="exercise_level", native_enum=False, validate_strings=True),
        nullable=False,
    )
    instructions = Column(Text, nullable=True)
    common_errors = Column(JSON, nullable=False, default=list)
    cautions = Column(JSON, nullable=False, default=list)
    # lista de slugs de outros exercicios desta biblioteca
    approved_substitutions = Column(JSON, nullable=False, default=list)
    # lista de objetos {type, url, alt?} - midia futura; nasce vazia
    media = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


@event.listens_for(Exercise.slug, "set", retval=True)
def _exercise_slug_immutable(target, value, oldvalue, initiator):
    """Regra obrigatoria da LIB-002: slug e imutavel apos definido."""
    if oldvalue is not NO_VALUE and oldvalue is not None and oldvalue != value:
        raise ValueError("Exercise.slug e imutavel e nao pode ser alterado")
    return value
