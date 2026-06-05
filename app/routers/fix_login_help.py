path = 'C:/Users/sot_s/OneDrive/Desktop/Sotel Fit Core/sotel-client/src/pages/LoginPage.tsx'
content = open(path, 'r', encoding='utf-8-sig').read()

old = '''      <p className="text-center text-xs text-muted font-mono mt-auto pt-10">
        Sotel Fit Core v1.0
      </p>'''

new = '''      <div className="mt-auto pt-10 text-center space-y-3">
        <button
          onClick={() => setShowHelp(!showHelp)}
          className="text-xs text-gray-500 underline underline-offset-2"
        >
          Nao consigo acessar
        </button>
        {showHelp && (
          <div className="rounded-2xl px-4 py-3 text-left" style={{ background: 'rgba(0,232,122,0.06)', border: '1px solid rgba(0,232,122,0.15)' }}>
            <p className="text-sm text-white font-semibold mb-1">Precisa de ajuda?</p>
            <p className="text-xs text-gray-400 leading-relaxed">
              Use o e-mail que voce informou no cadastro. Se nao lembrar, fale com seu personal pelo WhatsApp — ele pode reenviar seu acesso.
            </p>
          </div>
        )}
        <p className="text-xs text-muted font-mono">Sotel Fit Core v1.0</p>
      </div>'''

content = content.replace(old, new, 1)

# Adiciona useState para showHelp
content = content.replace(
    "  const [error, setError] = useState('')",
    "  const [error, setError] = useState('')\n  const [showHelp, setShowHelp] = useState(false)"
)

open(path, 'w', encoding='utf-8').write(content)
print('OK')