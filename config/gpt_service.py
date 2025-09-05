# Arquivo: src/config/gpt_service.py

import os
from openai import OpenAI
from typing import Dict, List

class GPTService:
    """Cliente para interagir com a API do GPT-5 Nano."""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GPT_API_KEY é obrigatório")
        
        self.client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1") 

    def generate_flashcards_from_text(self, summary_content: str) -> List[Dict[str, str]]:
        """
        Envia o conteúdo de um resumo para a API do GPT e formata a resposta.
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
                    {"role": "user", "content": summary_content}
                ],
                # ===== CORREÇÃO APLICADA AQUI =====
                # A linha 'temperature=0.5' foi removida para usar o padrão da API.
                # ====================================
                max_completion_tokens=5000,
            )
            


            # ===== NOVA E MELHOR DEPURAÇÃO =====
            # Vamos imprimir a resposta inteira como um JSON formatado
            print("--- RESPOSTA COMPLETA DA API DO GPT (JSON) ---")
            print(response.model_dump_json(indent=2))
            print("---------------------------------------------")
            # ==========================================

            raw_text = response.choices[0].message.content or ""

            flashcards = []
            
            for line in raw_text.strip().split('\n'):
                if '==' in line:
                    parts = line.split('==', 1)
                    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                        flashcards.append({
                            "question": parts[0].strip(),
                            "answer": parts[1].strip()
                        })
            
            return flashcards

        except Exception as e:
            print(f"ERRO AO GERAR FLASHCARDS COM GPT: {e}")
            raise

def get_gpt_service() -> GPTService:
    """Função helper para obter o cliente GPT a partir das configurações do Flask."""
    from flask import current_app
    api_key = current_app.config.get('GPT_API_KEY')
    return GPTService(api_key)