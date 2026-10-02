"""
ymove - cliente da Exercise API da YMove.

Fornecedor de DEMONSTRACAO em video. A Biblioteca Sotel continua sendo a
referencia da prescricao: id, slug, nome, aliases, execucao, series, descanso e
substituicoes sao nossos. Daqui vem so o filme do movimento.

Tres regras do contrato do fornecedor moldam este modulo inteiro
(conferidas em https://exercise-api.ymove.app/api/v2/openapi.json):

1. **URL de video e pre-assinada e expira em 48h.** Ela nao pode ser gravada em
   `media[]`, no plano publicado, no banco nem no navegador. E buscada na hora
   em que o aluno pede a demonstracao.

2. **Cobranca e por EXERCICIO DISTINTO, nao por segundo assistido.**
   `monthlyExercisesUsed` = "Distinct exercises accessed in last 30 days".
   Listar com `excludeVideos=1` ("browse mode") **nao** consome cota. Entao a
   navegacao do admin e sempre browse, e o video so e pedido para a
   demonstracao escolhida.

3. **`thumbnailUrl` e estatico e nao expira**, e vem tambem em browse mode.
   Por isso ele PODE ser guardado: e o que da previa ao aluno sem gastar cota.

A chave vive so aqui, no servidor. Nunca vai para o frontend, para URL, para
log ou para resposta de erro.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("YMOVE_API_URL", "https://exercise-api.ymove.app/api/v2")
TIMEOUT = (5, 15)  # (conexao, leitura) — a tela do aluno nao pode ficar pendurada

PROVIDER = "ymove"


class YMoveIndisponivel(RuntimeError):
    """Fornecedor fora do ar, lento ou com erro interno. Transitorio."""


class YMoveSemCredencial(RuntimeError):
    """Chave ausente ou recusada. NAO e falha do aluno nem do exercicio."""


class YMoveLimiteAtingido(RuntimeError):
    """Cota mensal ou limite de requisicoes estourado."""


class YMoveNaoEncontrado(LookupError):
    """O exercicio nao existe no catalogo do fornecedor."""


def configurado() -> bool:
    """Ha credencial para falar com o fornecedor?

    Separado do resto porque a resposta muda o que a tela mostra: sem
    credencial a integracao fica indisponivel, e isso nao e erro de ninguem.
    """
    return bool(os.getenv("YMOVE_API_KEY"))


def _chamar(caminho: str, params: Optional[dict] = None) -> dict:
    chave = os.getenv("YMOVE_API_KEY")
    if not chave:
        raise YMoveSemCredencial("YMOVE_API_KEY nao configurada")

    try:
        r = requests.get(
            f"{BASE_URL}{caminho}",
            params=params or {},
            # Header, nunca query string: chave em URL vaza em log de proxy,
            # em Referer e no historico de qualquer intermediario.
            headers={"X-API-Key": chave, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise YMoveIndisponivel("o fornecedor demorou demais para responder")
    except requests.RequestException as e:
        # str(e) pode conter a URL chamada, nunca a chave (que vai em header).
        logger.warning("falha de rede ao chamar a YMove: %s", type(e).__name__)
        raise YMoveIndisponivel("nao foi possivel falar com o fornecedor")

    if r.status_code == 401:
        raise YMoveSemCredencial("credencial recusada pelo fornecedor")
    if r.status_code == 429:
        raise YMoveLimiteAtingido("limite de requisicoes do fornecedor atingido")
    if r.status_code == 404:
        raise YMoveNaoEncontrado("exercicio nao encontrado no fornecedor")
    if r.status_code >= 500:
        raise YMoveIndisponivel("o fornecedor respondeu com erro interno")
    if r.status_code >= 400:
        # 402/403 costumam ser cota/plano. Mensagem generica: o corpo do
        # fornecedor nao vai cru para a nossa tela.
        raise YMoveLimiteAtingido("o fornecedor recusou a chamada")

    try:
        return r.json()
    except ValueError:
        raise YMoveIndisponivel("resposta ilegivel do fornecedor")


def buscar(
    termo: Optional[str] = None,
    muscle_group: Optional[str] = None,
    equipment: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Candidatos para o vinculo. BROWSE MODE — nao consome cota mensal.

    `excludeVideos=1` vence qualquer default da chave, segundo o proprio
    contrato do fornecedor. E o que garante que paginar nao gaste cota.
    """
    params = {
        "excludeVideos": 1,
        "page": max(1, int(page)),
        "pageSize": min(50, max(1, int(page_size))),
    }
    if termo:
        params["search"] = termo
    if muscle_group:
        params["muscleGroup"] = muscle_group
    if equipment:
        params["equipment"] = equipment

    bruto = _chamar("/exercises", params)
    return {
        "itens": [_resumo(x) for x in (bruto.get("data") or [])],
        "paginacao": bruto.get("pagination") or {},
    }


