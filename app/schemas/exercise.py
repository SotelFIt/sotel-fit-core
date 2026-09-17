"""
Schemas de dominio da Biblioteca de Exercicios V1 (LIB-002).
Validacao dos campos da tabela exercises. Sem endpoints nesta missao.
"""
import re
from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# slug URL-safe, um unico segmento: sem '/', sem espacos, so caracteres unreserved.
# Sem ancoras: a validacao usa fullmatch (ancora inicio E fim de forma exata),
# evitando o '$' que aceitaria uma quebra de linha final ("supino\n").
SLUG_RE = re.compile(r"[A-Za-z0-9._~-]+")
# Segmentos de path especiais que nunca podem ser slug (traversal).
SLUG_RESERVED = {".", ".."}

ExerciseLevel = Literal["iniciante", "intermediario", "avancado"]


# Formatos aceitos para DEMONSTRACAO. Curtos, sem audio, eficientes em rede
# movel. `type` deixou de ser string livre: sem restricao, nada impedia gravar
# "video/quicktime" ou "youtube" e o cliente descobrir isso em producao.
MEDIA_TYPES = ("video/mp4", "video/webm", "image/webp", "image/gif")
# Extensao esperada por tipo — a checagem cruzada pega URL trocada.
MEDIA_EXT = {
    "video/mp4": (".mp4",),
    "video/webm": (".webm",),
    "image/webp": (".webp",),
    "image/gif": (".gif",),
}
POSTER_EXT = (".jpg", ".jpeg", ".png", ".webp")

# Procedencia do arquivo. Obrigatoria: e o que permite responder "de quem e
# isso?" sem abrir o Cloudinary.
#
#   sotel_proprio  gravado pela Sotel. Publicavel.
#   licenciado     comprado de fornecedor. Publicavel SOMENTE com os dados da
#                  licenca preenchidos (ver LicencaMedia).
#   fixture_teste  arquivo sintetico de teste. NUNCA publicavel — existe para
#                  provar o fluxo tecnico sem acervo real.
#
# Nao existe valor para "material de terceiro sem autorizacao": a ausencia e
# proposital, e um `licenciado` sem licenca cai exatamente nesse caso e e
# recusado.
MediaSource = Literal["sotel_proprio", "licenciado", "fixture_teste"]

# Como o direito de uso foi obtido.
#
#   comprada  aquisicao paga. Tem comprovante e, portanto, `referencia`.
#   gratuita  biblioteca liberada pelo fornecedor. NAO tem comprovante: exigir
#             um numero de pedido aqui obrigaria a inventar um, e um dado
#             inventado destroi exatamente a auditoria que este bloco existe
#             para sustentar. A identidade do arquivo e o `checksum`.
ModalidadeLicenca = Literal["comprada", "gratuita"]

# Procedencias que podem chegar ao cliente.
FONTES_PUBLICAVEIS = ("sotel_proprio", "licenciado")


