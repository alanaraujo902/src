"""
Rotas para sistema de revisão espaçada
"""

import json

from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from datetime import datetime, timedelta

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('/pending', methods=['GET'])
@require_auth
def get_pending_reviews():
    """Obter resumos pendentes de revisão com dados aninhados."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Query para buscar sessões de revisão que:
        # 1. Pertencem ao usuário atual ('user_id')
        # 2. NÃO estão marcadas como completas ('is_completed', False)
        # 3. A data da próxima revisão já passou ou é agora ('next_review', lte('now()'))
        # 4. <<< ADICIONADA: O resumo associado NÃO ESTÁ soft-deletado (summaries.deleted_at IS NULL) >>>
        
        response = (
            supabase.table('review_sessions')
            .select('''
                *,
                summaries (
                    *,
                    subjects (*, deleted_at) # Adicionado deleted_at para sujeitos também, se necessário
                )
            ''')
            .eq('user_id', current_user['id'])
            .eq('is_completed', False)
            .lte('next_review', 'now()')
            .is_('summaries.deleted_at', None) # <<< FILTRO CHAVE ADICIONADO AQUI >>>
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
    try:
        current_user = get_current_user()
        data = request.get_json()

        if not data or 'summary_id' not in data or 'difficulty_rating' not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        summary_id = data['summary_id']
        difficulty_rating = int(data['difficulty_rating'])
        
        supabase = get_supabase_client()
        user_id = current_user['id']

        # --- NOVA LÓGICA DE ACOPLAMENTO ---
        # 1. Buscar todos os flashcards associados a este resumo
        flashcards_response = supabase.table('flashcards').select('id').eq('summary_id', summary_id).eq('user_id', user_id).execute()
        
        coupling_data = None
        if flashcards_response.data:
            flashcard_ids = [fc['id'] for fc in flashcards_response.data]

            # 2. Buscar as sessões de revisão desses flashcards para obter as notas mais recentes
            sessions_response = supabase.table('flashcard_review_sessions').select('difficulty_rating, review_count').in_('flashcard_id', flashcard_ids).execute()
            
            if sessions_response.data:
                all_grades_are_1 = all(s['difficulty_rating'] == 5 for s in sessions_response.data) # No app, 5 é Muito Difícil (g=1 na sua fórmula)

                card_grades_for_coupling = {
                    "all_grades_are_1": all_grades_are_1,
                    "grades": [
                        {
                            "grade": s['difficulty_rating'], 
                            "weight": min(1.0, s['review_count'] / 3.0) # Peso por confiança (k=3)
                        } 
                        for s in sessions_response.data
                    ]
                }
                coupling_data = card_grades_for_coupling

        # ------------------------------------
        
        # Chamar a nova função RPC v2
        calc_response = supabase.rpc('calculate_srs_update_v2', {
            'p_item_id': summary_id,
            'p_item_type': 'summary',
            'p_user_id': user_id,
            'p_grade': difficulty_rating,
            'p_coupling_data': coupling_data  # Passa os dados de acoplamento
        }).execute()
        
        if not calc_response.data:
            return jsonify({"error": "Failed to calculate SRS update"}), 500

        srs_data = calc_response.data[0]
        new_interval = srs_data['new_interval']
        new_ease_factor = srs_data['new_ease_factor']
        new_review_date = srs_data['new_review_date']

        # Inserir na tabela 'review_sessions'
        session_insert = {
            'user_id': user_id,
            'summary_id': summary_id,
            'difficulty_rating': difficulty_rating,
            'review_date': datetime.now().isoformat()
        }
        supabase.table('review_sessions').insert(session_insert).execute()

        # Atualizar a tabela 'summaries'
        summary_update = {
            'current_interval': new_interval,
            'ease_factor': new_ease_factor,
            'next_review_date': new_review_date,
            'last_review_date': datetime.now().isoformat()
        }
        supabase.table('summaries').update(summary_update).eq('id', summary_id).execute()

        return jsonify({"message": "Review completed successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

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

