"""Données du planning d'une journée, plannings sauvegardés et occupation standard."""
import logging

from .connexion import get_db_connection

logger = logging.getLogger(__name__)


def get_planning_data(date_str):
    """Get all material requests for planning generation on a specific date"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()

    placeholder = '%s' if db_type == 'postgresql' else '?'
    false_val = 'FALSE' if db_type == 'postgresql' else '0'

    cursor.execute(f'''
        SELECT mr.id, mr.teacher_id, mr.request_date, mr.horaire, mr.class_name,
               mr.material_description, mr.quantity, mr.selected_materials, mr.computers_needed,
               mr.notes, mr.prepared, mr.modified, mr.group_count, mr.material_prof,
               mr.request_name, mr.room_type, mr.image_url, mr.exam, mr.created_at,
               t.name as teacher_name, mr.custom_duration, mr.labo_observations, mr.room_type_manual
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.request_date = {placeholder}
        AND mr.selected_materials != 'Absent'
        AND (mr.is_lab_test = {false_val} OR mr.is_lab_test IS NULL)
        ORDER BY mr.horaire, mr.created_at
    ''', (date_str,))
    requests = cursor.fetchall()
    conn.close()
    return requests


def get_saved_planning(date_str):
    """Retourne le planning sauvegardé (dict) pour une date, ou None si absent."""
    import json
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT data FROM plannings WHERE date = {placeholder}', (date_str,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    raw = row['data'] if isinstance(row, dict) else row[0]
    return json.loads(raw) if isinstance(raw, str) else raw


def get_planning_observations(date_str):
    """Retourne les observations (notes internes) du planning sauvegardé pour une date."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    try:
        cursor.execute(f'SELECT observations FROM plannings WHERE date = {placeholder}', (date_str,))
    except Exception:
        conn.close()
        return ''
    row = cursor.fetchone()
    conn.close()
    if not row:
        return ''
    obs = row['observations'] if isinstance(row, dict) else row[0]
    return obs or ''


def get_lab_test_requests(date_str):
    """Liste les demandes 'Test au labo' (sans salle attribuée) pour une date."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    true_val = 'TRUE' if db_type == 'postgresql' else '1'
    cursor.execute(f'''
        SELECT mr.horaire, mr.class_name, mr.request_name, t.name as teacher_name, mr.material_description
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.request_date = {placeholder} AND mr.is_lab_test = {true_val}
        ORDER BY mr.horaire, mr.created_at
    ''', (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) if hasattr(r, 'keys') else
            {'horaire': r[0], 'class_name': r[1], 'request_name': r[2], 'teacher_name': r[3],
             'material_description': r[4]}
            for r in rows]


def get_labo_observations_map(request_ids):
    """Retourne {request_id: labo_observations} pour une liste d'IDs de demandes."""
    if not request_ids:
        return {}
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    placeholders_list = ','.join([placeholder] * len(request_ids))
    cursor.execute(f'SELECT id, labo_observations FROM material_requests WHERE id IN ({placeholders_list})', request_ids)
    result = {}
    for r in cursor.fetchall():
        rid = r['id'] if isinstance(r, dict) else r[0]
        labo_obs = r['labo_observations'] if isinstance(r, dict) else r[1]
        result[rid] = labo_obs or ''
    conn.close()
    return result


def get_standard_occupation(day_of_week):
    """
    Récupère l'occupation standard (nombre de cours attendus) pour chaque créneau d'un jour donné

    Args:
        day_of_week (str): Jour de la semaine (lundi, mardi, mercredi, jeudi, vendredi)

    Returns:
        dict: {slot: value}
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()

        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'SELECT slot, value FROM standard_occupation WHERE day_of_week = {placeholder}', (day_of_week,))
        rows = cursor.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}

    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'occupation standard {day_of_week}: {e}")
        return {}


def set_standard_occupation(day_of_week, slot, value):
    """
    Enregistre (ou supprime si value est None) l'occupation standard d'un créneau donné

    Args:
        day_of_week (str): Jour de la semaine (lundi, mardi, mercredi, jeudi, vendredi)
        slot (str): Créneau horaire (ex: '9h00')
        value (int|None): Nombre de cours attendus, ou None pour effacer la valeur

    Returns:
        bool: True si succès, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()

        placeholder = '%s' if db_type == 'postgresql' else '?'

        if value is None:
            cursor.execute(f'''
                DELETE FROM standard_occupation WHERE day_of_week = {placeholder} AND slot = {placeholder}
            ''', (day_of_week, slot))
        elif db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO standard_occupation (day_of_week, slot, value)
                VALUES ({placeholder}, {placeholder}, {placeholder})
                ON CONFLICT(day_of_week, slot) DO UPDATE SET value = EXCLUDED.value
            ''', (day_of_week, slot, value))
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO standard_occupation (day_of_week, slot, value)
                VALUES ({placeholder}, {placeholder}, {placeholder})
            ''', (day_of_week, slot, value))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'occupation standard {day_of_week} {slot}: {e}")
        return False
