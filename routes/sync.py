"""
Rotas para sincronização de dados offline-first.
"""
import re
import json
from flask import Blueprint, request, jsonify, Response

from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from datetime import datetime, timezone # <-- Certifique-se de que timezone está importado
from datetime import date, datetime



sync_bp = Blueprint('sync', __name__)

def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

# --- INÍCIO DA NOVA LÓGICA DE CONVERSÃO CORRIGIDA ---
def convert_value(value):
    """Tenta converter um valor de timestamp em milissegundos para string ISO 8601."""
    # Verifica se o valor é um inteiro ou float e se parece um timestamp em ms (maior que o ano 2001)
    if isinstance(value, (int, float)) and value > 1000000000000:
        try:
            # Converte de milissegundos para segundos, cria o objeto datetime com fuso horário UTC
            # e formata para a string ISO 8601 que o Supabase/PostgreSQL entende.
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
        except (ValueError, TypeError):
            # Se a conversão falhar por qualquer motivo, retorna o valor original sem quebrar.
            return value
    return value

def convert_payload(data):
    """
    Converte recursivamente as chaves do payload para snake_case e os
    valores de timestamp em milissegundos para strings ISO 8601.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_key = camel_to_snake(k)
            # A conversão de valor é aplicada dentro da chamada recursiva
            new_value = convert_payload(v)
            new_dict[new_key] = new_value
        return new_dict
    if isinstance(data, list):
        return [convert_payload(i) for i in data]
    
    # Aplica a conversão de valor para itens que não são dicionários ou listas
    return convert_value(data)
# --- FIM DA NOVA LÓGICA DE CONVERSÃO CORRIGIDA ---


sync_bp = Blueprint('sync', __name__)

def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

# --- INÍCIO DA NOVA LÓGICA DE CONVERSÃO CORRIGIDA ---
def convert_value(value):
    """Tenta converter um valor de timestamp em milissegundos para string ISO 8601."""
    if isinstance(value, (int, float)) and value > 1000000000000:
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
        except (ValueError, TypeError):
            return value
    return value

def convert_payload(data):
    """
    Converte recursivamente as chaves do payload para snake_case e os
    valores de timestamp em milissegundos para strings ISO 8601.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_key = camel_to_snake(k)
            new_value = convert_payload(v)
            new_dict[new_key] = new_value
        return new_dict
    if isinstance(data, list):
        return [convert_payload(i) for i in data]
    
    return convert_value(data)
# --- FIM DA NOVA LÓGICA DE CONVERSÃO CORRIGIDA ---


