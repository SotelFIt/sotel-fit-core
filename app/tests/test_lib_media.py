"""
LIB-MEDIA — contrato da demonstração e vínculo canônico escolhido por humano.

O que estes testes protegem
---------------------------
1. `media.type` era string livre. Nada impedia gravar "youtube" ou
   "video/quicktime" e o cliente descobrir isso em produção.
2. A resolução `nome → slug` é heurística e falha em silêncio: nos planos reais
   **106 de 187 ocorrências (57%)** não casam com exercício nenhum. Quando um
   profissional escolhe o exercício à mão, essa escolha não pode ser
   sobrescrita pela heurística na próxima republicação.
3. Material de terceiro sem autorização não pode entrar na Biblioteca.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault("JWT_SECRET_KEY", "ec/hBUFhntuNSkRbbVvo6CnWDOkXV2b8TMLI5vMcFd8=")
os.environ.setdefault("LANDBOT_SECRET_TOKEN", "token-admin-teste")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from schemas.exercise import ExerciseMedia, MEDIA_TYPES  # noqa: E402

MP4 = "https://res.cloudinary.com/x/sotelfit/biblioteca/agachamento-livre.mp4"


def _media(**over):
    base = dict(type="video/mp4", url=MP4, source="sotel_proprio")
    base.update(over)
    return base


# ------------------------------------------------------- formatos aceitos

def test_aceita_os_quatro_formatos_de_demonstracao():
    assert set(MEDIA_TYPES) == {"video/mp4", "video/webm", "image/webp", "image/gif"}
    for tipo, ext in [
        ("video/mp4", ".mp4"), ("video/webm", ".webm"),
        ("image/webp", ".webp"), ("image/gif", ".gif"),
    ]:
        m = ExerciseMedia(**_media(type=tipo, url=f"https://res.cloudinary.com/x/a{ext}"))
        assert m.type == tipo


@pytest.mark.parametrize("tipo", ["youtube", "video/quicktime", "video/avi", "", "link"])
def test_formato_fora_da_lista_e_recusado(tipo):
    """Era o buraco do contrato antigo: `type` aceitava qualquer string."""
    with pytest.raises(ValidationError):
        ExerciseMedia(**_media(type=tipo))


def test_extensao_precisa_bater_com_o_tipo_declarado():
    """URL trocada é o erro mais comum de quem cola link à mão."""
    with pytest.raises(ValidationError) as e:
        ExerciseMedia(**_media(type="video/mp4", url="https://res.cloudinary.com/x/a.webm"))
    assert "nao corresponde" in str(e.value)


def test_url_precisa_ser_https():
    with pytest.raises(ValidationError):
        ExerciseMedia(**_media(url="http://res.cloudinary.com/x/a.mp4"))


# ------------------------------------------------------------- direitos

def test_origem_e_OBRIGATORIA():
    """Sem origem não dá para responder 'de quem é isso?' sem abrir o Cloudinary."""
    sem = _media()
    sem.pop("source")
    with pytest.raises(ValidationError):
        ExerciseMedia(**sem)


@pytest.mark.parametrize("origem", ["terceiros", "youtube", "internet", "desconhecida", ""])
def test_nao_existe_origem_para_material_de_terceiro(origem):
    """A ausência dessa opção é proposital, não esquecimento."""
    with pytest.raises(ValidationError):
        ExerciseMedia(**_media(source=origem))


def test_as_duas_origens_validas_sao_proprias_ou_licenciadas():
    for origem in ("sotel_proprio", "licenciado"):
        assert ExerciseMedia(**_media(source=origem)).source == origem


# --------------------------------------------------------------- poster

def test_poster_opcional_mas_validado_quando_existe():
    m = ExerciseMedia(**_media(poster="https://res.cloudinary.com/x/a.jpg"))
    assert m.poster.endswith(".jpg")
    with pytest.raises(ValidationError):
        ExerciseMedia(**_media(poster="https://res.cloudinary.com/x/a.mp4"))
    with pytest.raises(ValidationError):
        ExerciseMedia(**_media(poster="http://res.cloudinary.com/x/a.jpg"))


def test_poster_vazio_vira_ausente_em_vez_de_string_quebrada():
    assert ExerciseMedia(**_media(poster="   ")).poster is None


# ------------------------------------------- registros antigos preservados

def test_exercicio_sem_midia_continua_valido():
    """33 de 33 exercícios estão assim hoje. Não pode virar erro."""
    from schemas.exercise import ExerciseBase
    ex = ExerciseBase(
        slug="agachamento-livre", name="Agachamento Livre", primary_muscle="Quadríceps",
        equipment="Barra", level="intermediario",
    )
    assert ex.media == []


# ============================ vinculo canonico escolhido por humano ==========

import tempfile  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from core.database import Base  # noqa: E402
from models.exercise import Exercise  # noqa: E402
from services.exercise_binding import build_enrichment  # noqa: E402

_DB = os.path.join(tempfile.gettempdir(), "sotel_lib_media_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
_eng = create_engine(f"sqlite:///{_DB}", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_eng)

PLANO = """TREINO A - Segunda

