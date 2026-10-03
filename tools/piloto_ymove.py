"""
Piloto da Cadeira Extensora contra a YMove REAL — roteiro conferido.

Existe porque a validacao real esta bloqueada so pela credencial. No momento em
que `YMOVE_API_KEY` for configurada, isto executa a sequencia inteira numa
chamada e devolve um relatorio, em vez de alguem reconstruir os passos de
memoria.

O QUE ELE FAZ, E O QUE NAO FAZ

  Faz: le /usage (que NAO consome cota), procura a Cadeira Extensora no
  catalogo em BROWSE MODE (tambem sem consumir cota) e, so se o operador pedir
  com --reproduzir, busca UMA url de video do exercicio ja vinculado.

  Nao faz: varredura de catalogo, requisicao de video em lote, nem qualquer
  chamada que gaste cota sem o operador mandar. Nao escreve vinculo nenhum: a
  escolha do exercicio e da variante e humana, feita no painel.

  A chave e lida do ambiente pelo proprio `services.ymove`. Ela nao e impressa,
  nao entra em URL e nao aparece no relatorio.

CONFIGURACAO

  O `.env` do backend e carregado explicitamente, ANTES de qualquer import que
  leia variavel de ambiente. Sem isso o roteiro dizia "credencial ausente"
  para quem tinha acabado de configura-la no `.env` — um falso negativo que
  mandava a pessoa procurar defeito onde nao havia.

  Variavel ja definida no ambiente VENCE o arquivo: quem exporta na mao esta
  dizendo de proposito contra o que escolher.

  O BANCO precisa estar configurado explicitamente (`DATABASE_URL`, no `.env`
  ou no ambiente). O roteiro nao assume SQLite: apontar em silencio para um
  `test.db` qualquer leria o vinculo de uma base que nao e a do piloto e
  relataria "sem vinculo" com ar de verdade.

USO

    cd "C:\\SOTEL\\fit-core\\backend\\Sotel Fit Core"
    python tools/piloto_ymove.py              # so leitura, zero cota
    python tools/piloto_ymove.py --reproduzir # + UMA url de video (consome)
    python tools/piloto_ymove.py --env OUTRO  # outro arquivo de ambiente

Dados reais do fornecedor; nenhum aluno e tocado.

CODIGOS DE SAIDA
    0  percorreu tudo o que foi pedido
    1  falta configuracao (credencial ou banco) — nada foi consultado
    3  o fornecedor ou o banco falhou — o resultado NAO e conclusivo
"""
import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))


class ConfiguracaoFaltando(RuntimeError):
    """Falta algo que o operador precisa definir. Nao e falha de execucao."""


class ConsultaFalhou(RuntimeError):
    """A consulta foi tentada e falhou. O resultado nao e conclusivo."""


def _carregar_env(caminho: str | None) -> str:
    """Carrega o `.env` do backend antes de qualquer leitura de ambiente.

    Devolve o caminho carregado, para o relatorio dizer de ONDE veio a
    configuracao. Nenhum valor e exibido.
    """
    from dotenv import load_dotenv

    arquivo = caminho or os.path.join(RAIZ, ".env")
    if not os.path.isfile(arquivo):
        raise ConfiguracaoFaltando(
            f"arquivo de ambiente nao encontrado: {arquivo}\n"
            f"  Crie-o a partir de .env.example, ou aponte outro com --env."
        )
    # `override=False`: variavel ja exportada no ambiente vence o arquivo.
    load_dotenv(arquivo, override=False)
    return arquivo

# A Cadeira Extensora e o piloto definido pelo Proprietario.
SLUG_LOCAL = "cadeira-extensora"
BUSCA = "leg extension"


