# Caminho: src/utils/auth.py

from functools import wraps
from flask import request, jsonify
from src.config.database import get_supabase_client

def get_user_from_token(token: str):
    """
    Extrai informações do usuário do token JWT do Supabase
    """
    try:
        supabase = get_supabase_client()
        response = supabase.auth.get_user(token)
        
        if response.user:
            return {
                'id': str(response.user.id),
                'email': response.user.email,
                'user_metadata': response.user.user_metadata
            }
        return None
        
    except Exception as e:
        print(f"Erro ao validar token: {e}")
        return None

def require_auth(f):
    """
    Decorator para rotas que requerem autenticação
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Token de autorização necessário'}), 401
        
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({'error': 'Formato de token inválido'}), 401
        
        user = get_user_from_token(token)
        
        if not user:
            return jsonify({'error': 'Token inválido ou expirado'}), 401
        
        request.current_user = user
        
        return f(*args, **kwargs)
    
    return decorated_function

def get_current_user():
    """
    Obtém o usuário atual da requisição
    """
    return getattr(request, 'current_user', None)