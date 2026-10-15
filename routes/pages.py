"""Pages principales : accueil, calendrier, liste des demandes, générateur de planning."""
from flask import Blueprint, render_template

from database import get_all_teachers
from security import _get_current_user, _is_teacher_scoped_user

bp = Blueprint('pages', __name__)


# Route Générateur de Planning
@bp.route('/planning')
def planning():
    """Page Générateur de Planning pour voir les demandes d'un jour"""
    return render_template('planning.html')


@bp.route('/')
def index():
    """Home page with material request form"""
    user = _get_current_user()
    if user and _is_teacher_scoped_user(user) and user.get('teacher_id'):
        teachers = [{'id': user.get('teacher_id'), 'name': user.get('teacher_name') or user.get('full_name')}] if user.get('teacher_id') else []
    else:
        teachers = get_all_teachers()
    return render_template('index.html', teachers=teachers)


@bp.route('/calendar')
def calendar():
    """Calendar view of material requests"""
    user = _get_current_user()
    if user and _is_teacher_scoped_user(user) and user.get('teacher_id'):
        teachers = [{'id': user.get('teacher_id'), 'name': user.get('teacher_name') or user.get('full_name')}] if user.get('teacher_id') else []
    else:
        teachers = get_all_teachers()
    return render_template('calendar.html', teachers=teachers)


@bp.route('/requests')
def view_requests():
    """View all material requests in a table"""
    teachers = get_all_teachers()
    return render_template('requests.html', teachers=teachers)