def principal() -> int:
    p = argparse.ArgumentParser(description="Piloto da Cadeira Extensora na YMove real")
    p.add_argument("--reproduzir", action="store_true",
                   help="busca UMA url de video do exercicio vinculado (consome cota)")
    p.add_argument("--env", default=None,
                   help="arquivo de ambiente a carregar (padrao: .env do backend)")
    args = p.parse_args()

    print("=" * 66)
    print("PILOTO YMOVE — Cadeira Extensora")
    print("=" * 66)

    # O .env entra ANTES de importar services.ymove, que le a chave do ambiente
    # no momento da chamada. Importar primeiro faria a verificacao olhar um
    # ambiente que ainda nao tem a configuracao do arquivo.
    try:
        arquivo = _carregar_env(args.env)
    except ConfiguracaoFaltando as e:
        print()
        print("FALTA CONFIGURACAO:", e)
        return 1
    print(f"ambiente carregado de: {arquivo}")

    try:
        from services import ymove
    except Exception as e:
        print("nao foi possivel carregar o cliente do fornecedor:", type(e).__name__, e)
        return 3

    if not ymove.configurado():
        print()
        print("FALTA CONFIGURACAO: YMOVE_API_KEY nao esta definida.")
        print(f"  Onde: {arquivo}")
        print("  Como: acrescente uma linha  YMOVE_API_KEY=<a chave da YMove>")
        print("  O arquivo ja esta fora do indice do git. Nao e preciso mais nada,")
        print("  e nao me mande a chave — basta rodar este roteiro de novo.")
        return 1
    print("credencial YMOVE_API_KEY: presente (valor nao exibido)")

    if not os.getenv("DATABASE_URL"):
        print()
        print("FALTA CONFIGURACAO: DATABASE_URL nao esta definida.")
        print(f"  Onde: {arquivo} (ou exportada no ambiente)")
        print("  Por que exigir: sem isto o roteiro teria de adivinhar um banco, e")
        print("  leria o vinculo de uma base que pode nao ser a do piloto —")
        print("  relatando 'sem vinculo' com ar de verdade.")
        return 1
    esquema = os.environ["DATABASE_URL"].split("://")[0]
    print(f"banco: configurado (esquema {esquema})")

    # ---------------------------------------------------------------- /usage
    print()
    print("-- consumo da conta (/usage) — nao consome cota --")
    try:
        u = ymove.uso()
    except Exception as e:
        print("  falhou:", type(e).__name__, e)
        return 3

    limite_ex = u.get("exercicios_limite")
    print(f"  plano ............... {u.get('plano')}")
    print(f"  situacao ............ {u.get('situacao')}")
    print(f"  minutos ............. {u.get('minutos_usados')} / {u.get('minutos_limite')}"
          f"  (restantes: {u.get('minutos_restantes')}, {u.get('minutos_percentual')}%)")
    print(f"  exercicios distintos  {u.get('exercicios_distintos_no_mes')} / {limite_ex}"
          + ("  (sem limite)" if u.get("exercicios_ilimitados") else
             f"  (restantes: {u.get('exercicios_restantes')})"))
    print(f"  requisicoes/min ..... {u.get('requisicoes_por_minuto')}")
    print(f"  video sem marca ..... {u.get('video_sem_marca')}")
    print(f"  fim do teste ........ {u.get('fim_do_teste')}")

    # ------------------------------------------------- candidatos (browse)
    print()
    print(f"-- candidatos para '{BUSCA}' — BROWSE MODE, nao consome cota --")
    try:
        r = ymove.buscar(termo=BUSCA, page_size=5)
    except Exception as e:
        print("  falhou:", type(e).__name__, e)
        return 3

    itens = r.get("itens") or []
    if not itens:
        print("  nenhum candidato. Tente outro termo no painel.")
    for i in itens:
        variantes = ", ".join(
            f"{v.get('tag')}({v.get('orientacao')})" for v in (i.get("variantes") or [])
        ) or "nenhuma"
        print(f"  - {i.get('title')}  [{i.get('equipment')} / {i.get('muscle_group')}]")
        print(f"      id={i.get('exercise_id')}")
        print(f"      variantes: {variantes}")
        print(f"      capa: {'sim' if i.get('thumbnail_url') else 'nao (normal no plano com limite)'}")
    if r.get("cota_de_exercicios_estourada"):
        print("  AVISO: o fornecedor sinalizou cota de exercicios esgotada.")

    # ------------------------------------------------- vinculo ja aprovado
    print()
    print(f"-- vinculo local de '{SLUG_LOCAL}' --")
    # Tres desfechos diferentes, e so um deles e "sem vinculo":
    #
    #   a consulta falhou           -> erro, resultado nao conclusivo (saida 3)
    #   o exercicio nao existe      -> lacuna de catalogo, nao falta de vinculo
    #   existe e external_demo nulo -> SEM VINCULO, que e legitimo
    #
    # A versao anterior colapsava os tres: qualquer excecao virava `demo = None`
    # e saia imprimindo "SEM VINCULO" com codigo 0. Uma falha de banco era
    # relatada como estado legitimo, e o roteiro encerrava com sucesso.
    db = None
    try:
        from core.database import SessionLocal
        from models.exercise import Exercise
        db = SessionLocal()
        ex = db.query(Exercise).filter(Exercise.slug == SLUG_LOCAL).first()
        demo = (ex.external_demo if ex else None) or None
        existe = ex is not None
    except Exception as e:
        print("  ERRO ao consultar o banco:", type(e).__name__, str(e).splitlines()[0][:120])
        print("  O resultado NAO e conclusivo: nao da para afirmar que ha ou que")
        print("  nao ha vinculo. Confira DATABASE_URL e se o banco esta no ar.")
        return 3
    finally:
        if db is not None:
            db.close()

    if not existe:
        print(f"  o exercicio '{SLUG_LOCAL}' nao existe nesta base.")
        print("  Isso e lacuna de catalogo, nao falta de vinculo — confira se")
        print("  DATABASE_URL aponta para a base do piloto.")
        return 1

    if not demo:
        print("  SEM VINCULO. A escolha do exercicio e da variante e humana:")
        print("  faca no painel do admin (Biblioteca > Demonstracao) e rode de novo.")
        return 0

    print(f"  titulo ... {demo.get('title')}")
    print(f"  variante . {demo.get('variant')}")
    print(f"  id ....... {demo.get('exercise_id')}")
    print(f"  vinculado em {demo.get('linked_at')}")

    # ------------------------------------------------------ video (consome)
    if not args.reproduzir:
        print()
        print("Para buscar UMA url de video deste exercicio (consome cota),")
        print("rode de novo com --reproduzir.")
        return 0

    print()
    print("-- url de video — CONSOME COTA, uma unica vez --")
    try:
        v = ymove.url_de_video(demo.get("exercise_id") or demo.get("slug"),
                               demo.get("variant"))
    except Exception as e:
        print("  falhou:", type(e).__name__, e)
        return 3

    url = v.get("url") or ""
    # A url e pre-assinada e expira em 48h: nao vai inteira para o relatorio.
    print(f"  recebida: sim ({len(url)} caracteres, host {url.split('/')[2] if '://' in url else '?'})")
    print(f"  orientacao: {v.get('orientacao')}   duracao: {v.get('duracao_s')}s")
    print(f"  capa: {'sim' if v.get('thumbnail') else 'nao'}")
    print()
    print("Confira a reproducao no cliente, com o service worker ativo.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
