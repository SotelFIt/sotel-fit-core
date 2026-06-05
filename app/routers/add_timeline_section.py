path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# Adiciona estado de timeline
old = "  const [loading, setLoading] = useState(true)"
new = "  const [timeline, setTimeline] = useState<any[]>([])\n  const [loading, setLoading] = useState(true)"
content = content.replace(old, new, 1)

# Adiciona chamada de timeline no loadData
old2 = "        api.get(`/clients/${clientId}/checkins`),"
new2 = "        api.get(`/clients/${clientId}/checkins`),\n        api.get(`/timeline/client/${clientId}?limit=50`),"
content = content.replace(old2, new2, 1)

old3 = "      if (photoRes.status === 'fulfilled') setCheckins(photoRes.value.data)"
new3 = "      if (photoRes.status === 'fulfilled') setCheckins(photoRes.value.data)\n      if ((await Promise.allSettled([]))[0]) {}\n      const tlRes = await Promise.allSettled([api.get(`/timeline/client/${clientId}?limit=50`)])\n      if (tlRes[0].status === 'fulfilled') setTimeline((tlRes[0] as any).value.data)"
content = content.replace(old3, new3, 1)

open(path, 'w', encoding='utf-8').write(content)
print('OK')