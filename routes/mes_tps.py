"""Espace enseignant : mes TPs, emploi du temps type, gabarits de TP et cours réguliers."""
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database import (
    add_recurring_course,
    add_tp_chapter,
    arrange_tp_templates,
    delete_recurring_course,
    delete_tp_chapter,
    generate_draft_requests_for_week,
    get_all_teachers,
    get_db_connection,
    get_recurring_courses,
    get_tp_chapter_by_id,
    get_tp_chapters,
    get_tp_template_by_id,
    get_tp_templates,
    rename_tp_template,
    set_tp_template_chapter,
    update_tp_chapter,
    upsert_tp_template,
)
from deadline_utils import get_earliest_valid_date
from security import _get_current_user, _is_owner_or_admin, _is_privileged_user, api_error

bp = Blueprint('mes_tps', __name__)


# Nom généré automatiquement pour les cours issus de l'emploi du temps (voir
# database.generate_draft_requests_for_week, dans database/emploi_du_temps.py) : ce n'est pas un nom de TP choisi par l'enseignant.
def _est_nom_brouillon_auto(request_name, class_name):
    return bool(class_name) and request_name.strip() == f"{class_name} (cours régulier)"


def _cle_chapitre(number, title):
    """Ce qui distingue deux dossiers à l'affichage (nom comparé sans tenir compte des majuscules)."""
    return (number, (title or '').strip().lower())


def _lire_chapitre(data):
    """Lit et valide numéro + nom d'un dossier. Renvoie (number, title, message_erreur)."""
    title = (data.get('title') or '').strip() or None
    raw_number = data.get('number')
    if raw_number in (None, ''):
        number = None
    else:
        try:
            number = int(raw_number)
        except (TypeError, ValueError):
            return None, None, 'Le numéro du chapitre doit être un nombre'
    if number is None and not title:
        return None, None, 'Indiquez un numéro, un nom, ou les deux'
    return number, title, None


def _dossier_en_double(teacher_id, level, number, title, chapter_id=None):
    """Un autre dossier du niveau a-t-il déjà ce numéro ET ce nom ? (chapter_id : dossier modifié, exclu)"""
    cle = _cle_chapitre(number, title)
    return any(ch['id'] != chapter_id and _cle_chapitre(ch['number'], ch['title']) == cle
               for ch in get_tp_chapters(teacher_id, level))


def _dossier_valide(chapter_id, teacher_id, level):
    """Un TP ne peut être rangé que dans un dossier du même enseignant et du même niveau (None = sans dossier)."""
    if chapter_id is None:
        return True
    ch = get_tp_chapter_by_id(chapter_id)
    return bool(ch) and ch['teacher_id'] == teacher_id and ch['level'] == level


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
        chapter_id = data.get('chapter_id') or None
        if not _dossier_valide(chapter_id, user['teacher_id'], level):
            return jsonify({'error': 'Dossier invalide'}), 400
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
        if chapter_id is not None:
            created = next((t for t in get_tp_templates(user['teacher_id'], level) if t['request_name'] == request_name), None)
            if created:
                set_tp_template_chapter(created['id'], chapter_id)
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

        # Dossier : vérifié avant toute écriture ; absent des données = rangement inchangé.
        chapter_id = data.get('chapter_id') or None
        if not _dossier_valide(chapter_id, template['teacher_id'], template['level']):
            return jsonify({'error': 'Dossier invalide'}), 400

        # Renommage par l'id : l'upsert ci-dessous, indexé sur le nom, créerait sinon un second TP.
        old_name = template['request_name']
        new_name = (data.get('request_name') or old_name).strip()
        if new_name != old_name:
            if any(t['request_name'] == new_name for t in get_tp_templates(template['teacher_id'], template['level'])):
                return jsonify({'error': f'Un TP nommé "{new_name}" existe déjà pour ce niveau'}), 409
            if not rename_tp_template(template_id, template['teacher_id'], template['level'],
                                      old_name, new_name, get_earliest_valid_date()):
                return jsonify({'error': 'Erreur lors du renommage du TP'}), 500

        upsert_tp_template(
            teacher_id=template['teacher_id'],
            level=template.get('level', ''),
            request_name=new_name,
            material_description=data.get('material_description', ''),
            selected_materials=data.get('selected_materials', ''),
            material_prof=data.get('material_prof', ''),
            computers_needed=int(data.get('computers_needed', 0)),
            group_count=int(data.get('group_count', 1)),
            notes=data.get('notes', ''),
            image_url=data.get('image_url', ''),
            room_type=data.get('room_type', 'Mixte')
        )
        # Seulement si le dossier change : sinon la position choisie par glisser-déposer serait perdue.
        if 'chapter_id' in data and chapter_id != template.get('chapter_id'):
            set_tp_template_chapter(template_id, chapter_id)
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du template TP', e)


