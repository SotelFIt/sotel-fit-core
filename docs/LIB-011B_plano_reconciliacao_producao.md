# LIB-011B — Plano de reconciliação de PRODUÇÃO (NÃO EXECUTADO)

> **Este documento não executa nada.** Ele descreve as duas operações de escrita que
> restam para produção ficar idêntica ao catálogo oficial. A execução é uma **missão
> operacional separada, com autorização própria** do Proprietário.
>
> Estado no fechamento da LIB-011B: produção segue com **as duas divergências abaixo**.

## Contexto

- Produção: **29 exercícios ativos** (`GET /exercises`).
- Catálogo oficial (`app/data/exercise_catalog_sprint1.json`): **29 exercícios** após a LIB-011B.
- Divergências restantes: **2** (ambas exigem escrita em produção).
- Autenticação: header `x-api-key` cujo valor é o `LANDBOT_SECRET_TOKEN`.
  Obter via `railway run` — **nunca** colar segredo em comando, log ou chat.

---

## A. `flexao-de-bracos` — alias duplicado sob normalização

**Problema:** produção tem `"Push Up"` **e** `"Push-Up"`; ambos normalizam para `push up`.
O `build_index` mantém o primeiro e descarta o segundo — o duplicado é inútil e polui o dado.

**Forma canônica escolhida:** `"Push Up"` — é a que está no catálogo oficial e a que o
resolver já usa. `"Push-Up"` sai. **Nenhum outro alias é removido.**

- **Endpoint:** `PATCH /admin/exercises/flexao-de-bracos`
- **Método:** PATCH (parcial) · **Header:** `x-api-key: <LANDBOT_SECRET_TOKEN>`
- **Payload sanitizado:**
  ```json
  { "aliases": ["Flexão", "Push Up", "Flexão no Solo"] }
  ```
- **Estado antes:** `aliases` = `["Flexão", "Push Up", "Flexão no Solo", "Push-Up"]` (4 itens, 3 chaves normalizadas)
- **Estado esperado depois:** `aliases` = 3 itens, 3 chaves normalizadas, **zero duplicata**
- **Rollback:** `PATCH` com a lista original de 4 itens (registrar o valor exato antes de executar)
- **Verificação pós-operação:**
  `GET /exercises/flexao-de-bracos` → `len(aliases) == 3`;
  `GET /exercises/resolve?name=Push Up` → `{slug: "flexao-de-bracos", match: "alias"}`;
  `GET /exercises/resolve?name=Push-Up` → **também** resolve (normaliza igual) — comportamento preservado.

## B. `equipment: "halter" → "halteres"` (2 registros)

**Problema:** vocabulário controlado não admite singular e plural coexistindo.

- **Endpoint:** `PATCH /admin/exercises/remada-unilateral` e `PATCH /admin/exercises/triceps-frances`
- **Payload sanitizado (cada um):**
  ```json
  { "equipment": "halteres" }
  ```
- **Estado antes:** `remada-unilateral.equipment = "halter"` · `triceps-frances.equipment = "halter"`
  (distribuição em produção: `halteres` 6, `halter` 2)
- **Estado esperado depois:** ambos `"halteres"`; distribuição `halteres` 8, `halter` **0**;
  valores distintos de `equipment` em produção: 6 → **5**
- **Rollback:** `PATCH` com `{"equipment": "halter"}` nos mesmos dois slugs
- **Verificação pós-operação:**
  `GET /exercises` → nenhum registro com `equipment == "halter"`;
  demais campos (`name`, `aliases`, `primary_muscle`, `level`, `is_active`) **inalterados**.

---

## Regras de execução (quando autorizada)

1. **Dry-run primeiro:** ler o estado atual dos 3 slugs e registrar o payload de rollback exato.
2. Um `PATCH` por vez, verificando após cada um.
3. `slug` é **imutável** (trigger no banco) — nenhuma operação aqui o altera.
4. Não tocar em `instructions`, `media`, `approved_substitutions`, `secondary_muscles`,
   `common_errors`, `cautions` — permanecem como estão.
5. Após concluir: rodar o importer em **`--dry-run`** e confirmar **0 conflitos**
   (hoje ele reportaria 3: a flexão e os 2 de `equipment`).

## Impacto se NÃO for executado

Nenhum risco funcional. O importer trata divergência como `conflict` — **não sobrescreve**.
O efeito é apenas que catálogo e produção seguem diferentes em 2 pontos, e o `--dry-run`
continuará acusando esses conflitos até a reconciliação.

## Decisão adicional pendente (não faz parte deste plano)

`supino-reto` está em produção com o nome **`"SUPINO RETO"`** (caixa alta), destoando do
padrão Title Case dos outros 28. Foi copiado **exatamente como está** para o catálogo
(regra: não alterar nome sem evidência). Padronizar exige decisão do Proprietário e um
`PATCH` adicional.
