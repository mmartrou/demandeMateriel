"""Modèles de TP, cours récurrents et brouillons de demandes générés chaque semaine."""
import logging

from .connexion import get_db_connection
from .demandes import add_material_request
from .jours import is_working_day_configured

logger = logging.getLogger(__name__)


def get_tp_templates(teacher_id, level):
    """Retourne les templates TP d'un enseignant pour un niveau donné, triés par nom."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'''
            SELECT id, request_name, material_description, selected_materials,
                   material_prof, computers_needed, group_count, notes, image_url, room_type
            FROM tp_templates
            WHERE teacher_id = {placeholder} AND level = {placeholder}
            ORDER BY request_name
        ''', (teacher_id, level))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            else:
                result.append({
                    'id': row[0], 'request_name': row[1], 'material_description': row[2],
                    'selected_materials': row[3], 'material_prof': row[4],
                    'computers_needed': row[5], 'group_count': row[6],
                    'notes': row[7], 'image_url': row[8], 'room_type': row[9]
                })
        return result
    except Exception as e:
        logger.error(f"Erreur get_tp_templates: {e}")
        return []


def upsert_tp_template(teacher_id, level, request_name, material_description,
                       selected_materials, material_prof, computers_needed,
                       group_count, notes, image_url, room_type):
    """Insère ou met à jour un template TP (clé unique: teacher_id + level + request_name)."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute('''
                INSERT INTO tp_templates
                    (teacher_id, level, request_name, material_description, selected_materials,
                     material_prof, computers_needed, group_count, notes, image_url, room_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (teacher_id, level, request_name)
                DO UPDATE SET
                    material_description = EXCLUDED.material_description,
                    selected_materials   = EXCLUDED.selected_materials,
                    material_prof        = EXCLUDED.material_prof,
                    computers_needed     = EXCLUDED.computers_needed,
                    group_count          = EXCLUDED.group_count,
                    notes                = EXCLUDED.notes,
                    image_url            = EXCLUDED.image_url,
                    room_type            = EXCLUDED.room_type,
                    updated_at           = CURRENT_TIMESTAMP
            ''', (teacher_id, level, request_name, material_description, selected_materials,
                  material_prof, computers_needed, group_count, notes, image_url, room_type))
        else:
            cursor.execute('''
                INSERT INTO tp_templates
                    (teacher_id, level, request_name, material_description, selected_materials,
                     material_prof, computers_needed, group_count, notes, image_url, room_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(teacher_id, level, request_name)
                DO UPDATE SET
                    material_description = excluded.material_description,
                    selected_materials   = excluded.selected_materials,
                    material_prof        = excluded.material_prof,
                    computers_needed     = excluded.computers_needed,
                    group_count          = excluded.group_count,
                    notes                = excluded.notes,
                    image_url            = excluded.image_url,
                    room_type            = excluded.room_type,
                    updated_at           = CURRENT_TIMESTAMP
            ''', (teacher_id, level, request_name, material_description, selected_materials,
                  material_prof, computers_needed, group_count, notes, image_url, room_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur upsert_tp_template: {e}")
        return False


def get_tp_template_by_id(template_id):
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'''
            SELECT id, teacher_id, level, request_name, material_description,
                   selected_materials, material_prof, computers_needed,
                   group_count, notes, image_url, room_type
            FROM tp_templates
            WHERE id = {placeholder}
        ''', (template_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        if isinstance(row, dict):
            return row
        return {
            'id': row[0], 'teacher_id': row[1], 'level': row[2], 'request_name': row[3],
            'material_description': row[4], 'selected_materials': row[5],
            'material_prof': row[6], 'computers_needed': row[7],
            'group_count': row[8], 'notes': row[9], 'image_url': row[10],
            'room_type': row[11]
        }
    except Exception as e:
        logger.error(f"Erreur get_tp_template_by_id: {e}")
        return None


def get_recurring_courses(teacher_id):
    """Retourne les cours récurrents (emploi du temps type) d'un enseignant, triés par jour puis horaire."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'''
            SELECT id, teacher_id, day_of_week, horaire, class_name
            FROM recurring_courses
            WHERE teacher_id = {placeholder}
            ORDER BY day_of_week, horaire
        ''', (teacher_id,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            else:
                result.append({
                    'id': row[0], 'teacher_id': row[1], 'day_of_week': row[2],
                    'horaire': row[3], 'class_name': row[4]
                })
        return result
    except Exception as e:
        logger.error(f"Erreur get_recurring_courses: {e}")
        return []


def add_recurring_course(teacher_id, day_of_week, horaire, class_name):
    """Ajoute un cours récurrent (ou remplace le niveau si le créneau jour+horaire existe déjà)."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute('''
                INSERT INTO recurring_courses (teacher_id, day_of_week, horaire, class_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (teacher_id, day_of_week, horaire)
                DO UPDATE SET class_name = EXCLUDED.class_name
                RETURNING id
            ''', (teacher_id, day_of_week, horaire, class_name))
            row = cursor.fetchone()
            new_id = (row['id'] if isinstance(row, dict) else row[0]) if row else None
        else:
            cursor.execute('''
                INSERT INTO recurring_courses (teacher_id, day_of_week, horaire, class_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(teacher_id, day_of_week, horaire)
                DO UPDATE SET class_name = excluded.class_name
            ''', (teacher_id, day_of_week, horaire, class_name))
            cursor.execute(
                'SELECT id FROM recurring_courses WHERE teacher_id = ? AND day_of_week = ? AND horaire = ?',
                (teacher_id, day_of_week, horaire)
            )
            row = cursor.fetchone()
            new_id = (row['id'] if isinstance(row, dict) else row[0]) if row else None
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        logger.error(f"Erreur add_recurring_course: {e}")
        return None


def delete_recurring_course(course_id, teacher_id):
    """Supprime un cours récurrent (scoping par teacher_id pour éviter de supprimer celui d'un autre)."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(
            f'DELETE FROM recurring_courses WHERE id = {placeholder} AND teacher_id = {placeholder}',
            (course_id, teacher_id)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    except Exception as e:
        logger.error(f"Erreur delete_recurring_course: {e}")
        return False


def generate_draft_requests_for_week(teacher_id, week_start_date, enforce_deadline=True):
    """
    Crée une demande "brouillon" (is_draft=True, 'Pas besoin de matériel') pour chaque cours
    récurrent de l'enseignant, sur la semaine commençant à week_start_date (un lundi).
    Idempotent : si une demande existe déjà pour ce teacher_id + cette date + cet horaire,
    elle n'est pas recréée.
    Un jour non-ouvré (férié / config working_days_config) ou hors délai de dépôt (2 jours
    ouvrés) est ignoré silencieusement plutôt que de créer une demande invalide.
    Retourne (nb_crees, nb_ignores).
    """
    from datetime import datetime, timedelta
    from deadline_utils import is_request_deadline_respected
    if isinstance(week_start_date, str):
        week_start = datetime.strptime(week_start_date, '%Y-%m-%d').date()
    else:
        week_start = week_start_date

    courses = get_recurring_courses(teacher_id)
    if not courses:
        return 0, 0

    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'

    created = 0
    skipped = 0
    for course in courses:
        target_date = (week_start + timedelta(days=int(course['day_of_week']))).strftime('%Y-%m-%d')

        if not is_working_day_configured(target_date):
            skipped += 1
            continue

        if enforce_deadline and not is_request_deadline_respected(target_date)['valid']:
            skipped += 1
            continue

        cursor.execute(f'''
            SELECT 1 FROM material_requests
            WHERE teacher_id = {placeholder} AND request_date = {placeholder} AND horaire = {placeholder}
        ''', (teacher_id, target_date, course['horaire']))
        if cursor.fetchone():
            skipped += 1
            continue
        add_material_request(
            teacher_id=teacher_id,
            request_date=target_date,
            class_name=course['class_name'],
            material_description='Cours théorique sans matériel',
            horaire=course['horaire'],
            selected_materials='Pas besoin de matériel',
            request_name=f"{course['class_name']} (cours régulier)",
            is_draft=True
        )
        created += 1
    conn.close()
    return created, skipped
