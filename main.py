# src/main.py

import os
import sys
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Carregar variáveis de ambiente
load_dotenv()

# --- 1. CRIAR E CONFIGURAR O APP FLASK ---
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configurações
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SUPABASE_URL'] = os.getenv('SUPABASE_URL')
app.config['SUPABASE_KEY'] = os.getenv('SUPABASE_KEY')
app.config['PERPLEXITY_API_KEY'] = os.getenv('PERPLEXITY_API_KEY')
app.config['GPT_API_KEY'] = os.getenv('GPT_API_KEY')

# Habilitar CORS
CORS(app, origins="*")

# Inicializar Supabase
from src.config.database import init_supabase
supabase = init_supabase(app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
app.config['SUPABASE_CLIENT'] = supabase

# ==================== INÍCIO DA CORREÇÃO ESTRUTURAL ====================

# --- 2. REGISTRAR OS BLUEPRINTS DA API ---
# A função `register_blueprints` agora irá registrar todas as suas rotas
# que começam com /api/
from src.routes import register_blueprints
register_blueprints(app)


# --- 3. ROTA "CATCH-ALL" PARA SERVIR O FRONTEND (WEB APP) ---
# Esta rota serve o index.html para qualquer caminho que NÃO seja uma rota da API já definida.
# Como ela é definida DEPOIS dos blueprints da API, o Flask sempre tentará
# corresponder às rotas da API primeiro.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_folder = app.static_folder
    
    # Se o caminho solicitado existir na pasta de arquivos estáticos, sirva-o.
    if path != "" and os.path.exists(os.path.join(static_folder, path)):
        return send_from_directory(static_folder, path)
    else:
        # Caso contrário, sirva o index.html (para o roteamento do lado do cliente funcionar).
        return send_from_directory(static_folder, 'index.html')

# ==================== FIM DA CORREÇÃO ESTRUTURAL ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)