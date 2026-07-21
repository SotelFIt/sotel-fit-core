"""
workout_extract - Extrator MINIMO de exercicios do texto do plano (LIB-005, Parte B).

Responsabilidade EXCLUSIVA: dado o texto do plano (`published_content`), devolver
a lista de ocorrencias de exercicio na ordem do plano, cada uma como:
    { "name": <str exatamente como no plano>, "context_path": "Treino X[/Grupo]" }

Isto NAO renderiza, NAO resolve identidade, NAO persiste e NAO chama a Biblioteca.
A resolucao name->slug (e os aliases) e responsabilidade da Biblioteca.

PARIDADE (justificativa do port): o cliente ja parseia o mesmo texto em
`sotel-client/src/lib/parseWorkout.ts`. Para o enriquecimento apontar para os
MESMOS itens que o aluno ve, a classificacao de "o que e exercicio" precisa ser
identica. Portamos SOMENTE o subconjunto de classificacao/nome/secao do parser
(sem weekday/focus/render/session-key) e travamos a igualdade por golden test
(`test_workout_extract_golden.py`) sobre as fixtures reais de producao.
"""
import re
from typing import List, Dict

# --- padroes (traducao fiel de parseWorkout.ts) ---------------------------

REP_RE = re.compile(
    r"\d+\s*[x×]\s*\d+(?:\s*[-–—]\s*\d+)?"
    r"|\d+\s*(?:a|at[ée])\s*\d+"
    r"|\d+\s*(?:rep|s[ée]rie|serie|segundos?|seg|min|passo|[\"'])",
    re.IGNORECASE,
)

HEADER_TREINO = re.compile(
    r"^treino\s+([a-z])\b\s*[-–—:•·]?\s*(.*)$", re.IGNORECASE
)
HEADER_WEEKDAY_PIPE_TREINO = re.compile(
    r"^\s*(.+?)\s*\|\s*treino\s+([a-z])\b\s*[-–—]?\s*(.*)$", re.IGNORECASE
)
TECH_RE = re.compile(
    r"^(bi[-\s]?s[ée]rie|super[-\s]?s[ée]rie|tri[-\s]?s[ée]rie"
    r"|super[-\s]?set|bi[-\s]?set|drop[-\s]?set|conjugad|pir[âa]mide)",
    re.IGNORECASE,
)
STOP_SECTION_RE = re.compile(
    r"^(orienta[çc][õo]es|restri[çc][õo]es|progress[ãa]o"
    r"|diretrizes|pr[óo]ximos passos|nota final|estrutura|ader[êe]ncia)\b",
    re.IGNORECASE,
)
META_LINE_RE = re.compile(
    r"^\s*(dura[çc][ãa]o|foco|descanso entre|intensidade|op[çc][ãa]o\s)",
    re.IGNORECASE,
)
OBS_LABEL_RE = re.compile(
    r"^\s*(observa[çc][ãa]o|nota|obs)\s*:?\s*", re.IGNORECASE
)

_LEAD_DECOR = re.compile(
    r"^[\s\U0001F000-\U0001FAFF←-⯿️•*>·#+]+"
)
_LEAD_KEYCAP = re.compile(r"^\s*\d️?⃣[\s.)]*")
_LEAD_ENUM = re.compile(r"^\s*\d{1,2}[.)º°]\s+")

_EX_NAME_TRIM = re.compile(r"[-–—|:(·•=\s]+$")
_HAS_LETTER = re.compile(r"[a-zà-ÿ]", re.IGNORECASE)
_ONLY_LETTERS = re.compile(r"[^A-Za-zÀ-ÿ]")
_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|?\s*$")


def _strip_lead(s0: str) -> str:
    s = _LEAD_DECOR.sub("", s0)
    s = _LEAD_KEYCAP.sub("", s)
    s = _LEAD_ENUM.sub("", s)
    return s.strip()


def _titleize(s: str) -> str:
    t = s.strip().lower()
    return (t[0].upper() + t[1:]) if t else t


def _is_muscle_subheader(s: str) -> bool:
    if not s or re.search(r"\d", s):
        return False
    if len(s) > 26:
        return False
    if len(s.split()) > 3:
        return False
    letters = _ONLY_LETTERS.sub("", s)
    if len(letters) < 2:
        return False
    return letters == letters.upper()


def _parse_table_row_name(line: str):
    t = line.strip()
    if not t.startswith("|"):
        return None
    if _TABLE_SEP.match(t):
        return None
    cells = [c.strip() for c in t.split("|")]
    while cells and cells[0] == "":
        cells.pop(0)
    while cells and cells[-1] == "":
        cells.pop()
    if len(cells) < 2:
        return None
    sets_idx = next((i for i, c in enumerate(cells) if REP_RE.search(c)), -1)
    if sets_idx <= 0:
        return None
    name = cells[0]
    return name or None


def _parse_exercise_name(body: str):
    m = REP_RE.search(body)
    if not m:
        return None
    name = _EX_NAME_TRIM.sub("", body[: m.start()]).strip()
    if not name or not _HAS_LETTER.search(name):
        return None
    return name


def extract_exercises(raw: str) -> List[Dict[str, str]]:
    """Lista ordenada de {name, context_path}. Vazia se o texto nao tiver treino."""
    if not raw or not raw.strip():
        return []

    workouts = []          # cada: {"title": str, "sections": [ {"name": str, "ex": [str]} ]}
    current = None
    section = None
    pending_tech = False
    ignoring = False

    def ensure_section(cur):
        nonlocal section
        if section is None:
            section = {"name": "", "ex": []}
            cur["sections"].append(section)
        return section

    def push_exercise(cur, name):
        nonlocal pending_tech
        sec = ensure_section(cur)
        sec["ex"].append(name)
        pending_tech = False

    def start_treino(division):
        nonlocal current, section, pending_tech, ignoring
        section = None
        pending_tech = False
        ignoring = False
        current = {"title": f"Treino {division.upper()}", "sections": []}
        workouts.append(current)

    for raw_line in raw.split("\n"):
        trimmed = raw_line.replace("\r", "").strip()
        if not trimmed:
            continue
        led = _strip_lead(trimmed)

        mh = HEADER_TREINO.match(led)
        if mh:
            start_treino(mh.group(1))
            continue
        mh = HEADER_WEEKDAY_PIPE_TREINO.match(trimmed)
        if mh:
            start_treino(mh.group(2))
            continue

        if STOP_SECTION_RE.match(led):
            ignoring = True
            continue
        if ignoring or current is None:
            continue
        cur = current

        if TECH_RE.match(led):
            pending_tech = True
            continue

        if _is_muscle_subheader(led):
            section = {"name": _titleize(led), "ex": []}
            cur["sections"].append(section)
            continue

        trow = _parse_table_row_name(trimmed)
        if trow:
            push_exercise(cur, trow)
            continue

        if OBS_LABEL_RE.match(trimmed):
            continue
        if META_LINE_RE.match(trimmed):
            continue

        ex = _parse_exercise_name(led)
        if ex:
            push_exercise(cur, ex)
            continue
        # demais linhas: observacao do ultimo exercicio -> ignorada na extracao

    items: List[Dict[str, str]] = []
    for w in workouts:
        secs = [s for s in w["sections"] if s["ex"]]
        if not any(s["ex"] for s in secs):
            continue
        for s in secs:
            ctx = w["title"] + ("/" + s["name"] if s["name"] else "")
            for name in s["ex"]:
                items.append({"name": name, "context_path": ctx})
    return items
