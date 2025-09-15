# src/routes/images.py
from flask import Blueprint, request, jsonify
from src.utils.auth import require_auth, get_current_user
from src.config.database import get_supabase_client
import uuid

images_bp = Blueprint('images', __name__)

@images_bp.route('/register', methods=['POST'])
@require_auth
def register_image():
    """
    Registra os metadados de uma imagem após o upload do cliente para o Storage.
    """
    data = request.get_json()
    # ... (validação de campos)

    current_user = get_current_user()
    supabase = get_supabase_client()
# start changes
    try:
        image_data = {
            'id': str(uuid.uuid4()),
            'owner_id': current_user['id'],
            'entity_type': data['entity_type'],
            'entity_id': data['entity_id'],
            'storage_path': data['storage_path'],
            'content_hash': data['content_hash'],
            'width': data['width'],
            'height': data['height'],
            'size_bytes': data['size_bytes'],
            'caption': data.get('caption'),
            'position': data.get('position', 0),
            # ===============================================
            # ===            MUDANÇA AQUI                 === 
            # Usa o mime_type enviado pelo cliente, com fallback
            # ===============================================
            'mime_type': data.get('mime_type', 'image/jpeg') 
        }
        
        response = supabase.table('images').insert(image_data).execute()

        if response.data:
            return jsonify({'message': 'Imagem registrada com sucesso', 'image': response.data[0]}), 201
        else:
            return jsonify({'error': 'Falha ao registrar imagem no banco de dados', 'details': str(response.error)}), 500

    except Exception as e:
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500
    
# Rota para receber o upload da imagem vinda do Flutter
@images_bp.route('/upload', methods=['POST'])
@require_auth
def upload_image():
    """
    Recebe um arquivo de imagem do cliente e o envia para o Supabase Storage.
    """
    current_user = get_current_user()
    supabase = get_supabase_client()

    if 'image' not in request.files:
        return jsonify({'error': 'Nenhum arquivo de imagem enviado'}), 400
    
    file = request.files['image']
    storage_path = request.form.get('storage_path')

    if not storage_path:
        return jsonify({'error': 'O caminho de destino (storage_path) é obrigatório'}), 400

    try:
        file_bytes = file.read()
        
        # ======================================================================
        # ===                      A CORREÇÃO ESTÁ AQUI                      ===
        # Vamos definir explicitamente o 'content-type' para 'image/jpeg',
        # pois sabemos que o cliente sempre enviará este formato.
        # ======================================================================
        file_options = {'content-type': 'image/jpeg', 'upsert': 'true'}
        
        response = supabase.storage.from_('user-media').upload(
            path=storage_path,
            file=file_bytes,
            file_options=file_options # <-- Usando as opções definidas
        )
        
        return jsonify({'message': 'Upload realizado com sucesso'}), 200

    except Exception as e:
        # Adicionamos um log mais detalhado do erro real no console do Flask
        print(f"--- ERRO DETALHADO NO UPLOAD (FLASK -> SUPABASE) ---")
        print(f"Erro: {e}")
        print(f"Tipo do Erro: {type(e)}")
        print(f"----------------------------------------------------")
        return jsonify({'error': f'Erro interno ao fazer upload: {str(e)}'}), 500