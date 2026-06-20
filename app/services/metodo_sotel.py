"""
Metodo Sotel V1 - camada de decisao estrategica para os geradores de treino e dieta.

Logica PURA: nao acessa banco, nao chama IA, nao depende de FastAPI.
Recebe um dict de dados do onboarding e retorna um dict com a diretriz estrategica.

Uso:
    from services.metodo_sotel import decidir
    resultado = decidir(dados)
    # resultado["diretriz"]  -> texto para injetar no prompt
    # resultado["status"]    -> "ok" | "requires_admin_definition"
    # resultado["modo"]      -> "sotel" | "assistido"

NAO contem prescricao de exercicios nem alimentos. Contem apenas diretrizes
estrategicas (o "como pensar") que orientam a IA antes dela montar o draft.
As regras aqui pertencem ao Metodo Sotel e devem ser preenchidas/validadas pelo Sotel.
"""

import logging

logger = logging.getLogger(__name__)


# =========================================================================
# ALERTA OBRIGATORIO (modo assistido - perfil sem regra definida)
# =========================================================================
ALERTA_ASSISTIDO = (
    "ATENCAO:\n"
    "Este perfil ainda nao possui regra completa cadastrada no Metodo Sotel V1.\n"
    "O conteudo abaixo foi gerado em modo assistido e exige revisao administrativa "
    "obrigatoria antes da liberacao ao cliente."
)

# Principios conservadores aplicados SEMPRE (inclusive no modo assistido)
PRINCIPIOS_CONSERVADORES = (
    "PRINCIPIOS OBRIGATORIOS DO METODO SOTEL (seguir sempre):\n"
    "- Seguranca acima de intensidade.\n"
    "- Limitacoes acima de performance.\n"
    "- Aderencia acima de perfeicao.\n"
    "- Musculacao como ferramenta principal.\n"
    "- Intensidade moderada.\n"
    "- Sem hipertrofia agressiva.\n"
    "- Sem dietas extremas.\n"
    "- Revisao obrigatoria do administrador antes de liberar."
)


# =========================================================================
# 1. INFERENCIA DE COMPOSICAO (proxy conservador via IMC - padrao OMS)
# =========================================================================
def _inferir_composicao(dados: dict) -> str:
    """Retorna: 'obeso' | 'sobrepeso' | 'eutrofico' | 'indefinido'."""
    peso = _to_float(dados.get("peso"))
    altura = _to_float(dados.get("altura"))

    if not peso or not altura:
        return "indefinido"

    # altura pode vir em cm (ex: 175) ou em m (ex: 1.75)
    altura_m = altura / 100.0 if altura > 3 else altura
    if altura_m <= 0:
        return "indefinido"

    imc = peso / (altura_m ** 2)

    if imc >= 30:
        return "obeso"
    if imc >= 25:
        return "sobrepeso"
    return "eutrofico"


def _to_float(v):
    try:
        if v is None:
            return None
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


# =========================================================================
# 2. NORMALIZACAO DE ENTRADAS (strings livres do onboarding -> valores fixos)
# =========================================================================
def _norm(texto) -> str:
    return (str(texto) if texto is not None else "").strip().lower()


def _normalizar_nivel(dados: dict) -> str:
    """Retorna: 'iniciante' | 'intermediario' | 'avancado' | 'indefinido'."""
    n = _norm(dados.get("nivel_treino"))
    if not n:
        return "indefinido"
    if "inici" in n or "nunca" in n or "comec" in n:
        return "iniciante"
    if "interm" in n or "medio" in n or "moder" in n:
        return "intermediario"
    if "avanc" in n or "experiente" in n or "avancado" in n:
        return "avancado"
    return "indefinido"


def _normalizar_objetivo(dados: dict) -> str:
    """Retorna: 'emagrecimento' | 'hipertrofia' | 'recomposicao' | 'indefinido'."""
    o = _norm(dados.get("objetivo")) + " " + _norm(dados.get("meta_principal"))
    if "emagre" in o or "perder" in o or "gordura" in o or "secar" in o or "definir" in o:
        return "emagrecimento"
    if "hipertrof" in o or "massa" in o or "musculo" in o or "ganhar" in o:
        return "hipertrofia"
    if "recompos" in o or "tonific" in o:
        return "recomposicao"
    return "indefinido"


