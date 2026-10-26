"""Demandes de matériel : consultation, création, modification, suppression, export CSV."""
import csv
from datetime import datetime
import io

from flask import Blueprint, jsonify, make_response, request

from database import (
    add_material_request,
    confirm_draft_request,
    delete_material_request,
    get_all_teachers,
    get_db_connection,
    get_material_request_by_id,
    get_material_requests,
    sync_field_to_related_requests,
    toggle_prepared_status,
    update_material_request,
    update_room_type,
    get_saved_planning,
)
from routes.mes_tps import _enregistrer_template_tp
from security import (
    _get_current_user,
    _is_labo_user,
    _is_owner_or_admin,
    _is_privileged_user,
    _is_teacher_scoped_user,
    api_error,
)
from planning import SANS_SALLE
from datetime import datetime, timedelta, time
from deadline_utils import _now_local

bp = Blueprint('demandes', __name__)


@bp.route('/api/teachers', methods=['GET'])
def api_get_teachers():
    """API endpoint to get all teachers"""
    user = _get_current_user()
    if user and _is_teacher_scoped_user(user) and user.get('teacher_id'):
        teachers = [{'id': user.get('teacher_id'), 'name': user.get('teacher_name') or user.get('full_name')}] if user.get('teacher_id') else []
    else:
        teachers = get_all_teachers()
    teachers_list = []
    for teacher in teachers:
        teachers_list.append({
            'id': teacher['id'],
            'name': teacher['name']
        })
    return jsonify(teachers_list)


@bp.route('/api/replacement-teachers', methods=['GET'])
def api_replacement_teachers():
    """Retourne les enseignants sélectionnables en mode remplacement."""
    user = _get_current_user()
    teachers = get_all_teachers()

    if user and _is_teacher_scoped_user(user) and user.get('teacher_id'):
        current_teacher_id = int(user.get('teacher_id'))
        teachers = [teacher for teacher in teachers if int(teacher['id']) != current_teacher_id]

    return jsonify([
        {
            'id': teacher['id'],
            'name': teacher['name']
        }
        for teacher in teachers
    ])


@bp.route('/api/requests', methods=['GET'])
def api_get_requests():
    """API endpoint to get material requests"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    teacher_id = request.args.get('teacher_id')

    requests = get_material_requests(start_date, end_date, teacher_id)
    # Compatibilité PostgreSQL/SQLite : transformer en liste de dicts
    requests_list = []
    for req in requests:
        if isinstance(req, dict):
            r = req
        elif hasattr(req, '_fields'):  # namedtuple (rare)
            r = req._asdict()
        else:
            # sqlite3.Row peut être converti en dict avec dict()
            try:
                r = dict(req)
                # Ajouter teacher_name si manquant (dernière colonne)
                if 'teacher_name' not in r and len(req.keys()) > 0:
                    r['teacher_name'] = req[list(req.keys())[-1]]
                print(f"🔍 SQLite Row converti: id={r.get('id')}, group_count={r.get('group_count')}, quantity={r.get('quantity')}")
                requests_list.append(r)
                continue
            except (TypeError, AttributeError):
                pass
            # tuple (PostgreSQL sans row_factory)
            # Ordre des colonnes : voir la requête SELECT
            r = {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': int(req[12]) if len(req) > 12 and req[12] is not None else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[19] if len(req) > 19 else '',
                'custom_duration': req[20] if len(req) > 20 else None,
                'is_lab_test': bool(req[21]) if len(req) > 21 and req[21] is not None else False,
                'is_draft': bool(req[22]) if len(req) > 22 and req[22] is not None else False,
                'labo_observations': req[23] if len(req) > 23 else None
            }
            # Debug log
            try:
                if int(req[12]) != 1:
                    print(f"🔍 Backend: Request #{req[0]} has group_count={req[12]} (type={type(req[12])})")
            except Exception:
                pass
        if not _is_privileged_user():
            r.pop('labo_observations', None)
        requests_list.append(r)
    return jsonify(requests_list)


def _salles_par_demande(date_str):
    """Retourne un dict {request_id: salle} pour toutes les demandes d'une date donnée."""
    planning = get_saved_planning(date_str)
    if not planning:
        return {}
    affectations = planning.get('room_assignments', {}) or {}
    resultat = {}
    for course in planning.get('courses', []) or []:
        requestID = course.get('request_id')
        salle = course.get('room') or affectations.get(str(course.get('id', '')), '')
        if requestID is not None and salle not in SANS_SALLE:
            resultat[requestID] = salle
    return resultat


