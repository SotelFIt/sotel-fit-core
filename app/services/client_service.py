from sqlalchemy.orm import Session
from sqlalchemy import text
from core.phone import normalize_phone
import logging

logger = logging.getLogger(__name__)


class ClienteExcluido(ValueError):
    """O telefone pertence a um cadastro que o profissional excluiu.

    Erro proposital: pagamento, WhatsApp e onboarding nao reativam cadastro
    sozinhos. Quem reativa e o painel.
    """


def get_or_create_client_from_phone(db: Session, phone: str, name: str = None) -> dict:
    normalized = normalize_phone(phone)
    # REL-V1-004: sem telefone canonico nao ha identidade. Criar cliente aqui
    # geraria um registro sem como ser encontrado depois - e sem como saber de quem e.
    if not normalized:
        raise ValueError(f"telefone invalido; cliente nao criado (entrada com {len(str(phone or ''))} caracteres)")

    row = db.execute(
        text("SELECT id, name, phone, objective, status, deleted_at FROM clients WHERE phone = :p LIMIT 1"),
        {"p": normalized}
    ).fetchone()

    # Aluno EXCLUIDO nao volta por aqui. Esta funcao e a porta de entrada de
    # WhatsApp e pagamento: sem esta guarda, a primeira mensagem do numero
    # reativaria o cadastro que o profissional removeu — ou, pior, criaria um
    # segundo cliente com o mesmo telefone. Reativar e decisao do painel.
    if row and row[5] is not None:
        raise ClienteExcluido(
            f"cadastro excluido para este telefone (client_id={row[0]}); "
            "reative pelo painel antes de continuar"
        )

    if row:
        if name and name != row[1]:
            db.execute(
                text("UPDATE clients SET name = :name WHERE phone = :p"),
                {"name": name, "p": normalized}
            )
            db.commit()
        return {"id": row[0], "name": name or row[1], "phone": row[2], "objective": row[3], "status": row[4]}

    result = db.execute(
        text("INSERT INTO clients (name, phone, status, created_at) VALUES (:name, :phone, 'lead', NOW()) RETURNING id, name, phone, objective, status"),
        {"name": name or "Cliente WhatsApp", "phone": normalized}
    ).fetchone()
    db.commit()
    logger.info(f"Cliente criado automaticamente: {normalized}")
    return {"id": result[0], "name": result[1], "phone": result[2], "objective": result[3], "status": result[4]}


def fix_orphan_conversation_states(db: Session):
    orphans = db.execute(
        text("SELECT cs.phone, cs.name FROM conversation_states cs WHERE cs.phone IS NOT NULL AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.phone = cs.phone)")
    ).fetchall()

    count = 0
    for row in orphans:
        try:
            normalized = normalize_phone(row[0])
            db.execute(
                text("INSERT INTO clients (name, phone, status, created_at) VALUES (:name, :phone, 'lead', NOW()) ON CONFLICT DO NOTHING"),
                {"name": row[1] or "Lead WhatsApp", "phone": normalized}
            )
            count += 1
        except Exception as e:
            logger.warning(f"Erro ao criar client para {row[0]}: {e}")
            db.rollback()

    if count > 0:
        db.commit()
        logger.info(f"fix_orphan_conversation_states: {count} clientes criados")
    return count

# ---------------------------------------------------------------------------
# Troca de telefone do cliente.
#
# BL-PHONE-001 dizia que telefone nao se edita. A regra foi revogada pelo
# Proprietario: o profissional precisa corrigir numero errado. O que NAO mudou
# e o motivo pelo qual ela existia — telefone e a chave operacional pela qual o
# WhatsApp, o onboarding e a ativacao encontram o aluno. Entao editar so e
# aceitavel levando esses vinculos junto, de uma vez so.
#
# O que MIGRA (o vinculo vive no numero; ficar para tras e perder o aluno):
#   - conversation_states : a conversa de WhatsApp em andamento;
#   - lead_onboardings    : o onboarding/anamnese, inclusive nas variantes
#                           gravadas com "whatsapp:" ou sem o "+".
#
# O que NAO migra, de proposito (registra o que aconteceu NAQUELE momento;
# reescrever seria falsificar historico):
#   - admin_audit_log, decision_logs, whatsapp_events, timeline_events.
# ---------------------------------------------------------------------------


