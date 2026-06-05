path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/routers/admin.py'
content = open(path, 'r', encoding='utf-8-sig').read()

new_endpoint = '''

@router.post("/twilio/resend-onboarding")
def resend_onboarding(payload: ActivateLeadRequest, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    state = db.query(ConversationState).filter(ConversationState.phone == payload.phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")
    # Reset do flag para permitir reenvio
    state.onboarding_link_sent = False
    state.step = "active_client"
    state.status = "onboarding_pending"
    db.commit()
    try:
        twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        twilio_client.messages.create(
            from_=get_twilio_from(),
            to=whatsapp_to(payload.phone),
            content_sid=os.getenv("TWILIO_TEMPLATE_PLANO"),
            messaging_service_sid=None
        )
        state.onboarding_link_sent = True
        db.commit()
        logger.info(f"Reenvio onboarding para {payload.phone}")
    except Exception as e:
        logger.error(f"Erro ao reenviar onboarding: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao enviar WhatsApp: {str(e)}")
    audit_log(db, action="resend_onboarding", client_id=None, details=f"phone={payload.phone}")
    return {"status": "success", "phone": payload.phone, "message": "Onboarding reenviado"}


@router.post("/twilio/resend-access/{client_id}")
def resend_access(client_id: int, db: Session = Depends(get_db), _: int = Depends(require_admin)):
    from services.twilio_service import send_whatsapp_message
    client = db.execute(
        text("SELECT id, name, phone FROM clients WHERE id = :cid"),
        {"cid": client_id}
    ).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    _, name, phone = client
    if not phone:
        raise HTTPException(status_code=400, detail="Cliente sem telefone")
    first_name = (name or "").split()[0] if name else "cliente"
    message = (
        f"Oi {first_name}! Seu acesso ao Sotel Fit Core esta disponivel.\\n\\n"
        f"Acesse aqui:\\n{APP_LINK}\\n\\n"
        f"Use o e-mail cadastrado para entrar."
    )
    success = send_whatsapp_message(phone, message)
    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar WhatsApp")
    audit_log(db, action="resend_access", client_id=client_id, details=f"phone={phone}")
    return {"status": "success", "phone": phone, "message": "Acesso reenviado"}
'''

# Insere antes do último endpoint
insert_before = "\n@router.post(\"/twilio/send-retention/{client_id}\")"
content = content.replace(insert_before, new_endpoint + insert_before, 1)
open(path, 'w', encoding='utf-8').write(content)
print('OK - resend_onboarding:', content.count('resend_onboarding'))