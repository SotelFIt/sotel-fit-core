"""
ymove - cliente da Exercise API da YMove.

Fornecedor de DEMONSTRACAO em video. A Biblioteca Sotel continua sendo a
referencia da prescricao: id, slug, nome, aliases, execucao, series, descanso e
substituicoes sao nossos. Daqui vem so o filme do movimento.

Quatro fatos do contrato do fornecedor moldam este modulo inteiro. Todos
conferidos em https://exercise-api.ymove.app/api/v2/openapi.json (v2.5.0) e,
quanto a planos, em https://ymove.app/exercise-api/pricing:

1. **URL de video e pre-assinada e expira em 48h.** O proprio schema `Video`
   diz "Do not cache these URLs". Ela nao pode ser gravada em `media[]`, no
   plano publicado, no banco nem no navegador. E buscada na hora em que o aluno
   pede a demonstracao.

2. **O consumo tem DUAS dimensoes, nao uma.**
   - MINUTOS de video (`minutesUsed` / `minutesLimit`): e o que a pagina de
     precos vende por plano, e e o que devolve 429 quando estoura.
   - EXERCICIOS DISTINTOS em 30 dias (`monthlyExercisesUsed` /
     `monthlyExerciseLimit`, que pode vir como a string "unlimited").
   Nenhuma das duas e consumida em `excludeVideos=1` ("browse mode"). Por isso
   a navegacao do admin e sempre browse, e o video so e pedido para a
   demonstracao que o aluno abriu. Quantos minutos cada abertura custa e
   contabilidade do fornecedor: nao estimamos nem prometemos proporcao.

3. **O thumbnail PODE FALTAR em browse mode.** Ele e estatico e nao expira
   (logo pode ser guardado), mas o contrato do objeto `Thumbnails` e explicito:
   "On Scale they are also returned without a video, in browse mode and with
   excludeVideos; on the capped plans they are not". Ou seja: no plano em uso
   podemos simplesmente nao receber capa nenhuma ao navegar. Ausencia de capa
   NAO e erro e NAO impede busca, vinculo nem treino — e nunca motivo para
   pedir video so para conseguir uma imagem, porque isso consumiria cota.

4. **Cota estourada nao vem como erro HTTP.** Quando o limite de exercicios
   distintos e excedido, a resposta continua 200 e o fornecedor *remove* os
   campos de video, incluindo um objeto `_warning` com
   `reason = "monthly_exercise_cap"`. Sem ler esse aviso, "sem video" e "sem
   cota" ficariam indistinguiveis — e a tela diria ao aluno que o exercicio nao
   tem demonstracao quando o problema e da conta.

A chave vive so aqui, no servidor. Nunca vai para o frontend, para URL, para
log ou para resposta de erro. O fornecedor tambem aceita a chave em query
string (`ApiKeyQuery`); nao usamos — chave em URL vaza em log de proxy, em
Referer e no historico de qualquer intermediario.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("YMOVE_API_URL", "https://exercise-api.ymove.app/api/v2")
TIMEOUT = (5, 15)  # (conexao, leitura) — a tela do aluno nao pode ficar pendurada

PROVIDER = "ymove"

# Dominio dos thumbnails, por contrato: "served from ymove.app".
HOSTS_DE_IMAGEM = ("ymove.app",)

# Framings estaticos que o fornecedor documenta no objeto Thumbnails.
FRAMINGS = ("default", "square", "portrait", "landscape", "original")


class YMoveIndisponivel(RuntimeError):
    """Fornecedor fora do ar, lento ou com erro interno. Transitorio."""


class YMoveSemCredencial(RuntimeError):
    """Chave ausente ou recusada. NAO e falha do aluno nem do exercicio."""


class YMoveLimiteAtingido(RuntimeError):
    """Cota (minutos ou exercicios distintos) ou limite de requisicoes estourado."""

    def __init__(self, mensagem: str, retry_after_ms: Optional[int] = None):
        super().__init__(mensagem)
        self.retry_after_ms = retry_after_ms


class YMoveNaoEncontrado(LookupError):
    """O exercicio nao existe no catalogo do fornecedor, ou nao tem video."""


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
            # Header, nunca query string (ver nota no topo do modulo).
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
        # `retryAfterMs` e do contrato (schema RateLimitError). Passa adiante
        # para a tela poder dizer "tente de novo em X", em vez de so falhar.
        raise YMoveLimiteAtingido(
            "limite do fornecedor de video atingido", _retry_after_ms(r)
        )
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


def _retry_after_ms(r) -> Optional[int]:
    """Quanto esperar antes de tentar de novo, se o fornecedor disser."""
    try:
        valor = (r.json() or {}).get("retryAfterMs")
        return int(valor) if valor is not None else None
    except Exception:
        return None


def _cota_de_exercicios_estourada(corpo: dict) -> bool:
    """O 200 veio sem video POR CAUSA da cota de exercicios distintos?

    Fato 4 do topo: o fornecedor nao usa status HTTP para isso. Ele responde
    200, tira os campos de video e explica em `_warning`.
    """
    aviso = (corpo or {}).get("_warning") or {}
    return aviso.get("reason") == "monthly_exercise_cap"


def buscar(
    termo: Optional[str] = None,
    muscle_group: Optional[str] = None,
    equipment: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Candidatos para o vinculo. BROWSE MODE — nao consome cota nenhuma.

    `excludeVideos=1` vence qualquer default da chave, segundo o proprio
    contrato ("wins if includeVideos is also sent"). E o que garante que
    paginar nao gaste minutos nem queime exercicios distintos — importante
    porque o default de chaves antigas (anteriores a 2026-07-07) e `true`.

    Os candidatos podem vir SEM `thumbnail_url` (fato 3). A busca continua
    valendo: quem decide o vinculo e o humano, lendo titulo, equipamento, grupo
    muscular e variantes — nao a figura.
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
        # Em browse mode nao deveria aparecer (nao pedimos video); se aparecer,
        # o admin precisa saber, e nao descobrir pela fatura.
        "cota_de_exercicios_estourada": _cota_de_exercicios_estourada(bruto),
    }


def detalhe_sem_video(identificador: str) -> dict:
    """Metadados de um exercicio, sem pedir video. Nao consome cota.

    Atencao ao default invertido deste endpoint: em `/exercises/{id}` o video
    vem POR PADRAO ("you asked for one specific exercise"). O
    `excludeVideos=1` aqui nao e redundante — e o que impede a conferencia do
    admin de custar cota.
    """
    bruto = _chamar(f"/exercises/{identificador}", {"excludeVideos": 1})
    return _resumo(bruto.get("data") or {})


def url_de_video(identificador: str, variante: Optional[str] = None) -> dict:
    """URL ASSINADA do video. **Consome cota** (minutos e exercicio distinto).

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
        # A ORDEM importa: cota estourada chega como 200 sem video. Checar o
        # aviso ANTES de concluir "nao tem video" e a diferenca entre dizer ao
        # aluno "este exercicio nao tem demonstracao" (falso) e dizer ao admin
        # "a cota do mes acabou" (verdadeiro, e acionavel).
        if _cota_de_exercicios_estourada(bruto):
            raise YMoveLimiteAtingido(
                "cota mensal de exercicios distintos do fornecedor atingida"
            )
        raise YMoveNaoEncontrado("o fornecedor nao tem video para este exercicio")

    return {
        "url": url,
        # Enum do contrato e minusculo: "portrait" | "landscape". A maioria dos
        # clipes e portrait — o proprio contrato avisa "Do not assume landscape".
        "orientacao": (escolhido or {}).get("orientation") or "portrait",
        "duracao_s": dados.get("videoDurationSecs"),
        # Thumbnail estatico: pode acompanhar a resposta sem risco de expirar.
        # Pode ser None, e isso nao impede reproduzir.
        "thumbnail": _imagem_valida(
            (escolhido or {}).get("thumbnailUrl") or dados.get("thumbnailUrl")
        ),
    }


