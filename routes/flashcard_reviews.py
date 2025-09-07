from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from datetime import datetime

flashcard_reviews_bp = Blueprint('flashcard_reviews', __name__)

@flashcard_reviews_bp.route('/pending', methods=['GET'])
@require_auth
def get_pending_flashcard_reviews():
    """Obter flashcards pendentes de revisão."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        response = (
            supabase.table('flashcard_review_sessions')
            .select('''
                *,
                flashcards (
                    *,
                    flashcard_decks (name)
                )
            ''')
            .eq('user_id', current_user['id'])
            .eq('is_completed', False)
            .lte('next_review', 'now()')
            .is_('flashcards.deleted_at', None) 
            .order('next_review', desc=False)
            .execute()
        )
        
        pending_reviews = response.data if response.data else []
        
        return jsonify({
            'pending_reviews': pending_reviews,
            'total_pending': len(pending_reviews)
        }), 200
        
    except Exception as e:
        print(f"ERRO EM /flashcard-reviews/pending: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@flashcard_reviews_bp.route('/complete', methods=['POST'])
@require_auth
def complete_flashcard_review():
    """Marcar revisão de flashcard como completa e calcular próxima."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        flashcard_id = data.get('flashcard_id')
        difficulty_rating = int(data.get('difficulty_rating'))
        
        if not flashcard_id or not difficulty_rating:
            return jsonify({'error': 'flashcard_id e difficulty_rating são obrigatórios'}), 400

        supabase = get_supabase_client()
        
        review_response = supabase.table('flashcard_review_sessions').select('*').eq('user_id', current_user['id']).eq('flashcard_id', flashcard_id).execute()
        
        if not review_response.data:
            return jsonify({'error': 'Sessão de revisão do flashcard não encontrada'}), 404
            
        current_review = review_response.data[0]
        
        # Reutilizamos a MESMA função SQL genérica!
        calc_response = supabase.rpc('calculate_next_review', {
            'current_ease_factor': current_review['ease_factor'],
            'current_interval': current_review['interval_days'],
            'difficulty_rating': difficulty_rating
        }).execute()

        if calc_response.data:
            next_review_data = calc_response.data[0]
            update_data = {
                'last_reviewed': datetime.now().isoformat(),
                'next_review': next_review_data['next_review_date'],
                'review_count': current_review['review_count'] + 1,
                'difficulty_rating': difficulty_rating,
                'ease_factor': next_review_data['new_ease_factor'],
                'interval_days': next_review_data['new_interval'],
                'is_completed': (6 - difficulty_rating) >= 4 
            }
            
            update_response = supabase.table('flashcard_review_sessions').update(update_data).eq('id', current_review['id']).select('*').execute()

            if update_response.data:
                # Opcional: registrar estatística de flashcard revisado
                return jsonify({
                    'message': 'Revisão de flashcard completada com sucesso',
                    'review_session': update_response.data[0]
                }), 200
            else:
                return jsonify({'error': 'Erro ao atualizar revisão do flashcard'}), 400
        else:
            return jsonify({'error': 'Erro ao calcular próxima revisão'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500