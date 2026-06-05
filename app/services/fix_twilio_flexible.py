path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/services/twilio_flow_service.py'
content = open(path, 'r', encoding='utf-8-sig').read()

old = """    step = state.step
    if step == "start":"""

new = """    step = state.step

    # Palavras de entrada — reinicia o fluxo se usuario mandar mensagem de interesse
    ENTRY_KEYWORDS = [
        "oi", "ola", "ola!", "oi!", "hello", "hi",
        "quero", "entrar", "comecar", "iniciar", "sotel",
        "fit", "core", "cadastro", "acesso", "plano",
        "contratar", "assinar", "treino", "personal"
    ]
    msg_lower = incoming_msg.lower().strip()
    is_entry = any(kw in msg_lower for kw in ENTRY_KEYWORDS)

    if is_entry and step not in ("ask_name", "ask_goal", "ask_routine", "active_client"):
        state.step = "ask_name"
        db.commit()
        return "Fala! Eu sou o assistente da Sotel Personal Trainer. Qual seu nome?"

    if step == "start":"""

content = content.replace(old, new, 1)
open(path, 'w', encoding='utf-8').write(content)
print('OK - entry keywords:', content.count('ENTRY_KEYWORDS'))