def uso() -> dict:
    """Consumo real da conta. Para o ADMIN — nunca para a tela do aluno.

    Devolve as DUAS dimensoes que o fornecedor publica, sem inventar nenhuma:
    minutos de video e exercicios distintos no mes. O limite de exercicios pode
    vir como a string "unlimited" (planos anuais), entao `..._restantes` so e
    calculado quando ha dois numeros — subtrair de uma palavra produziria um
    numero inventado.
    """
    bruto = _chamar("/usage")
    d = bruto.get("data") or {}

    limite_ex = d.get("monthlyExerciseLimit")
    ilimitado = isinstance(limite_ex, str) and limite_ex.lower() == "unlimited"
    postura = d.get("postureAnalyses") or {}

    return {
        "plano": d.get("plan"),
        "situacao": d.get("status"),
        # --- dimensao 1: minutos de video
        "minutos_usados": d.get("minutesUsed"),
        "minutos_limite": d.get("minutesLimit"),
        "minutos_restantes": d.get("minutesRemaining"),
        "minutos_percentual": d.get("percentUsed"),
        # --- dimensao 2: exercicios distintos em 30 dias
        "exercicios_distintos_no_mes": d.get("monthlyExercisesUsed"),
        "exercicios_limite": limite_ex,
        "exercicios_ilimitados": ilimitado,
        "exercicios_restantes": _restante(
            d.get("monthlyExercisesUsed"), None if ilimitado else limite_ex
        ),
        # --- limites de chamada e caracteristicas do plano
        "requisicoes_por_minuto": d.get("rateLimit"),
        "video_sem_marca": d.get("premiumVideoAccess"),
        "video_fundo_branco": d.get("whiteVideoAccess"),
        "analises_de_postura_usadas": postura.get("used"),
        "analises_de_postura_incluidas": postura.get("included"),
        "fim_do_teste": d.get("trialEndsAt"),
    }


