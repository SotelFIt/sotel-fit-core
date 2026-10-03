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

USO

    cd "C:\\SOTEL\\fit-core\\backend\\Sotel Fit Core"
    python tools/piloto_ymove.py              # so leitura, zero cota
    python tools/piloto_ymove.py --reproduzir # + UMA url de video (consome)

Dados reais do fornecedor; nenhum aluno e tocado.
"""
import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))

# A Cadeira Extensora e o piloto definido pelo Proprietario.
SLUG_LOCAL = "cadeira-extensora"
BUSCA = "leg extension"


def principal() -> int:
    p = argparse.ArgumentParser(description="Piloto da Cadeira Extensora na YMove real")
    p.add_argument("--reproduzir", action="store_true",
                   help="busca UMA url de video do exercicio vinculado (consome cota)")
    args = p.parse_args()

    try:
        from services import ymove
    except Exception as e:
        print("nao foi possivel carregar o cliente do fornecedor:", type(e).__name__, e)
        return 2

    print("=" * 66)
    print("PILOTO YMOVE — Cadeira Extensora")
    print("=" * 66)

    if not ymove.configurado():
        print()
        print("BLOQUEADO: YMOVE_API_KEY nao esta configurada.")
        print("Defina-a no .env do backend (o arquivo ja esta fora do indice do")
        print("git) e rode de novo. Nada mais e necessario.")
        return 1
    print("credencial: presente (valor nao exibido)")

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
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    try:
        from core.database import SessionLocal
        from models.exercise import Exercise
        db = SessionLocal()
        ex = db.query(Exercise).filter(Exercise.slug == SLUG_LOCAL).first()
        demo = (ex.external_demo if ex else None) or None
        db.close()
    except Exception as e:
        print("  nao foi possivel ler o banco:", type(e).__name__, e)
        demo = None

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
