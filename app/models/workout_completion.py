"""
WorkoutCompletion — fonte canônica da conclusão de treino (WORKOUT-DATA-001).

Por que esta tabela existe
--------------------------
A conclusão do treino vivia SOMENTE no `localStorage` do aparelho. O backend
recebia `POST /timeline/event`, mas `timeline_events` é log append-only: não
serve de fonte da verdade, não deduplica e ainda alimenta o contador de marcos
(5/10/20/50). Em falha de transporte o cliente não sabia se o INSERT ocorreu, e
repetir a chamada podia duplicar o evento e disparar um marco falso.

Escopo deliberadamente MÍNIMO
-----------------------------
Isto registra que UM treino foi concluído. Não é acompanhamento de série, carga,
repetição ou exercício atual — nada disso entra aqui sem decisão própria.

Identidade da ocorrência
------------------------
Duas garantias independentes, porque protegem de coisas diferentes:

1. `idempotency_key` — gerada e persistida pelo CLIENTE **antes** do primeiro
   envio. Protege o retry: a mesma intenção reenviada N vezes é uma conclusão
   só, mesmo que a primeira resposta tenha se perdido.

2. `(client_id, client_plan_id, workout_key, completed_date)` — chave natural.
   Protege o caso em que o cliente PERDEU a chave (storage limpo, outro
   aparelho) e tenta concluir o mesmo treino do mesmo plano no mesmo dia.

Sem a (1) o retry duplica. Sem a (2) limpar o storage duplica. As duas.

`client_plan_id` é resolvido **no servidor** a partir do plano ativo, não
enviado pelo cliente: o servidor é quem sabe qual plano está publicado, e assim
o contrato de `GET /clients/{id}/plan` não precisa mudar. `0` significa plano
desconhecido (cliente sem plano ativo no momento da conclusão) — mantém a chave
natural utilizável em vez de virar NULL, que não compara igual em SQL e furaria
a restrição única.

Schema: `Base.metadata.create_all()` cria a tabela; a restrição única e os
índices que o create_all não garante em bases já existentes ficam em
`migrate.py`, de forma idempotente. Mesma convenção de `exercises` (LIB-002).
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

from core.database import Base

# Nome da restrição natural — repetido em migrate.py e nos testes.
UQ_OCORRENCIA = "uq_workout_completion_ocorrencia"

# Marcos de constância. Contados sobre ESTA tabela, nunca sobre timeline_events:
# é o que impede que um reenvio infle o contador e dispare marco falso.
MARCOS = {
    5: ("💪", "5 treinos concluídos", "O hábito está sendo construído. Cinco sessões registradas."),
    10: ("⚡", "10 treinos concluídos", "Dois dígitos. Consistência real em andamento."),
    20: ("🚀", "20 treinos concluídos", "Vinte sessões. Disciplina consolidada."),
    50: ("🏆", "50 treinos concluídos", "Cinquenta treinos. Você está construindo algo real."),
}


class WorkoutCompletion(Base):
    __tablename__ = "workout_completions"

    id = Column(Integer, primary_key=True, index=True)

    # Sem ForeignKey por opção: `client_plans` também usa Integer puro, e o FK
    # obrigaria a suíte a materializar `clients` só para testar conclusão.
    client_id = Column(Integer, nullable=False, index=True)

    # Plano publicado ao qual a conclusão pertence. 0 = desconhecido.
    client_plan_id = Column(Integer, nullable=False, server_default=text("0"), default=0)

    # Identificação do treino dentro do plano ("A", "B", "C" ou o rótulo real).
    workout_key = Column(String(32), nullable=False)

    # Dia da conclusão na LEITURA DO CLIENTE (fuso do aparelho). É o que fecha a
    # chave natural: concluir "Treino A" duas vezes no mesmo dia é uma coisa só.
    completed_date = Column(Date, nullable=False)

    # Instante real do registro, para auditoria. Não entra na chave natural.
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Chave de idempotência do cliente. UNIQUE global: é o identificador da
    # INTENÇÃO, gerado antes da primeira tentativa.
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)

    # Evento de Timeline correspondente. Timeline é CONSEQUÊNCIA, não fonte.
    timeline_event_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "client_plan_id",
            "workout_key",
            "completed_date",
            name=UQ_OCORRENCIA,
        ),
    )
