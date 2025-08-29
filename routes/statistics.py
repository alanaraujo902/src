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
                'total_study_time_ms': 0,
                'avg_daily_summaries': 0,
                'avg_daily_reviews': 0,
                'streak_days': 0,
                'subjects_count': 0
            }
        
        today = datetime.now().date()
        today_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).eq('date', today.isoformat()).execute()
        
        today_data = today_stats.data[0] if today_stats.data else {
            'summaries_created': 0,
            'summaries_reviewed': 0,
            'total_study_time_ms': 0
        }
        
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
                # CORREÇÃO: Padronizado para 'study_time_ms' para corresponder ao modelo do Flutter
                'study_time_ms': today_data['total_study_time_ms']
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
        
        days_back = int(request.args.get('days', 30))
        start_date = (datetime.now() - timedelta(days=days_back)).date()
        
        response = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).gte('date', start_date.isoformat()).order('date').execute()
        
        daily_stats = response.data if response.data else []
        
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
                    # CORREÇÃO: Alterado de 'total_study_time_minutes' para 'total_study_time_ms'
                    'total_study_time_ms': 0,
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

@statistics_bp.route('/performance', methods=['GET'])
@require_auth
def get_performance_stats():
    """Obter estatísticas de performance"""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        difficulty_stats = {}
        for level in range(1, 6):
            count_response = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).eq('difficulty_rating', level).execute()
            difficulty_stats[f'level_{level}'] = count_response.count or 0
        
        total_reviews = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).execute()
        completed_reviews = supabase.table('review_sessions').select('id', count='exact').eq('user_id', current_user['id']).eq('is_completed', True).execute()
        
        total_count = total_reviews.count or 0
        completed_count = completed_reviews.count or 0
        completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0
        
        recent_reviews = supabase.table('review_sessions').select('difficulty_rating, last_reviewed').eq('user_id', current_user['id']).gte('last_reviewed', (datetime.now() - timedelta(days=30)).isoformat()).order('last_reviewed').execute()
        
        difficulty_evolution = []
        if recent_reviews.data:
            for review in recent_reviews.data:
                if review['last_reviewed'] and review['difficulty_rating']:
                    difficulty_evolution.append({
                        'date': review['last_reviewed'][:10],
                        'difficulty': review['difficulty_rating']
                    })
        
        # CORREÇÃO PRINCIPAL: Alterado para consultar 'total_study_time_ms'
        study_time_response = supabase.table('study_statistics').select('total_study_time_ms').eq('user_id', current_user['id']).gte('date', (datetime.now() - timedelta(days=30)).date().isoformat()).execute()
        
        # CORREÇÃO: Alterado para somar 'total_study_time_ms'
        total_study_time = sum(stat['total_study_time_ms'] for stat in study_time_response.data or [])
        avg_daily_study_time = total_study_time / 30 if study_time_response.data else 0
        
        return jsonify({
            'difficulty_distribution': difficulty_stats,
            'completion_rate': round(completion_rate, 2),
            'total_reviews': total_count,
            'completed_reviews': completed_count,
            'difficulty_evolution': difficulty_evolution,
            # CORREÇÃO: Renomeado para 'avg_daily_study_time_ms'
            'avg_daily_study_time_ms': round(avg_daily_study_time, 2),
            # CORREÇÃO: Renomeado para 'total_study_time_last_30_days_ms'
            'total_study_time_last_30_days_ms': total_study_time
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

# O restante do arquivo (get_subjects_stats, get_goals_progress, etc.) pode permanecer o mesmo por agora,
# pois o erro principal estava em get_performance_stats.

# ... (cole o restante do seu arquivo statistics.py aqui) ...
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
            'study_time_ms': 60 * 60 * 1000 # 60 minutos em ms
        }
        
        weekly_goals = {
            'summaries_created': 15,
            'summaries_reviewed': 25,
            'study_time_ms': 300 * 60 * 1000 # 300 minutos em ms
        }
        
        # Progresso de hoje
        today = datetime.now().date()
        today_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).eq('date', today.isoformat()).execute()
        
        today_data = today_stats.data[0] if today_stats.data else {
            'summaries_created': 0,
            'summaries_reviewed': 0,
            'total_study_time_ms': 0
        }
        
        # Progresso da semana
        week_start = today - timedelta(days=today.weekday())
        week_stats = supabase.table('study_statistics').select('*').eq('user_id', current_user['id']).gte('date', week_start.isoformat()).execute()
        
        week_totals = {
            'summaries_created': sum(stat['summaries_created'] for stat in week_stats.data or []),
            'summaries_reviewed': sum(stat['summaries_reviewed'] for stat in week_stats.data or []),
            'study_time_ms': sum(stat['total_study_time_ms'] for stat in week_stats.data or [])
        }
        
        # Calcular progresso
        daily_progress = {}
        weekly_progress = {}
        
        # CORREÇÃO: A lógica foi ajustada para usar 'study_time_ms' e 'total_study_time_ms'
        daily_progress['summaries_created'] = {
            'current': today_data.get('summaries_created', 0),
            'goal': daily_goals['summaries_created'],
            'percentage': min(100, (today_data.get('summaries_created', 0) / daily_goals['summaries_created'] * 100)) if daily_goals['summaries_created'] > 0 else 0
        }
        daily_progress['summaries_reviewed'] = {
            'current': today_data.get('summaries_reviewed', 0),
            'goal': daily_goals['summaries_reviewed'],
            'percentage': min(100, (today_data.get('summaries_reviewed', 0) / daily_goals['summaries_reviewed'] * 100)) if daily_goals['summaries_reviewed'] > 0 else 0
        }
        daily_progress['study_time_ms'] = {
            'current': today_data.get('total_study_time_ms', 0),
            'goal': daily_goals['study_time_ms'],
            'percentage': min(100, (today_data.get('total_study_time_ms', 0) / daily_goals['study_time_ms'] * 100)) if daily_goals['study_time_ms'] > 0 else 0
        }
            
        weekly_progress['summaries_created'] = {
            'current': week_totals['summaries_created'],
            'goal': weekly_goals['summaries_created'],
            'percentage': min(100, (week_totals['summaries_created'] / weekly_goals['summaries_created'] * 100)) if weekly_goals['summaries_created'] > 0 else 0
        }
        weekly_progress['summaries_reviewed'] = {
            'current': week_totals['summaries_reviewed'],
            'goal': weekly_goals['summaries_reviewed'],
            'percentage': min(100, (week_totals['summaries_reviewed'] / weekly_goals['summaries_reviewed'] * 100)) if weekly_goals['summaries_reviewed'] > 0 else 0
        }
        weekly_progress['study_time_ms'] = {
            'current': week_totals['study_time_ms'],
            'goal': weekly_goals['study_time_ms'],
            'percentage': min(100, (week_totals['study_time_ms'] / weekly_goals['study_time_ms'] * 100)) if weekly_goals['study_time_ms'] > 0 else 0
        }
        
        return jsonify({
            'daily_goals': { 'date': today.isoformat(), 'goals': daily_goals, 'progress': daily_progress },
            'weekly_goals': { 'week_start': week_start.isoformat(), 'week_end': (week_start + timedelta(days=6)).isoformat(), 'goals': weekly_goals, 'progress': weekly_progress }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@statistics_bp.route('/log-session', methods=['POST'])
@require_auth
def log_study_session():
    """Registra o tempo de uma sessão de estudo."""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        study_time_ms = data.get('study_time_ms', 0)
        
        if study_time_ms <= 0:
            return jsonify({'message': 'Nenhum tempo de estudo para registrar'}), 200

        supabase = get_supabase_client()
        
        supabase.rpc('update_study_statistics', {
            'user_uuid': current_user['id'],
            'total_study_time_ms_add': study_time_ms
        }).execute()

        return jsonify({'message': 'Sessão de estudo registrada com sucesso'}), 200

    except Exception as e:
        print(f"ERRO AO REGISTRAR SESSÃO DE ESTUDO: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
    

@statistics_bp.route('/subject-performance', methods=['GET'])
@require_auth
def get_subject_performance_ranking():
    """Obter o ranking de desempenho por matéria."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()
        
        response = supabase.rpc('get_subject_performance_ranking', {
            'p_user_id': current_user['id']
        }).execute()
        
        if response.data:
            return jsonify({'ranking': response.data}), 200
        else:
            return jsonify({'ranking': []}), 200
            
    except Exception as e:
        print(f"ERRO AO OBTER RANKING DE MATÉRIAS: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@statistics_bp.route('/hourly-activity', methods=['GET'])
@require_auth
def get_hourly_activity():
    """Retorna o tempo total de estudo agregado por hora do dia."""
    try:
        current_user = get_current_user()
        supabase = get_supabase_client()

        response = supabase.rpc('get_user_hourly_study_activity', {
            'p_user_id': current_user['id']
        }).execute()

        if response.data:
            return jsonify({'hourly_activity': response.data}), 200
        else:
            return jsonify({'hourly_activity': []}), 200

    except Exception as e:
        print(f"ERRO AO OBTER ATIVIDADE POR HORA: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500