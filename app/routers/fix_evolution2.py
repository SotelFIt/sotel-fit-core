path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

old = """  // Dados para gráficos
  const weightData = photosByDate.filter(g => g.weight).map(g => parseFloat(g.weight)).reverse()
  const gorduraData = history.filter(h => h.gordura_min && h.gordura_max).map(h => (h.gordura_min + h.gordura_max) / 2)
  const massaData = history.filter(h => h.massa_magra_min && h.massa_magra_max).map(h => (h.massa_magra_min + h.massa_magra_max) / 2)

  const pesoInicial = weightData[0] || null
  const pesoAtual = weightData[weightData.length - 1] || null
  const diffPeso = pesoInicial && pesoAtual ? pesoAtual - pesoInicial : null"""

new = """  // Dados para gráficos
  const checkinPesos = checkins
    .filter(c => c.peso)
    .map(c => ({ peso: parseFloat(c.peso), date: c.created_at?.slice(0, 10) || '' }))
    .reverse()

  const weightData = checkinPesos.map(c => c.peso)
  const weightDates = checkinPesos.map(c => c.date)
  const gorduraData = history.filter(h => h.gordura_min && h.gordura_max).map(h => (h.gordura_min + h.gordura_max) / 2)
  const massaData = history.filter(h => h.massa_magra_min && h.massa_magra_max).map(h => (h.massa_magra_min + h.massa_magra_max) / 2)

  const pesoInicial = weightData[0] || null
  const pesoAtual = weightData[weightData.length - 1] || null
  const diffPeso = pesoInicial && pesoAtual ? pesoAtual - pesoInicial : null
  const ultimoPesoDate = weightDates[weightDates.length - 1] || null"""

content = content.replace(old, new, 1)

open(path, 'w', encoding='utf-8').write(content)
print('OK - pesos:', content.count('checkinPesos')) 	