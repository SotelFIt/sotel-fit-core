"""
ExerciseSetLog — carga utilizada por série (WORKOUT-CARGA-001).

Por que esta tabela existe
--------------------------
`WORKOUT_SPEC.md` §8 registrava "Carga anterior" como **MISSING DATA / FUTURE
CAPABILITY**: a referência visual mostrava `120 kg` e não havia campo de carga
em lugar nenhum — nem no plano, nem na execução. Mostrar aquele número exigiria
inventá-lo. Isto é a capacidade que faltava.

O que esta tabela NÃO é
-----------------------
Não é conclusão de treino. `workout_completions` registra que **um treino foi
concluído** e o próprio modelo diz, em texto, que série/carga/repetição "não
entra aqui sem decisão própria". A decisão foi tomada, e a resposta é uma
estrutura própria: o significado do evento de conclusão **não muda**, os marcos
de constância continuam contados sobre ele, e nada aqui participa daquela
contagem. Um aluno pode registrar carga e não concluir o treino, ou concluir
sem registrar carga nenhuma.

Identidade da ocorrência
------------------------
Uma linha é "a carga que este aluno usou NESTA série, DESTE exercício, NESTE
dia". Cinco coisas fazem parte da identidade, e cada uma resolve uma confusão
diferente:

1. `client_id` — de quem é.
2. `client_plan_id` — **qual versão do plano**. O treinador republica o plano e
   o "Treino A" de hoje não é o de duas semanas atrás: podem ter mudado
   exercícios, ordem e séries. Sem isto, a carga anterior viria de uma
   prescrição que não existe mais. `0` = plano desconhecido, mesma convenção de
   `workout_completions`, porque NULL não compara igual em SQL e furaria a
   restrição única.
3. `workout_key` — qual treino dentro do plano ("A", "B", ...).
4. `occurrence_key` — **qual ocorrência**. O mesmo exercício aparece duas vezes
   no mesmo treino com frequência (Leg Press no aquecimento e no bloco
   principal). A chave vem do enriquecimento do plano, que já distingue as
   duas; usar o nome do exercício juntaria as cargas de ambas num número só.
5. `set_index` — qual série, de 1 a N.

6. `performed_date` — o dia **na leitura do aparelho do aluno**, como em
   `workout_completions`. É o que torna repetir o mesmo treino na semana
   seguinte um registro novo em vez de uma sobrescrita.

Regravar a mesma série no mesmo dia é CORREÇÃO, não duplicata: o aluno errou o
número, ou aumentou a carga na segunda tentativa. A restrição única garante uma
linha por identidade, e a rota atualiza em vez de inserir.

O nome é copiado, de propósito
------------------------------
`exercise_name` guarda o nome como estava prescrito no dia. O plano é texto
livre reescrito pelo treinador, e `library_ref` pode nem existir (39% das
ocorrências dos planos reais não resolvem para a Biblioteca). Sem a cópia, um
registro de três meses atrás perderia o nome do exercício quando o plano fosse
reescrito — e sobraria um número de kg sem referente.

Peso
----
`weight_kg` é `Float` e **pode ser nulo**: há exercícios sem carga externa
(prancha, flexão), e para eles a série existe e o peso não. Nulo significa "sem
carga", nunca "zero" — a mesma regra do contrato da tela: *ausência nunca vira
zero*.

Schema: `Base.metadata.create_all()` cria a tabela; a restrição única e os
índices ficam em `migrate.py`, de forma idempotente. Mesma convenção de
`exercises` (LIB-002) e `workout_completions` (WORKOUT-DATA-001).
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)

from core.database import Base

# Nome da restrição — repetido em migrate.py e nos testes.
UQ_SERIE = "uq_exercise_set_log_serie"

# Teto de sanidade, não de prescrição. Serve para recusar entrada absurda
# (dedo escorregou no teclado) sem opinar sobre o treino de ninguém: a maior
# marca registrada de levantamento terra fica bem abaixo disto.
PESO_MAXIMO_KG = 1000.0


class ExerciseSetLog(Base):
    __tablename__ = "exercise_set_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Sem ForeignKey por opção, como em `workout_completions`: `client_plans`
    # também usa Integer puro, e o FK obrigaria a suíte a materializar
    # `clients` só para testar registro de carga.
    client_id = Column(Integer, nullable=False, index=True)

    # Versão do plano a que a carga pertence. 0 = desconhecido.
    client_plan_id = Column(Integer, nullable=False, server_default=text("0"), default=0)

    # Treino dentro do plano ("A", "B", "C" ou o rótulo real).
    workout_key = Column(String(32), nullable=False)

    # Ocorrência do exercício dentro do treino, vinda do enriquecimento.
    # Distingue o mesmo exercício prescrito duas vezes na mesma sessão.
    occurrence_key = Column(String(64), nullable=False)

    # Cópia do nome como prescrito no dia (ver nota no topo).
    exercise_name = Column(String(200), nullable=False)

    # Slug da Biblioteca, quando a ocorrência resolve. Pode ser nulo.
    library_ref = Column(String(200), nullable=True)

    # Série, de 1 a N.
    set_index = Column(Integer, nullable=False)

    # Dia na leitura do aparelho do aluno. Fecha a identidade.
    performed_date = Column(Date, nullable=False)

    # Carga em kg. NULO = exercício sem carga externa. Nunca 0 por ausência.
    weight_kg = Column(Float, nullable=True)

    # Repetições realmente feitas, quando o aluno informar. Opcional: a
    # prescrição já diz quantas são, e isto só existe para registrar desvio.
    reps_done = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "client_plan_id",
            "workout_key",
            "occurrence_key",
            "set_index",
            "performed_date",
            name=UQ_SERIE,
        ),
    )
