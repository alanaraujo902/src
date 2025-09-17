# src/routes/images.py
from flask import Blueprint, request, jsonify
from src.utils.auth import require_auth, get_current_user
from src.config.database import get_supabase_client
import uuid
from PIL import Image  # <-- Garanta que esta linha importe 'Image' com 'I' maiúsculo
import io

images_bp = Blueprint('images', __name__)

# Função auxiliar para redimensionar e converter a imagem
def create_image_variant(image_bytes, max_size):
    # Usa a classe Image importada
    img = Image.open(io.BytesIO(image_bytes))
    
    # Preserva a orientação da imagem se houver dados EXIF
    if hasattr(img, '_getexif'):
        exif = img._getexif()
        if exif:
            orientation = exif.get(274) # 274 é a tag EXIF para orientação
            if orientation == 3: img = img.rotate(180, expand=True)
            elif orientation == 6: img = img.rotate(270, expand=True)
            elif orientation == 8: img = img.rotate(90, expand=True)

    img.thumbnail((max_size, max_size))
    
    byte_arr = io.BytesIO()
    # Converte para RGB antes de salvar como JPEG para evitar problemas com paletas de cores (ex: PNGs)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
        
    img.save(byte_arr, format='JPEG', quality=85)
    return byte_arr.getvalue()

@images_bp.route('/upload', methods=['POST'])
@require_auth
def upload_image():
    """
    Recebe UMA imagem original do cliente, gera as variantes no servidor
    e faz o upload de todas para o Supabase Storage.
    """
    supabase = get_supabase_client()

    if 'image' not in request.files:
        return jsonify({'error': 'Nenhum arquivo de imagem enviado'}), 400
    
    file = request.files['image']
    storage_path_prefix = request.form.get('storage_path_prefix')

    if not storage_path_prefix:
        return jsonify({'error': 'O prefixo do caminho (storage_path_prefix) é obrigatório'}), 400

    try:
        original_bytes = file.read()

        variants = {
            'orig': create_image_variant(original_bytes, 2048),
            'large': create_image_variant(original_bytes, 1024),
            'thumb': create_image_variant(original_bytes, 256),
        }
        
        for name, data in variants.items():
            full_path = f"{storage_path_prefix}/{name}.jpg"
            supabase.storage.from_('user-media').upload(
                path=full_path,
                file=data,
                file_options={'content-type': 'image/jpeg', 'upsert': 'true'}
            )
            
        return jsonify({'message': 'Upload de todas as variantes concluído com sucesso'}), 200

    except Exception as e:
        print(f"--- ERRO DETALHADO NO UPLOAD (FLASK -> SUPABASE) ---")
        print(f"Erro: {e}")
        print(f"Tipo do Erro: {type(e)}")
        print(f"----------------------------------------------------")
        return jsonify({'error': f'Erro interno ao fazer upload: {str(e)}'}), 500


@images_bp.route('/register', methods=['POST'])
@require_auth
def register_image():
    data = request.get_json()
    required_fields = ['entity_type', 'entity_id', 'storage_path_prefix', 'content_hash', 'width', 'height', 'size_bytes']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Dados insuficientes para registrar a imagem'}), 400

    current_user = get_current_user()
    supabase = get_supabase_client()

    try:
        image_data = {
            'id': str(uuid.uuid4()),
            'owner_id': current_user['id'],
            'entity_type': data['entity_type'],
            'entity_id': data['entity_id'],
            'storage_path': data['storage_path_prefix'],
            'content_hash': data['content_hash'],
            'width': data['width'],
            'height': data['height'],
            'size_bytes': data['size_bytes'],
            'caption': data.get('caption'),
            'position': data.get('position', 0),
            'mime_type': data.get('mime_type', 'image/jpeg')
        }
        
        response = supabase.table('images').insert(image_data).execute()

        if response.data:
            return jsonify({'message': 'Imagem registrada com sucesso', 'image': response.data[0]}), 201
        else:
            return jsonify({'error': 'Falha ao registrar imagem no banco de dados', 'details': str(response.error)}), 500

    except Exception as e:
        return jsonify({'error': f'Erro interno do servidor: {str(e)}'}), 500