path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/services/twilio_flow_service.py'
content = open(path, 'r', encoding='utf-8-sig').read()

old = """    if step == "start":
        state.step = "ask_name"
        db.commit()
        return "Fala! Eu sou o assistente da Sotel Personal Trainer. Qual seu nome?"

    if step == "start":"""

new = """    if step == "start":
        state.step = "ask_name"
        db.commit()
        return "Fala! Eu sou o assistente da Sotel Personal Trainer. Qual seu nome?"

    if step == "ask_name":"""

# Verifica o que tem na linha 58-65
lines = content.split('\n')
for i, l in enumerate(lines[54:68], start=55):
    print(i, repr(l))