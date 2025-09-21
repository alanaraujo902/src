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

        # --- INÍCIO DA MODIFICAÇÃO ---
        # Validação mais robusta dos dados de entrada
        if not data or not data.get('name') or not data.get('name').strip():
            return jsonify({'error': 'O nome da matéria é obrigatório e não pode ser vazio'}), 400
        # --- FIM DA MODIFICAÇÃO ---

        supabase = get_supabase_client()
        
        subject_data = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'name': data['name'].strip(), # Usa .strip() para remover espaços em branco
            'description': data.get('description', ''),
            'parent_id': data.get('parent_id'),
            'color': data.get('color', '#3B82F6'),
            'icon': data.get('icon', 'book')
        }
        
        if subject_data['parent_id']:
            parent_response = supabase.table('subjects').select('id').eq('id', subject_data['parent_id']).eq('user_id', current_user['id']).execute()
            if not parent_response.data:
                return jsonify({'error': 'Matéria pai não encontrada'}), 404
        
        response = supabase.table('subjects').insert(subject_data).execute()
        
        # O erro 400 provavelmente acontece aqui, vindo do Supabase
        if not response.data:
            # Se não houver dados, é provável que um erro de banco de dados tenha ocorrido.
            # A causa mais comum é a falha da FK para user_id.
            return jsonify({
                'error': 'Falha ao criar matéria. Verifique se o perfil de usuário existe ou se os dados são válidos.',
                'details': 'PostgREST API did not return data for the inserted row.'
            }), 500
            
        return jsonify({
            'message': 'Matéria criada com sucesso',
            'subject': response.data[0]
        }), 201
            
    except Exception as e:
        # Adiciona um log mais detalhado no console do backend
        print(f"ERRO CRÍTICO EM create_subject: {str(e)}")
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500

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
    """Deletar matéria e todos os seus descendentes (soft delete) usando RPC."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # 1. Verificar se a matéria existe e pertence ao usuário (para segurança)
        existing_response = supabase.table('subjects').select('id').eq('id', subject_id).eq('user_id', current_user['id']).maybe_single().execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # 2. Chamar a função RPC para realizar o soft delete em cascata de forma segura e atômica
        supabase.rpc('soft_delete_subject_and_descendants', {
            'start_subject_id': subject_id,
            'p_user_id': current_user['id']
        }).execute()

        return jsonify({'message': 'Matéria e seus conteúdos foram movidos para a lixeira.'}), 200
        
    except Exception as e:
        print(f"ERRO AO DELETAR MATÉRIA: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500





# ADICIONE ESTA NOVA ROTA COMPLETA no final do arquivo, antes da função build_subjects_tree
@subjects_bp.route('/<subject_id>/summaries', methods=['GET'])
@require_auth
def get_subject_and_descendants_summaries(subject_id):
    """Listar todos os resumos de uma matéria e de todas as suas submatérias descendentes."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        id_response = supabase.rpc('get_subject_and_descendant_ids', {'start_subject_id': subject_id}).execute()
        
        if not id_response.data:
            return jsonify({'error': 'Matéria não encontrada ou sem descendentes'}), 404

        subject_ids = [item['id'] for item in id_response.data]

        # ==================== INÍCIO DA CORREÇÃO ====================
        # Substituímos o "..." por uma seleção explícita para evitar ambiguidade.
        # Incluímos todos os campos da tabela summaries e os campos necessários de subjects.
        query = supabase.table('summaries').select('''
            id,
            user_id,
            subject_id,
            title,
            content,
            original_query,
            difficulty_level,
            is_favorite,
            created_at,
            updated_at,
            deleted_at,
            free_rev,
            incidence_weight,
            subjects (
                name,
                color
            )
        ''').in_('subject_id', subject_ids).eq('user_id', current_user['id']).is_('deleted_at', None)
        # ===================== FIM DA CORREÇÃO ======================
        
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


@subjects_bp.route('/<subject_id>/study-time', methods=['GET'])
@require_auth
def get_subject_study_time(subject_id):
    """Obtém o tempo total de estudo para uma matéria e suas submatérias."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # Chama a função SQL via RPC
        response = supabase.rpc('get_total_study_time_for_subject', {
            'p_subject_id': subject_id,
            'p_user_id': current_user['id']
        }).execute()

        total_time_ms = response.data if response.data else 0

        return jsonify({'total_study_time_ms': total_time_ms}), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500