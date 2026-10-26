"""Enseignants, niveaux, comptes Google (users) et effectifs."""
import logging
import sqlite3
import unicodedata

from .connexion import get_db_connection

logger = logging.getLogger(__name__)


def add_teacher(name):
    """Add a new teacher. Returns the new teacher's id."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    if db_type == 'postgresql':
        cursor.execute(f'INSERT INTO teachers (name) VALUES ({placeholder}) RETURNING id', (name.strip(),))
        row = cursor.fetchone()
        new_id = row[0] if row else None
    else:
        cursor.execute(f'INSERT INTO teachers (name) VALUES ({placeholder})', (name.strip(),))
        new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def delete_teacher(teacher_id):
    """Delete a teacher. Returns number of associated requests (informational)."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT COUNT(*) FROM material_requests WHERE teacher_id = {placeholder}', (teacher_id,))
    row = cursor.fetchone()
    request_count = row[0] if row else 0
    cursor.execute(f'DELETE FROM teachers WHERE id = {placeholder}', (teacher_id,))
    conn.commit()
    conn.close()
    return request_count


def get_all_teachers():
    """Get all teachers from the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, short_name FROM teachers ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        if isinstance(row, dict):
            result.append({'id': row['id'], 'name': row['name'], 'short_name': row.get('short_name') or ''})
        elif isinstance(row, sqlite3.Row):
            result.append({'id': row['id'], 'name': row['name'], 'short_name': row['short_name'] or ''})
        else:
            result.append({'id': row[0], 'name': row[1], 'short_name': row[2] or '' if len(row) > 2 else ''})
    return result


def update_teacher_short_name(teacher_id, short_name):
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'UPDATE teachers SET short_name={placeholder} WHERE id={placeholder}',
                   (short_name or None, teacher_id))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_all_levels():
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, short_name, default_duration, display_order, default_groups FROM levels ORDER BY display_order, name')
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        # dict (PostgreSQL), sqlite3.Row et tuple s'indexent tous par position.
        values = list(row.values()) if isinstance(row, dict) else list(row)
        groups = values[5]
        result.append({'id': values[0], 'name': values[1], 'short_name': values[2] or '',
                       'default_duration': values[3] or 85, 'display_order': values[4] or 0,
                       'default_groups': 1 if groups is None else groups})
    return result


def add_level(name):
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT COALESCE(MAX(display_order), 0) + 1 FROM levels')
    next_order = cursor.fetchone()[0]
    if db_type == 'postgresql':
        cursor.execute(f'INSERT INTO levels (name, display_order) VALUES ({placeholder},{placeholder}) RETURNING id', (name, next_order))
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute(f'INSERT INTO levels (name, display_order) VALUES ({placeholder},{placeholder})', (name, next_order))
        new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def delete_level(level_id):
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'DELETE FROM levels WHERE id={placeholder}', (level_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def update_level(level_id, short_name=None, default_duration=None, display_order=None, default_groups=None):
    """Met à jour uniquement les champs fournis (None = inchangé). Pour effacer le nom
    court, passer une chaîne vide."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    sets = []
    params = []
    if short_name is not None:
        sets.append(f'short_name={placeholder}')
        params.append(short_name or None)
    if default_duration is not None:
        sets.append(f'default_duration={placeholder}')
        params.append(int(default_duration))
    if display_order is not None:
        sets.append(f'display_order={placeholder}')
        params.append(int(display_order))
    if default_groups is not None:
        sets.append(f'default_groups={placeholder}')
        params.append(max(0, int(default_groups)))
    if not sets:
        conn.close()
        return False
    params.append(level_id)
    cursor.execute(f'UPDATE levels SET {", ".join(sets)} WHERE id={placeholder}', tuple(params))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def _normalize_name(s):
    """Lowercase + strip accents for case/accent-insensitive comparison."""
    return unicodedata.normalize('NFD', s.strip().lower()).encode('ascii', 'ignore').decode('ascii')


def find_teacher_id_by_name(teacher_name):
    """Find teacher ID by name (case and accent insensitive)."""
    if not teacher_name:
        return None
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM teachers')
    rows = cursor.fetchall()
    conn.close()
    target = _normalize_name(teacher_name)
    for row in rows:
        db_name = row['name'] if isinstance(row, dict) else row[1]
        if _normalize_name(db_name) == target:
            return row['id'] if isinstance(row, dict) else row[0]
    return None


