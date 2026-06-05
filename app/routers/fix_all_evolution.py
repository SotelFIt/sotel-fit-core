path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# 1. Remove photosByDate state e substitui por checkins
content = content.replace(
    "  const [photosByDate, setPhotosByDate] = useState<any[]>([])",
    "  const [checkins, setCheckins] = useState<any[]>([])"
)

# 2. Remove photosApi do Promise.allSettled e adiciona checkins
old_load = "        photosApi.listByDate(clientId),\n      ])\n      if (histRes.status === 'fulfilled') setHistory(histRes.value.data)\n      if (anaRes.status === 'fulfilled') setAnalysis(anaRes.value.data.analysis)\n      if (photoRes.status === 'fulfilled') setPhotosByDate(photoRes.value.data)"
new_load = "        api.get(`/clients/${clientId}/checkins`),\n      ])\n      if (histRes.status === 'fulfilled') setHistory(histRes.value.data)\n      if (anaRes.status === 'fulfilled') setAnalysis(anaRes.value.data.analysis)\n      if (photoRes.status === 'fulfilled') setCheckins(photoRes.value.data)"
content = content.replace(old_load, new_load, 1)

# 3. Renomeia a variável no Promise.allSettled
content = content.replace(
    "const [histRes, anaRes, photoRes, checkinRes] = await Promise.allSettled([",
    "const [histRes, anaRes, photoRes] = await Promise.allSettled(["
)
content = content.replace(
    "      if (checkinRes.status === 'fulfilled') setCheckins(checkinRes.value.data)\n",
    ""
)

open(path, 'w', encoding='utf-8').write(content)

# Verifica
c2 = open(path, 'r', encoding='utf-8').read()
print('setCheckins:', c2.count('setCheckins'))
print('photosByDate:', c2.count('photosByDate'))
print('checkins state:', c2.count("useState<any[]>([])"))