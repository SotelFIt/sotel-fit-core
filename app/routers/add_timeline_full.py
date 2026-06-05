path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# 1. Adiciona estado timeline
content = content.replace(
    "  const [checkins, setCheckins] = useState<any[]>([])",
    "  const [checkins, setCheckins] = useState<any[]>([])\n  const [timeline, setTimeline] = useState<any[]>([])"
)

# 2. Adiciona timeline ao Promise.allSettled
content = content.replace(
    "        api.get(`/clients/${clientId}/checkins`),\n      ])",
    "        api.get(`/clients/${clientId}/checkins`),\n        api.get(`/timeline/client/${clientId}?limit=50`),\n      ])"
)

# 3. Adiciona destructuring de tlRes
content = content.replace(
    "      const [histRes, anaRes, photoRes] = await Promise.allSettled([",
    "      const [histRes, anaRes, photoRes, tlRes] = await Promise.allSettled(["
)

# 4. Salva resultado de tlRes
content = content.replace(
    "      if (photoRes.status === 'fulfilled') setCheckins(photoRes.value.data)",
    "      if (photoRes.status === 'fulfilled') setCheckins(photoRes.value.data)\n      if (tlRes.status === 'fulfilled') setTimeline((tlRes as any).value.data)"
)

# 5. Adiciona seção Minha Jornada antes do fechamento
timeline_section = """
      {/* Minha Jornada */}
      <div className="px-4 mt-2 mb-6">
        <p className="text-xs text-gray-500 font-mono uppercase tracking-widest mb-4">Minha Jornada</p>
        {timeline.length === 0 ? (
          <div className="rounded-2xl p-5 text-center" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <p className="text-gray-500 text-sm">Seu historico de evolucao aparecera aqui conforme voce utilizar o sistema.</p>
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
            <div className="space-y-4">
              {timeline.map((event: any, i: number) => {
                const date = new Date(event.created_at)
                const dateStr = date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
                const timeStr = date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
                return (
                  <div key={event.id || i} className="flex gap-4 pl-2">
                    <div className="relative z-10 w-6 h-6 rounded-full flex items-center justify-center text-sm flex-shrink-0 mt-0.5" style={{ background: '#111', border: '1px solid rgba(255,255,255,0.15)' }}>
                      <span>{event.icon || '\u26a1'}</span>
                    </div>
                    <div className="flex-1 rounded-2xl px-4 py-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
                      <p className="text-white text-sm font-semibold mb-0.5">{event.title}</p>
                      {event.description && <p className="text-gray-400 text-xs mb-1">{event.description}</p>}
                      <p className="text-gray-600 text-[10px] font-mono">{dateStr} \u00b7 {timeStr}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>"""

content = content.replace(
    "    </div>\n  )\n}",
    timeline_section + "\n    </div>\n  )\n}"
)

open(path, 'w', encoding='utf-8').write(content)

# Verifica
c2 = open(path, 'r', encoding='utf-8').read()
print('setTimeline:', c2.count('setTimeline'))
print('Minha Jornada:', c2.count('Minha Jornada'))
print('tlRes:', c2.count('tlRes'))
