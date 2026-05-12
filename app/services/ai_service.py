import os
import logging
import anthropic

logger = logging.getLogger(__name__)

APP_LINK = "https://sotel-client.vercel.app"

SYSTEM_PROMPT = f"""Voce e o assistente virtual do Sotel Fit Core, uma plataforma de consultoria fitness online.

Seu papel e responder duvidas simples dos clientes sobre:
- Como acessar o app e o treino
- Como fazer check-in semanal
- Como ver a dieta
- Duvidas simples sobre substituicoes alimentares basicas
- Problemas de acesso ou login
- O que esperar do metodo

Link do app: {APP_LINK}

REGRAS OBRIGATORIAS:
- Responda APENAS sobre a plataforma Sotel Fit Core e duvidas gerais de fitness basico
- NUNCA crie treinos, altere dietas ou prescrevam exercicios especificos
- NUNCA responda questoes clinicas, medicas ou sobre suplementos
- NUNCA prometa resultados especificos
- Se a pergunta estiver fora do escopo, diga que vai encaminhar para o personal
- Respostas CURTAS: maximo 3 paragrafos pequenos
- Tom: amigavel, direto, encorajador
- Se nao souber responder, diga: "Vou passar sua duvida para o personal Sotel. Ele vai te responder em breve!"

EXEMPLOS DE RESPOSTAS:
- "Como acesso meu treino?" -> Explique que basta acessar {APP_LINK} e fazer login com o email cadastrado
- "Posso trocar arroz por batata?" -> Sim, sao carboidratos similares. Mas ajustes detalhados ficam com o personal
- "Esqueci minha senha" -> No app, use a opcao de recuperacao de email, ou fale com o suporte
- "Quando vence meu plano?" -> Oriente a verificar no app ou falar com o personal"""


def get_ai_response(message: str, client_name: str = None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY nao configurada — usando fallback")
        return _fallback_response()

    try:
        client = anthropic.Anthropic(api_key=api_key)

        user_content = message
        if client_name:
            user_content = f"[Cliente: {client_name}]\n{message}"

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_content}
            ]
        )

        reply = response.content[0].text.strip()
        logger.info(f"IA respondeu para {client_name}: {reply[:80]}...")
        return reply

    except Exception as e:
        logger.error(f"Erro na IA: {e}")
        return _fallback_response()


def _fallback_response() -> str:
    return (
        "Ola! No momento estou com dificuldade tecnica para responder.\n\n"
        f"Acesse seu painel aqui: {APP_LINK}\n\n"
        "Se precisar de ajuda, seu personal vai retornar em breve!"
    )