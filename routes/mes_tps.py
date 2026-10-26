"""Espace enseignant : mes TPs, emploi du temps type, gabarits de TP et cours réguliers."""
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database import (
    add_recurring_course,
    delete_recurring_course,
    generate_draft_requests_for_week,
    get_all_teachers,
    get_db_connection,
    get_recurring_courses,
    get_tp_template_by_id,
    get_tp_templates,
    upsert_tp_template,
)
from security import _get_current_user, _is_owner_or_admin, _is_privileged_user, api_error

bp = Blueprint('mes_tps', __name__)


# Nom généré automatiquement pour les cours issus de l'emploi du temps (voir
# database.generate_draft_requests_for_week, dans database/emploi_du_temps.py) : ce n'est pas un nom de TP choisi par l'enseignant.
def _est_nom_brouillon_auto(request_name, class_name):
    return bool(class_name) and request_name.strip() == f"{class_name} (cours régulier)"


def _enregistrer_template_tp(data, group_count):
    """Enregistre la demande dans la base de TP de l'enseignant, si c'en est bien un.

    'Absent' décrit l'état d'un créneau, pas un TP réutilisable. En revanche un
    examen nommé ou un cours 'Pas besoin de matériel' renommé doivent pouvoir être
    réutilisés ; les noms automatiques "(cours régulier)" sont exclus plus bas.
    """
    sm = data.get('selected_materials', '')
    request_name = (data.get('request_name') or '').strip()
    class_name = data.get('class_name')
    if sm == 'Absent':
        return
    if not request_name or not class_name:
        return
    if _est_nom_brouillon_auto(request_name, class_name):
        return
    try:
        upsert_tp_template(
            teacher_id=data['teacher_id'],
            level=class_name,
            request_name=request_name,
            material_description=data.get('material_description', ''),
            selected_materials=sm,
            material_prof=data.get('material_prof', ''),
            computers_needed=data.get('computers_needed', 0),
            group_count=group_count,
            notes=data.get('notes', ''),
            image_url=data.get('image_url', ''),
            room_type=data.get('room_type', 'Mixte')
        )
    except Exception:
        pass  # Echec silencieux : ne pas bloquer l'enregistrement de la demande


@bp.route('/mes-tps')
def mes_tps():
    """Page pour voir les TP enregistrés par l'enseignant connecté"""
    user = _get_current_user()
    if not user or not user.get('teacher_id'):
        return redirect(url_for('auth.login'))
    teachers = get_all_teachers()
    return render_template('mes_tps.html', teachers=teachers)


@bp.route('/mon-emploi-du-temps')
def mon_emploi_du_temps():
    """Page pour définir son emploi du temps type et générer les demandes de la semaine"""
    user = _get_current_user()
    if not user or not user.get('teacher_id'):
        return redirect(url_for('auth.login'))
    return render_template('mon_emploi_du_temps.html')


@bp.route('/api/tp-templates', methods=['GET'])
def api_get_tp_templates():
    """Retourne les templates TP d'un enseignant pour un niveau donné."""
    try:
        teacher_id = request.args.get('teacher_id', type=int)
        level = request.args.get('level', '')
        if not teacher_id or not level:
            return jsonify({'error': 'teacher_id et level sont requis'}), 400
        templates = get_tp_templates(teacher_id, level)
        return jsonify(templates)
    except Exception as e:
        return api_error('Erreur lors de la récupération des templates TP', e)


@bp.route('/api/tp-templates/<int:template_id>', methods=['GET'])
def api_get_tp_template_by_id(template_id):
    """Retourne un template TP par son ID."""
    try:
        template = get_tp_template_by_id(template_id)
        if not template:
            return jsonify({'error': 'Template non trouvé'}), 404
        return jsonify(template)
    except Exception as e:
        return api_error('Erreur lors de la récupération du template TP', e)


@bp.route('/api/tp-templates', methods=['POST'])
def api_create_tp_template():
    """Crée un nouveau template TP pour l'enseignant connecté, sans l'affecter à une date."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        level = (data.get('level') or '').strip()
        request_name = (data.get('request_name') or '').strip()
        if not level or not request_name:
            return jsonify({'error': 'level et request_name sont requis'}), 400
        existing = get_tp_templates(user['teacher_id'], level)
        if any(t.get('request_name') == request_name for t in existing):
            return jsonify({'error': f'Un TP nommé "{request_name}" existe déjà pour ce niveau'}), 409
        upsert_tp_template(
            teacher_id=user['teacher_id'],
            level=level,
            request_name=request_name,
            material_description=data.get('material_description', ''),
            selected_materials=data.get('selected_materials', ''),
            material_prof=data.get('material_prof', ''),
            computers_needed=int(data.get('computers_needed', 0)),
            group_count=int(data.get('group_count', 1)),
            notes=data.get('notes', ''),
            image_url=data.get('image_url', ''),
            room_type=data.get('room_type', 'Mixte')
        )
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la création du template TP', e)


@bp.route('/api/tp-templates/copy', methods=['POST'])
def api_copy_tp_template():
    """Copie un template TP d'un autre enseignant vers l'enseignant connecté."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        source_id = data.get('source_id')
        new_name = (data.get('request_name') or '').strip()
        level = (data.get('level') or '').strip()
        if not source_id or not new_name or not level:
            return jsonify({'error': 'source_id, request_name et level sont requis'}), 400
        source = get_tp_template_by_id(source_id)
        if not source:
            return jsonify({'error': 'Template source non trouvé'}), 404
        upsert_tp_template(
            teacher_id=user['teacher_id'],
            level=level,
            request_name=new_name,
            material_description=source.get('material_description', ''),
            selected_materials=source.get('selected_materials', ''),
            material_prof=source.get('material_prof', ''),
            computers_needed=source.get('computers_needed', 0),
            group_count=source.get('group_count', 1),
            notes=source.get('notes', ''),
            image_url=source.get('image_url', ''),
            room_type=source.get('room_type', 'Mixte')
        )
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la copie du template TP', e)


