# Arquivo: src/routes/flashcards.py

from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from src.config.gpt_service import get_gpt_service
import uuid
from datetime import datetime, timezone # Importar datetime

flashcards_bp = Blueprint('flashcards', __name__)

# --- ROTAS POST ---

@flashcards_bp.route('/generate-from-summary', methods=['POST'])
@require_auth
def generate_from_summary():
    """Gera flashcards a partir do conteúdo de um resumo existente."""
    data = request.get_json()
    summary_id = data.get('summary_id')

    if not summary_id:
        return jsonify({'error': 'summary_id é obrigatório'}), 400

    supabase = get_supabase_client()
    current_user = get_current_user()

    # Busca o conteúdo do resumo no banco
    summary_response = supabase.table('summaries').select('content').eq('id', summary_id).eq('user_id', current_user['id']).single().execute()
    
    if not summary_response.data:
        return jsonify({'error': 'Resumo não encontrado'}), 404
        
    summary_content = summary_response.data['content']

    try:
        # Chama o serviço do GPT para gerar os flashcards
        gpt_service = get_gpt_service()
        generated_flashcards = gpt_service.generate_flashcards_from_text(summary_content)
        
        return jsonify({'generated_flashcards': generated_flashcards}), 200

    except Exception as e:
        return jsonify({'error': f'Erro ao gerar flashcards: {str(e)}'}), 500



# --- ROTAS GET, PUT, DELETE ---

# ==========================================================
# ROTAS PARA DECKS DE FLASHCARDS (flashcard_decks)
# ==========================================================

@flashcards_bp.route('/decks', methods=['GET'])
@require_auth
def get_flashcard_decks():
    """Listar todos os decks de flashcards do usuário com contagem de flashcards."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        response = supabase.table('flashcard_decks').select('*, flashcards(id, count)').eq('user_id', current_user['id']).is_('deleted_at', None).execute()
        
        decks = []
        if response.data:
            for deck_data in response.data:
                deck_data['flashcards_count'] = deck_data['flashcards'][0]['count'] if deck_data.get('flashcards') else 0
                del deck_data['flashcards']
                decks.append(deck_data)
        
        return jsonify({'decks': decks}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@flashcards_bp.route('/decks/<deck_id>', methods=['GET'])
@require_auth
def get_flashcard_deck_details(deck_id):
    """Obter os detalhes de um deck específico, incluindo todos os seus flashcards."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        response = supabase.table('flashcard_decks').select('*, flashcards(*)').eq('id', deck_id).eq('user_id', current_user['id']).is_('deleted_at', None).single().execute()
        
        if not response.data:
            return jsonify({'error': 'Deck não encontrado'}), 404
            
        return jsonify({'deck': response.data}), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@flashcards_bp.route('/decks/<deck_id>', methods=['PUT'])
