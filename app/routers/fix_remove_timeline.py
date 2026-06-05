path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/EvolutionPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

# Remove estado de timeline
content = content.replace(
    "  const [timeline, setTimeline] = useState<any[]>([])\n",
    ""
)

# Remove chamada de timeline do Promise.allSettled
content = content.replace(
    "        api.get(`/timeline/client/${clientId}?limit=50`),\n",
    ""
)

# Remove destructuring de tlRes
content = content.replace(
    "      const [histRes, anaRes, photoRes, tlRes] = await Promise.allSettled([",
    "      const [histRes, anaRes, photoRes] = await Promise.allSettled(["
)

# Remove setTimeline
content = content.replace(
    "\n      if (tlRes.status === 'fulfilled') setTimeline((tlRes as any).value.data)",
    ""
)

# Remove seção Minha Jornada inteira
import re
content = re.sub(
    r'\s*\{/\* Minha Jornada \*/\}.*?</div>\s*\n\s*\)',
    '\n    )',
    content,
    flags=re.DOTALL
)

open(path, 'w', encoding='utf-8').write(content)
c2 = open(path, 'r', encoding='utf-8').read()
print('timeline:', c2.count('timeline'))
print('Minha Jornada:', c2.count('Minha Jornada'))