@bp.route('/api/tp-templates/<int:template_id>', methods=['DELETE'])
def api_delete_tp_template(template_id):
    """Supprime un template TP."""
    try:
        user = _get_current_user()
        if not user:
            return jsonify({'error': 'Non autorisé'}), 401
        template = get_tp_template_by_id(template_id)
        if not template:
            return jsonify({'error': 'Template non trouvé'}), 404
        if not _is_owner_or_admin(template.get('teacher_id')):
            return jsonify({'error': 'Non autorisé'}), 403
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'DELETE FROM tp_templates WHERE id = {placeholder}', (template_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la suppression du template TP', e)


@bp.route('/api/tp-templates/<int:template_id>', methods=['PUT'])
def api_update_tp_template(template_id):
    """Met à jour un template TP existant."""
    try:
        user = _get_current_user()
        if not user:
            return jsonify({'error': 'Non autorisé'}), 401
        template = get_tp_template_by_id(template_id)
        if not template:
            return jsonify({'error': 'Template non trouvé'}), 404
        if not _is_owner_or_admin(template.get('teacher_id')):
            return jsonify({'error': 'Non autorisé'}), 403
        data = request.get_json(silent=True) or {}
        upsert_tp_template(
            teacher_id=template['teacher_id'],
            level=template.get('level', ''),
            request_name=data.get('request_name', template.get('request_name', '')),
            material_description=data.get('material_description', ''),
            selected_materials=data.get('selected_materials', ''),
            material_prof=data.get('material_prof', ''),
            computers_needed=int(data.get('computers_needed', 0)),
            group_count=int(data.get('group_count', 1)),
            notes=data.get('notes', ''),
            image_url=data.get('image_url', ''),
            room_type=data.get('room_type', 'Mixte')
        )
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du template TP', e)


@bp.route('/api/recurring-courses', methods=['GET'])
def api_get_recurring_courses():
    """Retourne l'emploi du temps type de l'enseignant connecté."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        return jsonify(get_recurring_courses(user['teacher_id']))
    except Exception as e:
        return api_error('Erreur lors de la récupération de l\'emploi du temps', e)


@bp.route('/api/recurring-courses', methods=['POST'])
def api_add_recurring_course():
    """Ajoute (ou remplace) un créneau récurrent pour l'enseignant connecté."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        try:
            day_of_week = int(data.get('day_of_week'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Jour de la semaine invalide'}), 400
        if day_of_week < 0 or day_of_week > 4:
            return jsonify({'error': 'Le jour doit être entre Lundi (0) et Vendredi (4)'}), 400
        horaire = (data.get('horaire') or '').strip()
        class_name = (data.get('class_name') or '').strip()
        if not horaire or not class_name:
            return jsonify({'error': 'horaire et class_name sont requis'}), 400
        course_id = add_recurring_course(user['teacher_id'], day_of_week, horaire, class_name)
        if course_id is None:
            return jsonify({'error': 'Erreur lors de l\'ajout du créneau'}), 500
        return jsonify({'success': True, 'id': course_id})
    except Exception as e:
        return api_error('Erreur lors de l\'ajout du créneau récurrent', e)


@bp.route('/api/recurring-courses/<int:course_id>', methods=['DELETE'])
def api_delete_recurring_course(course_id):
    """Supprime un créneau récurrent de l'enseignant connecté."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        deleted = delete_recurring_course(course_id, user['teacher_id'])
        if not deleted:
            return jsonify({'error': 'Créneau non trouvé'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la suppression du créneau récurrent', e)


@bp.route('/api/recurring-courses/generate', methods=['POST'])
def api_generate_recurring_courses():
    """Génère les demandes 'brouillon' de la semaine indiquée à partir de l'emploi du temps type."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        week_start = (data.get('week_start') or '').strip()
        if not week_start:
            return jsonify({'error': 'week_start (date du lundi) est requis'}), 400
        try:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Format de date invalide (attendu YYYY-MM-DD)'}), 400
        if week_start_date.weekday() != 0:
            return jsonify({'error': 'La date doit être un lundi'}), 400
        enforce_deadline = not _is_privileged_user(user)
        created, skipped = generate_draft_requests_for_week(user['teacher_id'], week_start, enforce_deadline=enforce_deadline)
        return jsonify({'success': True, 'created': created, 'skipped': skipped})
    except Exception as e:
        return api_error('Erreur lors de la génération des cours de la semaine', e)
