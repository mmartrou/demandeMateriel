import sqlite3
import os
import logging
from datetime import datetime
from urllib.parse import urlparse, urlunparse

# Configuration des logs
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
    logger.info("PostgreSQL disponible")
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.info("PostgreSQL non disponible, utilisation de SQLite")

DATABASE_PATH = 'material_requests.db'

def get_db_connection():
    """Get database connection - PostgreSQL in production, SQLite locally"""
    
    # Option 1: Variables PostgreSQL séparées (plus fiable)
    pg_host = os.getenv('PGHOST')
    pg_user = os.getenv('PGUSER') 
    pg_password = os.getenv('PGPASSWORD')
    pg_database = os.getenv('PGDATABASE')
    pg_port = os.getenv('PGPORT', '5432')
    
    # Option 2: URL complète (fallback)
    database_url = os.getenv('DATABASE_URL')
    
    if POSTGRES_AVAILABLE and (pg_host or database_url):
        # Production: PostgreSQL sur Railway
        
        # Approche 1: Variables séparées (plus fiable, évite les problèmes d'encodage)
        if pg_host and pg_user and pg_password and pg_database:
            try:
                logger.info(f"Connexion PostgreSQL avec variables séparées: {pg_host}:{pg_port}")
                conn = psycopg2.connect(
                    host=pg_host,
                    port=pg_port,
                    user=pg_user,
                    password=pg_password,
                    database=pg_database,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10,
                    client_encoding='utf8'
                )
                logger.info("✅ Connexion PostgreSQL (variables séparées) réussie")
                return conn, 'postgresql'
                
            except Exception as e:
                logger.error(f"Erreur PostgreSQL (variables séparées): {e}")
                
        # Approche 2: URL complète (fallback)
        elif database_url:
            try:
                logger.info("Tentative avec URL PostgreSQL...")
                
                # Essayer l'URL directement d'abord
                try:
                    logger.info(f"Connexion directe: {database_url[:50]}...")
                    conn = psycopg2.connect(
                        database_url, 
                        cursor_factory=RealDictCursor,
                        connect_timeout=10,
                        client_encoding='utf8'
                    )
                    logger.info("✅ Connexion PostgreSQL (URL) réussie")
                    return conn, 'postgresql'
                    
                except UnicodeDecodeError as ude:
                    logger.debug(f"Encodage URL PostgreSQL: utilisation du fallback SQLite")
                    # Pas de log d'erreur - c'est normal en mode développement
                    
            except Exception as e:
                logger.error(f"Erreur PostgreSQL (URL): {e}")
        
        logger.info("Fallback vers SQLite après échec PostgreSQL")
    
    # Local: SQLite
    logger.info("Utilisation de SQLite")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn, 'sqlite'

