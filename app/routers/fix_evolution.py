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

# Atualiza o card de peso para mostrar data e fallback
old2 = """          {/* Peso */}
          {pesoInicial && pesoAtual && (
            <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-[10px] text-gray-500 font-mono uppercase tracking-widest">Peso</p>
                {diffPeso !== null && <DiffBadge diff={diffPeso} unit="kg" />}
              </div>
              <div className="flex items-end justify-between mb-3">
                <div>
                  <p className="text-xs text-gray-600 mb-0.5">Inicio</p>
                  <p className="text-lg font-bold text-gray-400">{pesoInicial} kg</p>
                </div>
                <div className="text-gray-600">→</div>
                <div className="text-right">
                  <p className="text-xs text-green-400 mb-0.5">Agora</p>
                  <p className="text-lg font-bold text-white">{pesoAtual} kg</p>
                </div>
              </div>
              {weightData.length >= 2 && <MiniChart data={weightData} color="#00E87A" unit="kg" />}
            </div>
          )}"""

new2 = """          {/* Peso */}
          <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-widest">Peso</p>
              {diffPeso !== null && weightData.length >= 2 && <DiffBadge diff={diffPeso} unit="kg" />}
            </div>
            {weightData.length === 0 ? (
              <p className="text-sm text-gray-500">Nenhum peso registrado ainda.</p>
            ) : (
              <>
                <div className="flex items-end justify-between mb-3">
                  <div>
                    <p className="text-xs text-gray-600 mb-0.5">Inicio</p>
                    <p className="text-lg font-bold text-gray-400">{pesoInicial} kg</p>
                  </div>
                  <div className="text-gray-600">→</div>
                  <div className="text-right">
                    <p className="text-xs text-green-400 mb-0.5">Agora</p>
                    <p className="text-lg font-bold text-white">{pesoAtual} kg</p>
                    {ultimoPesoDate && <p className="text-[10px] text-gray-600 mt-0.5">{new Date(ultimoPesoDate + 'T12:00:00').toLocaleDateString('pt-BR')}</p>}
                  </div>
                </div>
                {weightData.length >= 2 && <MiniChart data={weightData} color="#00E87A" unit="kg" />}
              </>
            )}
          </div>"""

content = content.replace(old2, new2, 1)

# Remove peso dos cards antigos (gordura e massa já existem)
old3 = "      {(pesoInicial || gorduraInicial || massaInicial) && ("
new3 = "      {(true) && ("
content = content.replace(old3, new3, 1)

open(path, 'w', encoding='utf-8').write(content)
print('OK')