QUADRÍCEPS
- Agachamento Livre: 4x10 | descanso 90s
- Leg Press Inclinado Xyz: 3x12
"""


@pytest.fixture()
def db():
    Base.metadata.create_all(_eng, tables=[Exercise.__table__])
    s = _Session()
    s.query(Exercise).delete()
    s.add(Exercise(
        slug="agachamento-livre", name="Agachamento Livre", aliases=["agachamento"],
        primary_muscle="Quadríceps", secondary_muscles=[], equipment="Barra",
        level="intermediario", common_errors=[], cautions=[],
        approved_substitutions=[], media=[],
    ))
    s.add(Exercise(
        slug="leg-press", name="Leg Press", aliases=[], primary_muscle="Quadríceps",
        secondary_muscles=[], equipment="Máquina", level="iniciante",
        common_errors=[], cautions=[], approved_substitutions=[], media=[],
    ))
    s.commit()
    yield s
    s.close()


def _por_nome(enr, trecho):
    return next(e for e in enr["exercises"] if trecho.lower() in e["name_raw"].lower())


def test_sem_binding_o_comportamento_e_o_de_sempre(db):
    """Todo plano ja publicado passa por aqui. Nao pode mudar."""
    enr = build_enrichment(db, PLANO)
    assert _por_nome(enr, "Agachamento")["status"] == "resolved"
    assert _por_nome(enr, "Xyz")["status"] == "unresolved"
    assert _por_nome(enr, "Xyz")["library_ref"] is None


def test_escolha_humana_resolve_ocorrencia_que_a_heuristica_nao_resolveu(db):
    enr = build_enrichment(db, PLANO)
    chave = _por_nome(enr, "Xyz")["occurrence_key"]

    com = build_enrichment(db, PLANO, bindings={chave: "leg-press"})
    alvo = _por_nome(com, "Xyz")
    assert alvo["library_ref"] == "leg-press"
    assert alvo["status"] == "manual", "a escolha humana precisa ser distinguivel"
    assert com["coverage"]["resolved"] == 2


def test_escolha_humana_TEM_PRECEDENCIA_sobre_a_heuristica(db):
    """O profissional discorda do casamento automatico. Quem manda e ele.

    Sem isto, republicar o plano desfaria a correcao em silencio.
    """
    enr = build_enrichment(db, PLANO)
    chave = _por_nome(enr, "Agachamento")["occurrence_key"]
    assert _por_nome(enr, "Agachamento")["library_ref"] == "agachamento-livre"

    com = build_enrichment(db, PLANO, bindings={chave: "leg-press"})
    assert _por_nome(com, "Agachamento")["library_ref"] == "leg-press"
    assert _por_nome(com, "Agachamento")["status"] == "manual"


def test_binding_para_slug_INEXISTENTE_e_ignorado(db):
    """Vinculo fantasma e pior que vinculo nenhum: o cliente pediria orientacao
    de um exercicio que nao existe."""
    enr = build_enrichment(db, PLANO)
    chave = _por_nome(enr, "Xyz")["occurrence_key"]
    com = build_enrichment(db, PLANO, bindings={chave: "nao-existe-este-slug"})
    alvo = _por_nome(com, "Xyz")
    assert alvo["library_ref"] is None
    assert alvo["status"] == "unresolved", "nao pode virar manual apontando p/ nada"


def test_nenhuma_troca_silenciosa_por_similaridade(db):
    """`Leg Press Inclinado Xyz` NAO vira `leg-press` sozinho."""
    enr = build_enrichment(db, PLANO)
    assert _por_nome(enr, "Xyz")["library_ref"] is None


def test_ocorrencia_nao_resolvida_continua_sinalizada_e_o_treino_segue(db):
    enr = build_enrichment(db, PLANO)
    pendentes = [e for e in enr["exercises"] if e["status"] == "unresolved"]
    assert len(pendentes) == 1
    # O plano continua com TODAS as ocorrencias — nada some por nao resolver.
    assert enr["coverage"]["total"] == len(enr["exercises"]) == 2