def _salle_visible(date_cours, maintenant):
    """Salle visible pour les jours passés, aujourd'hui, et demain à partir de 18h."""
    debut = datetime.combine(date_cours - timedelta(days=1), time(18, 0), tzinfo=maintenant.tzinfo)
    return maintenant >= debut


@bp.route('/api/calendar-events', methods=['GET'])
def api_calendar_events():
    """API endpoint to get calendar events with optional filters"""
    teacher_id = request.args.get('teacher_id')
    user = _get_current_user()
    if user and _is_teacher_scoped_user(user):
        teacher_id = user.get('teacher_id')
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')
    
    # Get all requests with optional teacher filter
    requests = get_material_requests(teacher_id=teacher_id)

    # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
    def to_dict(req):
        if isinstance(req, dict):
            return req
        elif hasattr(req, '_fields'):
            return req._asdict()
        else:
            return {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': req[12] if len(req) > 12 else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[19] if len(req) > 19 else '',
                'custom_duration': req[20] if len(req) > 20 else None,
                'is_lab_test': bool(req[21]) if len(req) > 21 and req[21] is not None else False,
                'is_draft': bool(req[22]) if len(req) > 22 and req[22] is not None else False
            }

    requests = [to_dict(req) for req in requests]

    # Filter by status if needed
    if status_filter:
        filtered_requests = []
        for req in requests:
            prepared = req.get('prepared', False)
            modified = req.get('modified', False)
            if status_filter == 'prepared' and prepared:
                filtered_requests.append(req)
            elif status_filter == 'not-prepared' and not prepared:
                filtered_requests.append(req)
            elif status_filter == 'modified' and modified:
                filtered_requests.append(req)
        requests = filtered_requests

    # Filter by type if needed
    if type_filter:
        filtered_requests = []
        for req in requests:
            selected_materials = req.get('selected_materials', '')
            material_description = req.get('material_description', '')
            if type_filter == 'absent' and selected_materials == 'Absent':
                filtered_requests.append(req)
            elif type_filter == 'no-material' and selected_materials == 'Pas besoin de matériel':
                filtered_requests.append(req)
            elif type_filter == 'normal' and selected_materials not in ['Absent', 'Pas besoin de matériel']:
                filtered_requests.append(req)
        requests = filtered_requests

    maintenant = _now_local()
    cache_salles = {} # date_str -> {request_id: salle}
    events = []
    for req in requests:
        d = req['request_date']
        if isinstance(d, str):
            d = datetime.strptime(d[:10], '%Y-%m-%d').date()
        date_str = d.isoformat()

        salle = ''
        if _salle_visible(d, maintenant):
            if date_str not in cache_salles:
                cache_salles[date_str] = _salles_par_demande(date_str)
            salle = cache_salles[date_str].get(req['id'], '')

        # Choose color based on status and type
        bg_color = '#007bff'  # Default blue

        if req.get('is_draft'):
            bg_color = '#adb5bd'  # Grey for auto-generated draft (not yet reviewed by the teacher)
        elif req.get('is_lab_test'):
            bg_color = '#fd7e14'  # Orange for lab test (no room assigned)
        elif req['selected_materials'] == 'Absent':
            bg_color = '#dc3545'  # Red for absent
        elif req['selected_materials'] == 'Pas besoin de matériel':
            bg_color = '#6f42c1'  # Purple for no material
        elif req['prepared']:
            bg_color = '#28a745'  # Green for prepared
        elif req['modified']:
            bg_color = '#ffc107'  # Yellow for modified

        events.append({
            'id': req['id'],
            'title': f"{req['teacher_name']} - {req['class_name']}",
            'start': req['request_date'],
            'description': f"Matériel: {req['material_description']} (Quantité: {req['quantity'] if req['quantity'] else 1})",
            'backgroundColor': bg_color,
            'borderColor': bg_color,
            'textColor': '#ffffff',
            # Champs bruts pour le positionnement dans la grille horaire (type Pronote)
            'teacher_name': req.get('teacher_name'),
            'class_name': req.get('class_name'),
            'is_lab_test': req.get('is_lab_test', False),
            'is_draft': req.get('is_draft', False),
            'request_name': req.get('request_name'),
            'horaire': req.get('horaire'),
            'custom_duration': req.get('custom_duration'),
            'material_description': req.get('material_description'),
            'selected_materials': req.get('selected_materials'),
            'room_type': req.get('room_type'),
            'room': salle,
            'prepared': req.get('prepared'),
            'modified': req.get('modified')
        })

    return jsonify(events)


