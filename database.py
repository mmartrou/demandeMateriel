import sqlite3
import os
from datetime import datetime

DATABASE_PATH = 'material_requests.db'

def init_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
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
        cursor.executemany('''
            INSERT INTO rooms (name, type, ordinateurs, chaises, eviers, hotte, 
                             bancs_optiques, oscilloscopes, becs_electriques, 
                             support_filtration, imprimante, examen) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        cursor.executemany('''
            INSERT INTO student_numbers (teacher_name, student_count, level) 
            VALUES (?, ?, ?)
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
            ('Moreau',),
            ('Paupy',),
            ('Potier',),
            ('Richard',),
            ('Vernudachi',),
            ('Vila Gisbert',),
        ]
        cursor.executemany('INSERT INTO teachers (name) VALUES (?)', sample_teachers)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def get_all_teachers():
    """Get all teachers from the database"""
    conn = get_db_connection()
    teachers = conn.execute('SELECT * FROM teachers ORDER BY name').fetchall()
    conn.close()
    return teachers

def add_material_request(teacher_id, request_date, class_name, material_description, 
                        horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                        notes='', exam=False, group_count=1, material_prof=''):
    """Add a new material request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO material_requests 
        (teacher_id, request_date, horaire, class_name, material_description, quantity, 
         selected_materials, computers_needed, notes, exam, group_count, material_prof)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity, 
          selected_materials, computers_needed, notes, exam, group_count, material_prof))
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    return request_id

def get_material_requests(start_date=None, end_date=None, teacher_id=None):
    """Get material requests with optional filters"""
    conn = get_db_connection()
    query = '''
        SELECT mr.*, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE 1=1
    '''
    params = []
    
    if start_date:
        query += ' AND mr.request_date >= ?'
        params.append(start_date)
    
    if end_date:
        query += ' AND mr.request_date <= ?'
        params.append(end_date)
    
    if teacher_id:
        query += ' AND mr.teacher_id = ?'
        params.append(teacher_id)
    
    query += ' ORDER BY mr.request_date, mr.created_at'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    return requests

def get_requests_for_calendar():
    """Get all requests formatted for calendar display"""
    conn = get_db_connection()
    requests = conn.execute('''
        SELECT mr.id, mr.request_date, mr.class_name, mr.material_description, 
               mr.quantity, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        ORDER BY mr.request_date
    ''').fetchall()
    conn.close()
    return requests

def get_material_request_by_id(request_id):
    """Get a specific material request by ID"""
    conn = get_db_connection()
    request = conn.execute('''
        SELECT mr.*, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.id = ?
    ''', (request_id,)).fetchone()
    conn.close()
    return request

def update_material_request(request_id, teacher_id, request_date, class_name, material_description, 
                           horaire=None, quantity=1, selected_materials='', computers_needed=0, 
                           notes='', group_count=1, material_prof=''):
    """Update an existing material request and mark it as modified"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE material_requests 
        SET teacher_id=?, request_date=?, horaire=?, class_name=?, material_description=?, 
            quantity=?, selected_materials=?, computers_needed=?, notes=?, 
            group_count=?, material_prof=?, prepared=FALSE, modified=TRUE
        WHERE id=?
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity, 
          selected_materials, computers_needed, notes, group_count, material_prof, request_id))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0

def toggle_prepared_status(request_id):
    """Toggle the prepared status of a request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current status
    current = conn.execute('SELECT prepared FROM material_requests WHERE id = ?', (request_id,)).fetchone()
    if not current:
        conn.close()
        return False
    
    new_prepared = not current['prepared']
    # When marking as prepared, remove modified flag
    # When unmarking prepared, keep modified flag as is
    if new_prepared:
        cursor.execute('UPDATE material_requests SET prepared=TRUE, modified=FALSE WHERE id=?', (request_id,))
    else:
        cursor.execute('UPDATE material_requests SET prepared=FALSE WHERE id=?', (request_id,))
    
    conn.commit()
    conn.close()
    return True

def delete_material_request(request_id):
    """Delete a material request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM material_requests WHERE id = ?', (request_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def update_room_type(request_id, room_type):
    """Update the room type of a material request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE material_requests SET room_type = ? WHERE id = ?', (room_type, request_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def get_all_rooms():
    """Get all rooms from the database"""
    conn = get_db_connection()
    rooms = conn.execute('SELECT * FROM rooms ORDER BY name').fetchall()
    conn.close()
    return rooms

def update_room(room_id, room_data):
    """Update a room in the database"""
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE rooms SET 
                name = ?, type = ?, ordinateurs = ?, chaises = ?, eviers = ?, 
                hotte = ?, bancs_optiques = ?, oscilloscopes = ?, becs_electriques = ?, 
                support_filtration = ?, imprimante = ?, examen = ?
            WHERE id = ?
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
        print(f"Erreur lors de la mise à jour de la salle: {e}")
        return False

def import_rooms_from_csv_content(csv_content):
    """Import rooms from CSV content, replacing existing rooms"""
    conn = get_db_connection()
    try:
        import csv as csv_module
        import io
        
        # Clear existing rooms
        conn.execute('DELETE FROM rooms')
        
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
        
        # Insert new rooms
        conn.executemany('''
            INSERT INTO rooms (name, type, ordinateurs, chaises, eviers, hotte, 
                             bancs_optiques, oscilloscopes, becs_electriques, 
                             support_filtration, imprimante, examen) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', rooms_data)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"Erreur lors de l'import CSV: {e}")
        raise e

def get_all_student_numbers():
    """Get all student numbers from the database"""
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM student_numbers ORDER BY teacher_name').fetchall()
    conn.close()
    return students

def update_student_number(student_id, student_data):
    """Update student number in the database"""
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE student_numbers SET 
                teacher_name = ?, student_count = ?, level = ?
            WHERE id = ?
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
        print(f"Erreur lors de la mise à jour de l'effectif: {e}")
        return False

def add_student_number(teacher_name, student_count, level='2nde'):
    """Add a new student number entry"""
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO student_numbers (teacher_name, student_count, level) 
            VALUES (?, ?, ?)
        ''', (teacher_name, student_count, level))
        conn.commit()
        student_id = conn.lastrowid
        conn.close()
        return student_id
    except Exception as e:
        conn.close()
        print(f"Erreur lors de l'ajout de l'effectif: {e}")
        return None

def delete_student_number(student_id):
    """Delete a student number entry"""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM student_numbers WHERE id = ?', (student_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"Erreur lors de la suppression de l'effectif: {e}")
        return False

def get_student_count_for_teacher(teacher_name, level):
    """Get student count for a specific teacher and level"""
    conn = get_db_connection()
    result = conn.execute('''
        SELECT student_count FROM student_numbers 
        WHERE teacher_name = ? AND level = ?
    ''', (teacher_name, level)).fetchone()
    conn.close()
    return result['student_count'] if result else 20  # Default fallback

def get_planning_data(date_str):
    """Get all material requests for planning generation on a specific date"""
    conn = get_db_connection()
    requests = conn.execute('''
        SELECT mr.*, t.name as teacher_name
        FROM material_requests mr
        JOIN teachers t ON mr.teacher_id = t.id
        WHERE mr.request_date = ?
        AND mr.selected_materials != 'Enseignant absent'
        ORDER BY mr.horaire, mr.created_at
    ''', (date_str,)).fetchall()
    conn.close()
    return requests

if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")