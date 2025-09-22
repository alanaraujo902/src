# src/utils/exercise_parser.py

import re
import json

def parse_single_gpt_exercise(text: str) -> dict:
    """
    Faz o parsing de uma string que contém UM ÚNICO exercício formatado pela IA.
    Esta versão é mais robusta a pequenas variações de formatação.
    """
    try:
        # Usa re.IGNORECASE para ser mais flexível com as tags
        statement_match = re.search(r'\+Enunciado:(.*?)\+Fim do enunciado', text, re.DOTALL | re.IGNORECASE)
        if not statement_match:
            raise ValueError("Tag '+Enunciado:' ou '+Fim do enunciado' não encontrada.")
        # Remove aspas e colchetes do início/fim do enunciado
        statement = re.sub(r'^[\[\"]*(.*?)[\]\"]*$', r'\1', statement_match.group(1).strip())

        options_text_match = re.search(r'\+Enunciado de alterantivas(.*?)\+Fim dos enunciados de alternativas', text, re.DOTALL | re.IGNORECASE)
        if not options_text_match:
            raise ValueError("Bloco de alternativas não encontrado.")
        options_text = options_text_match.group(1).strip()

        options = []
        # Regex melhorado para capturar variações como "+ A) [...]" ou "+A) '[...]'""
        pattern = r'\+\s*([A-Za-z])\)\s*[\[\'\"]*(.*?)[\]\'\"]*$'
        matches = re.findall(pattern, options_text, re.MULTILINE)
        
        for match in matches:
            options.append({'option': match[0].upper(), 'text': match[1].strip()})
            
        if len(options) < 2:
             raise ValueError("Não foram encontradas alternativas suficientes no formato esperado.")

        # ====================================================================
        # ===                   A CORREÇÃO PRINCIPAL ESTÁ AQUI             ===
        # ====================================================================
        # A regex agora aceita letras maiúsculas ou minúsculas [A-Za-z]
        answer_match = re.search(r'\+Gabarito:\s*([A-Za-z])', text, re.IGNORECASE)
        # ====================================================================
        if not answer_match:
            raise ValueError("Tag '+Gabarito:' não encontrada.")
        # Sempre armazena a resposta em maiúscula para consistência
        answer = answer_match.group(1).strip().upper()

        if not statement or not answer:
            raise ValueError("Enunciado ou gabarito estão vazios após o parsing.")

        return {
            "statement": statement,
            "options": options,
            "answer": answer
        }
    except Exception as e:
        raise ValueError(f"Erro no parsing de exercício único: {e}")


def parse_multiple_gpt_exercises(text: str) -> list[dict]:
    """
    Faz o parsing de uma string que contém MÚLTIPLOS exercícios formatados pela IA.
    """
    print(f"\n--- [PARSER-LOG 1] Iniciando parsing de texto com {len(text)} caracteres ---")
    
    parsed_exercises = []
    # Divide o texto completo em blocos, onde cada bloco começa com "Questão" ou "---"
    # Isso torna o split mais robusto caso a IA esqueça um dos separadores.
    exercise_blocks = re.split(r'Questão|---', text)
    
    print(f"--- [PARSER-LOG 2] Texto dividido em {len(exercise_blocks)} blocos ---")

    for i, block in enumerate(exercise_blocks):
        if len(block.strip()) < 10: # Ignora blocos vazios ou muito pequenos
            continue

        try:
            # Não precisa mais adicionar "Questão", pois o parser único já o encontra
            parsed_exercise = parse_single_gpt_exercise(block)
            parsed_exercises.append(parsed_exercise)
            print(f"--- [PARSER-LOG 3.{i}] Bloco {i} parseado com SUCESSO ---")
        except ValueError as e:
            print(f"--- [PARSER-LOG 3.{i}] AVISO: Falha ao parsear o bloco {i+1}. Erro: {e} ---")
            print(f"Bloco problemático: {block[:200]}...")
            continue

    print(f"--- [PARSER-LOG 4] Parsing finalizado. Total de exercícios extraídos: {len(parsed_exercises)} ---")
    return parsed_exercises