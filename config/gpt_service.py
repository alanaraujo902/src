# Arquivo: src/config/gpt_service.py

import os
from typing import Dict, List
from openai import OpenAI

# ==================== PROMPTS DISPONÍVEIS ====================
GPT_PROMPTS: Dict[str, str] = {
    "default": """
        Você é um assistente de estudos especializado em criar resumos de alta qualidade.
        Analise o texto fornecido e transforme-o em um resumo claro, conciso e bem estruturado para um estudante.
        Siga estas diretrizes estritamente:
        1.  Identifique e destaque os **conceitos-chave em negrito**.
        2.  Utilize **listas com marcadores ou numeração** para organizar informações e passos.
        3.  Estruture o conteúdo usando **tópicos e subtópicos** para facilitar a leitura.
        4.  Mantenha uma linguagem didática, mas sem simplificar excessivamente os termos importantes.
        5.  Conclua com uma breve **revisão ou conclusão** dos pontos mais importantes.
        O formato de saída deve ser em **Markdown**.
    """,
    "com_emojis": """
        Você é um assistente de estudos que cria resumos visualmente atraentes e fáceis de memorizar usando emojis e markdown.
        Siga estas diretrizes estritamente:
        - Use emojis relevantes no início de tópicos e subtópicos para criar âncoras visuais. (Ex: 🦠 Agente, 🤒 Clínica).
        - Destaque **termos-chave e conceitos importantes em negrito**.
        - Utilize **listas com marcadores ou numeração** para organizar informações.
        - Estruture o conteúdo de forma clara, usando **tópicos e subtópicos**.
        - Finalize com uma seção de **"Como cai em provas"** ou um **resumo rápido** usando um emoji como 👉.
        O tom deve ser didático e direto, ideal para estudantes que precisam de informações rápidas e organizadas.
    """,
}
# =============================================================


class GPTService:
    """Cliente para interagir com a API do GPT-5 Nano."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GPT_API_KEY é obrigatório")
        # Se precisar customizar o endpoint, ajuste base_url aqui.
        self.client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

    # ==================== RESTAURADO: GERAÇÃO DE FLASHCARDS ====================
    def generate_flashcards_from_text(self, summary_content: str) -> List[Dict[str, str]]:
        """
        Envia o conteúdo de um resumo para a API do GPT e formata a resposta em pares Pergunta/Resposta.
        Saída esperada por linha: "PERGUNTA==RESPOSTA"
        """
        system_prompt = """
        Você é um especialista em criar flashcards para estudantes.
        Analise o texto fornecido e crie pares de PERGUNTA e RESPOSTA concisos e eficazes.
        Siga estas regras estritamente:
        1.  Para cada flashcard, formule uma pergunta clara e direta.
        2.  A resposta deve ser objetiva e conter a informação essencial.
        3.  Separe a PERGUNTA da RESPOSTA usando exatamente '=='.
        4.  Separe cada flashcard (par pergunta/resposta) com uma nova linha.

        Exemplo de formato de saída:
        Qual é a capital da França?==Paris
        Quem escreveu "Dom Quixote"?==Miguel de Cervantes
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": summary_content},
                ],
                max_completion_tokens=5000,
                
            )

            # Logs úteis em desenvolvimento
            if os.getenv("DEBUG_GPT", "0") == "1":
                print("--- RESPOSTA COMPLETA DA API DO GPT (JSON) ---")
                print(response.model_dump_json(indent=2))
                print("---------------------------------------------")

            raw_text = response.choices[0].message.content or ""
            flashcards: List[Dict[str, str]] = []

            for line in raw_text.strip().split("\n"):
                if "==" in line:
                    q, a = line.split("==", 1)
                    q, a = q.strip(), a.strip()
                    if q and a:
                        flashcards.append({"question": q, "answer": a})

            return flashcards

        except Exception as e:
            print(f"ERRO AO GERAR FLASHCARDS COM GPT: {e}")
            raise
    # ==========================================================================

    # ==================== RESUMO COM ESTILO SELECIONÁVEL ====================
    def summarize_text(self, text_to_summarize: str, prompt_style: str = "default") -> str:
        """
        Envia um texto para a API do GPT e pede para criar um resumo didático.
        """
        system_prompt = GPT_PROMPTS.get(prompt_style, GPT_PROMPTS["default"])

        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_to_summarize},
                ],
                max_completion_tokens=5000,
            )

            summary_content = response.choices[0].message.content or ""
            return summary_content.strip()

        except Exception as e:
            print(f"ERRO AO GERAR RESUMO COM GPT: {e}")
            raise
    # ======================================================================


def get_gpt_service() -> GPTService:
    """Helper para obter o cliente GPT a partir das configurações do Flask."""
    from flask import current_app

    api_key = current_app.config.get("GPT_API_KEY")
    return GPTService(api_key)