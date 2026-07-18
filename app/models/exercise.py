"""
Exercise - Biblioteca de Exercicios V1 (LIB-002).
Fundacao tecnica: somente a tabela. Sem endpoints, sem CRUD, sem integracao
com os planos texto atuais.

Autoridade de schema (decisao do Proprietario, 2026-07-17):
- a tabela nasce via Base.metadata.create_all() (mecanismo real de producao);
- constraints que o create_all nao garante (trigger de imutabilidade do slug
  no PostgreSQL) vivem em migrate.py, de forma especifica e idempotente.
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func, event, text
from sqlalchemy import Enum as SAEnum, JSON, true
from sqlalchemy.orm.attributes import NO_VALUE
from core.database import Base

EXERCISE_LEVELS = ("iniciante", "intermediario", "avancado")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    # slug: identificador estavel, unico e IMUTAVEL (listener ORM + trigger PG no migrate.py)
    slug = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    primary_muscle = Column(String, nullable=False)
    secondary_muscles = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    equipment = Column(String, nullable=False)
    level = Column(
        SAEnum(
            *EXERCISE_LEVELS,
            name="exercise_level",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    instructions = Column(Text, nullable=True)
    common_errors = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    cautions = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    # lista de slugs de outros exercicios desta biblioteca
    approved_substitutions = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    # lista de objetos {type, url, alt?} - midia futura; nasce vazia
    media = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


@event.listens_for(Exercise.slug, "set", retval=True)
def _exercise_slug_immutable(target, value, oldvalue, initiator):
    """Protecao ORM da regra: slug e imutavel apos definido.
    A garantia no BANCO (bulk updates, SQL direto) e o trigger PostgreSQL
    criado em migrate.py (exercises_slug_immutable)."""
    if oldvalue is not NO_VALUE and oldvalue is not None and oldvalue != value:
        raise ValueError("Exercise.slug e imutavel e nao pode ser alterado")
    return value
