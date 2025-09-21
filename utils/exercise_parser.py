# src/utils/exercise_parser.py

import re
import json

def parse_gpt_exercise_response(text: str) -> dict:
    """
    Faz o parsing da resposta em texto da IA para um formato estruturado (dicionário Python).
    Esta função é projetada para ser robusta contra pequenas variações no texto da IA.

    Args:
        text: A string de resposta completa vinda da API do GPT.

    Returns:
        Um dicionário contendo 'statement', 'options' (uma lista de dicts), e 'answer'.

    Raises:
        ValueError: Se qualquer parte essencial do formato esperado não for encontrada.
    """
    try:
        # Extrai o enunciado principal
        statement_match = re.search(r'\+Enunciado:(.*?)\+Fim do enunciado', text, re.DOTALL)
        if not statement_match:
            raise ValueError("Tag '+Enunciado:' ou '+Fim do enunciado' não encontrada.")
        statement = statement_match.group(1).strip().replace('"', '')

        # Extrai o bloco de texto contendo todas as alternativas
        options_text_match = re.search(r'\+Enunciado de alterantivas(.*?)\+Fim dos enunciados de alternativas', text, re.DOTALL)
        if not options_text_match:
            raise ValueError("Bloco de alternativas não encontrado.")
        options_text = options_text_match.group(1).strip()

        # Extrai cada alternativa individualmente
        options = []
        # Regex para capturar "+ Letra) Texto da alternativa"
        pattern = r'\+\s*([A-Z])\)\s*"(.*?)"'
        matches = re.findall(pattern, options_text)
        
        for match in matches:
            options.append({'option': match[0], 'text': match[1].strip()})
            
        if len(options) < 2: # Um exercício deve ter pelo menos 2 opções
             raise ValueError("Não foram encontradas alternativas suficientes no formato esperado.")

        # Extrai o gabarito
        answer_match = re.search(r'\+Gabarito:\s*([A-Z])', text)
        if not answer_match:
            raise ValueError("Tag '+Gabarito:' não encontrada.")
        answer = answer_match.group(1).strip()

        # Validação final
        if not statement or not answer:
            raise ValueError("Enunciado ou gabarito estão vazios após o parsing.")

        return {
            "statement": statement,
            "options": options, # Já está no formato JSONB-friendly
            "answer": answer
        }
    except Exception as e:
        # Adiciona contexto ao erro para facilitar a depuração
        print(f"--- FALHA NO PARSING DA RESPOSTA DA IA ---\nTEXTO RECEBIDO:\n{text}\nERRO: {e}\n-----------------------------------------")
        raise ValueError(f"Erro de parsing: {e}")