"""
Rotas para sistema de revisão espaçada
"""

import json

from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from datetime import datetime, timedelta

reviews_bp = Blueprint('reviews', __name__)

# <<< SUBSTITUA A FUNÇÃO 'get_pending_reviews' INTEIRA POR ESTA >>>
@reviews_bp.route('/pending', methods=['GET'])
@require_auth
def get_pending_reviews():
    """Obter resumos pendentes de revisão com dados aninhados."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Esta é a consulta correta e definitiva. Ela busca sessões de revisão que:
        # 1. Pertencem ao usuário atual ('user_id')
        # 2. NÃO estão marcadas como completas ('is_completed', False)
        # 3. A data da próxima revisão já passou ou é agora ('next_review', lte('now()'))
        response = (
            supabase.table('review_sessions')
            .select('''
                *,
                summaries (
                    *,
                    subjects (*)
                )
            ''')
            .eq('user_id', current_user['id'])
            .eq('is_completed', False)
            .lte('next_review', 'now()')
            .order('next_review', desc=False)
            .execute()
        )
        
        pending_reviews = response.data if response.data else []

        # --- BLOCO DE DEPURAÇÃO (MUITO IMPORTANTE) ---
        # Verifique o terminal do Flask após acessar a tela de revisão.
        # Ele mostrará exatamente o que está sendo enviado para o app.
        print("\n--- JSON SENDO ENVIADO PARA O FRONTEND (/reviews/pending) ---")
        print(f"Total de revisões pendentes encontradas: {len(pending_reviews)}")
        # Use 'default=str' para lidar com objetos de data e hora que não são serializáveis por padrão
        print(json.dumps(pending_reviews, indent=2, default=str))
        print("----------------------------------------------------------\n")
        # --- FIM DO BLOCO ---
        
        return jsonify({
            'pending_reviews': pending_reviews,
            'total_pending': len(pending_reviews)
        }), 200
        
    except Exception as e:
        # Adiciona um print para ver o erro no terminal do Flask
        print(f"ERRO EM /reviews/pending: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@reviews_bp.route('/session/start', methods=['POST'])
@require_auth
def start_review_session():
    """Iniciar sessão de revisão"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        subject_id = data.get('subject_id')  # Opcional: filtrar por matéria
        limit = data.get('limit', 10)  # Limite de resumos na sessão
        
        supabase = get_supabase_client()
        
        # Construir query para resumos pendentes
        query = supabase.table('review_sessions').select('''
            *,
            summaries(id, title, content, subject_id, difficulty_level),
            summaries.subjects(name, color)
        ''').eq('user_id', current_user['id']).lte('next_review', 'now()').eq('is_completed', False)
        
        if subject_id:
            # Filtrar por matéria através da tabela summaries
            query = query.eq('summaries.subject_id', subject_id)
        
        response = query.order('next_review').limit(limit).execute()
        
        session_reviews = response.data if response.data else []
        
        if not session_reviews:
            return jsonify({
                'message': 'Nenhuma revisão pendente encontrada',
                'session_reviews': [],
                'session_id': None
            }), 200
        
        # Criar ID da sessão (timestamp)
        session_id = str(int(datetime.now().timestamp()))
        
        return jsonify({
            'message': 'Sessão de revisão iniciada',
            'session_reviews': session_reviews,
            'session_id': session_id,
            'total_reviews': len(session_reviews)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@reviews_bp.route('/complete', methods=['POST'])
@require_auth
def complete_review():
    """Marcar revisão como completa e calcular próxima"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        required_fields = ['summary_id', 'difficulty_rating']
        if not data or not all(data.get(field) for field in required_fields):
            return jsonify({'error': 'Campos obrigatórios: summary_id, difficulty_rating'}), 400
        
        summary_id = data['summary_id']
        difficulty_rating = int(data['difficulty_rating'])
        
        if difficulty_rating < 1 or difficulty_rating > 5:
            return jsonify({'error': 'difficulty_rating deve estar entre 1 e 5'}), 400
        
        supabase = get_supabase_client()
        
        # --- INÍCIO DO BLOCO DE DEPURAÇÃO ---
        user_id = current_user['id']
        print("\n--- INICIANDO /reviews/complete ---")
        print(f"Buscando review_session para user_id: {user_id}")
        print(f"Buscando review_session para summary_id: {summary_id}")
        # --- FIM DO BLOCO DE DEPURAÇÃO ---
        
        # Buscar sessão de revisão atual
        review_response = supabase.table('review_sessions').select('*').eq('user_id', user_id).eq('summary_id', summary_id).execute()
        
        # --- INÍCIO DO BLOCO DE DEPURAÇÃO ---
        print(f"Resultado da busca no Supabase: {review_response.data}")
        # --- FIM DO BLOCO DE DEPURAÇÃO ---

        if not review_response.data:
            print("!!! ERRO: Sessão de revisão NÃO encontrada no banco de dados. Retornando 404. !!!")
            return jsonify({'error': 'Sessão de revisão não encontrada'}), 404
        
        current_review = review_response.data[0]
        
        # Calcular próxima revisão usando função do banco
        calc_response = supabase.rpc('calculate_next_review', {
            'current_ease_factor': current_review['ease_factor'],
            'current_interval': current_review['interval_days'],
            'difficulty_rating': difficulty_rating
        }).execute()
        
        if calc_response.data:
            next_review_data = calc_response.data[0]
            
            # Atualizar sessão de revisão
            update_data = {
                'last_reviewed': datetime.now().isoformat(),
                'next_review': next_review_data['next_review_date'],
                'review_count': current_review['review_count'] + 1,
                'difficulty_rating': difficulty_rating,
                'ease_factor': next_review_data['new_ease_factor'],
                'interval_days': next_review_data['new_interval'],
                # <<< CORREÇÃO SUTIL: A lógica de 'is_completed' deve ser baseada na QUALIDADE, não na dificuldade.
                # Se a dificuldade for 4 (Fácil) ou 5 (Muito Fácil), a qualidade (q) será >= 4
                'is_completed': (6 - difficulty_rating) >= 4
            }
            
            update_response = supabase.table('review_sessions').update(update_data).eq('id', current_review['id']).select('*').execute()
            
            if update_response.data:
                # Atualizar estatísticas
                supabase.rpc('update_study_statistics', {
                    'user_uuid': user_id,
                    'summaries_reviewed_count': 1
                }).execute()
                
                print("--- SUCESSO: Revisão completada e atualizada. ---")
                return jsonify({
                    'message': 'Revisão completada com sucesso',
                    'review_session': update_response.data[0]
                }), 200
            else:
                return jsonify({'error': 'Erro ao atualizar revisão'}), 400
        else:
            return jsonify({'error': 'Erro ao calcular próxima revisão'}), 500
            
    except Exception as e:
        print(f"!!! ERRO INTERNO CATASTRÓFICO em /reviews/complete: {str(e)} !!!")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@reviews_bp.route('/frequency', methods=['PUT'])
@require_auth
def update_review_frequency():
    """Atualizar frequência de revisão"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data or not data.get('summary_id') or not data.get('frequency_days'):
            return jsonify({'error': 'summary_id e frequency_days são obrigatórios'}), 400
        
        summary_id = data['summary_id']
        frequency_days = int(data['frequency_days'])
        
        if frequency_days < 1:
            return jsonify({'error': 'frequency_days deve ser maior que 0'}), 400
        
        supabase = get_supabase_client()
        
        # Atualizar frequência
        response = supabase.table('review_sessions').update({
            'review_frequency_days': frequency_days
        }).eq('user_id', current_user['id']).eq('summary_id', summary_id).execute()
        
        if response.data:
            return jsonify({
                'message': 'Frequência de revisão atualizada',
                'new_frequency_days': frequency_days
            }), 200
        else:
            return jsonify({'error': 'Sessão de revisão não encontrada'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@reviews_bp.route('/stats', methods=['GET'])
@require_auth
def get_review_stats():
    """Obter estatísticas de revisão"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Estatísticas gerais de revisão
        stats_query = supabase.table('review_sessions').select('*').eq('user_id', current_user['id'])
        
        all_reviews = stats_query.execute().data or []
        
        # Calcular estatísticas
        total_reviews = len(all_reviews)
        completed_reviews = len([r for r in all_reviews if r['is_completed']])
        pending_reviews = len([r for r in all_reviews if not r['is_completed'] and r['next_review'] <= datetime.now().isoformat()])
        
        # Revisões por dificuldade
        difficulty_stats = {}
        for i in range(1, 6):
            difficulty_stats[f'difficulty_{i}'] = len([r for r in all_reviews if r['difficulty_rating'] == i])
        
        # Streak de revisões (dias consecutivos)
        today = datetime.now().date()
        streak_days = 0
        check_date = today
        
        while True:
            day_reviews = supabase.table('review_sessions').select('id').eq('user_id', current_user['id']).gte('last_reviewed', check_date.isoformat()).lt('last_reviewed', (check_date + timedelta(days=1)).isoformat()).execute()
            
            if day_reviews.data:
                streak_days += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        return jsonify({
            'total_reviews': total_reviews,
            'completed_reviews': completed_reviews,
            'pending_reviews': pending_reviews,
            'completion_rate': (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0,
            'difficulty_stats': difficulty_stats,
            'streak_days': streak_days
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@reviews_bp.route('/reset/<summary_id>', methods=['POST'])
@require_auth
def reset_review_progress(summary_id):
    """Resetar progresso de revisão de um resumo"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Resetar sessão de revisão
        reset_data = {
            'last_reviewed': datetime.now().isoformat(),
            'next_review': (datetime.now() + timedelta(days=1)).isoformat(),
            'review_count': 0,
            'difficulty_rating': 3,
            'ease_factor': 2.50,
            'interval_days': 1,
            'is_completed': False
        }
        
        response = supabase.table('review_sessions').update(reset_data).eq('user_id', current_user['id']).eq('summary_id', summary_id).execute()
        
        if response.data:
            return jsonify({'message': 'Progresso de revisão resetado'}), 200
        else:
            return jsonify({'error': 'Sessão de revisão não encontrada'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

