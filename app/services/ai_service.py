import logging
import re

logger = logging.getLogger(__name__)

APP_LINK = "https://sotel-client.vercel.app"

FAQ = [
    {
        "keywords": ["acesso", "acessar", "entrar", "login", "logar", "app", "plataforma", "abrir"],
        "response": (
            f"Para acessar seu painel, entre em {APP_LINK} e faça login com o e-mail cadastrado.\n\n"
            "Se tiver dificuldade, me fala que te ajudo!"
        )
    },
    {
        "keywords": ["senha", "esqueci", "recuperar", "redefinir", "reset"],
        "response": (
            "Para recuperar sua senha, acesse o app e clique em *Esqueci minha senha*.\n\n"
            "Um e-mail de recuperação será enviado. Não recebeu? Me avisa aqui."
        )
    },
    {
        "keywords": ["treino", "exercicio", "exercício", "musculacao", "musculação", "treinar"],
        "response": (
            f"Seu treino está disponível no app: {APP_LINK}\n\n"
            "Acesse, faça login e ele aparece direto no seu painel. "
            "Qualquer dúvida sobre os exercícios, fala com o personal!"
        )
    },
    {
        "keywords": ["dieta", "alimentacao", "alimentação", "comer", "refeicao", "refeição", "plano alimentar"],
        "response": (
            f"Seu plano alimentar está no app: {APP_LINK}\n\n"
            "Lá você encontra todas as refeições organizadas. "
            "Para ajustes específicos, o personal é quem define."
        )
    },
    {
        "keywords": ["substituir", "substituicao", "substituição", "trocar", "trocar arroz", "trocar batata", "alternativa"],
        "response": (
            "Substituições simples geralmente são tranquilas — por exemplo, arroz e batata são carboidratos similares.\n\n"
            "Mas ajustes mais específicos ficam com o personal para garantir que seu plano continue no ponto certo."
        )
    },
    {
        "keywords": ["check-in", "checkin", "check in", "relatorio", "relatório", "responder semana"],
        "response": (
            f"Seu check-in semanal está disponível no app: {APP_LINK}\n\n"
            "Acesse, responda como foi sua semana e o personal vai analisar tudo. "
            "É importante não pular — é por ali que o plano evolui!"
        )
    },
    {
        "keywords": ["plano", "vence", "vencimento", "prazo", "mensalidade", "pagamento", "renovar"],
        "response": (
            "Informações sobre seu plano e pagamento você encontra diretamente no app ou falando com o personal.\n\n"
            f"Acesse: {APP_LINK}"
        )
    },
    {
        "keywords": ["resultado", "resultado", "emagrecer", "perder peso", "ganhar massa", "definir"],
        "response": (
            "Os resultados dependem da consistência no treino, na dieta e nos check-ins semanais.\n\n"
            "Seguindo o plano que o personal montou pra você, o caminho fica muito mais claro. Bora!"
        )
    },
    {
        "keywords": ["suporte", "ajuda", "problema", "erro", "nao funciona", "não funciona", "bug"],
        "response": (
            "Vou passar sua dúvida para o personal Sotel. Ele vai te responder em breve!\n\n"
            f"Enquanto isso, tente acessar o app por aqui: {APP_LINK}"
        )
    },
    {
        "keywords": ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem", "tudo bom"],
        "response": (
            "Olá! Tudo certo por aqui. 💪\n\n"
            "Sou o assistente do Sotel Fit Core. Como posso te ajudar hoje?"
        )
    },
]

DEFAULT_RESPONSE = (
    "Vou passar sua dúvida para o personal Sotel. Ele vai te responder em breve!\n\n"
    f"Enquanto isso, você pode acessar seu painel aqui: {APP_LINK}"
)


def get_ai_response(message: str, client_name: str = None) -> str:
    try:
        normalized = message.lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)

        for item in FAQ:
            for keyword in item["keywords"]:
                if keyword in normalized:
                    reply = item["response"]
                    logger.info(f"FAQ match '{keyword}' para {client_name}: {reply[:60]}...")
                    return reply

        logger.info(f"Sem match FAQ para {client_name}: '{message[:60]}'")
        return DEFAULT_RESPONSE

    except Exception as e:
        logger.error(f"Erro no ai_service: {e}")
        return _fallback_response()


def _fallback_response() -> str:
    return (
        "Olá! No momento estou com dificuldade técnica para responder.\n\n"
        f"Acesse seu painel aqui: {APP_LINK}\n\n"
        "Se precisar de ajuda, seu personal vai retornar em breve!"
    )