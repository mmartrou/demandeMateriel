import sqlite3
import psycopg2
import psycopg2.extras
import os
import logging
from datetime import datetime

# Configuration des logs
logger = logging.getLogger(__name__)

# Base de données SQLite dans un sous-dossier du dossier Google Drive (fallback local)
DATABASE_PATH = os.path.join('imagesDemandesMateriel', 'base', 'material_requests.db')

def get_db_connection():
    """Get database connection - PostgreSQL en priorité, SQLite en fallback"""
    
    # Essayer PostgreSQL d'abord
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        try:
            logger.info("Tentative de connexion PostgreSQL")
            conn = psycopg2.connect(database_url)
            conn.autocommit = True
            logger.info("Connexion PostgreSQL réussie")
            return conn, 'postgresql'
        except Exception as e:
            logger.warning(f"Échec PostgreSQL: {e}")
    
    # Fallback vers SQLite dans Google Drive
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    logger.info(f"Fallback vers SQLite: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn, 'sqlite'

def init_database():
    """Initialize the database with required tables"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    # Adapter la syntaxe selon le type de base de données
    if db_type == 'postgresql':
        auto_increment = 'SERIAL PRIMARY KEY'
        text_type = 'TEXT'
        timestamp_default = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    else:  # SQLite
        auto_increment = 'INTEGER PRIMARY KEY AUTOINCREMENT'
        text_type = 'TEXT'
        timestamp_default = 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    
    # Create teachers table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS teachers (
            id {auto_increment},
            name {text_type} NOT NULL UNIQUE,
            created_at {timestamp_default}
        )
    ''')
    
    # Create material requests table with all columns
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS material_requests (
            id {auto_increment},
            teacher_id INTEGER NOT NULL,
            request_date DATE NOT NULL,
            horaire {text_type},
            class_name {text_type} NOT NULL,
            material_description {text_type} NOT NULL,
            quantity INTEGER DEFAULT 1,
            selected_materials {text_type},
            computers_needed INTEGER DEFAULT 0,
            notes {text_type},
            prepared BOOLEAN DEFAULT FALSE,
            modified BOOLEAN DEFAULT FALSE,
            group_count INTEGER DEFAULT 1,
            material_prof {text_type},
            request_name {text_type},
            room_type {text_type} DEFAULT 'Mixte',
            image_url {text_type},
            exam BOOLEAN DEFAULT FALSE,
            created_at {timestamp_default},
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    ''')
    
    # Ajout des colonnes manquantes si elles n'existent pas (pour migration)
    columns_to_add = [
        ('horaire', 'TEXT'),
        ('selected_materials', 'TEXT'),
        ('computers_needed', 'INTEGER DEFAULT 0'),
        ('prepared', 'BOOLEAN DEFAULT FALSE'),
        ('modified', 'BOOLEAN DEFAULT FALSE'),
        ('room_type', 'TEXT DEFAULT "Mixte"'),
        ('exam', 'BOOLEAN DEFAULT FALSE'),
        ('group_count', 'INTEGER DEFAULT 1'),
        ('material_prof', 'TEXT'),
        ('request_name', 'TEXT'),
        ('image_url', 'TEXT')
    ]
    
    for column_name, column_type in columns_to_add:
        # Vérification préalable pour PostgreSQL
        if db_type == 'postgresql':
            cursor.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name='material_requests' AND column_name=%s
            """, (column_name,))
            exists = cursor.fetchone() is not None
            if exists:
                continue
        try:
            cursor.execute(f'ALTER TABLE material_requests ADD COLUMN {column_name} {column_type}')
        except (sqlite3.OperationalError, psycopg2.errors.DuplicateColumn):
            pass  # Column already exists
    
    
    # Create rooms table for planning
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS rooms (
            id {auto_increment},
            name {text_type} NOT NULL UNIQUE,
            type {text_type} NOT NULL,
            ordinateurs INTEGER DEFAULT 0,
            chaises INTEGER DEFAULT 0,
            eviers INTEGER DEFAULT 0,
            hotte INTEGER DEFAULT 0,
            bancs_optiques INTEGER DEFAULT 0,
            oscilloscopes INTEGER DEFAULT 0,
            becs_electriques INTEGER DEFAULT 0,
            support_filtration INTEGER DEFAULT 0,
            imprimante INTEGER DEFAULT 0,
            examen INTEGER DEFAULT 0,
            created_at {timestamp_default}
        )
    ''')
    
    # Create student numbers table for 2nd level classes
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS student_numbers (
            id {auto_increment},
            teacher_name {text_type} NOT NULL UNIQUE,
            student_count INTEGER NOT NULL DEFAULT 20,
            level {text_type} DEFAULT '2nde',
            created_at {timestamp_default}
        )
    ''')
    
    # Create working days configuration table
    default_working_day = 'TRUE' if db_type == 'postgresql' else '1'
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS working_days_config (
            id {auto_increment},
            date DATE NOT NULL UNIQUE,
            is_working_day BOOLEAN NOT NULL DEFAULT {default_working_day},
            description {text_type},
            created_at {timestamp_default},
            updated_at {timestamp_default}
        )
    ''')

    # Create C21 availability table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS c21_availability (
            id {auto_increment},
            jour {text_type} NOT NULL,
            heure_debut {text_type} NOT NULL,
            heure_fin {text_type} NOT NULL,
            created_at {timestamp_default},
            UNIQUE(jour, heure_debut, heure_fin)
        )
    ''')

    # Create pending modifications table for tracking changes before validation
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS pending_modifications (
            id {auto_increment},
            request_id INTEGER NOT NULL,
            field_name {text_type} NOT NULL,
            original_value {text_type},
            new_value {text_type},
            created_at {timestamp_default},
            modified_by {text_type},
            FOREIGN KEY (request_id) REFERENCES material_requests(id) ON DELETE CASCADE
        )
    ''')
    
    # Add a new table for storing planning data
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS plannings (
            date {text_type} PRIMARY KEY,
            data {text_type} NOT NULL
        );
    ''')
    
    # Insert sample data if tables are empty
    cursor.execute('SELECT COUNT(*) FROM rooms')
    if cursor.fetchone()[0] == 0:
        sample_rooms = [
            # PHYSIQUE (ordre demandé: C23, C25, C27, C22, C24)
            ('C23', 'physique', 10, 53, 0, 0, 0, 0, 0, 0, 0, 1),
            ('C25', 'physique', 20, 40, 0, 0, 1, 0, 0, 0, 0, 0),
            ('C27', 'physique', 20, 40, 0, 0, 0, 1, 0, 0, 1, 0),
            ('C22', 'mixte', 10, 29, 5, 1, 0, 0, 0, 0, 0, 0),
            ('C24', 'mixte', 20, 30, 10, 0, 0, 0, 0, 0, 0, 0),
            # CHIMIE (ordre demandé: C32, C33, C31)
            ('C32', 'chimie', 10, 32, 10, 1, 0, 0, 1, 1, 0, 0),
            ('C33', 'chimie', 10, 25, 10, 1, 0, 0, 1, 1, 1, 0),
            ('C31', 'chimie', 10, 30, 10, 1, 0, 0, 1, 1, 0, 0),
            # C21 séparée (à la fin)
            ('C21', 'mixte', 0, 40, 0, 0, 0, 0, 0, 0, 0, 1),
        ]
        
        placeholders = ', '.join(['%s' if db_type == 'postgresql' else '?'] * 12)
        cursor.executemany(f'''
            INSERT INTO rooms (name, type, ordinateurs, chaises, eviers, hotte, 
                             bancs_optiques, oscilloscopes, becs_electriques, 
                             support_filtration, imprimante, examen) 
            VALUES ({placeholders})
        ''', sample_rooms)
    
    # Insert sample student numbers if table is empty
    cursor.execute('SELECT COUNT(*) FROM student_numbers')
    if cursor.fetchone()[0] == 0:
        sample_students = [
            ('Bonfand', 29, '2nde'),
            ('Carpentier', 27, '2nde'),
            ('Courreges', 28, '2nde'),
            ('Landspurg', 30, '2nde'),
            ('Lefranc', 30, '2nde'),
            ('Martrou', 25, '2nde'),
            ('Masnou', 30, '2nde'),
            ('Moreau', 30, '2nde'),
            ('Paupy', 27, '2nde'),
            ('Richard', 29, '2nde'),
            ('Vila', 30, '2nde'),
        ]
        student_placeholders = ', '.join(['%s' if db_type == 'postgresql' else '?'] * 3)
        cursor.executemany(f'''
            INSERT INTO student_numbers (teacher_name, student_count, level) 
            VALUES ({student_placeholders})
        ''', sample_students)
    
    # Insert sample teachers if table is empty
    cursor.execute('SELECT COUNT(*) FROM teachers')
    if cursor.fetchone()[0] == 0:
        sample_teachers = [
            ('Bats',),
            ('Bonfand',),
            ('Calazel',),
            ('Carpentier',),
            ('Courrèges',),
            ('Diaz Del Pino',),
            ('Hidalgo',),
            ('Landspurg',),
            ('Lefranc',),
            ('Martrou',),
            ('Masnou',),
            ('Mazy',),
            ('Moreau',),
            ('Paupy',),
            ('Potier',),
            ('Richard',),
            ('Vernudachi',),
            ('Vila Gisbert',),
        ]
        teacher_placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.executemany(f'INSERT INTO teachers (name) VALUES ({teacher_placeholder})', sample_teachers)
    
    conn.commit()
    conn.close()

