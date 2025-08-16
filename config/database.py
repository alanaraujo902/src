"""
Configuração do banco de dados Supabase
"""
from supabase import create_client, Client
from typing import Optional

def init_supabase(url: str, key: str) -> Optional[Client]:
    """
    Inicializa cliente Supabase
    
    Args:
        url: URL do projeto Supabase
        key: Chave de API do Supabase
        
    Returns:
        Cliente Supabase configurado
    """
    if not url or not key:
        raise ValueError("SUPABASE_URL e SUPABASE_KEY são obrigatórios")
    
    try:
        supabase: Client = create_client(url, key)
        return supabase
    except Exception as e:
        print(f"Erro ao conectar com Supabase: {e}")
        raise

def get_supabase_client() -> Client:
    """
    Obtém cliente Supabase da configuração da aplicação Flask
    """
    from flask import current_app
    return current_app.config['SUPABASE_CLIENT']

