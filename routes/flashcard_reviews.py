from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
import traceback

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
    
    print("\n--- 🏁 [DEBUG] Rota /api/flashcard-reviews/complete ACIONADA ---")
    
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        data = request.get_json()

        print(f"📌 [DEBUG] Payload recebido do App: {data}")

        flashcard_id = data.get('flashcard_id')
        difficulty_rating = data.get('difficulty_rating')

        if not flashcard_id or difficulty_rating is None:
            return jsonify({'error': 'flashcard_id e difficulty_rating são obrigatórios'}), 400

        # --- Etapa 1: Obter a sessão de revisão do flashcard ---
        print(f"🔍 [DEBUG] 1. Buscando sessão de revisão para o flashcard_id: {flashcard_id}")
        review_response = (
            supabase.table('flashcard_review_sessions')
            .select('*')
            .eq('user_id', current_user['id'])
            .eq('flashcard_id', flashcard_id)
            .limit(1)
            .execute()
        )

        if not review_response.data:
            print(f"❌ [DEBUG] ERRO: Sessão de revisão do flashcard não encontrada.")
            return jsonify({'error': 'Sessão de revisão do flashcard não encontrada'}), 404
        
        current_review = review_response.data[0]
        print(f"✅ [DEBUG] 1. Sessão de revisão encontrada.")

        # --- Etapa 2: Descobrir o resumo pai ---
        print(f"🔍 [DEBUG] 2. Buscando resumo pai para o flashcard.")
        summary_id = None
        fc_resp = ( supabase.table('flashcards').select('summary_id').eq('id', flashcard_id).single().execute() )
        if fc_resp.data and fc_resp.data.get('summary_id'):
            summary_id = fc_resp.data.get('summary_id')
            print(f"✅ [DEBUG] 2. Resumo pai encontrado. summary_id: {summary_id}")
        else:
            print("⚠️ [DEBUG] 2. Flashcard não está associado a um resumo pai.")

        # --- Etapa 3: Buscar a nota da revisão mais recente do resumo ---
        summary_grade = None
        if summary_id:
            print(f"🔍 [DEBUG] 3. Buscando nota da última revisão do resumo.")
            rs_resp = (
                supabase.table('review_sessions')
                .select('difficulty_rating, last_reviewed')
                .eq('user_id', current_user['id'])
                .eq('summary_id', summary_id)
                .order('last_reviewed', desc=True)
                .limit(1)
                .execute()
            )
            if rs_resp.data:
                summary_grade = rs_resp.data[0].get('difficulty_rating')
                print(f"✅ [DEBUG] 3. Nota do resumo encontrada: {summary_grade}")
            else:
                print("⚠️ [DEBUG] 3. Nenhuma revisão encontrada para o resumo pai.")
        
        coupling_data = {"summaryGrade": summary_grade} if summary_grade is not None else None
        print(f"🔩 [DEBUG] Dados de acoplamento preparados: {coupling_data}")

        # ==================== LÓGICA RESTAURADA ====================
        # --- Etapa 4: Chamar a função RPC para calcular a próxima revisão ---
        print(f"📞 [DEBUG] 4. Chamando RPC 'calculate_srs_update_v2' para o flashcard.")
        calc_response = supabase.rpc('calculate_srs_update_v2', {
            'p_item_id': flashcard_id,
            'p_item_type': 'flashcard',
            'p_user_id': current_user['id'],
            'p_grade': difficulty_rating,
            'p_coupling_data': coupling_data
        }).execute()

        # Adicione um log para ver a resposta da RPC
        print(f"📦 [DEBUG] Resposta completa da RPC: {calc_response.data}")

        if not calc_response.data:
            print(f"❌ [DEBUG] ERRO: RPC não retornou dados.")
            return jsonify({'error': 'Erro ao calcular próxima revisão'}), 500

        # ==================== CORREÇÃO APLICADA AQUI ====================
        # A resposta da RPC é um único objeto, não uma lista.
        # Removemos o acesso ao índice [0].
        next_review_data = calc_response.data
        # ================================================================
        print(f"✅ [DEBUG] 4. RPC executada com sucesso. Próxima revisão: {next_review_data}")

        # --- Etapa 5: Atualizar a sessão de revisão no banco de dados ---
        print(f"💾 [DEBUG] 5. Atualizando a sessão de revisão no banco de dados.")

        update_data = {
            'last_reviewed': datetime.now(timezone.utc).isoformat(),
            'next_review': next_review_data['next_review_date'],
            'review_count': current_review['review_count'] + 1,
            'difficulty_rating': difficulty_rating,
            'ease_factor': next_review_data['new_ease_factor'],
            'interval_days': next_review_data['new_interval'],
            'last_weight_multiplier': next_review_data.get('new_weight_multiplier'),
            'is_completed': (6 - difficulty_rating) >= 4
        }
        
        # ==================== CORREÇÃO APLICADA AQUI ====================
        # A sintaxe foi corrigida. O método .update() seguido de .execute()
        # já retorna os dados atualizados. O método .select() não deve ser
        # encadeado aqui.
        update_response = (
            supabase.table('flashcard_review_sessions')
            .update(update_data)
            .eq('id', current_review['id'])
            .execute()
        )
        # ================================================================

        if not update_response.data:
            print(f"❌ [DEBUG] ERRO: Falha ao atualizar a sessão de revisão no banco.")
            return jsonify({'error': 'Erro ao atualizar revisão do flashcard'}), 400
        
        print("✅ [DEBUG] 5. Sessão de revisão atualizada com sucesso.")
        print("--- ✅ [DEBUG] Rota concluída com sucesso. ---")

        return jsonify({
            'message': 'Revisão de flashcard completada com sucesso',
            'review_session': update_response.data[0]
        }), 200

    except Exception as e:
        print("\n💥💥💥 [DEBUG] UM ERRO CRÍTICO OCORREU! 💥💥💥")
        print(f"   Tipo do Erro: {type(e)}")
        print(f"   Mensagem: {e}")
        traceback.print_exc()
        print("--------------------------------------------------\n")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500