def _normalizar_sexo(dados: dict) -> str:
    s = _norm(dados.get("sexo"))
    if s.startswith("f") or "mulher" in s or "femin" in s:
        return "feminino"
    if s.startswith("m") or "homem" in s or "mascul" in s:
        return "masculino"
    return "indefinido"


# =========================================================================
# 3. DETECCAO DE MODIFICADORES (em lesoes / observacoes / texto livre)
# =========================================================================
def _detectar_modificadores(dados: dict) -> list:
    """Retorna lista de codigos de modificador ativos: M01, M02, M03, M04."""
    blob = " ".join([
        _norm(dados.get("lesoes")),
        _norm(dados.get("observacoes")),
        _norm(dados.get("maior_dificuldade")),
        _norm(dados.get("alimentacao_atual")),
    ])
    mods = []
    if any(k in blob for k in ["mounjaro", "ozempic", "tirzepatida", "semaglutida", "wegovy", "saxenda"]):
        mods.append("M01")
    if "menopausa" in blob or "climaterio" in blob:
        mods.append("M02")
    if "lipedema" in blob:
        mods.append("M03")
    if any(k in blob for k in ["dor", "articular", "joelho", "ombro", "coluna", "lesao", "lesão", "hernia", "tendin"]):
        mods.append("M04")
    return mods


# =========================================================================
# 4. PERFIS-BASE (diretrizes definidas pelo Sotel)
#    Apenas B01 e B02 tem regra real (Regras 1 e 2 do Sotel).
#    B03/B04/B05 estao registrados mas SEM diretriz -> caem em modo assistido.
# =========================================================================
def _perfil_base(sexo, nivel, composicao, objetivo) -> dict | None:
    """Retorna dict {codigo, diretriz} se houver regra definida, senao None."""

    # B01 - Iniciante + Obeso + Emagrecimento (Regra 1 do Sotel)
    if nivel == "iniciante" and composicao == "obeso" and objetivo == "emagrecimento":
        return {
            "codigo": "B01",
            "diretriz": (
                "PERFIL B01 - Iniciante, obeso, emagrecimento.\n"
                "TREINO: priorizar maquinas; baixo impacto; cardio presente em todas as sessoes; "
                "esforco perceptivel sem buscar intensidade maxima no inicio; progressao gradual; "
                "foco em adaptacao e construir confianca.\n"
                "DIETA: deficit calorico controlado; buscar melhora visual pela reducao de gordura "
                "antes de qualquer estrategia agressiva.\n"
                "EVITAR: alto impacto, intensidade maxima precoce, volume inutil."
            ),
        }

    # B02 - Iniciante + Sobrepeso + Emagrecimento (Regra 2 do Sotel, mulher)
    if nivel == "iniciante" and composicao in ("sobrepeso", "eutrofico") and objetivo == "emagrecimento":
        return {
            "codigo": "B02",
            "diretriz": (
                "PERFIL B02 - Iniciante, sobrepeso, emagrecimento.\n"
                "TREINO: alternar grupos superiores e inferiores; priorizar gasto energetico; "
                "intensidade progressiva; foco em aderencia.\n"
                "DIETA: deficit calorico controlado, sustentavel, focado em constancia.\n"
                "EVITAR: excesso de volume inutil; estrategias agressivas que prejudiquem a aderencia."
            ),
        }

    # B03, B04, B05 - registrados mas SEM diretriz definida pelo Sotel
    # (retornam None -> fluxo cai em modo assistido)
    return None


# =========================================================================
# 5. MODIFICADORES (ajustes - apenas M01 tem regra real, Regra 4 do Sotel)
# =========================================================================
def _aplicar_modificadores(mods: list) -> tuple:
    """Retorna (lista_textos_definidos, lista_codigos_sem_regra)."""
    textos = []
    sem_regra = []

    for m in mods:
        if m == "M01":  # Medicacao emagrecedora (Regra 4 do Sotel)
            textos.append(
                "MODIFICADOR M01 (medicacao emagrecedora - Mounjaro/Ozempic/Tirzepatida): "
                "revisar estrategia proteica; ajustar ingestao energetica; considerar reducao "
                "de saciedade (cliente tende a comer menos). Atencao nutricional reforcada."
            )
        else:
            # M02 menopausa, M03 lipedema, M04 dor articular - sem regra definida ainda
            sem_regra.append(m)

    return textos, sem_regra


