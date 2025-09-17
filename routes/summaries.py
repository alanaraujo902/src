# Caminho: F:\projetos\projects\univ_ai\backend\app_estudos\backend\estudos_api\src\routes\summaries.py

"""
Rotas para gerenciamento de resumos
"""
from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.config.perplexity import get_perplexity_client
from src.utils.auth import require_auth, get_current_user
import uuid
import json
from datetime import datetime, timedelta # <-- CORREÇÃO: Import adicionado

summaries_bp = Blueprint('summaries', __name__)

@summaries_bp.route('', methods=['GET'])
@require_auth
def get_summaries():
    """Listar resumos do usuário"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Parâmetros de filtro
        subject_id = request.args.get('subject_id')
        search = request.args.get('search')
        tags = request.args.get('tags')
        difficulty = request.args.get('difficulty')
        is_favorite = request.args.get('is_favorite')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Construir query
        query = supabase.table('summaries').select('''...''').eq('user_id', current_user['id']).is_('deleted_at', None)
        
        # Aplicar filtros
        if subject_id:
            query = query.eq('subject_id', subject_id)
        
        if search:
            query = query.ilike('title', f'%{search}%')
        
        if difficulty:
            query = query.eq('difficulty_level', int(difficulty))
        
        if is_favorite == 'true':
            query = query.eq('is_favorite', True)
        
        if tags:
            tag_list = tags.split(',')
            query = query.contains('tags', tag_list)
        
        # Ordenar e paginar
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

@summaries_bp.route('/generate', methods=['POST'])
@require_auth
def generate_summary():
    """Gerar resumo usando Perplexity"""
    try:
        data = request.get_json()
        
        if not data or not data.get('query'):
            return jsonify({'error': 'Query é obrigatória'}), 400
        
        query = data['query']
        model = data.get('model', 'sonar-pro')
        # <-- ADICIONE ESTA LINHA -->
        # Pega o estilo do prompt da requisição, ou usa 'default' se não for enviado.
        prompt_style = data.get('prompt_style', 'default')
        
        perplexity = get_perplexity_client()
        # <-- MODIFIQUE ESTA LINHA para passar o novo parâmetro -->
        result = perplexity.generate_summary(query, model, prompt_style=prompt_style)
        
        if not result['success']:
            return jsonify({'error': f'Erro ao gerar resumo: {result.get("error", "Erro desconhecido")}'}), 500
        
        return jsonify({
            'message': 'Resumo gerado com sucesso',
            'content': result['content'],
            'citations': result['citations'],
            'search_results': result['search_results'],
            'model_used': result['model_used'],
            'tokens_used': result['tokens_used']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
        
        return jsonify({
            'message': 'Resumo gerado com sucesso',
            'content': result['content'],
            'citations': result['citations'],
            'search_results': result['search_results'],
            'model_used': result['model_used'],
            'tokens_used': result['tokens_used']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@summaries_bp.route('', methods=['POST'])
@require_auth
def create_summary():
    """Criar novo resumo (agora aceita um ID opcional do cliente)"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        required_fields = ['title', 'content', 'original_query', 'subject_id']
        if not data or not all(data.get(field) for field in required_fields):
            return jsonify({'error': 'Campos obrigatórios: title, content, original_query, subject_id'}), 400
        
        supabase = get_supabase_client()
        
        # Verificar se subject_id existe
        subject_response = supabase.table('subjects').select('id').eq('id', data['subject_id']).eq('user_id', current_user['id']).execute()
        
        if not subject_response.data:
            return jsonify({'error': 'Matéria não encontrada'}), 404
        
        # Se o cliente enviar um ID, use-o. Senão, gere um novo.
        summary_id = data.get('id', str(uuid.uuid4()))
        
        # Dados do resumo
        summary_data = {
            'id': summary_id, # <-- USA O ID DEFINIDO
            'user_id': current_user['id'],
            'subject_id': data['subject_id'],
            'title': data['title'],
            'content': data['content'],
            'original_query': data['original_query'],
            'perplexity_response': json.dumps(data.get('perplexity_response', {})),
            'perplexity_citations': data.get('perplexity_citations', []),
            'image_url': data.get('image_url'),
            'tags': data.get('tags', []),
            'difficulty_level': data.get('difficulty_level', 3),
            'is_favorite': data.get('is_favorite', False)
        }
        
        # Inserir resumo
        response = supabase.table('summaries').insert(summary_data).execute()
        
        if response.data:
            summary = response.data[0]
            
            ## <--- ALTERAÇÃO PRINCIPAL APLICADA AQUI --->
            
            # Define a data da primeira revisão para AGORA.
            # que ela seja imediatamente incluída na lista de pendentes, evitando race conditions.
            next_review_date = (datetime.now() - timedelta(seconds=1)).isoformat()
            
            # Criar sessão de revisão inicial com a data ajustada
            review_data = {
                'user_id': current_user['id'],
                'summary_id': summary['id'],
                'next_review': next_review_date,
                'review_frequency_days': 1
            }
            
            supabase.table('review_sessions').insert(review_data).execute()

            
            # Atualizar estatísticas
            supabase.rpc('update_study_statistics', {
                'user_uuid': current_user['id'],
                'summaries_created_count': 1,
                'subjects_studied_array': [data['subject_id']]
            }).execute()
            
            return jsonify({
                'message': 'Resumo criado com sucesso',
                'summary': summary
            }), 201
        else:
            # Adicione um print para ver a resposta de erro do Supabase
            print(f"ERRO AO CRIAR RESUMO (SUPABASE): {response.error}")
            return jsonify({'error': 'Erro ao criar resumo'}), 400
            
    except Exception as e:
        # Adicione um print para ver o erro detalhado no console do Flask
        print(f"ERRO INTERNO AO CRIAR RESUMO: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@summaries_bp.route('/<summary_id>', methods=['GET'])
@require_auth
def get_summary(summary_id):
    """Obter resumo específico"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Buscar resumo com informações da matéria
        response = supabase.table('summaries').select('''
            *,
            subjects(name, color, hierarchy_path),
            review_sessions(last_reviewed, next_review, review_count, difficulty_rating)
        ''').eq('id', summary_id).eq('user_id', current_user['id']).is_('deleted_at', None).execute()
        
        if not response.data:
            return jsonify({'error': 'Resumo não encontrado'}), 404
        
        summary = response.data[0]
        
        return jsonify({'summary': summary}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@summaries_bp.route('/<summary_id>', methods=['PUT'])
@require_auth
def update_summary(summary_id):
    """Atualizar resumo"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400
        
        supabase = get_supabase_client()
        
        # Verificar se resumo existe e pertence ao usuário
        existing_response = supabase.table('summaries').select('*').eq('id', summary_id).eq('user_id', current_user['id']).execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Resumo não encontrado'}), 404
        
        # Campos permitidos para atualização
        allowed_fields = ['title', 'content', 'tags', 'difficulty_level', 'is_favorite']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({'error': 'Nenhum campo válido para atualização'}), 400
        
        # Atualizar resumo
        response = supabase.table('summaries').update(update_data).eq('id', summary_id).eq('user_id', current_user['id']).execute()
        
        if response.data:
            return jsonify({
                'message': 'Resumo atualizado com sucesso',
                'summary': response.data[0]
            }), 200
        else:
            return jsonify({'error': 'Erro ao atualizar resumo'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@summaries_bp.route('/<summary_id>', methods=['DELETE'])
@require_auth
def delete_summary(summary_id):
    """Deletar resumo"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Verificar se resumo existe e pertence ao usuário
        existing_response = supabase.table('summaries').select('*').eq('id', summary_id).eq('user_id', current_user['id']).execute()
        
        if not existing_response.data:
            return jsonify({'error': 'Resumo não encontrado'}), 404
        
        # Deletar resumo (cascata deletará review_sessions)
        response = supabase.table('summaries').delete().eq('id', summary_id).eq('user_id', current_user['id']).execute()
        
        return jsonify({'message': 'Resumo deletado com sucesso'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@summaries_bp.route('/process-image', methods=['POST'])
@require_auth
def process_image():
    """Processar imagem e gerar resumo"""
    try:
        current_user = get_current_user()
        
        # Verificar se arquivo foi enviado
        if 'image' not in request.files:
            return jsonify({'error': 'Imagem não fornecida'}), 400
        
        file = request.files['image']
        question = request.form.get('question', '')
        subject_id = request.form.get('subject_id')
        
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Aqui você implementaria OCR (ex: Tesseract, Google Vision API)
        # Por simplicidade, vamos simular extração de texto
        extracted_text = "Texto extraído da imagem (implementar OCR aqui)"
        
        # Gerar resumo com Perplexity
        perplexity = get_perplexity_client()
        result = perplexity.process_image_query(extracted_text, question)
        
        if not result['success']:
            return jsonify({'error': f'Erro ao processar imagem: {result.get("error", "Erro desconhecido")}'}), 500
        
        return jsonify({
            'message': 'Imagem processada com sucesso',
            'extracted_text': extracted_text,
            'content': result['content'],
            'citations': result['citations'],
            'search_results': result['search_results']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@summaries_bp.route('/<summary_id>/log-free-rev', methods=['POST'])
@require_auth
def log_free_review(summary_id):
    """Incrementa o contador de revisões livres para um resumo."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        # Usamos RPC para uma operação atômica de incremento
        supabase.rpc('increment_free_rev_count', {
            'p_summary_id': summary_id,
            'p_user_id': current_user['id']
        }).execute()

        return jsonify({'message': 'Visualização registrada com sucesso'}), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
