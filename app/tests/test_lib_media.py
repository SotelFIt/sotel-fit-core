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


def test_as_procedencias_validas():
    """Contrato revisado: `licenciado` sozinho nao basta — exige a licenca.

    Antes desta rodada `licenciado` era aceito sem nenhum dado de direito, o
    que nao provava nada. Ver os testes de procedencia mais abaixo.
    """
    assert ExerciseMedia(**_media(source="sotel_proprio")).source == "sotel_proprio"
    assert ExerciseMedia(**_media(source="fixture_teste")).source == "fixture_teste"


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


# ==================== procedencia: proprio / licenciado / fixture ============

LIC = dict(
    fornecedor="GymVisual",
    produto_url="https://www.gymvisual.com/p/cable-seated-row",
    adquirido_em="2026-09-01",
    referencia="PED-2026-0001",
)
GIF = dict(type="image/gif", url="https://res.cloudinary.com/x/remada-sentada.gif")


def test_gif_licenciado_e_aceito_e_publicavel():
    """O caso real: GIF comprado da GymVisual para `remada-sentada`."""
    m = ExerciseMedia(**GIF, source="licenciado", licenca=LIC)
    assert m.publicavel is True
    assert m.licenca.fornecedor == "GymVisual"


def test_licenciado_SEM_licenca_e_midia_sem_procedencia_comprovada():
    """Era o buraco: `licenciado` sozinho nao prova direito de uso nenhum."""
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="licenciado")


def test_licenca_so_faz_sentido_em_midia_licenciada():
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="sotel_proprio", licenca=LIC)
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="fixture_teste", licenca=LIC)


def test_fixture_e_valida_como_objeto_mas_NAO_e_publicavel():
    """Existe para provar o fluxo tecnico sem acervo real — nunca para o cliente."""
    m = ExerciseMedia(**GIF, source="fixture_teste")
    assert m.publicavel is False


def test_midia_propria_continua_publicavel():
    assert ExerciseMedia(**GIF, source="sotel_proprio").publicavel is True


@pytest.mark.parametrize("campo", ["fornecedor", "produto_url", "adquirido_em", "referencia"])
def test_licenca_incompleta_e_recusada(campo):
    parcial = {k: v for k, v in LIC.items() if k != campo}
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="licenciado", licenca=parcial)


@pytest.mark.parametrize("ref", ["recibo.pdf", "https://drive.google.com/x", "nota.jpg"])
def test_referencia_nao_pode_ser_o_documento_nem_link_para_ele(ref):
    """A referencia e o identificador interno. Documento privado nao vive aqui."""
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="licenciado", licenca={**LIC, "referencia": ref})


def test_produto_url_aponta_para_a_pagina_do_produto_em_https():
    with pytest.raises(ValidationError):
        ExerciseMedia(**GIF, source="licenciado",
                      licenca={**LIC, "produto_url": "http://gymvisual.com/p/x"})


# ------------------------- resposta publica nao vaza dados privados ---------

def test_resposta_publica_REMOVE_a_licenca():
    """Fornecedor, comprovante e data de compra nao vao para o aparelho do aluno."""
    from routers.exercise import _midia_publica

    entrada = [{**GIF, "source": "licenciado", "licenca": LIC}]
    saida = _midia_publica(entrada)
    assert len(saida) == 1
    assert "licenca" not in saida[0]
    # O que o cliente precisa continua: url, tipo e a natureza da procedencia.
    assert saida[0]["url"] == GIF["url"]
    assert saida[0]["source"] == "licenciado"


def test_resposta_publica_REMOVE_a_fixture():
    from routers.exercise import _midia_publica

    assert _midia_publica([{**GIF, "source": "fixture_teste"}]) == []


def test_resposta_publica_preserva_midia_propria():
    from routers.exercise import _midia_publica

    saida = _midia_publica([{**GIF, "source": "sotel_proprio"}])
    assert len(saida) == 1 and "licenca" not in saida[0]


def test_nenhum_dado_de_compra_sobrevive_a_serializacao_publica():
    """Varredura: nenhum valor da licenca pode aparecer no que sai."""
    from routers.exercise import _midia_publica
    import json as _json

    bruto = _json.dumps(_midia_publica([{**GIF, "source": "licenciado", "licenca": LIC}]))
    for valor in LIC.values():
        assert str(valor) not in bruto, f"vazou dado privado: {valor}"


# ------------------------------- ruido estrutural do plano ------------------

def test_descanso_ja_e_filtrado_pelo_extrator():
    """Medido: linha de descanso nao chega a virar ocorrencia."""
    from services.workout_extract import extract_exercises

    plano = (
        "TREINO A - Segunda\n\nQUADRICEPS\n"
        "- Agachamento Livre: 4x10\n"
        "- Descanso: 90s\n"
        "Descanso entre series: 60s\n"
    )
    nomes = [e["name"] for e in extract_exercises(plano)]
    assert "Agachamento Livre" in nomes
    assert not any("descanso" in n.lower() for n in nomes)


@pytest.mark.parametrize("texto", [
    "Volta a calma: caminhada bem leve por 5 min",
    "Volta à calma",
    "Descanso entre series",
    "Intervalo entre blocos: 2 min",
])
def test_instrucao_de_prescricao_e_classificada_como_ruido(texto):
    from services.exercise_binding import eh_ruido_estrutural

    assert eh_ruido_estrutural(texto) is True


@pytest.mark.parametrize("texto", [
    "Prancha", "Abdutora", "Peck Deck", "Mesa Flexora", "Stiff com Halteres",
    "Agachamento Goblet", "Panturrilha Sentada", "Aquecimento Cardio",
    "Cardio Finalizacao", "Caminhada leve",
])
def test_exercicio_legitimo_NUNCA_e_tratado_como_ruido(texto):
    """A lista curta existe para nao apagar exercicio.

    `Aquecimento Cardio` e `Cardio Finalizacao` sao prescricoes reais: ficam
    para revisao humana, nao viram ruido por conta propria.
    """
    from services.exercise_binding import eh_ruido_estrutural

    assert eh_ruido_estrutural(texto) is False


def test_ruido_fica_registrado_e_sai_da_fila_de_revisao(db):
    """O plano nao perde a linha — ela so deixa de contar como falta de catalogo."""
    # SEM marcador: com "- " o extrator ja filtra sozinho. O que vaza para a
    # fila de revisao e a instrucao solta no corpo do bloco.
    plano = (
        "TREINO A - Segunda\n\nQUADRICEPS\n"
        "- Agachamento Livre: 4x10\n"
        "Volta a calma: caminhada bem leve por 5 min\n"
    )
    enr = build_enrichment(db, plano)
    nomes = {e["name_raw"]: e["status"] for e in enr["exercises"]}
    assert nomes.get("Agachamento Livre") == "resolved"
    ruidos = [n for n, st in nomes.items() if st == "ruido_estrutural"]
    assert ruidos and all("volta a calma" in n.lower() for n in ruidos), nomes
    # Nao entra no denominador: nao ha exercicio a vincular.
    assert enr["coverage"]["total"] == 1
    assert enr["coverage"]["resolved"] == 1