def _restante(usado, limite) -> Optional[int]:
    """Sobra, so quando as duas pontas sao numeros de verdade."""
    if isinstance(usado, bool) or isinstance(limite, bool):
        return None
    if not isinstance(usado, int) or not isinstance(limite, int):
        return None
    return max(0, limite - usado)


def _imagem_valida(url: Optional[str]) -> Optional[str]:
    """Thumbnail aceitavel, ou None.

    O mesmo criterio do schema que persiste o vinculo, aplicado ja na entrada:
    https e dominio do fornecedor. Vale a redundancia porque aqui a URL vai
    para a tela e la ela vai para o banco — sao dois caminhos distintos para o
    mesmo dado, e nenhum dos dois deve virar proxy de endereco arbitrario.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.lower().startswith("https://"):
        return None
    partes = url.split("/")
    host = partes[2].lower() if len(partes) > 2 else ""
    if not any(host == h or host.endswith("." + h) for h in HOSTS_DE_IMAGEM):
        return None
    return url


def _resumo(x: dict) -> dict:
    """So o que interessa ao vinculo. Nada de URL assinada entra aqui.

    `thumbnail_url` e `thumbnails` podem vir None/vazios em browse mode, e isso
    e normal (fato 3 do topo). Quem distingue execucoes parecidas e o conjunto
    titulo + equipamento + grupo muscular + variantes, que vem sempre.
    """
    if not x:
        return {}
    return {
        "provider": PROVIDER,
        "exercise_id": x.get("id"),
        "slug": x.get("slug"),
        "title": x.get("title"),
        "muscle_group": x.get("muscleGroup"),
        "equipment": x.get("equipment"),
        "category": x.get("category"),
        "difficulty": x.get("difficulty"),
        "has_video": bool(x.get("hasVideo")),
        "has_video_white": bool(x.get("hasVideoWhite")),
        "has_video_gym": bool(x.get("hasVideoGym")),
        "duration_secs": x.get("videoDurationSecs"),
        "thumbnail_url": _imagem_valida(x.get("thumbnailUrl")),
        "thumbnails": {
            k: v
            for k, v in (
                (f, _imagem_valida((x.get("thumbnails") or {}).get(f)))
                for f in FRAMINGS
            )
            if v
        },
        "variantes": [
            {"tag": v.get("tag"), "orientacao": v.get("orientation"),
             "principal": bool(v.get("isPrimary")),
             "thumbnail_url": _imagem_valida(v.get("thumbnailUrl"))}
            for v in (x.get("videos") or [])
        ],
    }
