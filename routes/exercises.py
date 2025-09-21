# src/routes/exercises.py

from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.config.gpt_service import get_gpt_service
from src.utils.auth import require_auth, get_current_user
from src.utils.exercise_parser import parse_gpt_exercise_response # Utilitário que criamos
import uuid
import json

exercises_bp = Blueprint('exercises', __name__)

@exercises_bp.route('/generate-from-text', methods=['POST'])
@require_auth
def generate_and_save_exercise():
    """
    Recebe um texto bruto, gera um exercício via IA, faz o parsing e salva no banco de dados.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Requisição sem corpo JSON'}), 400

    text = data.get('text')
    subject_id = data.get('subject_id')
    summary_id = data.get('summary_id') # Opcional

    if not text or not subject_id:
        return jsonify({'error': 'Campos "text" e "subject_id" são obrigatórios'}), 400

    gpt_service = get_gpt_service()
    supabase = get_supabase_client()
    current_user = get_current_user()

    try:
        # 1. Chamar a IA para gerar o exercício
        raw_gpt_response = gpt_service.generate_exercise_from_text(text)

        # 2. Fazer o parsing da resposta para um formato estruturado
        parsed_data = parse_gpt_exercise_response(raw_gpt_response)

        # 3. Preparar e salvar o novo exercício no banco de dados
        exercise_data = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'subject_id': subject_id,
            'summary_id': summary_id,
            'statement': parsed_data['statement'],
            'options': parsed_data['options'], # A biblioteca supabase converte dict/list para JSONB
            'answer': parsed_data['answer'],
            'original_text': text,
        }
        
        response = supabase.table('exercises').insert(exercise_data).execute()

        if not response.data:
            raise Exception("Falha ao salvar o exercício. Verifique as permissões (RLS) da tabela 'exercises'.")

        return jsonify({'message': 'Exercício criado com sucesso', 'exercise': response.data[0]}), 201

    except ValueError as ve: # Erro específico do nosso parser
        return jsonify({'error': f'Erro de parsing: {str(ve)}'}), 400
    except Exception as e:
        print(f"ERRO EM /generate-from-text: {e}")
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