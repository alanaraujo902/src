"""
Rotas para estatísticas de estudo
"""
from flask import Blueprint, request, jsonify
from src.config.database import get_supabase_client
from src.utils.auth import require_auth, get_current_user
from datetime import datetime, timedelta

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/overview', methods=['GET'])
@require_auth
def get_overview_stats():

    """Obter estatísticas gerais do usuário"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Usar função do banco para obter estatísticas
        days_back = int(request.args.get('days', 30))
        
        stats_response = supabase.rpc('get_user_study_stats', {
            'user_uuid': current_user['id'],
            'days_back': days_back
        }).execute()
        
        if stats_response.data:
            stats = stats_response.data[0]
        else:
            stats = {
                'total_summaries': 0,
                'total_reviews': 0,
                'total_study_time': 0,
                'avg_daily_summaries': 0,
                'avg_daily_reviews': 0,
                'streak_days': 0,
                'subjects_count': 0
            }
        
        # Estatísticas adicionais
        today = datetime.now().date()
        
        # Atividade de hoje
        today_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).eq('date', today.isoformat()).execute()
        
        today_data = today_stats.data[0] if today_stats.data else {
            'summaries_created': 0,
            'summaries_reviewed': 0,
            'total_study_time_ms': 0
        }
        
        # Revisões pendentes
        pending_reviews = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).lte('next_review', 'now()').eq('is_completed', False).execute()
        
        pending_count = pending_reviews.count if pending_reviews.count else 0
        
        return jsonify({
            'period_stats': {
                'days_analyzed': days_back,
                'total_summaries': stats['total_summaries'],
                'total_reviews': stats['total_reviews'],
                'total_study_time_ms': stats['total_study_time_ms'],
                'avg_daily_summaries': float(stats['avg_daily_summaries']),
                'avg_daily_reviews': float(stats['avg_daily_reviews']),
                'subjects_count': stats['subjects_count']
            },
            'today_stats': {
                'summaries_created': today_data['summaries_created'],
                'summaries_reviewed': today_data['summaries_reviewed'],
                'study_time_ms': today_data['total_study_time_ms']  # Alterado de _minutes para _ms
            },
            'streak_days': stats['streak_days'],
            'pending_reviews': pending_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500





@statistics_bp.route('/daily', methods=['GET'])
@require_auth
def get_daily_stats():
    """Obter estatísticas diárias"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Parâmetros
        days_back = int(request.args.get('days', 30))
        start_date = (datetime.now() - timedelta(days=days_back)).date()
        
        # Buscar estatísticas diárias
        response = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).gte('date', start_date.isoformat()).order('date').execute()
        
        daily_stats = response.data if response.data else []
        
        # Preencher dias sem dados
        all_days = []
        current_date = start_date
        end_date = datetime.now().date()
        
        stats_dict = {stat['date']: stat for stat in daily_stats}
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            if date_str in stats_dict:
                day_data = stats_dict[date_str]
            else:
                day_data = {
                    'date': date_str,
                    'summaries_created': 0,
                    'summaries_reviewed': 0,
                    'total_study_time_minutes': 0,
                    'subjects_studied': []
                }
            
            all_days.append(day_data)
            current_date += timedelta(days=1)
        
        return jsonify({
            'daily_stats': all_days,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days_count': len(all_days)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@statistics_bp.route('/subjects', methods=['GET'])
@require_auth
def get_subjects_stats():
    """Obter estatísticas por matéria"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Estatísticas de resumos por matéria
        summaries_stats = supabase.table('summaries').select('''
            subject_id,
            subjects(name, color, hierarchy_path),
            count
        ''', count='exact').eq('user_id', current_user['id']).execute()
        
        # Agrupar por matéria
        subjects_data = {}
        
        # Buscar todas as matérias do usuário
        subjects_response = supabase.table('subjects').select('*').eq('user_id', current_user['id']).execute()
        
        for subject in subjects_response.data or []:
            subjects_data[subject['id']] = {
                'subject': subject,
                'summaries_count': 0,
                'reviews_completed': 0,
                'avg_difficulty': 0,
                'last_activity': None
            }
        
        # Contar resumos por matéria
        summaries_count = supabase.table('summaries').select('subject_id', count='exact').eq('user_id', current_user['id']).execute()
        
        for subject_id in subjects_data.keys():
            count_response = supabase.table('summaries').select('id', count='exact').eq('user_id', current_user['id']).eq('subject_id', subject_id).execute()
            
            subjects_data[subject_id]['summaries_count'] = count_response.count or 0
            
            # Estatísticas de revisão
            reviews_response = supabase.table('review_sessions').select('difficulty_rating, last_reviewed').eq('user_id', current_user['id']).in_('summary_id', 
                supabase.table('summaries').select('id').eq('subject_id', subject_id).eq('user_id', current_user['id'])
            ).execute()
            
            if reviews_response.data:
                reviews = reviews_response.data
                subjects_data[subject_id]['reviews_completed'] = len(reviews)
                
                # Dificuldade média
                if reviews:
                    avg_diff = sum(r['difficulty_rating'] for r in reviews if r['difficulty_rating']) / len(reviews)
                    subjects_data[subject_id]['avg_difficulty'] = round(avg_diff, 2)
                
                # Última atividade
                last_reviews = [r['last_reviewed'] for r in reviews if r['last_reviewed']]
                if last_reviews:
                    subjects_data[subject_id]['last_activity'] = max(last_reviews)
        
        # Converter para lista
        subjects_stats = list(subjects_data.values())
        
        # Ordenar por número de resumos (decrescente)
        subjects_stats.sort(key=lambda x: x['summaries_count'], reverse=True)
        
        return jsonify({
            'subjects_stats': subjects_stats,
            'total_subjects': len(subjects_stats)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@statistics_bp.route('/performance', methods=['GET'])
@require_auth
def get_performance_stats():
    """Obter estatísticas de performance"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Estatísticas de dificuldade
        difficulty_stats = {}
        for level in range(1, 6):
            count_response = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).eq('difficulty_rating', level).execute()
            
            difficulty_stats[f'level_{level}'] = count_response.count or 0
        
        # Taxa de conclusão
        total_reviews = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).execute()
        completed_reviews = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).eq('is_completed', True).execute()
        
        total_count = total_reviews.count or 0
        completed_count = completed_reviews.count or 0
        completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0
        
        # Evolução da dificuldade ao longo do tempo
        recent_reviews = supabase.table('review_sessions').select('difficulty_rating, last_reviewed').eq('user_id', current_user['id']).gte('last_reviewed', (datetime.now() - timedelta(days=30)).isoformat()).order('last_reviewed').execute()
        
        difficulty_evolution = []
        if recent_reviews.data:
            for review in recent_reviews.data:
                if review['last_reviewed'] and review['difficulty_rating']:
                    difficulty_evolution.append({
                        'date': review['last_reviewed'][:10],  # Apenas a data
                        'difficulty': review['difficulty_rating']
                    })
        
        # Tempo médio de estudo por dia
        study_time_response = supabase.table('study_statistics').select('total_study_time_minutes').eq('user_id', current_user['id']).gte('date', (datetime.now() - timedelta(days=30)).date().isoformat()).execute()
        
        total_study_time = sum(stat['total_study_time_minutes'] for stat in study_time_response.data or [])
        avg_daily_study_time = total_study_time / 30 if study_time_response.data else 0
        
        return jsonify({
            'difficulty_distribution': difficulty_stats,
            'completion_rate': round(completion_rate, 2),
            'total_reviews': total_count,
            'completed_reviews': completed_count,
            'difficulty_evolution': difficulty_evolution,
            'avg_daily_study_time_minutes': round(avg_daily_study_time, 2),
            'total_study_time_last_30_days': total_study_time
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@statistics_bp.route('/goals', methods=['GET'])
@require_auth
def get_goals_progress():
    """Obter progresso das metas"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        # Metas padrão (podem ser personalizáveis no futuro)
        daily_goals = {
            'summaries_created': 3,
            'summaries_reviewed': 5,
            'study_time_minutes': 60
        }
        
        weekly_goals = {
            'summaries_created': 15,
            'summaries_reviewed': 25,
            'study_time_minutes': 300
        }
        
        # Progresso de hoje
        today = datetime.now().date()
        today_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).eq('date', today.isoformat()).execute()
        
        today_data = today_stats.data[0] if today_stats.data else {
            'summaries_created': 0,
            'summaries_reviewed': 0,
            'total_study_time_minutes': 0
        }
        
        # Progresso da semana
        week_start = today - timedelta(days=today.weekday())
        week_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).gte('date', week_start.isoformat()).execute()
        
        week_totals = {
            'summaries_created': sum(stat['summaries_created'] for stat in week_stats.data or []),
            'summaries_reviewed': sum(stat['summaries_reviewed'] for stat in week_stats.data or []),
            'study_time_minutes': sum(stat['total_study_time_minutes'] for stat in week_stats.data or [])
        }
        
        # Calcular progresso
        daily_progress = {}
        weekly_progress = {}
        
        for key in daily_goals:
            daily_progress[key] = {
                'current': today_data.get(key.replace('study_time_minutes', 'total_study_time_minutes'), 0),
                'goal': daily_goals[key],
                'percentage': min(100, (today_data.get(key.replace('study_time_minutes', 'total_study_time_minutes'), 0) / daily_goals[key] * 100))
            }
            
            weekly_progress[key] = {
                'current': week_totals[key],
                'goal': weekly_goals[key],
                'percentage': min(100, (week_totals[key] / weekly_goals[key] * 100))
            }
        
        return jsonify({
            'daily_goals': {
                'date': today.isoformat(),
                'goals': daily_goals,
                'progress': daily_progress
            },
            'weekly_goals': {
                'week_start': week_start.isoformat(),
                'week_end': (week_start + timedelta(days=6)).isoformat(),
                'goals': weekly_goals,
                'progress': weekly_progress
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

# No final de src/routes/statistics.py

@statistics_bp.route('/log-session', methods=['POST'])
@require_auth
def log_study_session():
    """Registra o tempo de uma sessão de estudo."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        study_time_ms = data.get('study_time_ms', 0) # Espera milissegundos
        
        if study_time_ms <= 0:
            return jsonify({'message': 'Nenhum tempo de estudo para registrar'}), 200

        supabase = get_supabase_client()
        
        # Chama a função RPC atualizada no Supabase
        supabase.rpc('update_study_statistics', {
            'user_uuid': current_user['id'],
            'total_study_time_ms_add': study_time_ms
        }).execute()

        return jsonify({'message': 'Sessão de estudo registrada com sucesso'}), 200

    except Exception as e:
        print(f"ERRO AO REGISTRAR SESSÃO DE ESTUDO: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500