@bp.route('/api/requests', methods=['POST'])
def api_add_request():
    """API endpoint to add a new material request"""
    try:
        data = request.get_json()
        user = _get_current_user()

        replacement_mode = str(data.get('replacement_mode', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        replacement_teacher_id_raw = data.get('replacement_teacher_id')
        replacement_teacher_id = None
        if replacement_teacher_id_raw not in (None, ''):
            try:
                replacement_teacher_id = int(replacement_teacher_id_raw)
            except (TypeError, ValueError):
                return jsonify({'error': 'Enseignant remplacé invalide'}), 400

        if user and _is_teacher_scoped_user(user) and user.get('teacher_id'):

            own_teacher_id = int(user.get('teacher_id'))
            target_teacher_id = own_teacher_id

            if replacement_mode:
                if replacement_teacher_id is None:
                    return jsonify({'error': 'Veuillez choisir l\'enseignant absent en mode remplacement'}), 400

                if replacement_teacher_id == own_teacher_id:
                    return jsonify({'error': 'En mode remplacement, vous devez choisir un autre enseignant'}), 400

                teachers = get_all_teachers()
                teacher_by_id = {
                    int(teacher['id']): teacher.get('name', f"ID {teacher['id']}")
                    for teacher in teachers
                }
                if replacement_teacher_id not in teacher_by_id:
                    return jsonify({'error': 'Enseignant remplacé introuvable'}), 400

                target_teacher_id = replacement_teacher_id

                replacement_actor = user.get('teacher_name') or user.get('full_name') or user.get('email') or 'Enseignant'
                replaced_teacher_name = teacher_by_id.get(replacement_teacher_id, 'Enseignant absent')
                existing_notes = (data.get('notes') or '').strip()
                replacement_note = f"Remplacement: demande saisie par {replacement_actor} pour {replaced_teacher_name}"
                data['notes'] = f"{replacement_note} | {existing_notes}" if existing_notes else replacement_note

            data['teacher_id'] = target_teacher_id
        
        # Validation des champs principaux
        required_fields = ['teacher_id', 'class_name', 'material_description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Le champ {field} est requis'}), 400
        if not data.get('days_horaires') or not isinstance(data['days_horaires'], list) or len(data['days_horaires']) == 0:
            return jsonify({'error': 'Veuillez ajouter au moins un jour avec des horaires.'}), 400

        # Ajout d'une note automatique quand le compte labo soumet une demande
        if _is_labo_user():
            existing_notes = (data.get('notes') or '').strip()
            labo_note = "Demande saisie par Labo"
            data['notes'] = f"{labo_note} | {existing_notes}" if existing_notes else labo_note

        # Un TP ne peut jamais être demandé un jour non-ouvré (weekend ou jour férié),
        # y compris pour admin/labo qui ne sont exemptés que du délai de préavis ci-dessous.
        from database import is_working_day_configured
        for dh in data['days_horaires']:
            date = dh.get('date')
            if not date:
                return jsonify({'error': 'Date manquante pour un des jours'}), 400
            if not is_working_day_configured(date):
                return jsonify({'error': f'Le {date} n\'est pas un jour ouvré (week-end ou jour férié).'}), 400

        # Validation du délai de 2 jours ouvrés pour chaque date (sauf admin et labo)
        if not _is_privileged_user():
            from deadline_utils import is_request_deadline_respected, get_earliest_valid_date

            for dh in data['days_horaires']:
                date = dh.get('date')

                validation = is_request_deadline_respected(date)
                if not validation['valid']:
                    earliest_date = get_earliest_valid_date()
                    return jsonify({
                        'error': f'Délai insuffisant pour le {date}. {validation["message"]} Première date disponible: {earliest_date}'
                    }), 400

        # Ajout de chaque demande (jour/horaire)
        request_ids = []
        for dh in data['days_horaires']:
            date = dh.get('date')
            horaires = dh.get('horaires', [])
            for horaire in horaires:
                request_id = add_material_request(
                    teacher_id=data['teacher_id'],
                    request_date=date,
                    horaire=horaire,
                    class_name=data['class_name'],
                    material_description=data['material_description'],
                    quantity=data.get('quantity', 1),
                    selected_materials=data.get('selected_materials', ''),
                    computers_needed=data.get('computers_needed', 0),
                    notes=data.get('notes', ''),
                    group_count=data.get('group_count', data.get('quantity', 1)),
                    material_prof=data.get('material_prof', ''),
                    request_name=data.get('request_name', ''),
                    image_url=data.get('image_url', ''),
                    custom_duration=data.get('custom_duration'),
                    is_lab_test=bool(data.get('is_lab_test', False))
                )
                request_ids.append(request_id)

                # Sauvegarder comme template TP dans la base de l'enseignant
                _enregistrer_template_tp(data, data.get('group_count', data.get('quantity', 1)))

        if not request_ids:
            return jsonify({'error': "Aucun horaire fourni pour cette demande."}), 400

        return jsonify({'success': True, 'request_ids': request_ids}), 201
        
    except Exception as e:
        return api_error('Erreur lors de la création de la demande', e)


@bp.route('/export/csv')
def export_csv():
    """Export material requests to CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    teacher_id = request.args.get('teacher_id')
    user = _get_current_user()
    if user and _is_teacher_scoped_user(user):
        teacher_id = user.get('teacher_id')
    
    requests = get_material_requests(start_date, end_date, teacher_id)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Enseignant', 'Date demande', 'Horaire', 'Niveau',
        'Matériel sélectionné', 'Ordinateurs', 'Description matériel',
        'Nombre de groupes', 'Type de salle', 'Notes', 'Date création'
    ])
    
    # Write data
    for req in requests:
        # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
        if isinstance(req, dict):
            r = req
        elif hasattr(req, '_fields'):
            r = req._asdict()
        else:
            r = {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': req[12] if len(req) > 12 else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[19] if len(req) > 19 else '',
                'custom_duration': req[20] if len(req) > 20 else None
            }
        writer.writerow([
            r['id'],
            r['teacher_name'],
            r['request_date'],
            r['horaire'] if r['horaire'] else '',
            r['class_name'],
            r['selected_materials'] if r['selected_materials'] else '',
            r['computers_needed'] if r['computers_needed'] else 0,
            r['material_description'],
            r['quantity'],
            r['room_type'] if r['room_type'] else 'Mixte',
            r['notes'] if r['notes'] else '',
            r['created_at']
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=demandes_materiel_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response


@bp.route('/api/requests/prepared-states', methods=['GET'])
def api_requests_prepared_states():
    """Returns {id: prepared} for a comma-separated list of request IDs."""
    ids_str = request.args.get('ids', '')
    if not ids_str:
        return jsonify({})
    ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
    if not ids:
        return jsonify({})
    conn, db_type = get_db_connection()
    try:
        placeholder = '%s' if db_type == 'postgresql' else '?'
        placeholders = ','.join([placeholder] * len(ids))
        cursor = conn.cursor()
        cursor.execute(f'SELECT id, prepared FROM material_requests WHERE id IN ({placeholders})', ids)
        rows = cursor.fetchall()
        return jsonify({str(row[0]): bool(row[1]) for row in rows})
    finally:
        conn.close()


@bp.route('/api/requests/<int:request_id>', methods=['GET'])
def api_get_request_by_id(request_id):
    """API endpoint to get a specific material request by ID"""
    request_data = get_material_request_by_id(request_id)
    if not request_data:
        return jsonify({'error': 'Demande non trouvée'}), 404

    if not _is_owner_or_admin(request_data.get('teacher_id')):
        return jsonify({'error': 'Non autorisé'}), 403

    # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
    if isinstance(request_data, dict):
        r = request_data
    elif hasattr(request_data, '_fields'):
        r = request_data._asdict()
    else:
        # tuple (ordre des colonnes comme dans SELECT)
        r = {
            'id': request_data[0],
            'teacher_id': request_data[1],
            'request_date': request_data[2],
            'horaire': request_data[3],
            'class_name': request_data[4],
            'material_description': request_data[5],
            'quantity': request_data[6],
            'selected_materials': request_data[7] if request_data[7] else '',
            'computers_needed': request_data[8] if request_data[8] else 0,
            'notes': request_data[9],
            'prepared': request_data[10] if request_data[10] else False,
            'modified': request_data[11] if request_data[11] else False,
            'group_count': int(request_data[12]) if len(request_data) > 12 and request_data[12] is not None else 1,
            'material_prof': request_data[13] if len(request_data) > 13 else '',
            'request_name': request_data[14] if len(request_data) > 14 else '',
            'room_type': request_data[15] if len(request_data) > 15 and request_data[15] else 'Mixte',
            'image_url': request_data[16] if len(request_data) > 16 else None,
            'exam': request_data[17] if len(request_data) > 17 else False,
            'created_at': request_data[18] if len(request_data) > 18 else None,
            'teacher_name': request_data[-1]  # dernière colonne
        }

    # Calcul du délai (jours ouvrés)
    from deadline_utils import is_request_deadline_respected
    deadline_info = is_request_deadline_respected(r['request_date'])
    r['deadline'] = deadline_info
    return jsonify(r)


@bp.route('/api/requests/<int:request_id>', methods=['PUT'])
def api_update_request(request_id):
    """API endpoint to update a material request"""
    try:
        data = request.get_json()
        current_user = _get_current_user()

        current_request = get_material_request_by_id(request_id)
        if not current_request:
            return jsonify({'error': 'Demande non trouvée'}), 404
        if not _is_owner_or_admin(current_request.get('teacher_id')):
            return jsonify({'error': 'Non autorisé'}), 403

        if current_user and current_user.get('role') == 'teacher':
            if not current_user.get('teacher_id'):
                return jsonify({'error': 'Compte enseignant non associé à un profil'}), 403
            data['teacher_id'] = current_user.get('teacher_id')

        # Validation des champs principaux
        required_fields = ['teacher_id', 'class_name', 'material_description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Le champ {field} est requis'}), 400

        # Un TP ne peut jamais être programmé un jour non-ouvré, y compris pour admin/labo
        if data.get('request_date'):
            from database import is_working_day_configured
            if not is_working_day_configured(data['request_date']):
                return jsonify({'error': f'Le {data["request_date"]} n\'est pas un jour ouvré (week-end ou jour férié).'}), 400

        # Validation du délai de 2 jours ouvrés pour toute modification (sauf admin et labo)
        if not _is_privileged_user():
            from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
            from database import get_working_day_overrides
            from deadline_utils import get_required_working_days
            overrides = get_working_day_overrides()
            required_days = get_required_working_days()

            current_date = current_request['request_date']
            validation = is_request_deadline_respected(current_date, overrides=overrides, required_days=required_days)
            if not validation['valid']:
                earliest_date = get_earliest_valid_date(overrides=overrides, required_days=required_days)
                return jsonify({
                    'error': f'Modification interdite - délai insuffisant. {validation["message"]} Première date modifiable: {earliest_date}'
                }), 400

            if 'request_date' in data:
                new_date = data['request_date']
                validation = is_request_deadline_respected(new_date, overrides=overrides, required_days=required_days)
                if not validation['valid']:
                    earliest_date = get_earliest_valid_date(overrides=overrides, required_days=required_days)
                    return jsonify({
                        'error': f'Nouvelle date invalide - délai insuffisant. {validation["message"]} Première date disponible: {earliest_date}'
                    }), 400
        
        privileged = _is_privileged_user()
        # Éditer uniquement la note interne du labo ne doit pas faire perdre le statut
        # "préparée" ni marquer la demande comme modifiée (ce n'est pas un changement du
        # contenu de la demande) — cohérent avec la synchro vers les demandes liées
        # ci-dessous, qui ne touche déjà pas à ces statuts.
        preserve_prepared = bool(data.get('labo_observations_only')) and privileged
        # La modale envoie toujours la salle : ce n'est un choix du labo/admin que si elle change.
        new_room_type = data.get('room_type') if privileged else None
        if new_room_type == (current_request.get('room_type') or 'Mixte'):
            new_room_type = None
        success = update_material_request(
            request_id,
            data['teacher_id'],
            data['request_date'],
            data['class_name'],
            data['material_description'],
            data.get('horaire'),
            data.get('quantity', 1),
            data.get('selected_materials', ''),
            data.get('computers_needed', 0),
            data.get('notes', ''),
            group_count=data.get('group_count', 1),
            material_prof=data.get('material_prof', ''),
            request_name=data.get('request_name', ''),
            custom_duration=data.get('custom_duration'),
            is_lab_test=bool(data.get('is_lab_test', False)),
            image_url=data.get('image_url'),
            room_type=new_room_type,
            labo_observations=data.get('labo_observations') if privileged else None,
            preserve_prepared=preserve_prepared
        )
        
        if success:
            _enregistrer_template_tp(data, data.get('group_count', 1))

            # Les observations labo et la salle (chimie/physique/mixte) sont communes à
            # tous les TPs identiques (même enseignant + même nom), sauf les cours
            # réguliers (trop nombreux pour que ça ait du sens de les synchroniser).
            if privileged:
                request_name = (data.get('request_name') or '').strip()
                if request_name and '(cours régulier)' not in request_name.lower():
                    if data.get('labo_observations') is not None:
                        sync_field_to_related_requests(data['teacher_id'], request_name, 'labo_observations', data['labo_observations'], exclude_id=request_id)
                    if new_room_type is not None:
                        sync_field_to_related_requests(data['teacher_id'], request_name, 'room_type', new_room_type, exclude_id=request_id)

            return jsonify({'message': 'Demande mise à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404

    except Exception as e:
        return api_error('Erreur lors de la mise à jour de la demande', e)


@bp.route('/api/requests/<int:request_id>/toggle-prepared', methods=['POST'])
def api_toggle_prepared(request_id):
    """API endpoint to toggle prepared status of a request"""
    try:
        success = toggle_prepared_status(request_id)
        if success:
            return jsonify({'message': 'Statut mis à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du statut', e)


@bp.route('/api/requests/<int:request_id>', methods=['DELETE'])
def api_delete_request(request_id):
    """API endpoint to delete a material request"""
    try:
        current_request = get_material_request_by_id(request_id)
        if not current_request:
            return jsonify({'error': 'Demande non trouvée'}), 404
        if not _is_owner_or_admin(current_request.get('teacher_id')):
            return jsonify({'error': 'Non autorisé'}), 403

        success = delete_material_request(request_id)
        if success:
            return jsonify({'message': 'Demande supprimée avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la suppression de la demande', e)


@bp.route('/api/requests/<int:request_id>/confirm-draft', methods=['POST'])
def api_confirm_draft_request(request_id):
    """Confirme une demande brouillon (cours récurrent auto-généré) sans autre modification."""
    try:
        current_request = get_material_request_by_id(request_id)
        if not current_request:
            return jsonify({'error': 'Demande non trouvée'}), 404
        if not _is_owner_or_admin(current_request.get('teacher_id')):
            return jsonify({'error': 'Non autorisé'}), 403
        success = confirm_draft_request(request_id)
        if success:
            return jsonify({'message': 'Demande confirmée avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la confirmation de la demande', e)


@bp.route('/api/requests/<int:request_id>/room-type', methods=['PUT'])
def api_update_room_type(request_id):
    """API endpoint to update room type of a material request"""
    try:
        data = request.get_json()
        room_type = data.get('room_type')
        
        if room_type not in ['Physique', 'Chimie', 'Mixte']:
            return jsonify({'error': 'Type de salle invalide'}), 400
        
        success = update_room_type(request_id, room_type, manual=_is_privileged_user())
        if success:
            return jsonify({'message': 'Type de salle mis à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la mise à jour du type de salle', e)
