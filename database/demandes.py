"""Demandes de matériel : création, lecture, modification, état préparé, champs synchronisés."""

from .connexion import get_db_connection


def rien_a_preparer(selected_materials, computers_needed, notes):
    """Vrai si le labo n'a rien à préparer : la demande peut être marquée préparée d'office."""
    try:
        computers = int(computers_needed or 0)
    except (TypeError, ValueError):
        computers = 0
    return (selected_materials == 'Pas besoin de matériel'
            and computers == 0
            and not (notes or '').strip())


def add_material_request(teacher_id, request_date, class_name, material_description,
                        horaire=None, quantity=1, selected_materials='', computers_needed=0,
                        notes='', exam=False, group_count=1, material_prof='', request_name='', image_url='', custom_duration=None,
                        is_lab_test=False, is_draft=False):
    """Add a new material request"""
    prepared = rien_a_preparer(selected_materials, computers_needed, notes)
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    # Coerce group_count to an integer with a safe default (0 autorisé : niveaux sans répartition en groupes)
    try:
        group_count = int(group_count) if group_count is not None else 1
        if group_count < 0:
            group_count = 0
    except Exception:
        group_count = 1

    placeholders = ', '.join(['%s' if db_type == 'postgresql' else '?'] * 18)
    cursor.execute(f'''
        INSERT INTO material_requests
        (teacher_id, request_date, horaire, class_name, material_description, quantity,
         selected_materials, computers_needed, notes, exam, group_count, material_prof, request_name, image_url, custom_duration, is_lab_test, is_draft, prepared)
        VALUES ({placeholders})
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity,
          selected_materials, computers_needed, notes, exam, group_count, material_prof, request_name, image_url, custom_duration, bool(is_lab_test), bool(is_draft), bool(prepared)))
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    return request_id


def get_material_requests(start_date=None, end_date=None, teacher_id=None):
    """Get material requests with optional filters"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    query = '''
        SELECT mr.id, mr.teacher_id, mr.request_date, mr.horaire, mr.class_name,
               mr.material_description, mr.quantity, mr.selected_materials, mr.computers_needed,
               mr.notes, mr.prepared, mr.modified, mr.group_count, mr.material_prof,
               mr.request_name, mr.room_type, mr.image_url, mr.exam, mr.created_at,
               t.name as teacher_name, mr.custom_duration, mr.is_lab_test, mr.is_draft,
               mr.labo_observations
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE 1=1
    '''
    params = []
    
    if start_date:
        query += f' AND mr.request_date >= {placeholder}'
        params.append(start_date)
    
    if end_date:
        query += f' AND mr.request_date <= {placeholder}'
        params.append(end_date)
    
    if teacher_id:
        query += f' AND mr.teacher_id = {placeholder}'
        params.append(teacher_id)
    
    query += ' ORDER BY mr.request_date, mr.created_at'
    
    cursor.execute(query, params)
    requests = cursor.fetchall()
    conn.close()
    return requests


def get_material_request_by_id(request_id):
    """Get a specific material request by ID"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'''
        SELECT mr.id, mr.teacher_id, mr.request_date, mr.horaire, mr.class_name,
               mr.material_description, mr.quantity, mr.selected_materials, mr.computers_needed,
               mr.notes, mr.prepared, mr.modified, mr.group_count, mr.material_prof,
               mr.request_name, mr.room_type, mr.image_url, mr.exam, mr.created_at,
               t.name as teacher_name, mr.custom_duration, mr.is_lab_test, mr.is_draft,
               mr.labo_observations, mr.room_type_manual
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.id = {placeholder}
    ''', (request_id,))
    request = cursor.fetchone()
    conn.close()

    if not request:
        return None

    # Normaliser en dictionnaire pour compatibilité PostgreSQL/SQLite
    if isinstance(request, dict):
        return request
    elif hasattr(request, '_asdict') and callable(getattr(request, '_asdict', None)):
        return request._asdict()  # type: ignore[union-attr]
    else:
        # Tuple classique - mapping manuel selon l'ordre des colonnes SELECT
        return {
            'id': request[0],
            'teacher_id': request[1],
            'request_date': request[2],
            'horaire': request[3],
            'class_name': request[4],
            'material_description': request[5],
            'quantity': request[6],
            'selected_materials': request[7],
            'computers_needed': request[8],
            'notes': request[9],
            'prepared': request[10],
            'modified': request[11],
            'group_count': request[12],
            'material_prof': request[13],
            'request_name': request[14],
            'room_type': request[15],
            'image_url': request[16],
            'exam': request[17],
            'created_at': request[18],
            'teacher_name': request[19],
            'custom_duration': request[20] if len(request) > 20 else None,
            'is_lab_test': bool(request[21]) if len(request) > 21 and request[21] is not None else False,
            'is_draft': bool(request[22]) if len(request) > 22 and request[22] is not None else False,
            'labo_observations': request[23] if len(request) > 23 else None,
            'room_type_manual': bool(request[24]) if len(request) > 24 and request[24] is not None else False
        }


def update_material_request(request_id, teacher_id, request_date, class_name, material_description,
                           horaire=None, quantity=1, selected_materials='', computers_needed=0,
                           notes='', group_count=1, material_prof='', request_name='', custom_duration=None,
                           is_lab_test=False, image_url=None, room_type=None, labo_observations=None,
                           preserve_prepared=False):
    """Update an existing material request and mark it as modified.

    image_url=None leaves the stored image untouched (e.g. bulk edits of related
    requests don't carry an image_url) — pass a string (possibly empty) to set it.

    preserve_prepared=True laisse prepared/modified inchangés : à utiliser quand seule
    la note interne (labo_observations) change, puisque ce n'est pas un changement du
    contenu de la demande qui justifierait de redemander une préparation.
    """
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    # Coerce group_count to an integer with a safe default (0 autorisé : niveaux sans répartition en groupes)
    try:
        group_count = int(group_count) if group_count is not None else 1
        if group_count < 0:
            group_count = 0
    except Exception:
        group_count = 1

    placeholder = '%s' if db_type == 'postgresql' else '?'
    # Utiliser TRUE/FALSE pour PostgreSQL, 1/0 pour SQLite
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    true_val = 'TRUE' if db_type == 'postgresql' else '1'

    image_clause = f", image_url={placeholder}" if image_url is not None else ""
    room_type_clause = f", room_type={placeholder}, room_type_manual={true_val}" if room_type is not None else ""
    labo_obs_clause = f", labo_observations={placeholder}" if labo_observations is not None else ""
    if preserve_prepared:
        prepared_clause = ""
    elif rien_a_preparer(selected_materials, computers_needed, notes):
        prepared_clause = f"prepared={true_val}, modified={false_val}, "
    else:
        prepared_clause = f"prepared={false_val}, modified={true_val}, "
    params = [teacher_id, request_date, horaire, class_name, material_description, quantity,
              selected_materials, computers_needed, notes, group_count, material_prof, request_name, custom_duration,
              bool(is_lab_test)]
    if image_url is not None:
        params.append(image_url)
    if room_type is not None:
        params.append(room_type)
    if labo_observations is not None:
        params.append(labo_observations)
    params.append(request_id)

    cursor.execute(f'''
        UPDATE material_requests
        SET teacher_id={placeholder}, request_date={placeholder}, horaire={placeholder},
            class_name={placeholder}, material_description={placeholder}, quantity={placeholder},
            selected_materials={placeholder}, computers_needed={placeholder}, notes={placeholder},
            group_count={placeholder}, material_prof={placeholder}, request_name={placeholder}, custom_duration={placeholder},
            is_lab_test={placeholder}, {prepared_clause}is_draft={false_val}{image_clause}{room_type_clause}{labo_obs_clause}
        WHERE id={placeholder}
    ''', tuple(params))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def toggle_prepared_status(request_id):
    """Toggle the prepared status of a request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    # Get current status
    cursor.execute(f'SELECT prepared FROM material_requests WHERE id = {placeholder}', (request_id,))
    current = cursor.fetchone()
    if not current:
        conn.close()
        return False
    
    # Gérer l'accès selon le type de retour (tuple ou dict)
    if isinstance(current, dict):
        current_prepared = current['prepared']
    else:
        current_prepared = current[0]
    
    new_prepared = not current_prepared
    
    # Utiliser TRUE/FALSE pour PostgreSQL, 1/0 pour SQLite
    true_val = 'TRUE' if db_type == 'postgresql' else '1'
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    
    # When marking as prepared, remove modified flag
    # When unmarking prepared, keep modified flag as is
    if new_prepared:
        cursor.execute(f'UPDATE material_requests SET prepared={true_val}, modified={false_val} WHERE id={placeholder}', (request_id,))
    else:
        cursor.execute(f'UPDATE material_requests SET prepared={false_val} WHERE id={placeholder}', (request_id,))
    
    conn.commit()
    conn.close()
    return True


def confirm_draft_request(request_id):
    """Retire le statut 'brouillon' (cours récurrent auto-généré) d'une demande, sans autre changement."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    cursor.execute(f'UPDATE material_requests SET is_draft={false_val} WHERE id={placeholder}', (request_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_material_request(request_id):
    """Delete a material request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'DELETE FROM material_requests WHERE id = {placeholder}', (request_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def update_room_type(request_id, room_type, manual=True):
    """Update the room type of a material request.

    manual=True fige ce choix : le planning ne devinera plus la matière par mots-clés."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()

    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'UPDATE material_requests SET room_type = {placeholder}, room_type_manual = {placeholder} WHERE id = {placeholder}',
                   (room_type, bool(manual), request_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# Champs "labo" que l'on reporte sur toutes les demandes identiques (voir
# sync_field_to_related_requests) — whitelist nécessaire puisque le nom de colonne
# est interpolé dans le SQL.
SYNCABLE_REQUEST_FIELDS = {'labo_observations', 'room_type'}


def sync_field_to_related_requests(teacher_id, request_name, field_name, value, exclude_id):
    """Reporte un champ (observations labo ou salle) sur toutes les autres demandes
    identiques (même enseignant + même nom de demande), sans marquer ces demandes
    comme modifiées ni toucher à leur statut préparé — seul ce champ change. Utilisé
    pour que ces informations restent communes à tous les TPs identiques (voir
    appelant : exclut les cours réguliers, trop nombreux)."""
    if field_name not in SYNCABLE_REQUEST_FIELDS:
        raise ValueError(f'Champ non synchronisable: {field_name}')
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    true_val = 'TRUE' if db_type == 'postgresql' else '1'
    manual_clause = f", room_type_manual={true_val}" if field_name == 'room_type' else ""
    cursor.execute(f'''
        UPDATE material_requests
        SET {field_name}={placeholder}{manual_clause}
        WHERE teacher_id={placeholder} AND request_name={placeholder} AND id != {placeholder}
    ''', (value, teacher_id, request_name, exclude_id))
    conn.commit()
    conn.close()
    return cursor.rowcount
