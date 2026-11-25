"""Données du planning d'une journée, plannings sauvegardés et occupation standard."""
import json
import logging
import re

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


# --- Édition à plusieurs : numéro de version du planning ----------------------------------------------
# Un planning enregistré (table `plannings`) porte un numéro de version, augmenté de 1 à chaque
# modification (enregistrement complet, déplacement d'un cours, observations). Chaque poste de
# l'éditeur le compare régulièrement au sien pour savoir si un collègue a modifié le planning, et
# les enregistrements « complets » sont refusés s'ils partent d'une version périmée : on ne peut
# donc pas écraser sans le savoir le travail d'un autre. Les requêtes ci-dessous sont conditionnelles
# (UPDATE ... WHERE version = ...) plutôt que verrouillées : elles fonctionnent à l'identique sur
# PostgreSQL et SQLite, sans transaction ouverte.

TEMP_STORAGE_ID = '__TEMP__'  # « salle » virtuelle de l'éditeur (stockage temporaire d'un cours)
_FORMAT_CRENEAU = re.compile(r'^\d{1,2}h\d{2}$')
_ESSAIS_DEPLACEMENT = 5


def _ligne_retournee(cursor):
    """Première ligne renvoyée par un INSERT/UPDATE ... RETURNING, ou None. Le résultat est lu en entier
    (SQLite n'aime pas qu'on valide une transaction dont la requête n'est pas terminée)."""
    lignes = cursor.fetchall()
    return lignes[0] if lignes else None


def get_planning_version(date_str):
    """Retourne (version, existe) du planning d'une date : (0, False) s'il n'a jamais été enregistré."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT version FROM plannings WHERE date = {placeholder}', (date_str,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 0, False
    return int(row[0] or 0), True


def save_planning(date_str, planning_data, base_version=None):
    """Enregistre le planning complet d'une date.

    base_version : version du planning sur laquelle l'appelant s'est appuyé.
      - None : enregistrement sans condition (génération d'un nouveau planning, par exemple) ;
      - un entier : refusé si le planning a changé depuis (0 = « il n'existait pas encore »).
    Retourne (True, nouvelle_version) ou (False, version_actuelle) en cas de conflit."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    ph = '%s' if db_type == 'postgresql' else '?'
    data_json = json.dumps(planning_data)
    try:
        if base_version is None:
            cursor.execute(f'''
                INSERT INTO plannings (date, data, version) VALUES ({ph}, {ph}, 1)
                ON CONFLICT(date) DO UPDATE SET data = EXCLUDED.data, version = plannings.version + 1
                RETURNING version
            ''', (date_str, data_json))
            return True, int(_ligne_retournee(cursor)[0])

        cursor.execute(f'''
            UPDATE plannings SET data = {ph}, version = version + 1
            WHERE date = {ph} AND version = {ph}
            RETURNING version
        ''', (data_json, date_str, base_version))
        row = _ligne_retournee(cursor)
        if row is None and base_version == 0:
            # Aucune ligne à mettre à jour : si le planning n'existait pas, on le crée ; si un collègue
            # vient de le créer entre-temps, DO NOTHING ne renvoie rien et c'est un conflit.
            cursor.execute(f'''
                INSERT INTO plannings (date, data, version) VALUES ({ph}, {ph}, 1)
                ON CONFLICT(date) DO NOTHING
                RETURNING version
            ''', (date_str, data_json))
            row = _ligne_retournee(cursor)
        if row is not None:
            return True, int(row[0])
    finally:
        conn.commit()
        conn.close()
    return False, get_planning_version(date_str)[0]


def move_course(date_str, course_id, room, time_slot, extra_rooms=()):
    """Déplace un cours dans le planning enregistré (salle et horaire de début).

    Le déplacement est appliqué à la version la PLUS RÉCENTE du planning, pas à la copie qu'avait
    l'éditeur de l'appelant : deux techniciens qui déplacent deux cours différents en même temps
    ne s'écrasent donc pas. Si les deux déplacent le même cours, le dernier arrivé l'emporte.

    extra_rooms : noms de salles valides en plus de celles enregistrées dans le planning.
    Retourne (statut, version) ; statut vaut 'ok', 'planning_introuvable', 'cours_introuvable',
    'salle_inconnue', 'creneau_invalide' ou 'conflit' (trop de modifications simultanées)."""
    if not isinstance(time_slot, str) or not _FORMAT_CRENEAU.match(time_slot):
        return 'creneau_invalide', 0
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    ph = '%s' if db_type == 'postgresql' else '?'
    try:
        for _ in range(_ESSAIS_DEPLACEMENT):
            cursor.execute(f'SELECT data, version FROM plannings WHERE date = {ph}', (date_str,))
            row = cursor.fetchone()
            if not row:
                return 'planning_introuvable', 0
            version = int(row[1] or 0)
            planning = json.loads(row[0]) if isinstance(row[0], str) else row[0]

            cours = next((c for c in planning.get('courses', []) if str(c.get('id')) == str(course_id)), None)
            if cours is None:
                return 'cours_introuvable', version
            salles = {s.get('name') for s in planning.get('rooms') or []} | set(extra_rooms) | {TEMP_STORAGE_ID}
            if room not in salles:
                return 'salle_inconnue', version

            cours['room'] = room
            cours['time'] = time_slot
            planning.setdefault('room_assignments', {})[str(cours['id'])] = room

            cursor.execute(f'''
                UPDATE plannings SET data = {ph}, version = version + 1
                WHERE date = {ph} AND version = {ph}
                RETURNING version
            ''', (json.dumps(planning), date_str, version))
            row = _ligne_retournee(cursor)
            if row is not None:
                return 'ok', int(row[0])
            # Un autre enregistrement est passé entre la lecture et l'écriture : on recommence
            # avec la version à jour.
        return 'conflit', version
    finally:
        conn.commit()
        conn.close()


def set_planning_observations(date_str, observations):
    """Enregistre les observations du planning d'une date (crée la ligne si besoin) ; retourne la nouvelle version."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    ph = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'''
        INSERT INTO plannings (date, data, observations, version) VALUES ({ph}, {ph}, {ph}, 1)
        ON CONFLICT(date) DO UPDATE SET observations = EXCLUDED.observations, version = plannings.version + 1
        RETURNING version
    ''', (date_str, '{}', observations))
    version = int(_ligne_retournee(cursor)[0])
    conn.commit()
    conn.close()
    return version


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
