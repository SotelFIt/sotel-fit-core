path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# Encontra o início da seção Minha Jornada
start_marker = "\n      {/* Minha Jornada */}"
end_marker = "\n    </div>\n  )\n}"

start_idx = content.find(start_marker)
if start_idx == -1:
    print("ERRO: marcador nao encontrado")
else:
    # Mantém apenas o fechamento correto
    content = content[:start_idx] + "\n    </div>\n  )\n}"
    open(path, 'w', encoding='utf-8').write(content)
    print('OK - removido em idx:', start_idx)
    print('Minha Jornada:', content.count('Minha Jornada'))
    print('Final:', repr(content[-100:])) 