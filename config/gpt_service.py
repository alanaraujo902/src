# Arquivo: src/config/gpt_service.py

import os
from typing import Dict, List
from openai import OpenAI
import httpx # Importe a biblioteca httpx, que é uma dependência da openai





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
        # ====================================================================
        # ===                A CORREÇÃO COMPLETA ESTÁ AQUI                 ===
        # ====================================================================
        # Configura um cliente HTTP customizado com timeouts mais longos.
        # A IA pode levar mais de 30 segundos para processar grandes blocos de texto.
        timeout_config = httpx.Timeout(
            connect=10.0,      # Tempo para estabelecer a conexão
            read=120.0,        # Tempo para ler a resposta completa (aumentado para 2 minutos)
            write=10.0,        # Tempo para enviar os dados
            pool=10.0
        )

        # Instancia o cliente OpenAI passando a configuração de timeout.
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            timeout=timeout_config
        )
        # ====================================================================

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

    def reformat_exercises_from_text(self, text_content: str) -> str:
        """
        Envia um texto bruto contendo exercícios para a IA e pede para formatá-lo.
        Inclui logs detalhados para depuração.
        """
        # ==================== LOG 1: O que estamos enviando? ====================
        print(f"\n--- [GPT-LOG 1] INICIANDO 'reformat_exercises_from_text' ---")
        print(f"Tamanho do texto de entrada: {len(text_content)} caracteres")
        # Loga os primeiros 500 caracteres do texto para inspeção
        print(f"Início do texto de entrada: {text_content[:500]}...")
        # =======================================================================
        
        system_prompt = """
        Você formatara um texto enviado. Ele é composto por exercícios de múltipla escolha e o gabarito das questões.
        Não comente, não seja prolixo, não adicione comentários extras, envie apenas o que é pedido, sem ser solicito ou pedir se pode fazer algo a mais. 
        Primeiro, identifique cada questão individualmente. Uma questão tem um enunciado e várias alternativas (a, b, c, d, etc.). As questões podem ser numeradas (ex: "Questão 4", "Questão 10").
        Depois, localize o bloco de "gabarito" em algum lugar do texto. Ele conterá as respostas no formato "numeroLetra" (ex: "4c", "10a").
        Para CADA questão que você identificou, encontre o seu número e associe-o à letra correta do bloco de gabarito.

        Formate a saída para CADA questão usando as seguintes tags EXATAMENTE como mostrado. Coloque o conteúdo extraído entre aspas:

                    Questão
                    +Enunciado: "[coloque o enunciado completo da questão aqui, sem markdown]" +Fim do enunciado
                    +Enunciado de alterantivas
                    + A) "[enunciado da alternativa A]"
                    + B) "[enunciado da alternativa B]"
                    + C) "[enunciado da alternativa C]"
                    ... (continue para todas as alternativas)
                    +Fim dos enunciados de alternativas
                    +Gabarito: [letra correta que você encontrou no bloco de gabarito]
                    ---
        Se houver múltiplas questões no texto de entrada, separe CADA BLOCO de questão formatada com "---" em uma nova linha.
        NÃO adicione nenhum texto, introdução, comentário ou conclusão. A saída deve conter APENAS os blocos formatados.
        """
        
        try:
            # ==================== LOG 2: Chamando a API ====================
            print("--- [GPT-LOG 2] Enviando requisição para a API da OpenAI... ---")
            # ===============================================================
            
            response = self.client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_content},
                ],
                max_completion_tokens=50000,
            )
            
            # ==================== LOG 3: O que recebemos de volta? ====================
            print("--- [GPT-LOG 3] Resposta recebida da API da OpenAI ---")
            # Log do objeto de resposta completo para verificar o uso de tokens e a razão de finalização
            print(f"Objeto de Resposta Completo (diagnóstico): {response.model_dump_json(indent=2)}")
            # =========================================================================

            # Extrai o conteúdo da mensagem
            response_content = response.choices[0].message.content or ""

            # ==================== LOG 4: Qual conteúdo foi extraído? ====================
            print("\n--- [GPT-LOG 4] Conteúdo de texto extraído da resposta ---")
            print(f"Tamanho do conteúdo extraído: {len(response_content)} caracteres")
            print("Conteúdo:")
            print(response_content)
            print("----------------------------------------------------------\n")
            # ============================================================================

            return response_content

        except Exception as e:
            # ==================== LOG 5: Ocorreu um erro na chamada? ====================
            print(f"\n--- [GPT-LOG 5] ERRO CRÍTICO DURANTE A CHAMADA DA API ---")
            print(f"Tipo do Erro: {type(e)}")
            print(f"Mensagem de Erro: {e}")
            print("----------------------------------------------------------\n")
            # ===========================================================================
            raise # Re-lança a exceção para que a rota possa tratá-la e retornar um erro 500

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