def init_database():
    """Initialize the database with required tables"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    if db_type == 'postgresql':
        # PostgreSQL schemas
        # Create teachers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create material requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS material_requests (
                id SERIAL PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                request_date DATE NOT NULL,
                horaire VARCHAR(10),
                class_name VARCHAR(100) NOT NULL,
                material_description TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                selected_materials TEXT,
                computers_needed INTEGER DEFAULT 0,
                notes TEXT,
                prepared BOOLEAN DEFAULT FALSE,
                modified BOOLEAN DEFAULT FALSE,
                group_count INTEGER,
                material_prof TEXT,
                request_name TEXT,
                room_type VARCHAR(20) DEFAULT 'Mixte',
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teachers (id)
            )
        ''')
        
        # Create rooms table for planning (PostgreSQL)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                type VARCHAR(20) NOT NULL,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create student numbers table (PostgreSQL)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_numbers (
                id SERIAL PRIMARY KEY,
                teacher_name VARCHAR(100) NOT NULL UNIQUE,
                student_count INTEGER NOT NULL DEFAULT 20,
                level VARCHAR(20) DEFAULT '2nde',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
    else:
        # SQLite schemas (code existant)
        # Create teachers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create material requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS material_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL,
                request_date DATE NOT NULL,
                horaire TEXT,
                class_name TEXT NOT NULL,
                material_description TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                selected_materials TEXT,
                computers_needed INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES teachers (id)
            )
        ''')
    # Ajout du champ horaire si absent
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN horaire TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add new columns to existing table if they don't exist
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN selected_materials TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN computers_needed INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add status columns for prepared and modified states
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN prepared BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN modified BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add room type column with default value "Mixte"
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN room_type TEXT DEFAULT "Mixte"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add exam column to track exam mode
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN exam BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add group_count column
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN group_count INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add material_prof column for teacher materials
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN material_prof TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add request_name column for named requests
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN request_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add image_url column for Google Drive images
    try:
        cursor.execute('ALTER TABLE material_requests ADD COLUMN image_url TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create rooms table for planning
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create student numbers table for 2nd level classes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_name TEXT NOT NULL UNIQUE,
            student_count INTEGER NOT NULL DEFAULT 20,
            level TEXT DEFAULT '2nde',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample rooms if table is empty
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
        
        # Utilise les bons placeholders selon la base de données
        placeholder = '%s' if db_type == 'postgresql' else '?'
        placeholders = ', '.join([placeholder] * 12)
        
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
        student_placeholders = ', '.join([placeholder] * 3)
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
        cursor.executemany(f'INSERT INTO teachers (name) VALUES ({placeholder})', sample_teachers)

    # Create working days configuration table
    if db_type == 'postgresql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS working_days_config (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL UNIQUE,
                is_working_day BOOLEAN NOT NULL DEFAULT TRUE,
                description VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS working_days_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                is_working_day BOOLEAN NOT NULL DEFAULT 1,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # Create C21 availability table
    if db_type == 'postgresql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS c21_availability (
                id SERIAL PRIMARY KEY,
                jour VARCHAR(10) NOT NULL,
                heure_debut TIME NOT NULL,
                heure_fin TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(jour, heure_debut, heure_fin)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS c21_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jour TEXT NOT NULL,
                heure_debut TEXT NOT NULL,
                heure_fin TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(jour, heure_debut, heure_fin)
            )
        ''')

    # Create pending modifications table for tracking changes before validation
    if db_type == 'postgresql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_modifications (
                id SERIAL PRIMARY KEY,
                request_id INTEGER NOT NULL,
                field_name VARCHAR(50) NOT NULL,
                original_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_by VARCHAR(100),
                FOREIGN KEY (request_id) REFERENCES material_requests(id) ON DELETE CASCADE
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_modifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                original_value TEXT,
                new_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_by TEXT,
                FOREIGN KEY (request_id) REFERENCES material_requests(id) ON DELETE CASCADE
            )
        ''')
    
    conn.commit()
    conn.close()

# Ancienne fonction supprimée - remplacée par la nouvelle get_db_connection() qui supporte PostgreSQL

def get_all_teachers():
    """Get all teachers from the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM teachers ORDER BY name')
    teachers = cursor.fetchall()
    conn.close()
    return teachers

def add_material_request(teacher_id, request_date, class_name, material_description, 
                        horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                        notes='', exam=False, group_count=1, material_prof='', request_name='', image_url=''):
    """Add a new material request"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    placeholders = ', '.join([placeholder] * 14)
    
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
        SELECT mr.*, t.name as teacher_name
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
    conn, db_type = get_db_connection()
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
        SELECT mr.*, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.id = {placeholder}
    ''', (request_id,))
    request = cursor.fetchone()
    conn.close()
    return request

def update_material_request(request_id, teacher_id, request_date, class_name, material_description, 
                           horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                           notes='', group_count=1, material_prof='', request_name=''):
    """Update an existing material request and mark it as modified"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgresql' else '?'
    placeholders = ', '.join([placeholder] * 12)
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
    true_val = 'TRUE' if db_type == 'postgresql' else '1'
    false_val = 'FALSE' if db_type == 'postgresql' else '0'
    
    # Get current status
    cursor.execute(f'SELECT prepared FROM material_requests WHERE id = {placeholder}', (request_id,))
    current = cursor.fetchone()
    if not current:
        conn.close()
        return False
    
    new_prepared = not current['prepared']
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
    return rooms

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
    return students

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
                SELECT pm.*, mr.teacher_id, t.name as teacher_name, mr.request_name
                FROM pending_modifications pm
                JOIN material_requests mr ON pm.request_id = mr.id
                JOIN teachers t ON mr.teacher_id = t.id
                WHERE pm.request_id = {placeholder}
                ORDER BY pm.created_at DESC
            ''', (request_id,))
        else:
            cursor.execute('''
                SELECT pm.*, mr.teacher_id, t.name as teacher_name, mr.request_name
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
        for field_name, new_value in modifications:
            cursor.execute(f'''
                UPDATE material_requests 
                SET {field_name} = {placeholder} 
                WHERE id = {placeholder}
            ''', (new_value, request_id))
        
        # Reset modified flag to FALSE since modifications are now validated
        cursor.execute(f'''
            UPDATE material_requests 
            SET modified = FALSE 
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