class TelefoneInvalido(ValueError):
    """Entrada que nao e um telefone. Nunca vira identidade."""


class TelefoneDuplicado(ValueError):
    """Outro cliente ja usa esse numero."""

    def __init__(self, client_id: int):
        self.client_id = client_id
        super().__init__(f"telefone ja usado pelo cliente {client_id}")


class ConversaDeOutraPessoa(ValueError):
    """Ja existe conversa de WhatsApp para o numero de destino.

    `conversation_states.phone` e UNIQUE. Sobrescrever juntaria duas pessoas na
    mesma conversa — exatamente o que nao pode acontecer.
    """


def _variantes(numero: str) -> list:
    """Como o mesmo telefone pode ter sido gravado por caminhos diferentes."""
    so_digitos = numero.lstrip("+")
    return [numero, so_digitos, f"whatsapp:{numero}", f"whatsapp:{so_digitos}"]


def trocar_telefone(db: Session, client_id: int, bruto: str) -> dict:
    """Troca o telefone e leva os vinculos operacionais junto.

    NAO faz commit: quem chama decide a transacao. Qualquer excecao aqui deixa
    tudo para tras — e o rollback de quem chama que garante o tudo-ou-nada.

    Devolve o que foi feito, para registro no log administrativo.
    """
    novo = normalize_phone(bruto)
    if not novo:
        raise TelefoneInvalido(
            "numero invalido; informe DDD + numero (ex.: 17991234567)"
        )

    atual = db.execute(
        text("SELECT phone FROM clients WHERE id = :cid"), {"cid": client_id}
    ).fetchone()
    if atual is None:
        raise LookupError("Cliente nao encontrado")
    antigo = atual[0]

    if antigo == novo:
        return {"antigo": antigo, "novo": novo, "conversas": 0, "onboardings": 0}

    # Duplicidade: inclui cliente EXCLUIDO de proposito. O cadastro continua
    # existindo e o numero continua sendo dele; reaproveitar o numero
    # silenciosamente misturaria dois historicos.
    dono = db.execute(
        text("SELECT id FROM clients WHERE phone = :p AND id <> :cid LIMIT 1"),
        {"p": novo, "cid": client_id},
    ).fetchone()
    if dono:
        raise TelefoneDuplicado(dono[0])

    # conversation_states.phone e UNIQUE: se ja ha conversa no numero de
    # destino, ela e de outra pessoa e nao pode ser absorvida.
    ocupada = db.execute(
        text("SELECT phone FROM conversation_states WHERE phone = :p LIMIT 1"),
        {"p": novo},
    ).fetchone()
    if ocupada:
        raise ConversaDeOutraPessoa(
            "ja existe uma conversa de WhatsApp registrada nesse numero"
        )

    conversas = db.execute(
        text("UPDATE conversation_states SET phone = :novo WHERE phone = :antigo"),
        {"novo": novo, "antigo": antigo},
    ).rowcount

    onboardings = 0
    if antigo:
        vars_ = _variantes(antigo)
        marcadores = ", ".join(f":v{i}" for i in range(len(vars_)))
        params = {f"v{i}": v for i, v in enumerate(vars_)}
        onboardings = db.execute(
            text(f"UPDATE lead_onboardings SET phone = :novo WHERE phone IN ({marcadores})"),
            {"novo": novo, **params},
        ).rowcount

    db.execute(
        text("UPDATE clients SET phone = :novo, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"),
        {"novo": novo, "cid": client_id},
    )

    logger.info(
        "telefone trocado client_id=%s conversas=%s onboardings=%s",
        client_id, conversas, onboardings,
    )
    return {"antigo": antigo, "novo": novo,
            "conversas": conversas, "onboardings": onboardings}
