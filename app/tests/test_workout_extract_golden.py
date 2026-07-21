"""
LIB-005 Parte B - paridade do extrator com parseWorkout.ts (golden test).

O golden (`fixtures/golden_workout_extract.json`) foi GERADO rodando o proprio
`sotel-client/src/lib/parseWorkout.ts` sobre as fixtures reais de producao
(`fixtures/real_plans.json`, os mesmos planos de `realPlans.ts`). Este teste
trava a igualdade: o extrator do backend deve produzir EXATAMENTE os mesmos
{name, context_path} que o parser do cliente — incluindo linhas-ruido, que a
resolucao tratara como `unresolved`. Divergencia = quebra de paridade.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.workout_extract import extract_exercises

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _load(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return json.load(f)


def test_extrator_bate_exatamente_com_o_golden_do_parseworkout():
    plans = _load('real_plans.json')
    golden = _load('golden_workout_extract.json')
    assert set(plans) == set(golden)
    for k, raw in plans.items():
        got = extract_exercises(raw)
        exp = golden[k]['items'] if golden[k].get('ok') else []
        assert got == exp, f'plano {k}: extrator divergiu do parseWorkout.ts'


def test_texto_sem_treino_retorna_vazio():
    assert extract_exercises('Ola, isto nao e um plano.') == []
    assert extract_exercises('') == []
    assert extract_exercises('   ') == []
