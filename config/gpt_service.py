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

    def generate_exercise_from_text(self, text_content: str) -> str:
        """
        Envia um texto para a IA e pede para criar um exercício estruturado.
        """
        system_prompt = """
        Você é um especialista em criar questões de múltipla escolha para estudantes.
        Analise o texto fornecido e crie UMA ÚNICA questão objetiva com 5 alternativas (A, B, C, D, E).
        Siga ESTRITAMENTE o seguinte formato de saída, sem qualquer texto adicional antes ou depois:

        Questão
        +Enunciado: "[coloque o enunciado completo da questão aqui, baseado no texto]" +Fim do enunciado
        +Enunciado de alterantivas
        + A) "[enunciado da alternativa A]"
        + B) "[enunciado da alternativa B]"
        + C) "[enunciado da alternativa C]"
        + D) "[enunciado da alternativa D]"
        + E) "[enunciado da alternativa E]"
        +Fim dos enunciados de alternativas
        +Gabarito: [letra correta, ex: A]
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_content},
                ],
                max_completion_tokens=1000, # Ajuste conforme necessário
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"ERRO AO GERAR EXERCÍCIO COM GPT: {e}")
            raise

    # ==================== NOVO MÉTODO PARA INTEGRAR CONHECIMENTO ====================
    def integrate_exercise_into_summary(self, summary_content: str, exercise_statement: str, exercise_answer: str) -> str:
        """
        Integra o conhecimento de um exercício em um resumo existente.
        """
        system_prompt = """
        Você é um assistente de estudos especialista em refinar e consolidar conhecimento.
        A seguir, você receberá o conteúdo de um resumo existente e uma questão de exercício relacionada a ele.
        Sua tarefa é integrar de forma inteligente e coesa o conhecimento principal do exercício ao resumo. Não apenas cole a questão, mas incorpore a informação que ela valida no fluxo natural do texto.
        Mantenha o formato Markdown original do resumo.
        Retorne APENAS o texto completo e atualizado do resumo.
        """
        user_content = f"""
        --- RESUMO ATUAL ---
        {summary_content}

        --- EXERCÍCIO PARA INTEGRAR ---
        Enunciado: {exercise_statement}
        Resposta Correta: {exercise_answer}
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_completion_tokens=5000,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"ERRO AO INTEGRAR EXERCÍCIO NO RESUMO: {e}")
            raise

def get_gpt_service() -> GPTService:
    """Helper para obter o cliente GPT a partir das configurações do Flask."""
    from flask import current_app

    api_key = current_app.config.get("GPT_API_KEY")
    return GPTService(api_key)