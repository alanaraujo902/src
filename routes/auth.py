from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user

# Define o Blueprint para as rotas de autenticação
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Registrar novo usuário no Supabase."""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    supabase = get_supabase_client()
    try:
        res = supabase.auth.sign_up({
            "email": data['email'],
            "password": data['password'],
            "options": {
                "data": {
                    'full_name': data.get('full_name', '')
                }
            }
        })
        
        return jsonify({
            'message': 'Usuário registrado com sucesso. Verifique seu email para confirmação.',
            'user': res.user.dict() if res.user else None
        }), 201
    except Exception as e:
        print(f"ERRO DE REGISTRO: {e}") 
        return jsonify({'error': str(e)}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    """Fazer login do usuário com Supabase."""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email e senha são obrigatórios'}), 400

    supabase = get_supabase_client()
    try:
        res = supabase.auth.sign_in_with_password({
            "email": data['email'],
            "password": data['password']
        })
        return jsonify({
            'message': 'Login realizado com sucesso',
            'user': res.user.dict() if res.user else None,
            'access_token': res.session.access_token if res.session else None
        }), 200
    except Exception as e:
        print(f"ERRO DE REGISTRO: {e}")  # ADICIONE ESTA LINHA PARA VER O ERRO REAL NO TERMINAL
        return jsonify({'error': 'Credenciais inválidas'}), 401

@auth_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile():
    """Obter o perfil do usuário autenticado."""
    current_user = get_current_user()
    return jsonify({'user': current_user}), 200


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """Fazer logout do usuário invalidando o token no Supabase."""
    try:
        supabase = get_supabase_client()
        # A biblioteca do Supabase cuida da invalidação da sessão
        supabase.auth.sign_out()
        
        return jsonify({'message': 'Logout realizado com sucesso'}), 200
    except Exception as e:
        print(f"ERRO AO FAZER LOGOUT: {e}")
        return jsonify({'error': str(e)}), 400