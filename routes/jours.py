"""Jours ouvrés, jours fériés, délai de dépôt et informations du calendrier."""
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from database import (
    delete_working_day_config,
    get_deadline_working_days,
    get_working_days_config,
    set_deadline_working_days,
    set_working_day_config,
)
from security import _get_current_user, _is_privileged_user, api_error

bp = Blueprint('jours', __name__)


@bp.route('/admin/working-days')
def view_working_days():
    """Working days configuration page"""
    return render_template('working_days.html')


@bp.route('/api/deadline-config', methods=['GET'])
def api_get_deadline_config():
    """Nombre de jours ouvrés requis avant une demande (lecture publique aux utilisateurs connectés)."""
    try:
        return jsonify({'deadline_working_days': get_deadline_working_days()})
    except Exception as e:
        return api_error('Erreur lors de la récupération du délai de dépôt', e)


@bp.route('/api/calendar-info', methods=['GET'])
def api_calendar_info():
    """Infos d'affichage pour /calendar : jours non ouvrés (fériés...) et prochaine date limite de dépôt.

    Calculé côté serveur pour tenir compte des jours configurés dans /admin/working-days
    (le miroir JS de main.js ne connaît que les week-ends).
    """
    try:
        from deadline_utils import get_earliest_valid_date, get_required_working_days, _deadline_moment
        from database import get_working_day_overrides

        non_working_days = []
        for item in get_working_days_config():
            if item.get('is_working_day'):
                continue
            d = item.get('date')
            if hasattr(d, 'strftime'):
                d = d.strftime('%Y-%m-%d')
            elif isinstance(d, str) and len(d) > 10:
                from dateutil import parser
                try:
                    d = parser.parse(d).strftime('%Y-%m-%d')
                except Exception:
                    continue
            if d:
                non_working_days.append(d)

        overrides = get_working_day_overrides()
        required_days = get_required_working_days()
        earliest = get_earliest_valid_date(overrides=overrides, required_days=required_days)
        earliest_date = datetime.strptime(earliest, '%Y-%m-%d').date()
        deadline = _deadline_moment(earliest_date, required_days, overrides=overrides)

        return jsonify({
            'non_working_days': non_working_days,
            'next_deadline': {
                'request_date': earliest,
                'deadline_date': deadline.strftime('%Y-%m-%d'),
                'deadline_time': deadline.strftime('%Hh%M'),
            },
        })
    except Exception as e:
        return api_error('Erreur lors de la récupération des infos du calendrier', e)


@bp.route('/api/deadline-config', methods=['PUT'])
def api_set_deadline_config():
    """Modifie le nombre de jours ouvrés requis avant une demande (admin/labo)."""
    user = _get_current_user()
    if not user or not _is_privileged_user(user):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        data = request.get_json(silent=True) or {}
        days = data.get('deadline_working_days')
        if days is None:
            return jsonify({'error': 'deadline_working_days est requis'}), 400
        saved = set_deadline_working_days(days)
        return jsonify({'success': True, 'deadline_working_days': saved})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du délai de dépôt', e)


@bp.route('/api/working-days', methods=['GET'])
def api_get_working_days():
    """API endpoint to get working days config for a date range"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    try:
        config = get_working_days_config(start_date, end_date)
        # Format: [{date, is_working_day, description}]
        # Ensure is_working_day is bool and date is YYYY-MM-DD
        for item in config:
            item['is_working_day'] = bool(item['is_working_day'])
            # Convert date to YYYY-MM-DD if needed
            if item['date']:
                if isinstance(item['date'], str) and len(item['date']) > 10:
                    # Try to parse RFC 1123 or other formats
                    from dateutil import parser
                    try:
                        dt = parser.parse(item['date'])
                        item['date'] = dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass
                elif isinstance(item['date'], (str,)) and len(item['date']) == 10:
                    # Already correct format
                    pass
                elif hasattr(item['date'], 'strftime'):
                    item['date'] = item['date'].strftime('%Y-%m-%d')
        return jsonify(config)
    except Exception as e:
        return api_error('Erreur lors de la récupération des jours ouvrés', e)


@bp.route('/api/working-days/<date>', methods=['PUT'])
def api_set_working_day(date):
    """API endpoint to set a working day config for a specific date (YYYY-MM-DD)"""
    try:
        data = request.get_json()
        is_working_day = data.get('is_working_day')
        description = data.get('description', None)
        if is_working_day is None:
            return jsonify({'error': 'is_working_day is required'}), 400
        # Accept true/false as string or bool
        if isinstance(is_working_day, str):
            is_working_day = is_working_day.lower() == 'true'
        success = set_working_day_config(date, is_working_day, description)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update config'}), 500
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du jour ouvré', e)


@bp.route('/api/working-days/<date>', methods=['DELETE'])
def api_delete_working_day(date):
    """API endpoint to delete a working day config for a specific date (reset to default)"""
    try:
        success = delete_working_day_config(date)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to delete config'}), 500
    except Exception as e:
        return api_error('Erreur lors de la suppression du jour ouvré', e)


@bp.route('/api/working-days/bulk', methods=['PUT'])
def api_bulk_update_working_days():
    """API endpoint to bulk update working days config for multiple dates"""
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        updated_count = 0
        errors = []
        for upd in updates:
            date = upd.get('date')
            is_working_day = upd.get('is_working_day')
            description = upd.get('description', None)
            if date is None or is_working_day is None:
                errors.append(f"Donnée manquante pour {date or '[date inconnue]'}")
                continue
            # Accept true/false as string or bool
            if isinstance(is_working_day, str):
                is_working_day = is_working_day.lower() == 'true'
            success = set_working_day_config(date, is_working_day, description)
            if success:
                updated_count += 1
            else:
                errors.append(f"Erreur pour {date}")
        return jsonify({'updated_count': updated_count, 'errors': errors})
    except Exception as e:
        return api_error('Erreur lors de la mise à jour groupée des jours ouvrés', e)