@bp.route('/api/tp-templates/arrangement', methods=['PUT'])
def api_arrange_tp_templates():
    """Glisser-déposer dans Mes TPs : {chapter_id, template_ids} = contenu d'un dossier
    (chapter_id null = sans dossier), dans l'ordre affiché."""
    try:
        data = request.get_json(silent=True) or {}
        template_ids = data.get('template_ids')
        if not isinstance(template_ids, list) or not template_ids \
                or not all(isinstance(i, int) and not isinstance(i, bool) for i in template_ids):
            return jsonify({'error': 'template_ids doit être une liste d\'identifiants'}), 400
        templates = [get_tp_template_by_id(i) for i in template_ids]
        if not all(templates):
            return jsonify({'error': 'Template non trouvé'}), 404
        teacher_id, level = templates[0]['teacher_id'], templates[0]['level']
        if any(t['teacher_id'] != teacher_id or t['level'] != level for t in templates):
            return jsonify({'error': 'Les TP doivent être du même enseignant et du même niveau'}), 400
        if not _is_owner_or_admin(teacher_id):
            return jsonify({'error': 'Non autorisé'}), 403
        chapter_id = data.get('chapter_id') or None
        if not _dossier_valide(chapter_id, teacher_id, level):
            return jsonify({'error': 'Dossier invalide'}), 400
        if not arrange_tp_templates(chapter_id, template_ids):
            return jsonify({'error': 'Erreur lors du rangement des TP'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors du rangement des TP', e)


@bp.route('/api/tp-chapters', methods=['GET'])
def api_get_tp_chapters():
    """Dossiers d'un enseignant pour un niveau (mêmes droits de lecture que /api/tp-templates :
    le labo et l'admin en ont besoin pour la modale de modification d'une demande)."""
    try:
        teacher_id = request.args.get('teacher_id', type=int)
        level = request.args.get('level', '')
        if not teacher_id or not level:
            return jsonify({'error': 'teacher_id et level sont requis'}), 400
        return jsonify(get_tp_chapters(teacher_id, level))
    except Exception as e:
        return api_error('Erreur lors de la récupération des dossiers', e)


@bp.route('/api/tp-chapters', methods=['POST'])
def api_create_tp_chapter():
    """Crée un dossier pour l'enseignant connecté."""
    try:
        user = _get_current_user()
        if not user or not user.get('teacher_id'):
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        level = (data.get('level') or '').strip()
        if not level:
            return jsonify({'error': 'level est requis'}), 400
        number, title, erreur = _lire_chapitre(data)
        if erreur:
            return jsonify({'error': erreur}), 400
        if _dossier_en_double(user['teacher_id'], level, number, title):
            return jsonify({'error': 'Un dossier avec ce numéro et ce nom existe déjà'}), 409
        chapter_id = add_tp_chapter(user['teacher_id'], level, number, title)
        if chapter_id is None:
            return jsonify({'error': 'Erreur lors de la création du dossier'}), 500
        return jsonify({'success': True, 'id': chapter_id})
    except Exception as e:
        return api_error('Erreur lors de la création du dossier', e)


@bp.route('/api/tp-chapters/<int:chapter_id>', methods=['PUT'])
def api_update_tp_chapter(chapter_id):
    """Modifie le numéro et/ou le nom d'un dossier."""
    try:
        chapter = get_tp_chapter_by_id(chapter_id)
        if not chapter:
            return jsonify({'error': 'Dossier non trouvé'}), 404
        if not _is_owner_or_admin(chapter['teacher_id']):
            return jsonify({'error': 'Non autorisé'}), 403
        number, title, erreur = _lire_chapitre(request.get_json(silent=True) or {})
        if erreur:
            return jsonify({'error': erreur}), 400
        if _dossier_en_double(chapter['teacher_id'], chapter['level'], number, title, chapter_id):
            return jsonify({'error': 'Un dossier avec ce numéro et ce nom existe déjà'}), 409
        if not update_tp_chapter(chapter_id, number, title):
            return jsonify({'error': 'Erreur lors de la modification du dossier'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la modification du dossier', e)


@bp.route('/api/tp-chapters/<int:chapter_id>', methods=['DELETE'])
def api_delete_tp_chapter(chapter_id):
    """Supprime un dossier ; ses TP sont conservés et redeviennent « sans dossier »."""
    try:
        chapter = get_tp_chapter_by_id(chapter_id)
        if not chapter:
            return jsonify({'error': 'Dossier non trouvé'}), 404
        if not _is_owner_or_admin(chapter['teacher_id']):
            return jsonify({'error': 'Non autorisé'}), 403
        if not delete_tp_chapter(chapter_id):
            return jsonify({'error': 'Erreur lors de la suppression du dossier'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return api_error('Erreur lors de la suppression du dossier', e)


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