# Fonctions de base de données SQLite

def get_all_teachers():
    """Get all teachers from the database"""
    conn, db_type = get_db_connection()
    if db_type == 'postgresql':
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM teachers ORDER BY name')
        rows = cursor.fetchall()
        # rows is a list of tuples (id, name)
        teachers = [{'id': row[0], 'name': row[1]} for row in rows]
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM teachers ORDER BY name')
        rows = cursor.fetchall()
        # rows is a list of sqlite3.Row or tuples
        teachers = [{'id': row['id'], 'name': row['name']} if isinstance(row, sqlite3.Row) else {'id': row[0], 'name': row[1]} for row in rows]
    print("DEBUG teachers:", teachers)
    conn.close()
    return teachers

def add_material_request(teacher_id, request_date, class_name, material_description, 
                        horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                        notes='', exam=False, group_count=1, material_prof='', request_name='', image_url=''):
    """Add a new material request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ', '.join(['%s' if db_type == 'postgresql' else '?'] * 14)
    cursor.execute(f'''
        INSERT INTO material_requests 
        (teacher_id, request_date, horaire, class_name, material_description, quantity, 
         selected_materials, computers_needed, notes, exam, group_count, material_prof, request_name, image_url)
        VALUES ({placeholders})
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity, 
          selected_materials, computers_needed, notes, exam, group_count, material_prof, request_name, image_url))
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
               t.name as teacher_name
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

def get_requests_for_calendar():
    """Get all requests formatted for calendar display"""
    conn, _ = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mr.id, mr.request_date, mr.class_name, mr.material_description, 
               mr.quantity, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        ORDER BY mr.request_date
    ''')
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
               t.name as teacher_name
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
    elif hasattr(request, '_asdict'):
        return request._asdict()
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
            'teacher_name': request[19]
        }

def update_material_request(request_id, teacher_id, request_date, class_name, material_description, 
                           horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                           notes='', group_count=1, material_prof='', request_name=''):
    """Update an existing material request and mark it as modified"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    # Utiliser TRUE/FALSE pour PostgreSQL, 1/0 pour SQLite
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    true_val = 'TRUE' if db_type == 'postgresql' else '1'
    
    cursor.execute(f'''
        UPDATE material_requests 
        SET teacher_id={placeholder}, request_date={placeholder}, horaire={placeholder}, 
            class_name={placeholder}, material_description={placeholder}, quantity={placeholder}, 
            selected_materials={placeholder}, computers_needed={placeholder}, notes={placeholder}, 
            group_count={placeholder}, material_prof={placeholder}, request_name={placeholder}, prepared={false_val}, modified={true_val}
        WHERE id={placeholder}
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity, 
          selected_materials, computers_needed, notes, group_count, material_prof, request_name, request_id))
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

def get_grouped_requests_by_name(teacher_id, request_name):
    """Get all requests with the same name from the same teacher, grouped by date/time"""
    if not request_name or not request_name.strip():
        return []
        
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'''
        SELECT request_date, horaire, class_name
        FROM material_requests 
        WHERE teacher_id = {placeholder} AND request_name = {placeholder}
        ORDER BY request_date, horaire
    ''', (teacher_id, request_name.strip()))
    
    results = cursor.fetchall()
    conn.close()
    
    if db_type == 'postgresql':
        return [dict(row) for row in results]
    else:
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in results]

def update_room_type(request_id, room_type):
    """Update the room type of a material request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'UPDATE material_requests SET room_type = {placeholder} WHERE id = {placeholder}', (room_type, request_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def get_all_rooms():
    """Get all rooms from the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM rooms ORDER BY name')
    rooms = cursor.fetchall()
    conn.close()
    
    # Convert rows to dictionaries
    rooms_list = []
    for room in rooms:
        rooms_list.append({
            'id': room[0],
            'name': room[1],
            'type': room[2],
            'ordinateurs': room[3],
            'chaises': room[4],
            'eviers': room[5],
            'hotte': room[6],
            'bancs_optiques': room[7],
            'oscilloscopes': room[8],
            'becs_electriques': room[9],
            'support_filtration': room[10],
            'imprimante': room[11],
            'examen': room[12]
        })
    
    return rooms_list

def update_room(room_id, room_data):
    """Update a room in the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    placeholders = ', '.join([placeholder] * 13)
    
    try:
        cursor.execute(f'''
            UPDATE rooms SET 
                name = {placeholder}, type = {placeholder}, ordinateurs = {placeholder}, 
                chaises = {placeholder}, eviers = {placeholder}, hotte = {placeholder}, 
                bancs_optiques = {placeholder}, oscilloscopes = {placeholder}, 
                becs_electriques = {placeholder}, support_filtration = {placeholder}, 
                imprimante = {placeholder}, examen = {placeholder}
            WHERE id = {placeholder}
        ''', (
            room_data.get('name'),
            room_data.get('type'),
            room_data.get('ordinateurs', 0),
            room_data.get('chaises', 0),
            room_data.get('eviers', 0),
            room_data.get('hotte', 0),
            room_data.get('bancs_optiques', 0),
            room_data.get('oscilloscopes', 0),
            room_data.get('becs_electriques', 0),
            room_data.get('support_filtration', 0),
            room_data.get('imprimante', 0),
            room_data.get('examen', 0),
            room_id
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de la mise à jour de la salle: {e}")
        return False

def import_rooms_from_csv_content(csv_content):
    """Import rooms from CSV content, replacing existing rooms"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    try:
        import csv as csv_module
        import io
        
        # Clear existing rooms
        cursor.execute('DELETE FROM rooms')
        
        # Parse CSV content
        csv_reader = csv_module.reader(io.StringIO(csv_content))
        rooms_data = []
        
        for row in csv_reader:
            # Skip comments and empty lines
            if not row or row[0].startswith('#') or len(row) < 12:
                continue
            
            # Parse room data
            rooms_data.append((
                row[0],  # name
                row[1],  # type
                int(row[2]),  # ordinateurs
                int(row[3]),  # chaises
                int(row[4]),  # eviers
                int(row[5]),  # hotte
                int(row[6]),  # bancs_optiques
                int(row[7]),  # oscilloscopes
                int(row[8]),  # becs_electriques
                int(row[9]),  # support_filtration
                int(row[10]), # imprimante
                int(row[11])  # examen
            ))
        
        # Insert new rooms with proper placeholders
        placeholder = '%s' if db_type == 'postgresql' else '?'
        placeholders = ', '.join([placeholder] * 12)
        
        for room_data in rooms_data:
            cursor.execute(f'''
                INSERT INTO rooms (name, type, ordinateurs, chaises, eviers, hotte, 
                                 bancs_optiques, oscilloscopes, becs_electriques, 
                                 support_filtration, imprimante, examen) 
                VALUES ({placeholders})
            ''', room_data)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de l'import CSV: {e}")
        raise e

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
    return result['student_count'] if result else 20  # Default fallback

def get_planning_data(date_str):
    """Get all material requests for planning generation on a specific date"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    cursor.execute(f'''
        SELECT mr.*, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.request_date = {placeholder}
        AND mr.selected_materials != 'Enseignant absent'
        ORDER BY mr.horaire, mr.created_at
    ''', (date_str,))
    requests = cursor.fetchall()
    conn.close()
    return requests

# === GESTION DES JOURS OUVRÉS ===

def get_working_days_config(start_date=None, end_date=None):
    """
    Récupère la configuration des jours ouvrés pour une période donnée
    
    Args:
        start_date (str, optional): Date de début au format YYYY-MM-DD
        end_date (str, optional): Date de fin au format YYYY-MM-DD
        
    Returns:
        list: Liste des configurations [{date, is_working_day, description}]
    """
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    if start_date and end_date:
        cursor.execute(f'''
            SELECT date, is_working_day, description 
            FROM working_days_config 
            WHERE date BETWEEN {placeholder} AND {placeholder}
            ORDER BY date
        ''', (start_date, end_date))
    else:
        cursor.execute('''
            SELECT date, is_working_day, description 
            FROM working_days_config 
            ORDER BY date
        ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in results]

