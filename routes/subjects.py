"""
Rotas para gerenciamento de matérias
"""
from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
import uuid
import json

subjects_bp = Blueprint('subjects', __name__)

@subjects_bp.route('', methods=['GET'])
@require_auth
def get_subjects():
    """Listar matérias do usuário"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Buscar matérias do usuário ordenadas por hierarquia
        response = supabase.table('subjects').select('*').eq('user_id', current_user['id']).is_('deleted_at', None).order('hierarchy_path').execute()

        
        subjects = response.data if response.data else []
        
        # Organizar em estrutura hierárquica
        subjects_tree = build_subjects_tree(subjects)
        
        return jsonify({
            'subjects': subjects,
            'subjects_tree': subjects_tree
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@subjects_bp.route('', methods=['POST'])
@require_auth
def create_subject():
    """Criar nova matéria"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Nome da matéria é obrigatório'}), 400
        
        supabase = get_supabase_client()
        
        # Dados da nova matéria
        subject_data = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'name': data['name'],
            'description': data.get('description', ''),
            'parent_id': data.get('parent_id'),
            'color': data.get('color', '#3B82F6'),
            'icon': data.get('icon', 'book')
        }
        
        # Verificar se parent_id existe (se fornecido)
        if subject_data['parent_id']:
            parent_response = supabase.table('subjects').select('id').eq('id', subject_data['parent_id']).eq('user_id', current_user['id']).execute()
            
            if not parent_response.data:
                return jsonify({'error': 'Matéria pai não encontrada'}), 404
        
        # Inserir matéria
        response = supabase.table('subjects').insert(subject_data).execute()
        
        if response.data:
            return jsonify({
                'message': 'Matéria criada com sucesso',
                'subject': response.data[0]
            }), 201
        else:
            return jsonify({'error': 'Erro ao criar matéria'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@subjects_bp.route('/<subject_id>', methods=['GET'])
@require_auth
def get_subject(subject_id):
    """Obter matéria específica"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Buscar matéria
        response = supabase.table('subjects').select('*').eq('id', subject_id).eq('user_id', current_user['id']).is_('deleted_at', None).execute()

        
        if not response.data:
            return jsonify({'error': 'Matéria não encontrada'}), 404
        
        subject = response.data[0]
        
        # Buscar filhos da matéria
        children_response = supabase.table('subjects').select('*').eq('parent_id', subject_id).eq('user_id', current_user['id']).execute()
        
        children = children_response.data if children_response.data else []
        
        # Buscar resumos da matéria
        summaries_response = supabase.table('summaries').select('id, title, created_at, difficulty_level, is_favorite').eq('subject_id', subject_id).eq('user_id', current_user['id']).execute()
        
        summaries = summaries_response.data if summaries_response.data else []
        
        return jsonify({
            'subject': subject,
            'children': children,
            'summaries': summaries,
            'summaries_count': len(summaries)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@subjects_bp.route('/<subject_id>', methods=['PUT'])
@require_auth
def update_subject(subject_id):
    """Atualizar matéria"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        supabase = get_supabase_client()
        
        # Verificar se matéria existe e pertence ao usuário
        existing_response = supabase.table('subjects').select('*').eq('id', subject_id).eq('user_id', current_user['id']).execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # Campos permitidos para atualização
        allowed_fields = ['name', 'description', 'parent_id', 'color', 'icon']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({'error': 'Nenhum campo válido para atualização'}), 400
        
        # Verificar parent_id se fornecido
        if 'parent_id' in update_data and update_data['parent_id']:
            # Não permitir que seja pai de si mesmo
            if update_data['parent_id'] == subject_id:
                return jsonify({'error': 'Matéria não pode ser pai de si mesma'}), 400
            
            # Verificar se parent existe
            parent_response = supabase.table('subjects').select('id').eq('id', update_data['parent_id']).eq('user_id', current_user['id']).execute()
            
            if not parent_response.data:
                return jsonify({'error': 'Matéria pai não encontrada'}), 404
        
        # Atualizar matéria
        response = supabase.table('subjects').update(update_data).eq('id', subject_id).eq('user_id', current_user['id']).execute()
        
        if response.data:
            return jsonify({
                'message': 'Matéria atualizada com sucesso',
                'subject': response.data[0]
            }), 200
        else:
            return jsonify({'error': 'Erro ao atualizar matéria'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@subjects_bp.route('/<subject_id>', methods=['DELETE'])
@require_auth
def delete_subject(subject_id):
    """Deletar matéria"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Verificar se matéria existe e pertence ao usuário
        existing_response = supabase.table('subjects').select('*').eq('id', subject_id).eq('user_id', current_user['id']).execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # Verificar se tem filhos
        children_response = supabase.table('subjects').select('id').eq('parent_id', subject_id).execute()
        
        if children_response.data:
            return jsonify({'error': 'Não é possível deletar matéria que possui submatérias'}), 400
        
        # Verificar se tem resumos
        summaries_response = supabase.table('summaries').select('id').eq('subject_id', subject_id).execute()
        
        if summaries_response.data:
            return jsonify({'error': 'Não é possível deletar matéria que possui resumos'}), 400
        
        # Deletar matéria
        response = supabase.table('subjects').delete().eq('id', subject_id).eq('user_id', current_user['id']).execute()
        
        return jsonify({'message': 'Matéria deletada com sucesso'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500





# ADICIONE ESTA NOVA ROTA COMPLETA no final do arquivo, antes da função build_subjects_tree
@subjects_bp.route('/<subject_id>/summaries', methods=['GET'])
@require_auth
def get_subject_and_descendants_summaries(subject_id):
    """Listar todos os resumos de uma matéria e de todas as suas submatérias descendentes."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # Parâmetros de paginação
        limit = int(request.args.get('limit', 100)) # Aumentar o limite padrão para esta visualização
        offset = int(request.args.get('offset', 0))

        # 1. Usar uma função RPC para obter todos os IDs descendentes (a mesma do delete)
        #    Certifique-se que a função 'get_subject_and_descendant_ids' (criada abaixo) existe no seu banco.
        id_response = supabase.rpc('get_subject_and_descendant_ids', {'start_subject_id': subject_id}).execute()
        
        if not id_response.data:
            return jsonify({'error': 'Matéria não encontrada ou sem descendentes'}), 404

        subject_ids = [item['id'] for item in id_response.data]

        # 2. Buscar todos os resumos onde o subject_id está na lista de IDs encontrados
        query = supabase.table('summaries').select('''...''').in_('subject_id', subject_ids).eq('user_id', current_user['id']).is_('deleted_at', None)

        
        response = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        
        summaries = response.data if response.data else []
        
        return jsonify({
            'summaries': summaries,
            'total': len(summaries),
            'limit': limit,
            'offset': offset
        }), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500



def build_subjects_tree(subjects):
    """
    Constrói árvore hierárquica de matérias
    
    Args:
        subjects: Lista de matérias
        
    Returns:
        Lista de matérias organizadas em árvore
    """
    subjects_dict = {s['id']: {**s, 'children': []} for s in subjects}
    tree = []
    
    for subject in subjects:
        if subject['parent_id']:
            # Adicionar como filho do pai
            if subject['parent_id'] in subjects_dict:
                subjects_dict[subject['parent_id']]['children'].append(subjects_dict[subject['id']])
        else:
            # Matéria raiz
            tree.append(subjects_dict[subject['id']])
    
    return tree

@subjects_bp.route('/free-review-stats', methods=['GET'])
@require_auth
def get_subjects_with_mastery():
    """Listar matérias com estatísticas de maestria para a Revisão Livre."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # 1. Obter todas as matérias do usuário
        subjects_response = supabase.table('subjects').select('*').eq('user_id', current_user['id']).execute()
        subjects = subjects_response.data or []

        # 2. Obter as estatísticas de maestria usando a função RPC
        stats_response = supabase.rpc('get_subject_mastery_stats', {'user_uuid': current_user['id']}).execute()
        stats_map = {stat['subject_id']: stat for stat in (stats_response.data or [])}

        # 3. Combinar os dados
        for subject in subjects:
            subject_stats = stats_map.get(subject['id'])
            if subject_stats:
                subject['mastery_percentage'] = float(subject_stats['mastery_percentage'])
            else:
                subject['mastery_percentage'] = 100.0  # Padrão se não houver resumos

        return jsonify({'subjects': subjects}), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
    
@subjects_bp.route('/<subject_id>/free-review-summaries', methods=['GET'])
@require_auth
def get_free_review_summaries(subject_id):
    """Obter todos os resumos de uma matéria e suas descendentes para a Revisão Livre."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # Obter a matéria e todos os seus descendentes
        id_response = supabase.rpc('get_subject_and_descendant_ids', {'start_subject_id': subject_id}).execute()
        
        if not id_response.data:
            return jsonify({'summaries': []}), 200

        subject_ids = [item['id'] for item in id_response.data]

        # Buscar resumos, ordenando pelos mais recentes primeiro
        response = supabase.table('summaries').select('*, subjects(name, color)') \
            .in_('subject_id', subject_ids) \
            .eq('user_id', current_user['id']) \
            .order('created_at', desc=True) \
            .execute()
            
        summaries = response.data if response.data else []
        
        return jsonify({'summaries': summaries}), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
    #coment