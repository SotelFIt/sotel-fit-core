"""
client_safe.py - sanitizador de conteudo administrativo.

Funcao publica: make_client_safe(content: str) -> str.

Pega o rascunho gerado pela IA (ou editado pelo admin) e devolve
markdown limpo, sem cabecalhos de rascunho, sem blocos administrativos,
sem marcadores de metodo interno, sem separadores soltos e sem cards
vazios. Se sobrar nada util, retorna mensagem amigavel.
"""
import re

EMPTY_FALLBACK = "Plano em revisão. Em breve seu conteúdo estará disponível."

# Frases que, se encontradas em uma linha (case-insensitive),
# fazem a linha INTEIRA ser removida.
LINE_KILL_TOKENS = [
    "RASCUNHO",
    "REVISAO OBRIGATORIA", "REVISÃO OBRIGATÓRIA",
    "REVISAO ADMINISTRATIVA", "REVISÃO ADMINISTRATIVA",
    "AGUARDANDO REVISAO", "AGUARDANDO REVISÃO",
    "LEIA ANTES DE LIBERAR",
    "STATUS:",
    "DEBUG",
    "METODO SOTEL APLICADO", "MÉTODO SOTEL APLICADO",
    "PERFIL IDENTIFICADO",
    "MODIFICADORES",
    "VALIDACAO ADMINISTRATIVA", "VALIDAÇÃO ADMINISTRATIVA",
]

# Cabecalhos (##) que iniciam um bloco administrativo COMPLETO.
# Tudo, da linha do cabecalho ate o proximo separador (---/***/___)
# ou ate outro cabecalho ## ou ate o fim do texto, sai.
BLOCK_HEADER_TOKENS = [
    "NOTAS IMPORTANTES",
    "AVISOS CRITICOS", "AVISOS CRÍTICOS",
    "PENDENCIAS PARA VALIDACAO", "PENDÊNCIAS PARA VALIDAÇÃO",
    "PENDENCIAS", "PENDÊNCIAS",
    "VALIDACAO ADMINISTRATIVA", "VALIDAÇÃO ADMINISTRATIVA",
    "LEIA ANTES DE LIBERAR",
    "DEBUG",
]

# Marcadores internos de metodo: [B01]..[B19], [M01]..[M09]
MARKER_REGEX = re.compile(r"\[\s*[BM]\s*\d{2}\s*\]", re.IGNORECASE)

# Linhas que sao SO separador (depois de strip).
SEPARATOR_REGEX = re.compile(r"^[\-_\*\s]*$")

# Linhas de metadado do cliente que NAO devem aparecer no app
# (o cliente ja sabe que e dele).
CLIENT_META_REGEX = re.compile(
    r"^\s*\*{0,2}\s*Cliente\s*\*{0,2}\s*[:\-|].*",
    re.IGNORECASE
)

# Traducao de jargao tecnico de treino para linguagem do cliente.
JARGON_MAP = [
    ("TREM SUPERIOR", "PARTE SUPERIOR"),
    ("Trem Superior", "Parte Superior"),
    ("trem superior", "parte superior"),
    ("TREM INFERIOR", "PERNAS E GLÚTEOS"),
    ("Trem Inferior", "Pernas e Glúteos"),
    ("trem inferior", "pernas e glúteos"),
]

def _is_separator_only(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) < 3:
        return False
    return bool(re.fullmatch(r"[\-_\*\s]+", stripped))

def _is_kill_line(line: str) -> bool:
    upper = line.upper()
    return any(tok in upper for tok in LINE_KILL_TOKENS)

def _is_block_header(line: str) -> bool:
    """Detecta cabecalho ## que inicia bloco administrativo."""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return False
    cleaned = stripped.lstrip("#").strip()
    cleaned_upper = cleaned.upper()
    return any(tok in cleaned_upper for tok in BLOCK_HEADER_TOKENS)

def _is_header(line: str) -> bool:
    return line.strip().startswith("#")

def _strip_markdown_visual(line: str) -> str:
    """Remove TODO markdown visual: #, **, *, marcadores soltos."""
    s = line
    s = re.sub(r"^\s*#{1,6}\s*", "", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(?!\s)([^*\n]+?)(?<!\s)\*", r"\1", s)
    s = s.replace("*", "")
    return s

def _apply_jargon_translation(text: str) -> str:
    """Traduz jargao tecnico para linguagem do cliente."""
    for old, new in JARGON_MAP:
        text = text.replace(old, new)
    return text

def _remove_admin_blocks(lines):
    """Remove blocos delimitados por cabecalho administrativo + ate proximo
    separador ou proximo cabecalho ## ou fim."""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_block_header(line):
            i += 1
            while i < len(lines):
                if _is_separator_only(lines[i]):
                    i += 1
                    break
                if _is_header(lines[i]):
                    break
                i += 1
            continue
        out.append(line)
        i += 1
    return out

def _remove_empty_sections(lines):
    """Remove titulos (linhas que comecam com #) que nao tem conteudo util
    abaixo. Conteudo util = linha nao-vazia, nao-separador, nao-titulo."""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_header(line):
            has_content = False
            j = i + 1
            while j < len(lines):
                peek = lines[j]
                if _is_header(peek):
                    break
                if peek.strip() and not _is_separator_only(peek):
                    has_content = True
                    break
                j += 1
            if not has_content:
                i = j
                continue
        out.append(line)
        i += 1
    return out

def make_client_safe(content) -> str:
    if not content or not str(content).strip():
        return EMPTY_FALLBACK

    text = str(content)
    text = _apply_jargon_translation(text)
    text = MARKER_REGEX.sub("", text)

    lines = text.split("\n")
    lines = _remove_admin_blocks(lines)

    cleaned = []
    for line in lines:
        if _is_kill_line(line):
            continue
        if _is_separator_only(line):
            continue
        if CLIENT_META_REGEX.match(line):
            continue
        cleaned.append(line)
    lines = cleaned

    lines = _remove_empty_sections(lines)
    lines = [_strip_markdown_visual(l) for l in lines]

    text = "\n".join(l.rstrip() for l in lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if not text:
        return EMPTY_FALLBACK

    return text