class LicencaMedia(BaseModel):
    """Direitos de uso de midia licenciada. **PRIVADA**.

    Nunca sai na resposta publica do cliente — `_public()` remove este bloco.
    Guarda a RASTREABILIDADE, nao o documento: `referencia` e o identificador
    interno do comprovante (numero do pedido, id no arquivo do Proprietario),
    jamais o recibo, o PDF ou dados de pagamento.

    `produto_url` aponta para a PAGINA do produto no fornecedor, nunca para o
    arquivo — o arquivo publicado e o que esta no nosso armazenamento.
    """

    fornecedor: str = Field(min_length=2, max_length=80)
    produto_url: str = Field(min_length=1, max_length=500)
    modalidade: ModalidadeLicenca
    # A pagina de origem precisa AUTORIZAR uso comercial. Sem default de
    # proposito: `True` publicaria por suposicao, `False` bloquearia em
    # silencio. Quem cadastra declara.
    uso_comercial: bool
    adquirido_em: date
    # Quando os termos foram lidos. Termos de biblioteca gratuita mudam sem
    # aviso; esta data diz de quando e a NOSSA leitura, e nada mais.
    verificado_em: date
    # Obrigatoria na compra (numero do pedido). Na biblioteca gratuita nao
    # existe comprovante — ver ModalidadeLicenca.
    referencia: Optional[str] = Field(default=None, min_length=2, max_length=120)

    @field_validator("produto_url")
    @classmethod
    def _pagina_do_produto(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.lower().startswith("https://"):
            raise ValueError("produto_url deve ser https")
        return v

    @field_validator("referencia")
    @classmethod
    def _referencia_nao_e_o_comprovante(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        # Guarda contra colar o documento inteiro (ou um link de arquivo) aqui.
        proibido = (".pdf", ".jpg", ".png", "http://", "https://")
        if any(p in v.lower() for p in proibido):
            raise ValueError(
                "referencia e o identificador interno do comprovante, nao o "
                "documento nem um link para ele"
            )
        return v

    @model_validator(mode="after")
    def _compra_tem_comprovante(self):
        """Compra sem referencia e compra que ninguem consegue auditar."""
        if self.modalidade == "comprada" and not self.referencia:
            raise ValueError(
                "licenca comprada exige `referencia` (identificador interno do "
                "comprovante)"
            )
        return self


class ExerciseMedia(BaseModel):
    """Demonstracao vinculada a um exercicio canonico.

    `poster` existe porque o cliente mostra a imagem ANTES de baixar o video e
    nos pontos secundarios (proximo exercicio) nunca baixa o video.
    """
    type: Literal[MEDIA_TYPES]
    url: str = Field(min_length=1)
    poster: Optional[str] = None
    alt: Optional[str] = None
    source: MediaSource
    # PRIVADO: obrigatorio quando `source == "licenciado"`, proibido nos demais.
    licenca: Optional[LicencaMedia] = None

    # ---- identidade tecnica do arquivo ----------------------------------
    # Opcionais porque registros vinculados antes desta medicao continuam
    # validos. Preenchidos automaticamente pelo upload: ninguem digita isto.
    #
    # `width`/`height` nao sao enfeite: a demonstracao da YMove e VERTICAL
    # (720x1280) e a do acervo proprio pode ser horizontal. Sem a proporcao o
    # cliente desenha a moldura errada e sobra barra vazia dos dois lados.
    width: Optional[int] = Field(default=None, gt=0)
    height: Optional[int] = Field(default=None, gt=0)
    duration_s: Optional[float] = Field(default=None, gt=0)
    bytes: Optional[int] = Field(default=None, gt=0)
    # sha256 do arquivo publicado. E a identidade do arquivo — e, na licenca
    # gratuita, o unico "comprovante" que existe. PRIVADO: nao vai ao cliente.
    checksum: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _url_https(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.lower().startswith("https://"):
            raise ValueError("url da midia deve ser https")
        return v

    @field_validator("poster")
    @classmethod
    def _poster_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.lower().startswith("https://"):
            raise ValueError("poster deve ser https")
        if not any(v.lower().split("?")[0].endswith(e) for e in POSTER_EXT):
            raise ValueError(f"poster deve terminar em {', '.join(POSTER_EXT)}")
        return v

    @model_validator(mode="after")
    def _procedencia_coerente(self):
        """Licenciado SEM licenca e midia sem procedencia comprovada."""
        if self.source == "licenciado" and self.licenca is None:
            raise ValueError(
                "midia licenciada exige os dados da licenca (fornecedor, "
                "produto_url, adquirido_em, referencia)"
            )
        if self.source != "licenciado" and self.licenca is not None:
            raise ValueError(
                f"licenca so faz sentido em midia licenciada, nao em '{self.source}'"
            )
        return self

    @field_validator("checksum")
    @classmethod
    def _checksum_sha256(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = v.strip().lower()
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("checksum deve ser sha256 em hexadecimal (64 caracteres)")
        return v

    @property
    def orientacao(self) -> Optional[str]:
        """`vertical`, `horizontal` ou `quadrada` — derivada, nunca digitada."""
        if not self.width or not self.height:
            return None
        if self.height > self.width:
            return "vertical"
        if self.width > self.height:
            return "horizontal"
        return "quadrada"

    @property
    def publicavel(self) -> bool:
        """Pode chegar ao cliente?

        Fixture de teste, nunca. Licenciada, somente se a licenca declarar uso
        comercial: material cujo direito nao autoriza o nosso uso nao vira
        demonstracao so porque alguem preencheu o formulario.
        """
        if self.source not in FONTES_PUBLICAVEIS:
            return False
        if self.source == "licenciado":
            return bool(self.licenca and self.licenca.uso_comercial)
        return True

    @model_validator(mode="after")
    def _extensao_bate_com_tipo(self):
        esperadas = MEDIA_EXT[self.type]
        caminho = self.url.lower().split("?")[0]
        if not any(caminho.endswith(e) for e in esperadas):
            raise ValueError(
                f"url nao corresponde a {self.type}: esperado {', '.join(esperadas)}"
            )
        return self


class ExerciseMediaPublica(BaseModel):
    """A midia como ela chega ao CLIENTE.

    Nao e a mesma coisa que a midia ARMAZENADA. Aqui `licenca` e `checksum`
    nao sao "removidos": eles simplesmente **nao existem neste contrato**.

    A diferenca e o que corrige um defeito real: `ExerciseMedia` exige licenca
    quando `source == "licenciado"`. Ao tirar a licenca para responder ao aluno,
    o objeto violava a propria regra e o `response_model` derrubava a resposta
    — `GET /exercises/{slug}` respondia **500** para todo exercicio com midia
    licenciada, deixando o exercicio inteiro sem orientacao na tela de Treino.

    Separar as duas formas resolve na estrutura, nao no remendo: o que e privado
    nao tem por onde vazar, e o OpenAPI publico deixa de anunciar campo privado.
    """

    type: Literal[MEDIA_TYPES]
    url: str
    poster: Optional[str] = None
    alt: Optional[str] = None
    source: MediaSource
    # A proporcao vai junto: sem ela o cliente desenha a moldura no palpite.
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    bytes: Optional[int] = None


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
    is_active: bool = True


class ExerciseResponse(ExerciseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExercisePublicResponse(ExerciseResponse):
    """Resposta das rotas de LEITURA. Identica a administrativa, exceto pela
    midia: aqui ela e `ExerciseMediaPublica` (sem licenca, sem checksum)."""

    media: List[ExerciseMediaPublica] = Field(default_factory=list)


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
