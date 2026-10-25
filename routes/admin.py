"""Administration : tableau de bord, établissement, comptes, enseignants, niveaux et effectifs."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database import (
    add_level,
    add_student_number,
    add_teacher,
    delete_level,
    delete_student_number,
    delete_teacher,
    delete_user,
    get_all_levels,
    get_all_rooms,
    get_all_student_numbers,
    get_all_teachers,
    get_all_users,
    pre_associate_teacher,
    update_level,
    update_student_number,
    update_teacher_short_name,
)
from routes.salles import _availability_page_title
from security import _get_current_user, _is_admin_user, api_error
import site_settings

bp = Blueprint('admin', __name__)


@bp.route('/admin')
def dashboard():
    """Admin dashboard page"""
    setup = {'rooms': len(get_all_rooms()), 'teachers': len(get_all_teachers()), 'levels': len(get_all_levels())}
    return render_template('admin.html', availability_title=_availability_page_title(), setup=setup)


@bp.route('/admin/establishment')
def view_establishment():
    """Page des réglages de l'établissement"""
    from zoneinfo import available_timezones
    return render_template('establishment.html', settings=site_settings.get_site_settings(),
                           defaults=site_settings.DEFAULTS, is_admin=_is_admin_user(),
                           timezones=sorted(available_timezones()))


@bp.route('/api/site-settings', methods=['GET', 'PUT'])
def api_site_settings():
    """Lit ou modifie les réglages de l'établissement (admin/labo ; e-mails réservés à l'admin)."""
    if request.method == 'GET':
        return jsonify(site_settings.get_site_settings())
    data = request.get_json(silent=True) or {}
    clean, errors = site_settings.validate_settings({k: v for k, v in data.items() if k in site_settings.DEFAULTS})
    if errors:
        return jsonify({'error': ' ; '.join(errors.values()), 'fields': errors}), 400
    if not _is_admin_user():
        current = site_settings.get_site_settings()
        if any(clean.get(k, current[k]) != current[k] for k in site_settings.SENSITIVE_KEYS):
            return jsonify({'error': "Seul l'administrateur peut modifier l'e-mail du compte labo et le domaine autorisé."}), 403
    site_settings.save_settings(clean)
    return jsonify({'success': True, 'settings': site_settings.get_site_settings()})


@bp.route('/admin/users')
def admin_users():
    """Admin user management page"""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return redirect(url_for('auth.login'))
    users = get_all_users()
    teachers = get_all_teachers()
    return render_template('admin_users.html', users=users, teachers=teachers)


@bp.route('/admin/niveaux')
def admin_niveaux():
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return redirect(url_for('auth.login'))
    return render_template('admin_niveaux.html')


@bp.route('/api/admin/link-teacher', methods=['POST'])
def api_admin_link_teacher():
    """Associate an email with a teacher_id (admin/labo)."""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    payload = request.get_json(silent=True) or {}
    email = str(payload.get('email', '')).strip().lower()
    teacher_id = payload.get('teacher_id')
    if not email or teacher_id is None:
        return jsonify({'error': 'email et teacher_id requis'}), 400
    try:
        pre_associate_teacher(email, int(teacher_id))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def api_admin_delete_user(user_id):
    """Delete a Google account association (admin/labo)."""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        deleted = delete_user(user_id)
        if not deleted:
            return jsonify({'error': 'Compte introuvable'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/teachers', methods=['POST'])
def api_admin_add_teacher():
    """Create a new teacher (admin/labo)."""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name', '')).strip()
    if not name:
        return jsonify({'error': 'Le nom est requis'}), 400
    try:
        new_id = add_teacher(name)
        return jsonify({'success': True, 'id': new_id, 'name': name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/teachers/<int:teacher_id>', methods=['DELETE'])
def api_admin_delete_teacher(teacher_id):
    """Delete a teacher (admin/labo)."""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        request_count = delete_teacher(teacher_id)
        return jsonify({'success': True, 'requests_affected': request_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/teachers/<int:teacher_id>', methods=['PUT'])
def api_admin_update_teacher(teacher_id):
    """Update teacher short_name (admin/labo)."""
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    payload = request.get_json(silent=True) or {}
    short_name = str(payload.get('short_name', '')).strip()
    try:
        update_teacher_short_name(teacher_id, short_name)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/levels', methods=['POST'])
def api_admin_add_level():
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name', '')).strip()
    if not name:
        return jsonify({'error': 'Le nom est requis'}), 400
    try:
        new_id = add_level(name)
        return jsonify({'success': True, 'id': new_id, 'name': name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/levels/<int:level_id>', methods=['PUT'])
def api_admin_update_level(level_id):
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    payload = request.get_json(silent=True) or {}
    # Seuls les champs présents dans la requête sont modifiés (sinon éditer la durée
    # effaçait le nom court).
    short_name = str(payload['short_name']).strip() if 'short_name' in payload else None
    default_duration = payload.get('default_duration')
    display_order = payload.get('display_order')
    default_groups = payload.get('default_groups')
    try:
        update_level(level_id, short_name=short_name,
                     default_duration=int(default_duration) if default_duration is not None else None,
                     display_order=int(display_order) if display_order is not None else None,
                     default_groups=int(default_groups) if default_groups is not None else None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/levels/<int:level_id>', methods=['DELETE'])
def api_admin_delete_level(level_id):
    user = _get_current_user()
    if not user or user.get('role') not in ('admin', 'labo'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        delete_level(level_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/students')
def view_students():
    """Student management page"""
    return render_template('students.html')


# API Routes pour la gestion des effectifs d'étudiants
@bp.route('/api/students', methods=['GET'])
def api_get_students():
    """API endpoint to get all student numbers"""
    try:
        students = get_all_student_numbers()
        return jsonify(students)
    except Exception as e:
        return api_error('Erreur lors de la récupération des effectifs', e)


@bp.route('/api/students', methods=['POST'])
def api_add_student():
    """API endpoint to add a new student number entry"""
    try:
        data = request.get_json()
        teacher_name = data.get('teacher_name')
        student_count = data.get('student_count')
        level = data.get('level', '2nde')
        
        if not teacher_name or not student_count:
            return jsonify({'error': 'Nom de l\'enseignant et nombre d\'élèves requis'}), 400
        
        success = add_student_number(teacher_name, student_count, level)
        if success:
            return jsonify({'message': 'Effectif ajouté avec succès'}), 201
        else:
            return jsonify({'error': 'Erreur lors de l\'ajout'}), 500
            
    except Exception as e:
        return api_error('Erreur lors de l\'ajout de l\'effectif', e)


@bp.route('/api/students/<int:student_id>', methods=['PUT'])
def api_update_student(student_id):
    """API endpoint to update a student number entry"""
    try:
        data = request.get_json()
        success = update_student_number(student_id, data)
        if success:
            return jsonify({'message': 'Effectif mis à jour avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return api_error('Erreur lors de la mise à jour de l\'effectif', e)


@bp.route('/api/students/<int:student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    """API endpoint to delete a student number entry"""
    try:
        success = delete_student_number(student_id)
        if success:
            return jsonify({'message': 'Effectif supprimé avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return api_error('Erreur lors de la suppression de l\'effectif', e)