@sync_bp.route('/batch', methods=['POST'])
@require_auth
def sync_batch_changes():
    """
    Processa um lote de mudanças vindas do cliente (offline-first).
    """
    try:
        changes = request.get_json()
        if not isinstance(changes, list):
            return jsonify({'error': 'O corpo da requisição deve ser uma lista'}), 400

        supabase = get_supabase_client()
        current_user = get_current_user()
        results = []

        print(f"\n--- [SYNC] Iniciando /batch para o usuário: {current_user['id']} ---")
        print(f"--- [SYNC] Recebidas {len(changes)} alterações.")

        for change in changes:
            table_name = change.get('table')
            operation = change.get('op')
            payload_from_client = change.get('payload')

            if not all([table_name, operation, payload_from_client]):
                results.append({
                    'row_id': change.get('row_id'),
                    'status': 'failed',
                    'error': 'Dados incompletos'
                })
                continue

            try:
                converted_payload = convert_payload(payload_from_client)
                
                # --- INÍCIO DA CORREÇÃO ---
                # Adiciona o user_id apenas se a tabela não for uma tabela de junção
                # que não possui essa coluna diretamente.
                if table_name not in ['deck_summaries', 'study_statistics']:
                    converted_payload['user_id'] = current_user['id']
                # --- FIM DA CORREÇÃO ---

                if table_name not in ['study_logs', 'study_statistics']:
                    converted_payload['updated_at'] = datetime.now(timezone.utc).isoformat()

                print(f"--- [SYNC] Processando: op={operation}, table={table_name}")
                print(f"--- [SYNC] PAYLOAD FINAL PARA SUPABASE: {converted_payload}")

                if operation == 'upsert':
                    if table_name == 'study_statistics':
                        rpc_params = {
                            'user_uuid': current_user['id'],
                            'summaries_created_count': converted_payload.get('summaries_created', 0),
                            'summaries_reviewed_count': converted_payload.get('summaries_reviewed', 0),
                            'total_study_time_ms_add': converted_payload.get('total_study_time_ms', 0),
                        }
                        response = supabase.rpc('update_study_statistics', rpc_params).execute()

                        if hasattr(response, 'error') and response.error is not None:
                            print(f"--- [SYNC] !!! ERRO SUPABASE (RPC): {response.error.message}")
                            results.append({
                                'row_id': change.get('row_id'),
                                'status': 'failed',
                                'error': response.error.message
                            })
                        else:
                            print(f"--- [SYNC] SUCESSO (RPC).")
                            results.append({'row_id': change.get('row_id'), 'status': 'success'})

                    else:
                        response = supabase.table(table_name).upsert(converted_payload).execute()

                        if hasattr(response, 'error') and response.error is not None:
                            print(f"--- [SYNC] !!! ERRO SUPABASE: {response.error.message}")
                            results.append({
                                'row_id': change.get('row_id'),
                                'status': 'failed',
                                'error': response.error.message
                            })
                        elif not getattr(response, 'data', None):
                            print(f"--- [SYNC] !!! AVISO: Operação sem retorno de dados. Possível falha de RLS.")
                            results.append({
                                'row_id': change.get('row_id'),
                                'status': 'failed',
                                'error': 'Falha ao gravar, verifique as permissões (RLS).'
                            })
                        else:
                            print(f"--- [SYNC] SUCESSO. Resposta: {response.data}")
                            results.append({'row_id': change.get('row_id'), 'status': 'success'})

                else:
                    results.append({
                        'row_id': change.get('row_id'),
                        'status': 'skipped',
                        'error': f'Operação "{operation}" não suportada'
                    })

            except Exception as e:
                print(f"--- [SYNC] !!! EXCEÇÃO PYTHON: {e}")
                results.append({
                    'row_id': change.get('row_id'),
                    'status': 'failed',
                    'error': str(e)
                })

        print("--- [SYNC] Fim do processamento /batch ---\n")
        return jsonify({'message': 'Lote processado', 'results': results}), 200

    except Exception as e:
        print(f"ERRO CRÍTICO NO /api/sync/batch: {e}")
        return jsonify({'error': f'Erro interno do servidor: {e}'}), 500

# O endpoint /delta permanece o mesmo
@sync_bp.route('/delta/<string:table_name>', methods=['GET'])
@require_auth
def sync_delta_changes(table_name):
    try:
        since_timestamp = request.args.get('since')
        # --- INÍCIO DA MODIFICAÇÃO 1 ---
        # Obter parâmetros de paginação da requisição, com valores padrão
        limit = int(request.args.get('limit', 100)) # Padrão de 100 por página
        offset = int(request.args.get('offset', 0))
        # --- FIM DA MODIFICAÇÃO 1 ---
        
        current_user = get_current_user()
        supabase = get_supabase_client()

        allowed_tables = [
            'subjects', 'summaries', 'review_sessions', 'study_decks', 
            'deck_summaries', 'study_statistics', 'flashcard_decks', 'flashcards'
        ]
        
        if table_name not in allowed_tables:
            return jsonify({'error': f'Tabela "{table_name}" não permitida'}), 400
        
        if table_name == 'deck_summaries':
            # A query para tabelas de junção precisa de um join para filtrar pelo user_id
            query = supabase.table(table_name).select('*, study_decks!inner(user_id)') \
                .eq('study_decks.user_id', current_user['id'])
        else:
            query = supabase.table(table_name).select('*').eq('user_id', current_user['id'])
        
        if since_timestamp:
            query = query.gte('updated_at', since_timestamp)

        # --- INÍCIO DA MODIFICAÇÃO 2 ---
        # Aplicar paginação à consulta do Supabase
        query = query.range(offset, offset + limit - 1)
        # --- FIM DA MODIFICAÇÃO 2 ---

        response = query.execute()
        items = response.data if response.data else []
        
        server_now = datetime.now(timezone.utc).isoformat()
        payload = {
            'items': items,
            'server_timestamp': server_now
        }
        json_response = json.dumps(payload, default=json_converter)
        return Response(json_response, mimetype='application/json')

    except Exception as e:
        print(f"ERRO CRÍTICO NO /api/sync/delta/{table_name}: {e}")
        return jsonify({'error': f'Erro interno do servidor: {e}'}), 500

    


# Crie esta função auxiliar para lidar com a conversão
# Você pode colocá-la logo abaixo das importações
def json_converter(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    # Adicione outras conversões aqui se necessário (ex: para UUID)
    # if isinstance(o, uuid.UUID):
    #     return str(o)
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")