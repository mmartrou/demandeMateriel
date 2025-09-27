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
    
    # Insert sample teachers if table is empty
    cursor.execute('SELECT COUNT(*) FROM teachers')
    if cursor.fetchone()[0] == 0:
        sample_teachers = [
            ('Martrou',),
            ('Bats',),
            ('Vila',),
            ('Paupy',),
            ('Richard',)
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
                        horaire=None, quantity=1, selected_materials='', computers_needed=0, notes=''):
    """Add a new material request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO material_requests 
        (teacher_id, request_date, horaire, class_name, material_description, quantity, 
         selected_materials, computers_needed, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (teacher_id, request_date, horaire, class_name, material_description, quantity, 
          selected_materials, computers_needed, notes))
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

if __name__ == '__main__':
    init_database()
    print("Database initialized successfully!")