@require_auth
def update_flashcard_deck(deck_id):
    """Atualizar o nome ou descrição de um deck de flashcards."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados não fornecidos'}), 400

    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        allowed_fields = ['name', 'description']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            return jsonify({'error': 'Nenhum campo válido para atualização'}), 400
        
        response = supabase.table('flashcard_decks').update(update_data).eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if response.data:
            return jsonify({'message': 'Deck atualizado com sucesso', 'deck': response.data[0]}), 200
        else:
            return jsonify({'error': 'Deck não encontrado ou erro ao atualizar'}), 404

    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@flashcards_bp.route('/decks/<deck_id>', methods=['DELETE'])
@require_auth
def delete_flashcard_deck(deck_id):
    """Realiza o soft delete de um deck e de todos os flashcards contidos nele."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        now_ts = datetime.now(timezone.utc).isoformat()

        supabase.table('flashcards').update({'deleted_at': now_ts}).eq('deck_id', deck_id).eq('user_id', current_user['id']).execute()

        response = supabase.table('flashcard_decks').update({'deleted_at': now_ts}).eq('id', deck_id).eq('user_id', current_user['id']).execute()
        
        if response.data:
            return jsonify({'message': 'Deck e seus flashcards foram movidos para a lixeira'}), 200
        else:
            return jsonify({'error': 'Deck não encontrado'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

# ==========================================================
# ROTAS PARA FLASHCARDS INDIVIDUAIS (flashcards)
# ==========================================================

@flashcards_bp.route('/batch-create', methods=['POST'])
@require_auth
def batch_create_flashcards():
    """Cria múltiplos flashcards e o deck correspondente, se necessário."""
    data = request.get_json()
    flashcards_to_create = data.get('flashcards')
    subject_id = data.get('subject_id')
    summary_id = data.get('summary_id')

    print("--- INICIANDO /batch-create ---")
    print(f"Subject ID recebido: {subject_id}")
    print(f"Total de flashcards recebidos: {len(flashcards_to_create) if flashcards_to_create else 0}")

    if not all([flashcards_to_create, subject_id]):
        return jsonify({'error': 'Dados incompletos'}), 400
        
    if not isinstance(flashcards_to_create, list) or len(flashcards_to_create) == 0:
        return jsonify({'message': 'Nenhum flashcard para salvar.'}), 200

    supabase = get_supabase_client()
    current_user = get_current_user()
    
    try:
        # LOG 1: Verificando a resposta da busca pela matéria
        print("--- LOG 1: Buscando matéria ---")
        subject_response = supabase.table('subjects').select('name').eq('id', subject_id).eq('user_id', current_user['id']).maybe_single().execute()
        print(f"Subject Response: {subject_response}")
        
        if not subject_response or not subject_response.data:
            return jsonify({'error': 'Matéria de destino não encontrada (ou falha na busca).'}), 404
        
        subject_name = subject_response.data['name']
        print(f"--- LOG 1.1: Nome da matéria encontrado: {subject_name} ---")

        # LOG 2: Verificando a resposta da busca pelo deck de flashcards
        print("\n--- LOG 2: Buscando deck de flashcards existente ---")
        deck_response = supabase.table('flashcard_decks').select('id').eq('subject_id', subject_id).eq('user_id', current_user['id']).maybe_single().execute()
        print(f"Deck Response: {deck_response}")
        
        if deck_response and deck_response.data:
            deck_id = deck_response.data['id']
            print(f"--- LOG 2.1: Deck existente encontrado. ID: {deck_id} ---")
        else:
            print("\n--- LOG 3: Deck não encontrado, criando um novo ---")
            new_deck_data = {
                'id': str(uuid.uuid4()),
                'user_id': current_user['id'],
                'subject_id': subject_id,
                'name': subject_name
            }
            insert_response = supabase.table('flashcard_decks').upsert(new_deck_data).execute()
            print(f"Insert Deck Response: {insert_response}")

            if not insert_response or not insert_response.data:
                # Este é o local mais provável do erro se a política RLS estiver incorreta
                raise Exception("Falha ao criar o deck de flashcards. A resposta do upsert não retornou dados.")

            deck_id = insert_response.data[0]['id']
            print(f"--- LOG 3.1: Novo deck criado. ID: {deck_id} ---")

        flashcards_data = [
            {
                'id': str(uuid.uuid4()),
                'user_id': current_user['id'],
                'deck_id': deck_id,
                'summary_id': summary_id,
                'question': fc['question'],
                'answer': fc['answer']
            } for fc in flashcards_to_create
        ]
        
        # LOG 4: Verificando a resposta da inserção dos flashcards
        print("\n--- LOG 4: Inserindo flashcards em lote ---")
        insert_flashcards_response = supabase.table('flashcards').upsert(flashcards_data).execute()
        print(f"Insert Flashcards Response: {insert_flashcards_response}")
        
        # Verificação de segurança final
        if not insert_flashcards_response or not insert_flashcards_response.data:
             raise Exception("A operação de salvar os flashcards não retornou dados. Verifique as permissões (RLS) da tabela 'flashcards'.")

        print("--- FINALIZADO COM SUCESSO ---")
        return jsonify({'message': f'{len(flashcards_data)} flashcards foram enviados para salvamento.'}), 201

    except Exception as e:
        print(f"!!! ERRO INESPERADO EM /batch-create: {str(e)}")
        # Imprime o traceback completo no console do Flask para depuração detalhada
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao salvar flashcards: {str(e)}'}), 500