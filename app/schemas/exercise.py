"""
Schemas de dominio da Biblioteca de Exercicios V1 (LIB-002).
Validacao dos campos da tabela exercises. Sem endpoints nesta missao.
"""
import re
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# slug URL-safe, um unico segmento: sem '/', sem espacos, so caracteres unreserved.
# Sem ancoras: a validacao usa fullmatch (ancora inicio E fim de forma exata),
# evitando o '$' que aceitaria uma quebra de linha final ("supino\n").
SLUG_RE = re.compile(r"[A-Za-z0-9._~-]+")
# Segmentos de path especiais que nunca podem ser slug (traversal).
SLUG_RESERVED = {".", ".."}

ExerciseLevel = Literal["iniciante", "intermediario", "avancado"]


class ExerciseMedia(BaseModel):
    """Item de midia futura: {type, url, alt?}."""
    type: str = Field(min_length=1)
    url: str = Field(min_length=1)
    alt: Optional[str] = None


class ExternalDemo(BaseModel):
    """Referencia ESTAVEL a uma demonstracao de fornecedor externo.

    Extensao explicita do contrato de midia, nao afrouxamento dele: `media[]`
    continua sendo o acervo que NOS hospedamos, com as validacoes que ja tem.
    Aqui mora outra coisa — um ponteiro para o catalogo de terceiro.

    O que NAO entra aqui, por contrato do fornecedor: `videoUrl` e
    `videoHlsUrl`. Sao pre-assinadas e expiram em 48h; persistir qualquer uma
    criaria um link que quebra sozinho em dois dias. A URL e pedida na hora em
    que o aluno aperta "Ver execucao".

    `thumbnail_url` entra porque o contrato diz que ele e estatico e nao expira
    — quando ele existe, e ele que da previa ao aluno sem consumir cota.

    E OPCIONAL de proposito. Nos planos com limite de exercicios o fornecedor
    nao devolve thumbnail em browse mode ("on the capped plans they are not"),
    entao exigir capa aqui impediria de salvar um vinculo correto. Vinculo sem
    capa e vinculo valido: o aluno ve o botao de execucao sem previa.
    """

    provider: Literal["ymove"]
    exercise_id: str = Field(min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=200)
    title: Optional[str] = Field(default=None, max_length=300)
    # Variante de demonstracao (tag do fornecedor), quando houver mais de uma.
    variant: Optional[str] = Field(default=None, max_length=60)
    thumbnail_url: Optional[str] = None
    orientation: Optional[str] = Field(default=None, max_length=20)
    duration_secs: Optional[int] = Field(default=None, ge=0)
    linked_at: Optional[datetime] = None

    @field_validator("thumbnail_url")
    @classmethod
    def _thumb_https_do_fornecedor(cls, v: Optional[str]) -> Optional[str]:
        """So https, e so do dominio do fornecedor.

        Aceitar URL arbitraria transformaria este campo num proxy aberto para
        qualquer endereco — exatamente o que nao pode existir aqui.
        """
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.lower().startswith("https://"):
            raise ValueError("thumbnail_url deve ser https")
        host = v.split("/")[2].lower() if len(v.split("/")) > 2 else ""
        if not (host == "ymove.app" or host.endswith(".ymove.app")):
            raise ValueError("thumbnail_url deve vir do dominio do fornecedor")
        return v

    @model_validator(mode="after")
    def _sem_url_assinada(self):
        """Guarda contra o erro que o contrato do fornecedor torna caro.

        Se algum dia alguem colar aqui uma URL de video, ela expira em 48h e o
        aluno fica com um link morto. O campo nem existe — esta checagem pega a
        tentativa de disfarca-la no thumbnail.
        """
        suspeito = (self.thumbnail_url or "").lower()
        for marca in ("x-amz-signature", "x-amz-expires", "signature=", "expires=", "token="):
            if marca in suspeito:
                raise ValueError("thumbnail_url nao pode ser uma URL assinada (expira)")
        return self


class ExerciseBase(BaseModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: List[str] = Field(default_factory=list)
    primary_muscle: str = Field(min_length=1)
    secondary_muscles: List[str] = Field(default_factory=list)
    equipment: str = Field(min_length=1)
    level: ExerciseLevel
    instructions: Optional[str] = None
    common_errors: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)
    approved_substitutions: List[str] = Field(default_factory=list)
    media: List[ExerciseMedia] = Field(default_factory=list)
    external_demo: Optional[ExternalDemo] = None
    is_active: bool = True


class ExerciseResponse(ExerciseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------- LIB-003 (API) ----------------

class ExerciseCreate(ExerciseBase):
    """Payload de criacao administrativa. Herda todas as validacoes de campo
    de ExerciseBase (obrigatorios, enum de nivel, formato de midia)."""

    @field_validator("slug")
    @classmethod
    def _slug_url_safe(cls, v: str) -> str:
        # BLOCKER 3: rejeita slug que inviabiliza a rota ('/', espacos, invalidos).
        # 2a auditoria: fullmatch (nao match/'$', que aceitava '\n' final) e
        # rejeicao explicita dos segmentos especiais '.' e '..'.
        if v in SLUG_RESERVED or not SLUG_RE.fullmatch(v or ""):
            raise ValueError(
                "slug deve ser URL-safe e um unico segmento (apenas letras, numeros "
                "e '-', '_', '.', '~'; sem '/' nem espacos; '.' e '..' proibidos)"
            )
        return v


class ExerciseUpdate(BaseModel):
    """Edicao administrativa parcial (PATCH). Todos os campos opcionais.

    `slug` e aceito apenas para deteccao explicita de tentativa de alteracao:
    o endpoint responde 409 se vier diferente do slug do path (slug e imutavel).
    A desativacao logica e feita via `is_active=false` (sem exclusao fisica).
    """
    slug: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1)
    aliases: Optional[List[str]] = None
    primary_muscle: Optional[str] = Field(default=None, min_length=1)
    secondary_muscles: Optional[List[str]] = None
    equipment: Optional[str] = Field(default=None, min_length=1)
    level: Optional[ExerciseLevel] = None
    instructions: Optional[str] = None
    common_errors: Optional[List[str]] = None
    cautions: Optional[List[str]] = None
    approved_substitutions: Optional[List[str]] = None
    media: Optional[List[ExerciseMedia]] = None
    is_active: Optional[bool] = None

    # BLOCKER 2: campos NAO-anulaveis do contrato nao aceitam null explicito.
    # Omitir o campo => nao altera (exclude_unset no endpoint). Enviar null => 422,
    # nunca IntegrityError/500 nem estado invalido persistido. `instructions` fica
    # de fora por ser o unico campo anulavel no model.
    @field_validator(
        "slug", "name", "aliases", "primary_muscle", "secondary_muscles", "equipment",
        "level", "common_errors", "cautions", "approved_substitutions",
        "media", "is_active",
        mode="before",
    )
    @classmethod
    def _reject_explicit_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} nao pode ser null")
        return v