# =========================================================================
# FUNCAO PRINCIPAL
# =========================================================================
def decidir(dados: dict) -> dict:
    """
    Recebe dados do onboarding e retorna:
      { "diretriz": str, "status": str, "modo": str, "debug": dict }

    status: "ok" | "requires_admin_definition"
    modo:   "sotel" | "assistido"
    """
    composicao = _inferir_composicao(dados)
    nivel = _normalizar_nivel(dados)
    sexo = _normalizar_sexo(dados)
    objetivo_declarado = _normalizar_objetivo(dados)

    # --- REGRA DE SEGURANCA: composicao domina objetivo ---
    # Sem % de gordura, se ha sinais de sobrepeso/obesidade e o objetivo e hipertrofia,
    # NAO liberar superavit agressivo -> rebaixar para recomposicao.
    objetivo_efetivo = objetivo_declarado
    seguranca_aplicada = False
    if objetivo_declarado == "hipertrofia" and composicao in ("sobrepeso", "obeso"):
        objetivo_efetivo = "recomposicao"
        seguranca_aplicada = True

    mods = _detectar_modificadores(dados)
    mod_textos, mod_sem_regra = _aplicar_modificadores(mods)

    perfil = _perfil_base(sexo, nivel, composicao, objetivo_efetivo)

    debug = {
        "composicao": composicao, "nivel": nivel, "sexo": sexo,
        "objetivo_declarado": objetivo_declarado, "objetivo_efetivo": objetivo_efetivo,
        "seguranca_aplicada": seguranca_aplicada,
        "modificadores": mods, "perfil": perfil["codigo"] if perfil else None,
    }

    partes = []

    # Nota de seguranca, se aplicada
    if seguranca_aplicada:
        partes.append(
            "NOTA DE SEGURANCA: ha sinais de sobrepeso/obesidade e o objetivo declarado e "
            "hipertrofia. Sem avaliacao de gordura corporal, NAO usar superavit agressivo. "
            "Estrategia = recomposicao com preservacao muscular. Comunicar ao cliente como "
            "caminho para o objetivo, nao como recusa."
        )

    # --- CASO 1: perfil COM regra definida -> modo Sotel ---
    if perfil is not None:
        partes.append(perfil["diretriz"])
        partes.extend(mod_textos)
        if mod_sem_regra:
            partes.append(
                "MODIFICADORES SEM REGRA DEFINIDA (" + ", ".join(mod_sem_regra) + "): "
                "aplicar principios conservadores e sinalizar para revisao do admin."
            )
        partes.append(
            "HIERARQUIA: seguranca > limitacoes > aderencia > composicao > objetivo. "
            "Em qualquer conflito, seguranca e aderencia vencem intensidade."
        )

        status = "requires_admin_definition" if mod_sem_regra else "ok"
        modo = "sotel"
        diretriz = "\n\n".join(partes)

        # Se ha modificador sem regra, ainda assim avisa o admin (sem bloquear)
        if mod_sem_regra:
            diretriz = ALERTA_ASSISTIDO + "\n\n" + diretriz

        return {"diretriz": diretriz, "status": status, "modo": modo, "debug": debug}

    # --- CASO 2: perfil SEM regra -> modo assistido com alerta obrigatorio ---
    partes.insert(0, ALERTA_ASSISTIDO)
    partes.append(PRINCIPIOS_CONSERVADORES)
    partes.extend(mod_textos)
    if mod_sem_regra:
        partes.append(
            "MODIFICADORES SEM REGRA DEFINIDA (" + ", ".join(mod_sem_regra) + "): "
            "aplicar principios conservadores; revisao do admin obrigatoria."
        )
    partes.append(
        "HIERARQUIA: seguranca > limitacoes > aderencia > composicao > objetivo."
    )

    return {
        "diretriz": "\n\n".join(partes),
        "status": "requires_admin_definition",
        "modo": "assistido",
        "debug": debug,
    }
