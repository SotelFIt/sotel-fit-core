"""
Registro de carga por série (WORKOUT-CARGA-001).

Três rotas, todas sob `/clients/{client_id}/...` e todas protegidas por
`require_client_access` — que já resolve, num lugar só, as três perguntas de
acesso: está autenticado? é o dono (ou admin)? o cadastro continua ativo? Um
aluno excluído perde o acesso aqui mesmo com token de assinatura válida.

  PUT    /clients/{id}/set-logs            grava ou corrige uma série
  GET    /clients/{id}/set-logs            o que já foi registrado no dia
  GET    /clients/{id}/set-logs/anterior   a carga da vez passada, por ocorrência

Nada aqui depende do fornecedor de vídeo. A indisponibilidade da demonstração
não pode impedir o aluno de registrar o que levantou — são caminhos separados,
e é por isso que este router não importa nada de `services.ymove`.
"""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from core.security import require_client_access
from models.exercise_set_log import PESO_MAXIMO_KG, ExerciseSetLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["carga"])


def _peso(valor) -> Optional[float]:
    """Peso aceito como o aluno digita.

    O teclado do celular brasileiro oferece VÍRGULA, e é vírgula que a pessoa
    digita em "32,5". Recusar isso obrigaria a tela a traduzir antes de enviar
    — e aí a regra passaria a existir em dois lugares, com chance de divergir.
    Aqui ela existe uma vez só, e a tela pode mandar o que foi digitado.

    Vazio e `None` são "sem carga", que é diferente de zero: há exercício sem
    carga externa, e para ele o peso não existe. Zero continua aceito, porque
    é um valor que alguém pode querer registrar de propósito (barra vazia).
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        v = valor.strip().replace(",", ".")
        if not v:
            return None
        try:
            valor = float(v)
        except ValueError:
            raise ValueError("peso inválido")
    try:
        f = float(valor)
    except (TypeError, ValueError):
        raise ValueError("peso inválido")
    if f != f or f in (float("inf"), float("-inf")):
        raise ValueError("peso inválido")
    if f < 0:
        raise ValueError("peso não pode ser negativo")
    if f > PESO_MAXIMO_KG:
        raise ValueError(f"peso acima do limite de {PESO_MAXIMO_KG:.0f} kg")
    # Duas casas bastam: anilha de 1,25 kg é a menor fração usada na prática.
    return round(f, 2)


class SerieEntrada(BaseModel):
    """Uma série registrada.

    `client_plan_id` NÃO entra aqui: quem sabe qual plano está publicado é o
    servidor, e aceitá-lo do cliente deixaria o aluno escolher a que versão do
    plano a carga pertence. Mesma decisão de `workout_completions`.
    """

    workout_key: str = Field(min_length=1, max_length=32)
    occurrence_key: str = Field(min_length=1, max_length=64)
    exercise_name: str = Field(min_length=1, max_length=200)
    library_ref: Optional[str] = Field(default=None, max_length=200)
    set_index: int = Field(ge=1, le=50)
    performed_date: date
    weight_kg: Optional[float] = None
    reps_done: Optional[int] = Field(default=None, ge=0, le=1000)

    @field_validator("weight_kg", mode="before")
    @classmethod
    def _normaliza_peso(cls, v):
        return _peso(v)


class PlanoIndisponivel(RuntimeError):
    """A CONSULTA do plano ativo falhou.

    Diferente de "este aluno não tem plano ativo", que é situação legítima.
    """


def _plano_ativo(db: Session, client_id: int) -> int:
    """Versão do plano publicado agora. 0 quando não há.

    Resolvido no servidor, nunca enviado pelo cliente.

    `0` significa **aluno sem plano ativo** — situação normal e documentada,
    a mesma convenção de `workout_completions`, onde NULL furaria a chave
    natural porque não compara igual em SQL.

    O que `0` NÃO pode significar é "a consulta falhou". Antes, qualquer
    exceção aqui virava `0`, e as duas coisas ficavam indistinguíveis. Com o
    banco oscilando, a carga era gravada sob a versão 0 em vez da versão que o
    aluno está treinando — e sumia da tela na leitura seguinte, porque a
    listagem filtra pela versão vigente. O aluno via o campo esvaziar sozinho
    e nada no servidor explicava por quê.
    """
    try:
        linha = db.execute(
            text("SELECT id FROM client_plans WHERE client_id = :cid "
                 "AND status = 'active' ORDER BY created_at DESC LIMIT 1"),
            {"cid": client_id},
        ).fetchone()
    except Exception as e:
        db.rollback()
        logger.warning("falha ao resolver o plano ativo do cliente %s: %s",
                       client_id, type(e).__name__)
        raise PlanoIndisponivel("não foi possível resolver o plano ativo")
    return int(linha[0]) if linha and linha[0] is not None else 0


# Sem saber a que versão do plano a carga pertence, não se grava nem se lista:
# responder vazio seria indistinguível de "nada registrado", e a tela limparia
# os campos do aluno achando que não havia nada.
INDISPONIVEL = HTTPException(
    status_code=503,
    detail="não foi possível consultar seu plano agora. Tente de novo em instantes.",
)


def _saida(r: ExerciseSetLog) -> dict:
    return {
        "workout_key": r.workout_key,
        "occurrence_key": r.occurrence_key,
        "exercise_name": r.exercise_name,
        "library_ref": r.library_ref,
        "set_index": r.set_index,
        "performed_date": r.performed_date.isoformat() if r.performed_date else None,
        "weight_kg": r.weight_kg,
        "reps_done": r.reps_done,
    }


@router.put("/{client_id}/set-logs")
def gravar_serie(
    client_id: int,
    entrada: SerieEntrada,
    db: Session = Depends(get_db),
    _: int = Depends(require_client_access),
):
    """Grava a carga de uma série, ou corrige a que já estava lá.

    É PUT, não POST, porque a operação é idempotente por identidade: a mesma
    série do mesmo exercício no mesmo dia é uma linha só. Mandar duas vezes
    corrige; não duplica. Isso também torna o reenvio após falha de rede
    seguro, sem precisar de chave de idempotência separada.

    DUAS REQUISIÇÕES CRIANDO A MESMA SÉRIE
    --------------------------------------
    Acontece de verdade: duas abas, ou um toque duplo com a rede lenta. A
    restrição única do banco arbitra e uma das duas recebe `IntegrityError`.

    A versão anterior tratava isso relendo a linha que ficou e devolvendo-a
    como sucesso. O resultado era uma **confirmação falsa**: quem mandou
    34,5 kg e perdeu a corrida recebia `200` com os 30 kg da outra aba, via
    "Carga salva" na tela, e ia embora achando que havia registrado 34,5.

    Agora quem perde a corrida **aplica o próprio valor** sobre a linha que
    venceu. É o que PUT significa — "deixe esta série com este valor" — e é o
    que o aluno pediu ao digitar. A resposta é lida da linha depois do commit,
    então ela descreve o que está no banco, e não o que se esperava que
    estivesse.

    Só o conflito de unicidade entra nesse caminho. Qualquer outra falha de
    banco vira erro: antes, `except Exception` fazia com que um disco cheio ou
    uma conexão perdida também encontrasse a linha antiga na releitura e
    respondesse `200`, relatando como gravado algo que nunca foi.
    """
    try:
        plano = _plano_ativo(db, client_id)
    except PlanoIndisponivel:
        raise INDISPONIVEL

    def _existente():
        return (
            db.query(ExerciseSetLog)
            .filter(
                ExerciseSetLog.client_id == client_id,
                ExerciseSetLog.client_plan_id == plano,
                ExerciseSetLog.workout_key == entrada.workout_key,
                ExerciseSetLog.occurrence_key == entrada.occurrence_key,
                ExerciseSetLog.set_index == entrada.set_index,
                ExerciseSetLog.performed_date == entrada.performed_date,
            )
            .first()
        )

    def _aplicar(registro: ExerciseSetLog) -> ExerciseSetLog:
        registro.weight_kg = entrada.weight_kg
        registro.reps_done = entrada.reps_done
        # O nome é atualizado junto: se o treinador reescreveu a prescrição
        # hoje, o registro de hoje acompanha o nome de hoje.
        registro.exercise_name = entrada.exercise_name
        registro.library_ref = entrada.library_ref
        registro.updated_at = datetime.utcnow()
        return registro

    existente = _existente()
    if existente:
        registro = _aplicar(existente)
    else:
        registro = ExerciseSetLog(
            client_id=client_id,
            client_plan_id=plano,
            workout_key=entrada.workout_key,
            occurrence_key=entrada.occurrence_key,
            exercise_name=entrada.exercise_name,
            library_ref=entrada.library_ref,
            set_index=entrada.set_index,
            performed_date=entrada.performed_date,
            weight_kg=entrada.weight_kg,
            reps_done=entrada.reps_done,
            updated_at=datetime.utcnow(),
        )
        db.add(registro)

    try:
        db.commit()
    except IntegrityError:
        # Perdemos a corrida. A linha existe; aplicamos NOSSO valor sobre ela.
        db.rollback()
        vencedora = _existente()
        if vencedora is None:
            # Conflito sem linha correspondente: não é a corrida que
            # conhecemos. Não há o que confirmar.
            logger.warning("conflito sem linha correspondente ao gravar carga "
                           "cliente=%s serie=%s", client_id, entrada.set_index)
            raise HTTPException(
                status_code=409,
                detail="não foi possível gravar a carga. Tente de novo.",
            )
        registro = _aplicar(vencedora)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("falha ao reaplicar a carga apos corrida cliente=%s",
                           client_id)
            raise HTTPException(
                status_code=409,
                detail="não foi possível gravar a carga. Tente de novo.",
            )
    except Exception as e:
        # Falha que NÃO é conflito de unicidade. Nunca vira sucesso.
        db.rollback()
        logger.error("falha ao gravar carga cliente=%s: %s", client_id,
                     type(e).__name__)
        raise HTTPException(status_code=500, detail="não foi possível gravar a carga")

    # Lido do banco DEPOIS do commit: a resposta descreve o que ficou
    # persistido, não o que se esperava que estivesse.
    db.refresh(registro)
    return _saida(registro)


@router.get("/{client_id}/set-logs")
def listar_series(
    client_id: int,
    workout_key: Optional[str] = Query(None),
    performed_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: int = Depends(require_client_access),
):
    """O que já foi registrado — é o que faz a tela sobreviver a um recarregar.

    Filtra pela versão ATIVA do plano: carga de um plano que já foi substituído
    não deve reaparecer preenchida numa prescrição diferente.
    """
    try:
        plano = _plano_ativo(db, client_id)
    except PlanoIndisponivel:
        raise INDISPONIVEL
    q = db.query(ExerciseSetLog).filter(
        ExerciseSetLog.client_id == client_id,
        ExerciseSetLog.client_plan_id == plano,
    )
    if workout_key:
        q = q.filter(ExerciseSetLog.workout_key == workout_key)
    if performed_date:
        q = q.filter(ExerciseSetLog.performed_date == performed_date)

    linhas = q.order_by(ExerciseSetLog.occurrence_key, ExerciseSetLog.set_index).all()
    return {"itens": [_saida(r) for r in linhas]}


@router.get("/{client_id}/set-logs/anterior")
def carga_anterior(
    client_id: int,
    workout_key: Optional[str] = Query(None),
    antes_de: Optional[date] = Query(None, description="exclui este dia e os seguintes"),
    db: Session = Depends(get_db),
    _: int = Depends(require_client_access),
):
    """A carga da **vez passada**, por ocorrência — um registro REAL.

    Devolve um mapa `occurrence_key -> {data, peso, série}`. Quem não aparece
    no mapa não tem histórico, e a tela mostra estado vazio em vez de inventar
    um número. *Ausência nunca vira zero.*

    Duas escolhas que mudam o número exibido:

    - olha o dia MAIS RECENTE anterior a hoje, e dentro dele a MAIOR carga da
      ocorrência. A série mais pesada é a referência que interessa para decidir
      quanto pôr hoje; a média diluiria o aquecimento no número;
    - NÃO filtra por versão do plano. O plano é republicado com frequência, e a
      carga de um exercício não deixa de valer porque o treinador mexeu na
      prescrição. O que amarra é a ocorrência, não a versão.
    """
    limite = antes_de or date.today()

    q = db.query(ExerciseSetLog).filter(
        ExerciseSetLog.client_id == client_id,
        ExerciseSetLog.performed_date < limite,
        ExerciseSetLog.weight_kg.isnot(None),
    )
    if workout_key:
        q = q.filter(ExerciseSetLog.workout_key == workout_key)

    anterior: dict = {}
    for r in q.order_by(ExerciseSetLog.performed_date.desc()).all():
        atual = anterior.get(r.occurrence_key)
        if atual is None:
            anterior[r.occurrence_key] = {
                "performed_date": r.performed_date.isoformat(),
                "weight_kg": r.weight_kg,
                "set_index": r.set_index,
                "exercise_name": r.exercise_name,
            }
            continue
        # Já temos o dia mais recente (a ordenação garante). Dentro dele, fica
        # a série mais pesada; dias anteriores não substituem.
        if atual["performed_date"] == r.performed_date.isoformat() and (
            r.weight_kg or 0
        ) > (atual["weight_kg"] or 0):
            atual["weight_kg"] = r.weight_kg
            atual["set_index"] = r.set_index

    return {"anterior": anterior}
