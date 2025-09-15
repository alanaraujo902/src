# Arquivo: src/routes/gpt_utils.py CORRIGIDO

from flask import Blueprint, request, jsonify
from src.utils.auth import require_auth
from src.config.gpt_service import get_gpt_service

gpt_utils_bp = Blueprint('gpt_utils', __name__)

@gpt_utils_bp.route('/summarize-text', methods=['POST'])
@require_auth
def summarize_text_from_input():
    """Gera um resumo a partir de um texto fornecido pelo usuário."""
    data = request.get_json()
    text_content = data.get('text')
    
    # ==================== ADICIONE ESTA LINHA ====================
    prompt_style = data.get('prompt_style', 'default')
    # ===============================================================

    if not text_content:
        return jsonify({'error': 'O campo "text" é obrigatório'}), 400

    try:
        gpt_service = get_gpt_service()
        # ==================== MODIFIQUE ESTA LINHA ====================
        generated_summary = gpt_service.summarize_text(text_content, prompt_style=prompt_style)
        # ================================================================
        return jsonify({'summary_content': generated_summary}), 200
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar resumo: {str(e)}'}), 500