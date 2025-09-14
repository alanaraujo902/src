from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user

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
    """Marcar revisão de flashcard como completa e calcular próxima (com acoplamento ao resumo pai)."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        data = request.get_json()
        flashcard_id = data.get('flashcard_id')
        difficulty_rating = data.get('difficulty_rating')

        if not flashcard_id or difficulty_rating is None:
            return jsonify({'error': 'flashcard_id e difficulty_rating são obrigatórios'}), 400

        try:
            difficulty_rating = int(difficulty_rating)
        except ValueError:
            return jsonify({'error': 'difficulty_rating deve ser um número inteiro'}), 400

        if difficulty_rating < 1 or difficulty_rating > 5:
            return jsonify({'error': 'difficulty_rating deve estar entre 1 e 5'}), 400

        # 1) Obter a sessão atual do flashcard
        review_response = (
            supabase.table('flashcard_review_sessions')
            .select('*')
            .eq('user_id', current_user['id'])
            .eq('flashcard_id', flashcard_id)
            .limit(1)
            .execute()
        )

        if not review_response.data:
            return jsonify({'error': 'Sessão de revisão do flashcard não encontrada'}), 404

        current_review = review_response.data[0]

        # --- NOVA LÓGICA DE ACOPLAMENTO ---
        # 2) Descobrir o resumo pai do flashcard
        summary_id = None
        fc_resp = (
            supabase.table('flashcards')
            .select('summary_id')
            .eq('id', flashcard_id)
            .single()
            .execute()
        )
        if fc_resp.data:
            summary_id = fc_resp.data.get('summary_id')

        # 3) Buscar a nota da revisão MAIS RECENTE do resumo para ESTE usuário
        summary_grade = None
        if summary_id:
            # Tabela de revisões de resumos costuma ser 'review_sessions'
            # (enquanto flashcards usam 'flashcard_review_sessions')
            rs_resp = (
                supabase.table('review_sessions')
                .select('difficulty_rating, reviewed_at')
                .eq('user_id', current_user['id'])
                .eq('summary_id', summary_id)
                .order('reviewed_at', desc=True)
                .limit(1)
                .execute()
            )
            if rs_resp.data:
                summary_grade = rs_resp.data[0].get('difficulty_rating')

        coupling_data = {"summaryGrade": summary_grade} if summary_grade is not None else None
        # ----------------------------------

        # 4) Chamar a NOVA função RPC v2 com o acoplamento
        calc_response = supabase.rpc('calculate_srs_update_v2', {
            'p_item_id': flashcard_id,
            'p_item_type': 'flashcard',
            'p_user_id': current_user['id'],
            'p_grade': difficulty_rating,
            'p_coupling_data': coupling_data  # passa a nota do resumo (se existir)
        }).execute()

        if not calc_response.data:
            return jsonify({'error': 'Erro ao calcular próxima revisão'}), 500

        next_review_data = calc_response.data[0]
        update_data = {
            'last_reviewed': datetime.now(timezone.utc).isoformat(),
            'next_review': next_review_data['next_review_date'],
            'review_count': current_review['review_count'] + 1,
            'difficulty_rating': difficulty_rating,
            'ease_factor': next_review_data['new_ease_factor'],
            'interval_days': next_review_data['new_interval'],
            'last_weight_multiplier': next_review_data.get('new_weight_multiplier'),
            # Mantém a mesma regra de conclusão já usada
            'is_completed': (6 - difficulty_rating) >= 4
        }

        update_response = (
            supabase.table('flashcard_review_sessions')
            .update(update_data)
            .eq('id', current_review['id'])
            .select('*')
            .execute()
        )

        if not update_response.data:
            return jsonify({'error': 'Erro ao atualizar revisão do flashcard'}), 400

        return jsonify({
            'message': 'Revisão de flashcard completada com sucesso',
            'review_session': update_response.data[0]
        }), 200

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500