def get_user_by_email(email):
    """Get user by email address."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'''
        SELECT u.id, u.google_sub, u.email, u.full_name, u.role, u.teacher_id, t.name AS teacher_name
        FROM users u
        LEFT JOIN teachers t ON t.id = u.teacher_id
        WHERE u.email = {placeholder}
    ''', (email,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if isinstance(row, dict):
        return row
    return {
        'id': row[0],
        'google_sub': row[1],
        'email': row[2],
        'full_name': row[3],
        'role': row[4],
        'teacher_id': row[5],
        'teacher_name': row[6]
    }


def upsert_user(google_sub, email, full_name, role='teacher', teacher_id=None):
    """Create or update user account linked to Google identity."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'

    if db_type == 'postgresql':
        cursor.execute(f'''
            INSERT INTO users (google_sub, email, full_name, role, teacher_id)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            ON CONFLICT(email)
            DO UPDATE SET
                google_sub = EXCLUDED.google_sub,
                full_name = EXCLUDED.full_name,
                role = EXCLUDED.role,
                teacher_id = EXCLUDED.teacher_id,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        ''', (google_sub, email, full_name, role, teacher_id))
        row = cursor.fetchone()
        user_id = row[0] if row else None
    else:
        cursor.execute(f'''
            INSERT INTO users (google_sub, email, full_name, role, teacher_id)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            ON CONFLICT(email)
            DO UPDATE SET
                google_sub=excluded.google_sub,
                full_name=excluded.full_name,
                role=excluded.role,
                teacher_id=excluded.teacher_id,
                updated_at=CURRENT_TIMESTAMP
        ''', (google_sub, email, full_name, role, teacher_id))
        user_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return user_id


def pre_associate_teacher(email, teacher_id):
    """Admin: associate an email with a teacher_id before first login."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    email_clean = email.strip().lower()

    cursor.execute(f'SELECT id FROM users WHERE email = {placeholder}', (email_clean,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(f'UPDATE users SET teacher_id = {placeholder} WHERE email = {placeholder}',
                       (teacher_id, email_clean))
    else:
        fake_sub = f'__admin_link__{email_clean}'
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO users (google_sub, email, role, teacher_id)
                VALUES ({placeholder}, {placeholder}, 'teacher', {placeholder})
                ON CONFLICT(email) DO UPDATE SET teacher_id = EXCLUDED.teacher_id
            ''', (fake_sub, email_clean, teacher_id))
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO users (google_sub, email, role, teacher_id)
                VALUES ({placeholder}, {placeholder}, 'teacher', {placeholder})
            ''', (fake_sub, email_clean, teacher_id))

    conn.commit()
    conn.close()


def delete_user(user_id):
    """Delete a user account association (Google login link). Returns True if a row was deleted."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'DELETE FROM users WHERE id = {placeholder}', (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_all_users():
    """Return all users with their linked teacher name."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.email, u.full_name, u.role, u.teacher_id, t.name AS teacher_name
        FROM users u
        LEFT JOIN teachers t ON t.id = u.teacher_id
        ORDER BY u.email
    ''')
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        if isinstance(row, dict):
            result.append(dict(row))
        else:
            result.append({
                'id': row[0], 'email': row[1], 'full_name': row[2],
                'role': row[3], 'teacher_id': row[4], 'teacher_name': row[5]
            })
    return result


def get_all_student_numbers():
    """Get all student numbers from the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM student_numbers ORDER BY teacher_name')
    students = cursor.fetchall()
    conn.close()
    
    # Convert rows to dictionaries
    students_list = []
    for student in students:
        students_list.append({
            'id': student[0],
            'teacher_name': student[1],
            'student_count': student[2],
            'level': student[3]
        })
    
    return students_list


def update_student_number(student_id, student_data):
    """Update student number in the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    try:
        cursor.execute(f'''
            UPDATE student_numbers SET 
                teacher_name = {placeholder}, student_count = {placeholder}, level = {placeholder}
            WHERE id = {placeholder}
        ''', (
            student_data.get('teacher_name'),
            student_data.get('student_count', 20),
            student_data.get('level', '2nde'),
            student_id
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de la mise à jour de l'effectif: {e}")
        return False


def add_student_number(teacher_name, student_count, level='2nde'):
    """Add a new student number entry"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    placeholders = ', '.join([placeholder] * 3)
    
    try:
        cursor.execute(f'''
            INSERT INTO student_numbers (teacher_name, student_count, level) 
            VALUES ({placeholders})
        ''', (teacher_name, student_count, level))
        conn.commit()
        student_id = cursor.lastrowid
        conn.close()
        return student_id
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de l'ajout de l'effectif: {e}")
        return None


def delete_student_number(student_id):
    """Delete a student number entry"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    try:
        cursor.execute(f'DELETE FROM student_numbers WHERE id = {placeholder}', (student_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"Erreur lors de la suppression de l'effectif: {e}")
        return False


def get_student_count_for_teacher(teacher_name, level):
    """Get student count for a specific teacher and level"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    cursor.execute(f'''
        SELECT student_count FROM student_numbers 
        WHERE teacher_name = {placeholder} AND level = {placeholder}
    ''', (teacher_name, level))
    result = cursor.fetchone()
    conn.close()
    if not result:
        return 20  # Default fallback
    return result['student_count'] if isinstance(result, (dict, sqlite3.Row)) else result[0]
