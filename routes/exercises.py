# src/routes/exercises.py

from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.config.gpt_service import get_gpt_service
from src.utils.auth import require_auth, get_current_user
from src.utils.exercise_parser import parse_single_gpt_exercise, parse_multiple_gpt_exercises

import uuid
import json

exercises_bp = Blueprint('exercises', __name__)

# ROTA (para reformatar múltiplos exercícios) - CORRIGIDA
@exercises_bp.route('/reformat-and-save', methods=['POST'])
@require_auth
def reformat_and_save_exercises():
    """
    Recebe um texto bruto com MÚLTIPLOS exercícios, envia para a IA para formatação,
    faz o parsing da resposta e salva os exercícios no banco de dados.
    """
    data = request.get_json()
    raw_text = data.get('text')
    subject_id = data.get('subject_id')
    summary_id = data.get('summary_id')

    if not raw_text or not subject_id:
        return jsonify({'error': 'Campos "text" e "subject_id" são obrigatórios'}), 400

    gpt_service = get_gpt_service()
    supabase = get_supabase_client()
    current_user = get_current_user()

    try:
        raw_gpt_response = gpt_service.reformat_exercises_from_text(raw_text)


                # ====================================================================
        # ===            O LOG DE DIAGNÓSTICO ESTÁ AQUI                  ===
        # ====================================================================
        # Loga a resposta bruta da IA ANTES de qualquer tentativa de parsing.
        # Isso é essencial para depurar problemas de formatação da IA.
        print("\n--- [ROTA-LOG 1] RESPOSTA BRUTA DA IA (PARA REFORMATAR) ---")
        print(raw_gpt_response)
        print("----------------------------------------------------------\n")
        # ====================================================================

        # ====================================================================
        # ===                      A CORREÇÃO CRÍTICA                    ===
        # ====================================================================
        # Usa o novo parser para MÚLTIPLOS exercícios
        parsed_exercises = parse_multiple_gpt_exercises(raw_gpt_response)
        # ====================================================================

        if not parsed_exercises:
            return jsonify({'error': 'A IA não conseguiu formatar nenhum exercício a partir do texto fornecido.'}), 400

        exercises_to_insert = [
            {
                'id': str(uuid.uuid4()),
                'user_id': current_user['id'],
                'subject_id': subject_id,
                'summary_id': summary_id,
                'statement': exercise['statement'],
                'options': exercise['options'],
                'answer': exercise['answer'],
                'original_text': raw_text,
            }
            for exercise in parsed_exercises
        ]
        
        response = supabase.table('exercises').insert(exercises_to_insert).execute()
        if not response.data:
            raise Exception("Falha ao salvar os exercícios. Verifique as permissões (RLS).")

        return jsonify({
            'message': f'{len(response.data)} exercícios criados com sucesso', 
            'exercises': response.data
        }), 201

    except ValueError as ve:
        return jsonify({'error': f'Erro de parsing: {str(ve)}'}), 400
    except Exception as e:
        print(f"ERRO EM /reformat-and-save: {e}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500



@exercises_bp.route('/<exercise_id>/create-flashcard', methods=['POST'])
@require_auth
def create_flashcard_from_exercise(exercise_id):
    """
    Cria um flashcard diretamente a partir de um exercício existente e o liga a ele.
    """
    supabase = get_supabase_client()
    current_user = get_current_user()

    try:
        # 1. Buscar o exercício e verificar se pertence ao usuário
        exercise_response = supabase.table('exercises').select('*').eq('id', exercise_id).eq('user_id', current_user['id']).single().execute()
        if not exercise_response.data:
            return jsonify({'error': 'Exercício não encontrado'}), 404
        
        exercise = exercise_response.data
        correct_option_text = next((opt['text'] for opt in exercise['options'] if opt['option'] == exercise['answer']), 'Resposta não encontrada')

        # 2. Encontrar ou criar o deck de flashcards para a matéria correspondente
        deck_response = supabase.table('flashcard_decks').select('id').eq('subject_id', exercise['subject_id']).single().execute()
        if not deck_response.data:
             return jsonify({'error': 'Deck de flashcards para esta matéria não existe.'}), 404
        deck_id = deck_response.data['id']

        # 3. Criar o flashcard
        flashcard_id = str(uuid.uuid4())
        flashcard_data = {
            'id': flashcard_id,
            'user_id': current_user['id'],
            'deck_id': deck_id,
            'summary_id': exercise.get('summary_id'),
            'question': exercise['statement'],
            'answer': f"{exercise['answer']}) {correct_option_text}"
        }
        
        fc_response = supabase.table('flashcards').insert(flashcard_data).execute()
        if not fc_response.data:
            raise Exception("Falha ao criar o flashcard.")

        # 4. Criar a ligação na tabela exercise_flashcard_links
        link_data = {'exercise_id': exercise_id, 'flashcard_id': flashcard_id}
        supabase.table('exercise_flashcard_links').insert(link_data).execute()

        return jsonify({'message': 'Flashcard criado e vinculado com sucesso', 'flashcard': fc_response.data[0]}), 201

    except Exception as e:
        print(f"ERRO EM /<id>/create-flashcard: {e}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

@exercises_bp.route('/<exercise_id>/append-to-summary', methods=['POST'])
@require_auth
def append_knowledge_to_summary(exercise_id):
    """
    Usa a IA para integrar o conhecimento de um exercício ao seu resumo pai.
    """
    supabase = get_supabase_client()
    current_user = get_current_user()

    try:
        # 1. Buscar o exercício e seu resumo pai
        exercise_response = supabase.table('exercises').select('*, summaries(*)').eq('id', exercise_id).eq('user_id', current_user['id']).single().execute()
        
        if not exercise_response.data:
            return jsonify({'error': 'Exercício não encontrado'}), 404
            
        exercise = exercise_response.data
        summary = exercise.get('summaries')

        if not summary:
            return jsonify({'error': 'Este exercício não está associado a um resumo.'}), 400

        # 2. Chamar a IA para fazer a integração
        gpt_service = get_gpt_service()
        updated_content = gpt_service.integrate_exercise_into_summary(
            summary_content=summary['content'],
            exercise_statement=exercise['statement'],
            exercise_answer=exercise['answer']
        )

        # 3. Atualizar o resumo no banco de dados
        update_response = supabase.table('summaries').update({'content': updated_content}).eq('id', summary['id']).execute()
        
        if not update_response.data:
            raise Exception("Falha ao atualizar o resumo.")

        return jsonify({'message': 'Conhecimento integrado ao resumo com sucesso!', 'summary': update_response.data[0]}), 200

    except Exception as e:
        print(f"ERRO EM /<id>/append-to-summary: {e}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500
    
@exercises_bp.route('/suggested-daily', methods=['GET'])
@require_auth
def get_suggested_exercises():
    current_user = get_current_user()
    supabase = get_supabase_client()
    
    try:
        # Pega o limite dos parâmetros da URL, com um padrão seguro
        limit = int(request.args.get('limit', 50))
        
        response = supabase.rpc('get_daily_suggested_exercises', {
            'p_user_id': current_user['id'],
            'p_limit': limit
        }).execute()

        if response.data is None:
             # A RPC pode retornar nulo se a função tiver um erro interno não capturado
             raise Exception("A função RPC não retornou dados.")

        return jsonify({'exercises': response.data}), 200
    except Exception as e:
        print(f"ERRO AO BUSCAR EXERCÍCIOS SUGERIDOS: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

