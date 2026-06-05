path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# O bloco da timeline começa com esta string
cut_marker = "\n      {timeline.length === 0 ? ("
idx = content.find(cut_marker)

if idx == -1:
    # Tenta alternativa
    cut_marker = "\n      <div className=\"px-4 mt-2 mb-6\">"
    idx = content.find(cut_marker)

if idx == -1:
    print("ERRO - marcador nao encontrado")
    print("Ultimos 500 chars:", repr(content[-500:]))
else:
    # Corta tudo a partir do marcador e fecha o JSX corretamente
    content = content[:idx] + "\n    </div>\n  )\n}"
    open(path, 'w', encoding='utf-8').write(content)
    print('OK - cortado em idx:', idx)
    print('Final:', repr(content[-100:]))