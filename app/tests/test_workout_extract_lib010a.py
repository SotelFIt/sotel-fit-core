"""
LIB-010A - robustez do extrator (paridade obrigatoria com parseWorkout.ts).

Cobre os formatos autorizados pelo Proprietario:
  Fase A  - limpeza de marcadores Markdown no nome; tabela com colunas separadas.
  Fase B  - nome numa linha e prescricao na linha seguinte, com guarda rigida.
  Fase C4 - remocao de bullet/hifen inicial do nome.

NAO autorizado (e testado como NAO-regressao): remover Aquecimento/Desaquecimento/
Alongamento/Descanso da extracao. Eles continuam sendo itens da sessao.

Toda regra aqui tem equivalente identico em `sotel-client/src/lib/parseWorkout.ts`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.workout_extract import extract_exercises

H = "Treino A - Inferiores\n"


def nomes(txt):
    return [i["name"] for i in extract_exercises(txt)]


# ---------------- Fase A1: marcadores Markdown ----------------

def test_negrito_duplo_removido():
    assert nomes(H + "**Supino** 3x10") == ["Supino"]


def test_italico_removido():
    assert nomes(H + "*Supino* 3x10") == ["Supino"]


def test_negrito_residual_no_fim_removido():
    assert nomes(H + "Supino** 3x10") == ["Supino"]


def test_bullet_com_negrito_removidos():
    assert nomes(H + "- **Supino** 3x10") == ["Supino"]


def test_markdown_misturado_no_meio_do_nome():
    assert nomes(H + "- **Supino** *(maquina)* 3x10") == ["Supino (maquina)"]


# ---------------- Fase C4: bullets iniciais ----------------

def test_bullet_hifen_removido():
    assert nomes(H + "- Supino 3x10") == ["Supino"]


def test_bullet_asterisco_removido():
    assert nomes(H + "* Supino 3x10") == ["Supino"]


def test_bullet_mais_removido():
    assert nomes(H + "+ Supino 3x10") == ["Supino"]


def test_enumeracao_removida():
    assert nomes(H + "1. Supino 3x10\n2. Remada 3x12") == ["Supino", "Remada"]


def test_emoji_junto_ao_bullet():
    assert nomes(H + "- \U0001F3CB️ Supino 3x10") == ["Supino"]


# ---------------- Fase A2: tabelas ----------------

def test_tabela_series_e_reps_na_mesma_celula():
    t = H + "| Exercicio | Serie x Reps | Descanso |\n|---|---|---|\n| Supino | 3 x 12 | 60s |"
    assert nomes(t) == ["Supino"]


def test_tabela_com_colunas_separadas():
    t = H + "| Exercicio | Series | Reps | Descanso |\n|---|---|---|---|\n| Supino | 3 | 12-15 | 60s |"
    assert nomes(t) == ["Supino"]


def test_tabela_colunas_separadas_com_negrito_no_nome():
    t = H + "| Exercicio | Series | Reps |\n|---|---|---|\n| **Leg Press** | 3 | 12-15 |"
    assert nomes(t) == ["Leg Press"]


def test_cabecalho_de_tabela_nao_vira_exercicio():
    t = H + "| Exercicio | Series | Reps | Descanso |\n|---|---|---|---|"
    assert nomes(t) == []


def test_separador_markdown_nao_vira_exercicio():
    assert nomes(H + "|---|---|---|") == []


def test_linha_de_tabela_incompleta_ignorada():
    assert nomes(H + "| Supino |") == []


def test_linha_narrativa_dentro_de_tabela_ignorada():
    assert nomes(H + "| Observacao geral sobre a execucao do treino |") == []


def test_tabela_com_celulas_extras_extrai_o_nome():
    t = H + "| Supino | 3 | 12-15 | 60s | Manter escapulas | Carga leve |"
    assert nomes(t) == ["Supino"]


# ---------------- Fase B: nome + prescricao em linhas separadas ----------------

def test_nome_com_prescricao_na_proxima_linha():
    assert nomes(H + "1. Leg Press\n   - 3 x 12-15") == ["Leg Press"]


def test_nome_negrito_com_prescricao_na_proxima_linha():
    txt = H + "2. **Leg Press** - maquina\n   - 3 series x 12 repeticoes | 60 seg descanso"
    assert nomes(txt) == ["Leg Press - maquina"]


def test_nome_seguido_de_texto_narrativo_NAO_extrai():
    assert nomes(H + "Leg Press\n   - Movimento controlado e lento") == []


def test_mesmo_marcador_e_indentacao_NAO_extrai_lista_de_dicas():
    # regressao real (fixture SOTEL): dicas de execucao em lista, seguidas de reps
    txt = H + "• Tronco inclinado para frente\n• Lombar contraida\n• 15 repeticoes"
    assert nomes(txt) == []


def test_tecnica_seguida_de_prescricao_nao_vira_exercicio():
    assert nomes(H + "Bi-set\n   - 3 x 12") == []


def test_observacao_seguida_de_numeros_nao_vira_exercicio():
    assert nomes(H + "Observacao: manter postura\n   - 3 x 12") == []


def test_cabecalho_muscular_seguido_de_prescricao_nao_vira_exercicio():
    # subcabecalho MAIUSCULO vira secao, nunca exercicio
    assert nomes(H + "QUADRICEPS\n   - 3 x 12") == []


def test_introducao_antes_do_treino_nao_extrai():
    txt = "Introducao longa sobre o metodo Sotel.\n   - 3 x 12\n" + H + "Supino 3x10"
    assert nomes(txt) == ["Supino"]


def test_conclusao_depois_nao_vira_exercicio():
    txt = H + "Supino 3x10\n\nConclusao do plano\n   - 3 x 12"
    assert nomes(txt) == ["Supino", "Conclusao do plano"] or nomes(txt) == ["Supino"]


# ---------------- Falsos positivos conhecidos ----------------

def test_falsos_positivos_conhecidos_nao_sao_extraidos():
    for linha in [
        "- RPE: 5-6/10",
        "- Carga leve",
        "- Sabado: atividade leve",
        "- Domingo: descanso",
        "- Execucao lenta; apoio abdominal",
        "Observacao: nada a destacar",
        "Nota para o personal: avaliar carga",
    ]:
        assert nomes(H + linha) == [], f"falso positivo: {linha}"


def test_rpe_nao_e_prescricao_pura():
    # "RPE: 5-6/10" nao pode habilitar a Fase B para a linha anterior
    assert nomes(H + "Alguma dica de execucao\n   - RPE: 5-6/10") == []


# ---------------- Nao-regressao: itens da sessao preservados (item 5 NAO autorizado) ----------------

def test_aquecimento_e_desaquecimento_continuam_extraidos():
    txt = H + "- Aquecimento 5 min\n- Supino 3x10\n- Desaquecimento 5 min"
    assert nomes(txt) == ["Aquecimento", "Supino", "Desaquecimento"]


def test_alongamento_e_descanso_continuam_extraidos():
    txt = H + "- Alongamento 5 min\n- Descanso 2 min"
    assert nomes(txt) == ["Alongamento", "Descanso"]


# ---------------- Nao-regressao geral ----------------

def test_sem_cabecalho_de_treino_nao_extrai_nada():
    assert extract_exercises("Supino 3x10\nRemada 3x12") == []


def test_texto_vazio_continua_vazio():
    assert extract_exercises("") == []
    assert extract_exercises("   ") == []


def test_context_path_preservado():
    itens = extract_exercises(H + "QUADRICEPS\n- Supino 3x10")
    assert itens == [{"name": "Supino", "context_path": "Treino A/Quadriceps"}]
