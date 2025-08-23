"""
Rotas para gerenciamento de decks de estudo
"""
from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
import uuid

decks_bp = Blueprint('decks', __name__)

@decks_bp.route('/', methods=['GET'])
@require_auth
def get_decks():
    """Listar decks do usuário"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Buscar decks com informações da matéria e contagem de resumos
        response = supabase.table('study_decks').select('''...''').eq('user_id', current_user['id']).is_('deleted_at', None).order('created_at', desc=True).execute()

        
        decks = response.data if response.data else []
        
        # Adicionar contagem de resumos para cada deck
        for deck in decks:
            count_response = supabase.table('deck_summaries').select('id', count='exact').eq('deck_id', deck['id']).execute()
            deck['summaries_count'] = count_response.count if count_response.count else 0
        
        return jsonify({'decks': decks}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/', methods=['POST'])
@require_auth
def create_deck():
    """Criar novo deck"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Nome do deck é obrigatório'}), 400
        
        supabase = get_supabase_client()
        
        # Verificar subject_id se fornecido
        subject_id = data.get('subject_id')
        if subject_id:
            subject_response = supabase.table('subjects').select('id').eq('id', subject_id).eq('user_id', current_user['id']).execute()
            
            if not subject_response.data:
                return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # Dados do deck
        deck_data = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'name': data['name'],
            'description': data.get('description', ''),
            'subject_id': subject_id,
            'is_active': data.get('is_active', True),
            'deck_settings': data.get('deck_settings', {
                'auto_advance': True,
                'show_citations': True
            })
        }
        
        # Inserir deck
        response = supabase.table('study_decks').insert(deck_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Deck criado com sucesso',
                'deck': response.data[0]
            }), 201
        else:
            return jsonify({'error': 'Erro ao criar deck'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>', methods=['GET'])
@require_auth
def get_deck(deck_id):
    """Obter deck específico com resumos"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Buscar deck
        deck_response = supabase.table('study_decks').select('''...''').eq('id', deck_id).eq('user_id', current_user['id']).is_('deleted_at', None).execute()


        
        if not deck_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
        
        deck = deck_response.data[0]
        
        # Buscar resumos do deck
        summaries_response = supabase.table('deck_summaries').select('''
            position,
            summaries(
                id, title, content, difficulty_level, is_favorite, created_at,
                subjects(name, color),
                review_sessions(next_review, review_count, is_completed)
            )
        ''').eq('deck_id', deck_id).order('position').execute()
        
        summaries = []
        if summaries_response.data:
            for item in summaries_response.data:
                summary = item['summaries']
                summary['position'] = item['position']
                summaries.append(summary)
        
        deck['summaries'] = summaries
        deck['summaries_count'] = len(summaries)
        
        return jsonify({'deck': deck}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>', methods=['PUT'])
@require_auth
def update_deck(deck_id):
    """Atualizar deck"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        supabase = get_supabase_client()
        
        # Verificar se deck existe e pertence ao usuário
        existing_response = supabase.table('study_decks').select('*').eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
        
        # Campos permitidos para atualização
        allowed_fields = ['name', 'description', 'subject_id', 'is_active', 'deck_settings']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({'error': 'Nenhum campo válido para atualização'}), 400
        
        # Verificar subject_id se fornecido
        if 'subject_id' in update_data and update_data['subject_id']:
            subject_response = supabase.table('subjects').select('id').eq('id', update_data['subject_id']).eq('user_id', current_user['id']).execute()
            
            if not subject_response.data:
                return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # Atualizar deck
        response = supabase.table('study_decks').update(update_data).eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if response.data:
            return jsonify({
                'message': 'Deck atualizado com sucesso',
                'deck': response.data[0]
            }), 200
        else:
            return jsonify({'error': 'Erro ao atualizar deck'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>', methods=['DELETE'])
@require_auth
def delete_deck(deck_id):
    """Deletar deck (soft delete) e suas associações."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # 1. Verificar se o deck existe e pertence ao usuário
        existing_response = supabase.table('study_decks').select('id').eq('id', deck_id).eq('user_id', current_user['id']).execute()
        if not existing_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404

        # 2. Deletar as associações na tabela 'deck_summaries'.
        # Isso remove os resumos DO DECK, mas não os resumos em si.
        supabase.table('deck_summaries').delete().eq('deck_id', deck_id).execute()

        # 3. Marcar o deck como deletado (soft delete)
        now = datetime.now(timezone.utc).isoformat()
        response = supabase.table('study_decks').update({
            'deleted_at': now
        }).eq('id', deck_id).eq('user_id', current_user['id']).execute()

        print(f"Soft deleted deck {deck_id} for user {current_user['id']}")
        return jsonify({'message': 'Deck movido para a lixeira com sucesso'}), 200

    except Exception as e:
        print(f"ERRO AO DELETAR DECK: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>/summaries', methods=['POST'])
@require_auth
def add_summary_to_deck(deck_id):
    """Adicionar resumo ao deck"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data or not data.get('summary_id'):
            return jsonify({'error': 'summary_id é obrigatório'}), 400
        
        summary_id = data['summary_id']
        
        supabase = get_supabase_client()
        
        # Verificar se deck existe e pertence ao usuário
        deck_response = supabase.table('study_decks').select('id').eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if not deck_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
        
        # Verificar se resumo existe e pertence ao usuário
        summary_response = supabase.table('summaries').select('id').eq('id', summary_id).eq('user_id', current_user['id']).execute()
        
        if not summary_response.data:
            return jsonify({'error': 'Resumo não encontrado'}), 404
        
        # Verificar se resumo já está no deck
        existing_response = supabase.table('deck_summaries').select('id').eq('deck_id', deck_id).eq('summary_id', summary_id).execute()
        
        if existing_response.data:
            return jsonify({'error': 'Resumo já está no deck'}), 400
        
        # Obter próxima posição
        position_response = supabase.table('deck_summaries').select('position').eq('deck_id', deck_id).order('position', desc=True).limit(1).execute()
        
        next_position = 1
        if position_response.data:
            next_position = position_response.data[0]['position'] + 1
        
        # Adicionar resumo ao deck
        deck_summary_data = {
            'deck_id': deck_id,
            'summary_id': summary_id,
            'position': next_position
        }
        
        response = supabase.table('deck_summaries').insert(deck_summary_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Resumo adicionado ao deck',
                'position': next_position
            }), 201
        else:
            return jsonify({'error': 'Erro ao adicionar resumo ao deck'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>/summaries/<summary_id>', methods=['DELETE'])
@require_auth
def remove_summary_from_deck(deck_id, summary_id):
    """Remover resumo do deck"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Verificar se deck pertence ao usuário
        deck_response = supabase.table('study_decks').select('id').eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if not deck_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
        
        # Remover resumo do deck
        response = supabase.table('deck_summaries').delete().eq('deck_id', deck_id).eq('summary_id', summary_id).execute()
        
        return jsonify({'message': 'Resumo removido do deck'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@decks_bp.route('/<deck_id>/reorder', methods=['PUT'])
@require_auth
def reorder_deck_summaries(deck_id):
    """Reordenar resumos no deck"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data or not data.get('summary_positions'):
            return jsonify({'error': 'summary_positions é obrigatório'}), 400
        
        summary_positions = data['summary_positions']  # Lista de {summary_id, position}
        
        supabase = get_supabase_client()
        
        # Verificar se deck pertence ao usuário
        deck_response = supabase.table('study_decks').select('id').eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if not deck_response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
        
        # Atualizar posições
        for item in summary_positions:
            supabase.table('deck_summaries').update({
                'position': item['position']
            }).eq('deck_id', deck_id).eq('summary_id', item['summary_id']).execute()
        
        return jsonify({'message': 'Ordem dos resumos atualizada'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

