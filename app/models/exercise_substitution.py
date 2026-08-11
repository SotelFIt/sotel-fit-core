"""
ExerciseSubstitutionRule - regras DIRECIONAIS de substituicao (LIB-013B).

Substitui `Exercise.approved_substitutions` (lista de slugs) como FONTE DA VERDADE.
Aquele campo respondia apenas "SIM"; a ausencia de aresta confundia tres coisas
diferentes: par nao avaliado, par rejeitado e par que depende de contexto.

Aqui cada par avaliado vira UMA LINHA com direcao explicita:

    source -> target : relation_type + rationale (+ condition)

A relacao inversa NUNCA e inferida. Se A substitui B e B substitui A, sao DUAS
linhas - duas decisoes distintas, tomadas separadamente. Nao existe
`bidirectional=true` de proposito: esconder duas decisoes em uma linha foi
exatamente o defeito que motivou esta tabela.

Ausencia de linha significa NAO AVALIADO. Nunca significa rejeitado.
"""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Text,
    UniqueConstraint, func, true,
)
from sqlalchemy import Enum as SAEnum

from core.database import Base

# direct     -> alta equivalencia funcional            -> YES
# acceptable -> substitui, mas ha diferenca relevante  -> YES
# contextual -> so vale sob condicao declarada         -> DEPENDS (exige `condition`)
# rejected   -> avaliado e NAO aprovado                -> NO
RELATION_TYPES = ("direct", "acceptable", "contextual", "rejected")


class ExerciseSubstitutionRule(Base):
    __tablename__ = "exercise_substitution_rules"
    __table_args__ = (
        # o mesmo par so pode ter UMA decisao por direcao
        UniqueConstraint("source_exercise_id", "target_exercise_id",
                         name="uq_substitution_source_target"),
        # um exercicio nao substitui a si mesmo
        CheckConstraint("source_exercise_id <> target_exercise_id",
                        name="ck_substitution_nao_autorreferente"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_exercise_id = Column(
        Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_exercise_id = Column(
        Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type = Column(
        SAEnum(
            *RELATION_TYPES,
            name="exercise_relation_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    # por que esta decisao foi tomada - obrigatorio: relacao sem racional nao e auditavel
    rationale = Column(Text, nullable=False)
    # em que contexto vale - obrigatorio quando relation_type = 'contextual'
    condition = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
