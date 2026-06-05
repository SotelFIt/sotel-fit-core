path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
lines = open(path, 'r', encoding='utf-8-sig').readlines()
# Linha 307 (index 306) é onde começa o lixo
# Mantém linhas 1-306 e adiciona fechamento correto
new_lines = lines[:306]
new_lines.append('    </div>\n')
new_lines.append('  )\n')
new_lines.append('}\n')
open(path, 'w', encoding='utf-8').write(''.join(new_lines))
print('OK - total linhas:', len(new_lines))