def set_working_day_config(date, is_working_day, description=None):
    """
    Configure un jour comme ouvré ou non-ouvré
    
    Args:
        date (str): Date au format YYYY-MM-DD
        is_working_day (bool): True si jour ouvré, False sinon
        description (str, optional): Description du changement
        
    Returns:
        bool: True si succès, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        placeholder = '%s' if db_type == 'postgresql' else '?'
        
        # Utiliser INSERT ... ON CONFLICT pour PostgreSQL, ou INSERT OR REPLACE pour SQLite
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO working_days_config (date, is_working_day, description, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
                ON CONFLICT (date) 
                DO UPDATE SET 
                    is_working_day = EXCLUDED.is_working_day,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
            ''', (date, is_working_day, description))
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO working_days_config 
                (date, is_working_day, description, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
            ''', (date, is_working_day, description))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la configuration du jour ouvré {date}: {e}")
        return False

def is_working_day_configured(date):
    """
    Vérifie si un jour est configuré comme ouvré
    
    Args:
        date (str): Date au format YYYY-MM-DD
        
    Returns:
        bool: True si jour ouvré, False sinon (défaut basé sur weekday)
    """
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    cursor.execute(f'''
        SELECT is_working_day FROM working_days_config 
        WHERE date = {placeholder}
    ''', (date,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result is not None:
        return bool(result[0])
    else:
        # Défaut: lundi-vendredi sont ouvrés, samedi-dimanche non
        from datetime import datetime
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        return date_obj.weekday() < 5  # 0-4 = lundi-vendredi

def delete_working_day_config(date):
    """
    Supprime la configuration pour une date (retour au défaut)
    
    Args:
        date (str): Date au format YYYY-MM-DD
        
    Returns:
        bool: True si succès, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        placeholder = '%s' if db_type == 'postgresql' else '?'
        
        cursor.execute(f'DELETE FROM working_days_config WHERE date = {placeholder}', (date,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la configuration {date}: {e}")
        return False

# === GESTION DISPONIBILITÉ C21 ===

def get_c21_availability():
    """
    Récupère tous les créneaux de disponibilité de la C21
    
    Returns:
        list: Liste des créneaux avec jour, heure_debut, heure_fin, id
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, jour, heure_debut, heure_fin, created_at 
            FROM c21_availability 
            ORDER BY 
                CASE jour 
                    WHEN 'lundi' THEN 1
                    WHEN 'mardi' THEN 2
                    WHEN 'mercredi' THEN 3
                    WHEN 'jeudi' THEN 4
                    WHEN 'vendredi' THEN 5
                    WHEN 'samedi' THEN 6
                    WHEN 'dimanche' THEN 7
                END,
                heure_debut
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        availability = []
        for row in rows:
            availability.append({
                'id': row[0],
                'jour': row[1],
                'heure_debut': row[2],
                'heure_fin': row[3],
                'created_at': row[4]
            })
        
        return availability
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des créneaux C21: {e}")
        return []

def add_c21_availability(jour, heure_debut, heure_fin):
    """
    Ajoute un créneau de disponibilité pour la C21
    
    Args:
        jour (str): Jour de la semaine (lundi, mardi, etc.)
        heure_debut (str): Heure de début (format HH:MM)
        heure_fin (str): Heure de fin (format HH:MM)
        
    Returns:
        bool: True si succès, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        placeholder = '%s' if db_type == 'postgresql' else '?'
        
        cursor.execute(f'''
            INSERT INTO c21_availability (jour, heure_debut, heure_fin) 
            VALUES ({placeholder}, {placeholder}, {placeholder})
        ''', (jour, heure_debut, heure_fin))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du créneau C21 {jour} {heure_debut}-{heure_fin}: {e}")
        return False

def delete_c21_availability(availability_id):
    """
    Supprime un créneau de disponibilité de la C21
    
    Args:
        availability_id (int): ID du créneau à supprimer
        
    Returns:
        bool: True si succès, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        placeholder = '%s' if db_type == 'postgresql' else '?'
        
        cursor.execute(f'DELETE FROM c21_availability WHERE id = {placeholder}', (availability_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du créneau C21 {availability_id}: {e}")
        return False

def is_c21_available_db(jour, heure_debut_minutes, heure_fin_minutes):
    """
    Vérifie si la C21 est disponible pour un créneau donné en base de données
    
    Args:
        jour (str): Jour de la semaine
        heure_debut_minutes (int): Heure de début en minutes depuis minuit
        heure_fin_minutes (int): Heure de fin en minutes depuis minuit
        
    Returns:
        bool: True si disponible, False sinon
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        
        placeholder = '%s' if db_type == 'postgresql' else '?'
        
        # Convertir les minutes en format HH:MM
        def minutes_to_time(minutes):
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:02d}:{mins:02d}"
        
        heure_debut_str = minutes_to_time(heure_debut_minutes)
        heure_fin_str = minutes_to_time(heure_fin_minutes)
        
        # Chercher les créneaux qui contiennent complètement le cours
        if db_type == 'postgresql':
            cursor.execute(f'''
                SELECT COUNT(*) FROM c21_availability 
                WHERE jour = {placeholder} 
                AND heure_debut <= %s::time 
                AND heure_fin >= %s::time
            ''', (jour, heure_debut_str, heure_fin_str))
        else:
            cursor.execute(f'''
                SELECT COUNT(*) FROM c21_availability 
                WHERE jour = {placeholder} 
                AND time(heure_debut) <= time({placeholder}) 
                AND time(heure_fin) >= time({placeholder})
            ''', (jour, heure_debut_str, heure_fin_str))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de disponibilité C21: {e}")
        return False  # Par sécurité, considérer comme non disponible en cas d'erreur

def add_pending_modification(request_id, field_name, original_value, new_value, modified_by='System'):
    """Add a pending modification to the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    try:
        cursor.execute(f'''
            INSERT INTO pending_modifications 
            (request_id, field_name, original_value, new_value, modified_by) 
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        ''', (request_id, field_name, original_value, new_value, modified_by))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la modification en attente: {e}")
        conn.close()
        return False

def get_pending_modifications(request_id=None):
    """Get pending modifications for a specific request or all requests"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    try:
        if request_id:
            cursor.execute(f'''
                SELECT pm.id, pm.request_id, pm.field_name, pm.original_value, pm.new_value,
                       pm.created_at, pm.modified_by, mr.teacher_id, t.name as teacher_name, mr.request_name
                FROM pending_modifications pm
                JOIN material_requests mr ON pm.request_id = mr.id
                JOIN teachers t ON mr.teacher_id = t.id
                WHERE pm.request_id = {placeholder}
                ORDER BY pm.created_at DESC
            ''', (request_id,))
        else:
            cursor.execute('''
                SELECT pm.id, pm.request_id, pm.field_name, pm.original_value, pm.new_value,
                       pm.created_at, pm.modified_by, mr.teacher_id, t.name as teacher_name, mr.request_name
                FROM pending_modifications pm
                JOIN material_requests mr ON pm.request_id = mr.id
                JOIN teachers t ON mr.teacher_id = t.id
                ORDER BY pm.created_at DESC
            ''')
        
        modifications = cursor.fetchall()
        conn.close()
        return modifications
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modifications en attente: {e}")
        conn.close()
        return []

def get_requests_with_pending_modifications():
    """Get all request IDs that have pending modifications"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT DISTINCT request_id 
            FROM pending_modifications 
            ORDER BY request_id
        ''')
        
        request_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return request_ids
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des demandes avec modifications: {e}")
        conn.close()
        return []

def validate_pending_modifications(request_id):
    """Apply all pending modifications for a request and remove them from pending table"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    # Utiliser TRUE/FALSE pour PostgreSQL, 1/0 pour SQLite
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    
    try:
        # Get all pending modifications for this request
        cursor.execute(f'''
            SELECT field_name, new_value 
            FROM pending_modifications 
            WHERE request_id = {placeholder}
        ''', (request_id,))
        
        modifications = cursor.fetchall()
        
        if not modifications:
            conn.close()
            return False
        
        # Apply each modification to the material_requests table
        for mod in modifications:
            # Gérer tuple ou dict
            if isinstance(mod, dict):
                field_name = mod['field_name']
                new_value = mod['new_value']
            elif hasattr(mod, '_asdict'):
                mod_dict = mod._asdict()
                field_name = mod_dict['field_name']
                new_value = mod_dict['new_value']
            else:
                # Tuple classique [field_name, new_value]
                field_name = mod[0]
                new_value = mod[1]
            
            cursor.execute(f'''
                UPDATE material_requests 
                SET {field_name} = {placeholder} 
                WHERE id = {placeholder}
            ''', (new_value, request_id))
        
        # Reset both modified and prepared flags to FALSE since modifications are now applied
        # Une demande modifiée doit être re-préparée
        cursor.execute(f'''
            UPDATE material_requests 
            SET modified = {false_val}, prepared = {false_val}
            WHERE id = {placeholder}
        ''', (request_id,))
        
        # Remove the pending modifications
        cursor.execute(f'''
            DELETE FROM pending_modifications 
            WHERE request_id = {placeholder}
        ''', (request_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la validation des modifications: {e}")
        conn.rollback()
        conn.close()
        return False

def reject_pending_modifications(request_id):
    """Reject and remove all pending modifications for a request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    
    try:
        cursor.execute(f'''
            DELETE FROM pending_modifications 
            WHERE request_id = {placeholder}
        ''', (request_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur lors du rejet des modifications: {e}")
        conn.close()
        return False

if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")