def detalhe_sem_video(identificador: str) -> dict:
    """Metadados de um exercicio, sem pedir video. Nao consome cota."""
    bruto = _chamar(f"/exercises/{identificador}", {"excludeVideos": 1})
    return _resumo(bruto.get("data") or {})


def url_de_video(identificador: str, variante: Optional[str] = None) -> dict:
    """URL ASSINADA do video. **Consome cota** (exercicio distinto no mes).

    Chamada so quando o aluno pede a demonstracao — nunca ao abrir lista,
    nunca ao abrir o treino.
    """
    bruto = _chamar(f"/exercises/{identificador}")
    dados = bruto.get("data") or {}

    escolhido = None
    videos = dados.get("videos") or []
    if variante:
        escolhido = next((v for v in videos if v.get("tag") == variante), None)
    if escolhido is None:
        escolhido = next((v for v in videos if v.get("isPrimary")), None)
    if escolhido is None and videos:
        escolhido = videos[0]

    url = (escolhido or {}).get("videoUrl") or dados.get("videoUrl")
    if not url:
        raise YMoveNaoEncontrado("o fornecedor nao tem video para este exercicio")

    return {
        "url": url,
        "orientacao": (escolhido or {}).get("orientation") or "PORTRAIT",
        "duracao_s": dados.get("videoDurationSecs"),
        # Thumbnail estatico: pode acompanhar a resposta sem risco de expirar.
        "thumbnail": (escolhido or {}).get("thumbnailUrl") or dados.get("thumbnailUrl"),
    }


def uso() -> dict:
    """Consumo real da conta. Para o ADMIN — nunca para a tela do aluno."""
    bruto = _chamar("/usage")
    d = bruto.get("data") or {}
    return {
        "plano": d.get("plan"),
        "situacao": d.get("status"),
        "minutos_usados": d.get("minutesUsed"),
        "minutos_limite": d.get("minutesLimit"),
        "minutos_restantes": d.get("minutesRemaining"),
        "exercicios_distintos_no_mes": d.get("monthlyExercisesUsed"),
        "exercicios_limite": d.get("monthlyExerciseLimit"),
        "requisicoes_por_minuto": d.get("rateLimit"),
        "fim_do_teste": d.get("trialEndsAt"),
    }


def _resumo(x: dict) -> dict:
    """So o que interessa ao vinculo. Nada de URL assinada entra aqui.

    O `thumbnailUrl` entra porque o contrato diz, textualmente, que ele e
    "static and cacheable - it does not expire" e vem tambem em browse mode.
    """
    return {
        "provider": PROVIDER,
        "exercise_id": x.get("id"),
        "slug": x.get("slug"),
        "title": x.get("title"),
        "muscle_group": x.get("muscleGroup"),
        "equipment": x.get("equipment"),
        "difficulty": x.get("difficulty"),
        "has_video": bool(x.get("hasVideo")),
        "duration_secs": x.get("videoDurationSecs"),
        "thumbnail_url": x.get("thumbnailUrl"),
        "variantes": [
            {"tag": v.get("tag"), "orientacao": v.get("orientation"),
             "principal": bool(v.get("isPrimary"))}
            for v in (x.get("videos") or [])
        ],
    }
