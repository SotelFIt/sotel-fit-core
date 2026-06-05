path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/app/services/twilio_flow_service.py'
content = open(path, 'r', encoding='utf-8-sig').read()

# Remove o bloco duplicado vazio
old = '    if step == "start":\n\n    if step == "start":'
new = '    if step == "start":'
content = content.replace(old, new, 1)

open(path, 'w', encoding='utf-8').write(content)

# Verifica
lines = content.split('\n')
for i, l in enumerate(lines[50:70], start=51):
    print(i, repr(l))