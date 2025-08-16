import os
import sys
from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask, send_from_directory

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

# Habilitar CORS
CORS(app, origins="*")

# Inicializar Supabase
from src.config.database import init_supabase
supabase = init_supabase(app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
app.config['SUPABASE_CLIENT'] = supabase

# --- 2. IMPORTAR E REGISTRAR OS BLUEPRINTS DE FORMA CENTRALIZADA ---
from src.routes import register_blueprints
register_blueprints(app)

# --- 3. ROTAS ESTÁTICAS E DE INICIALIZAÇÃO ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if not static_folder_path:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)