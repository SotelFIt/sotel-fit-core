from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import logging
import os
from twilio.rest import Client as TwilioClient
from core.database import get_db
from core.security import identidade_opcional
from core.phone import normalize_phone, normalize_phone_for_whatsapp
from models.lead_onboarding import LeadOnboarding
from models.conversation_state import ConversationState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class LeadOnboardingRequest(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    idade: Optional[str] = None
    peso: Optional[str] = None
    altura: Optional[str] = None
    objetivo: Optional[str] = None
    nivel_treino: Optional[str] = None
    dias_treino: Optional[str] = None
    horario_treino: Optional[str] = None
    lesoes: Optional[str] = None
    alimentacao_atual: Optional[str] = None
    maior_dificuldade: Optional[str] = None
    meta_principal: Optional[str] = None
    observacoes: Optional[str] = None


@router.post("/lead")
def create_lead_onboarding(
    payload: LeadOnboardingRequest,
    db: Session = Depends(get_db),
    identidade: Optional[int] = Depends(identidade_opcional),
):
    """Conclusao do onboarding.

    QUEM SAO ESTAS RESPOSTAS
    -----------------------
    Antes, a unica coisa que ligava as respostas a um cadastro era o telefone
    DIGITADO no formulario. Isso quebrava de tres jeitos, todos reproduzidos em
    PostgreSQL:

      - telefone divergente: a pessoa recebia sucesso e um SEGUNDO cadastro era
        criado em silencio, enquanto o cadastro original continuava "em
        onboarding" e devolvia a pessoa ao formulario ao reabrir o app;
      - telefone em branco: sucesso, respostas gravadas soltas, nenhum cadastro
        tocado — e a mesma volta ao formulario;
      - telefone invalido: 400, e as respostas se perdiam.

    Agora, quando a requisicao chega com SESSAO VALIDA, as respostas pertencem
    a quem a sessao diz — e so a ele. O telefone deixa de decidir identidade e
    volta a ser o que sempre foi: um dado do formulario.

    `client_id` nunca e lido do corpo. Ele vem da assinatura do token, que o
    navegador nao sabe forjar. Aceita-lo do corpo deixaria qualquer um gravar o
    onboarding de outra pessoa.

    O CAMINHO ANONIMO CONTINUA
    --------------------------
    Quem chega sem sessao (lead publico) segue atendido pelo casamento por
    telefone, como antes. O que mudou e que telefone ausente passou a ser
    recusado nesse caminho: sem sessao e sem telefone nao ha como ligar nada a
    ninguem, e responder "sucesso" era a origem do problema.
    """
    phone_normalized = None
    phone_whatsapp = None

    if payload.telefone:
        phone_normalized = normalize_phone(payload.telefone)
        # REL-V1-004: telefone informado e invalido -> recusar, nao gravar meia identidade.
        if not phone_normalized:
            raise HTTPException(status_code=400, detail="telefone invalido")
        phone_whatsapp = normalize_phone_for_whatsapp(payload.telefone)

    # ------------------------------------------------------------- identidade
    cliente_alvo = None
    if identidade:
        linha = db.execute(
            text("SELECT id, phone FROM clients WHERE id = :cid LIMIT 1"),
            {"cid": identidade},
        ).fetchone()
        if linha:
            cliente_alvo = int(linha[0])
            # O telefone do CADASTRO manda no vinculo operacional (WhatsApp,
            # estado de conversa). Editar o campo do formulario nao pode mudar
            # de quem e o onboarding nem para onde vai a mensagem.
            if linha[1]:
                phone_whatsapp = normalize_phone_for_whatsapp(linha[1]) or phone_whatsapp

    if cliente_alvo is None and not phone_normalized:
        # Sem sessao e sem telefone: nao ha a quem ligar estas respostas.
        # Responder sucesso aqui era exatamente o defeito relatado.
        raise HTTPException(
            status_code=400,
            detail="informe o WhatsApp para concluir o cadastro",
        )

    onboarding = LeadOnboarding(
        client_id=cliente_alvo,
        phone=phone_normalized,
        nome=payload.nome,
        email=payload.email,
        telefone=payload.telefone,
        idade=payload.idade,
        peso=payload.peso,
        altura=payload.altura,
        objetivo=payload.objetivo,
        nivel_treino=payload.nivel_treino,
        dias_treino=payload.dias_treino,
        horario_treino=payload.horario_treino,
        lesoes=payload.lesoes,
        alimentacao_atual=payload.alimentacao_atual,
        maior_dificuldade=payload.maior_dificuldade,
        meta_principal=payload.meta_principal,
        observacoes=payload.observacoes,
    )
    db.add(onboarding)

    if phone_whatsapp:
        state = db.query(ConversationState).filter(
            ConversationState.phone == phone_whatsapp
        ).first()
        if state:
            state.status = "onboarding_completed"
            state.step = "onboarding_completed"

    if cliente_alvo is not None:
        # Identificado: atualiza ESTE cadastro. Nenhum outro e criado nem
        # procurado por telefone — era dai que vinha a duplicata silenciosa.
        db.execute(
            text("UPDATE clients SET status = 'waiting_plan', objective = COALESCE(:obj, objective) WHERE id = :cid"),
            {"obj": payload.objetivo, "cid": cliente_alvo},
        )
    elif phone_normalized:
        # Lead publico, sem sessao: comportamento anterior preservado.
        existing = db.execute(
            text("SELECT id FROM clients WHERE phone = :p LIMIT 1"),
            {"p": phone_normalized}
        ).fetchone()
        if not existing:
            db.execute(
                text("INSERT INTO clients (name, phone, status, email, objective, created_at, updated_at) VALUES (:name, :phone, 'waiting_plan', NULL, :objective, NOW(), NOW())"),
                {"name": payload.nome or "Cliente", "phone": phone_normalized, "objective": payload.objetivo}
            )
        else:
            db.execute(
                text("UPDATE clients SET status = 'waiting_plan', objective = :obj WHERE phone = :p"),
                {"obj": payload.objetivo, "p": phone_normalized}
            )

    try:
        db.commit()
    except Exception:
        # Sem persistencia nao ha conclusao. Responder "ok" aqui seria a mesma
        # confirmacao falsa que esta correcao existe para eliminar.
        db.rollback()
        logger.error("falha ao gravar a conclusao do onboarding")
        raise HTTPException(
            status_code=500,
            detail="nao foi possivel concluir agora. Suas respostas nao foram perdidas; tente de novo.",
        )

    # So agora o sucesso e verdade: a linha existe e, se havia identidade, ela
    # esta ligada ao cadastro certo.
    db.refresh(onboarding)

    if phone_whatsapp:
        try:
            twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            twilio_client.messages.create(
                from_=os.getenv("TWILIO_WHATSAPP_FROM"),
                to=phone_whatsapp,
                body="Cadastro recebido!\n\nAgora vamos montar seu plano personalizado.\n\nAssim que estiver pronto, voce sera avisado aqui no WhatsApp."
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "message": "Onboarding recebido com sucesso",
        "onboarding_completed": True,
        "next_step": "waiting_plan",
        "client_id": onboarding.client_id,
    }


@router.get("/status/{client_id}")
def get_onboarding_status(client_id: int, db: Session = Depends(get_db)):
    onboarding_completed = False
    client_status = None
    next_step = "onboarding"

    client_row = db.execute(
        text("SELECT id, phone, status FROM clients WHERE id = :cid LIMIT 1"),
        {"cid": client_id}
    ).fetchone()

    phone = None
    if client_row:
        phone = client_row[1]
        client_status = client_row[2]

    record = None

    # VINCULO EXPLICITO primeiro: quando a pessoa chegou identificada, as
    # respostas tem o `client_id` gravado e nao ha nada a adivinhar. E o unico
    # caminho que sobrevive a ela editar o telefone no formulario.
    record = db.execute(
        text("SELECT id FROM lead_onboardings WHERE client_id = :cid LIMIT 1"),
        {"cid": client_id},
    ).fetchone()

    # Sem vinculo explicito, o casamento por telefone continua valendo — e o
    # que mantem de pe as linhas anteriores a esta correcao. Compara valores
    # EXATOS em variantes de formato; nada de aproximacao por nome.
    #
    # `client_id IS NULL` e o que impede o roubo por digitacao: uma resposta que
    # JA TEM dono pertence a ele, mesmo que o telefone digitado no formulario
    # seja o de outra pessoa. Sem esse filtro, bastava alguem digitar o numero
    # alheio para concluir o onboarding de quem nunca preencheu nada.
    if not record and phone:
        phone_clean = phone.replace("whatsapp:", "").replace("+", "")
        record = db.execute(
            text("""SELECT id FROM lead_onboardings
                WHERE client_id IS NULL
                  AND (phone = :p1 OR phone = :p2 OR phone = :p3 OR phone = :p4)
                LIMIT 1"""),
            {"p1": phone, "p2": phone.replace("whatsapp:", ""),
             "p3": f"+{phone_clean}", "p4": phone_clean}
        ).fetchone()

    if record:
        onboarding_completed = True

    COMPLETED = {"onboarding_completed", "waiting_plan", "active", "active_client"}
    if not onboarding_completed and client_status in COMPLETED:
        onboarding_completed = True

    if not onboarding_completed and phone:
        for pv in [phone, phone.replace("whatsapp:", ""), f"whatsapp:{phone.replace('whatsapp:','')}"] :
            row = db.execute(
                text("SELECT status FROM conversation_states WHERE phone = :p LIMIT 1"),
                {"p": pv}
            ).fetchone()
            if row and row[0] in {"onboarding_completed", "active_client", "active"}:
                onboarding_completed = True
                break

    conversation_active = False
    if phone:
        for pv in [phone, phone.replace("whatsapp:", ""), f"whatsapp:{phone.replace('whatsapp:','')}"] :
            row = db.execute(
                text("SELECT status FROM conversation_states WHERE phone = :p LIMIT 1"),
                {"p": pv}
            ).fetchone()
            if row and row[0] in {"active", "active_client"}:
                conversation_active = True
                break

    if onboarding_completed:
        if client_status in {"active", "active_client"} or conversation_active:
            next_step = "app"
        else:
            next_step = "waiting_plan"

    # CRITICAL FIX: plano publicado ativo tem PRIORIDADE sobre clients.status.
    # Se existe treino ativo com conteudo publicado, o cliente ja tem acesso ao app,
    # independentemente do campo status (que pode estar defasado/onboarding_pending).
    has_published_plan = db.execute(
        text(
            "SELECT 1 FROM client_plans "
            "WHERE client_id = :cid AND status = 'active' "
            "AND COALESCE(published_content, '') <> '' LIMIT 1"
        ),
        {"cid": client_id},
    ).fetchone() is not None
    if has_published_plan:
        onboarding_completed = True
        next_step = "app"

    return {
        "client_id": client_id,
        "onboarding_completed": onboarding_completed,
        "client_status": client_status,
        "next_step": next_step,
    }