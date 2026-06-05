path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# Encontra onde começa o bloco sobrando — antes do upload form fecha corretamente
# O showUpload fecha com </div> e depois vem o lixo da timeline
# Encontra o ultimo fechamento correto do showUpload
cut_marker = "\n        </div>\n      )}\n    </div>\n  )\n}"
idx = content.rfind(cut_marker)
print('idx encontrado:', idx)

if idx != -1:
    content = content[:idx] + "\n        </div>\n      )}\n    </div>\n  )\n}"
    open(path, 'w', encoding='utf-8').write(content)
    print('Tamanho final:', len(content))
    print('Final:', repr(content[-200:]))