"""Création des tables et migrations (init_database), amorçage des réglages."""
import os
import psycopg2
import psycopg2.extras
import sqlite3

from .connexion import get_db_connection


# Migration d'une base créée avant l'apparition de l'ordre, des groupes et de la disponibilité
# limitée des salles : ces réglages étaient alors écrits en dur dans le code, pour les salles
# d'un établissement précis. (nom, groupe affiché en en-tête du planning, disponibilité limitée) ;
# l'ordre de la liste donne l'ordre d'affichage. Sans effet sur une base neuve ou sur d'autres noms
# de salles ; ensuite tout se modifie dans /admin/rooms.
ANCIENNE_ORGANISATION_DES_SALLES = [
    ('C23', 'Physique', 0), ('C25', 'Physique', 0), ('C27', 'Physique', 0),
    ('C22', 'Physique', 0), ('C24', 'Physique', 0),
    ('C32', 'Chimie', 0), ('C33', 'Chimie', 0), ('C31', 'Chimie', 0),
    ('C21', None, 1),
]


def _appliquer_ancienne_organisation_des_salles(cursor, db_type):
    placeholder = '%s' if db_type == 'postgresql' else '?'
    for ordre, (nom, groupe, limitee) in enumerate(ANCIENNE_ORGANISATION_DES_SALLES, start=1):
        cursor.execute(
            f'UPDATE rooms SET display_order={placeholder}, room_group={placeholder}, '
            f'limited_availability={placeholder} WHERE name={placeholder}',
            (ordre, groupe, limitee, nom))
    # Salles inconnues de l'organisation par défaut : placées à la suite, par ordre alphabétique
    connus = [nom for nom, _, _ in ANCIENNE_ORGANISATION_DES_SALLES]
    cursor.execute(f"SELECT id FROM rooms WHERE name NOT IN ({', '.join([placeholder] * len(connus))}) ORDER BY name",
                   tuple(connus))
    ordre = len(connus)
    for room_id in [r[0] for r in cursor.fetchall()]:
        ordre += 1
        cursor.execute(f'UPDATE rooms SET display_order={placeholder} WHERE id={placeholder}', (ordre, room_id))


def _table_exists(cursor, db_type, table):
    if db_type == 'postgresql':
        cursor.execute("SELECT to_regclass(%s)", (table,))
        return cursor.fetchone()[0] is not None
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def _add_column_if_missing(cursor, db_type, table, column, definition):
    """Ajoute une colonne à une table existante (migration). Renvoie True si elle vient
    d'être créée, ce qui permet de remplir ses valeurs initiales une seule fois."""
    if db_type == 'postgresql':
        cursor.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column))
        if cursor.fetchone() is not None:
            return False
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        return True
    try:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        return True
    except Exception:
        return False


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
            short_name {text_type},
            created_at {timestamp_default}
        )
    ''')
    # Migration : ajouter short_name si absent
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='teachers' AND column_name='short_name'
        """)
        if cursor.fetchone() is None:
            cursor.execute('ALTER TABLE teachers ADD COLUMN short_name TEXT')
    else:
        try:
            cursor.execute('ALTER TABLE teachers ADD COLUMN short_name TEXT')
        except Exception:
            pass

    # Create levels table
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS levels (
            id {auto_increment},
            name {text_type} NOT NULL UNIQUE,
            short_name {text_type},
            default_duration INTEGER DEFAULT 85,
            display_order INTEGER DEFAULT 0
        )
    ''')
    # Migration : ajouter default_duration si absent
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='levels' AND column_name='default_duration'
        """)
        if cursor.fetchone() is None:
            cursor.execute('ALTER TABLE levels ADD COLUMN default_duration INTEGER DEFAULT 85')
    else:
        try:
            cursor.execute('ALTER TABLE levels ADD COLUMN default_duration INTEGER DEFAULT 85')
        except Exception:
            pass
    # Migration : nombre de groupes proposé par défaut pour chaque niveau. Les valeurs de
    # départ reprennent les règles qui étaient auparavant codées en dur dans le JavaScript.
    placeholder = '%s' if db_type == 'postgresql' else '?'
    if _add_column_if_missing(cursor, db_type, 'levels', 'default_groups', 'INTEGER DEFAULT 1'):
        for name, groups in (
            [('2nd TP', 8)]
            + [(n, 10) for n in ("6ème", "5ème", "4ème", "3ème", "SNT", "SI", "1ère ES",
                                 "Terminale ES", "1ère Spécialité", "Terminale Spécialité")]
            + [(n, 0) for n in ("2nd Classe", "AP 2nd", "Autre")]
        ):
            cursor.execute(f'UPDATE levels SET default_groups={placeholder} WHERE name={placeholder}',
                           (groups, name))
    # Pré-remplir avec les niveaux par défaut si la table est vide
    cursor.execute('SELECT COUNT(*) FROM levels')
    row = cursor.fetchone()
    count = row[0] if row is not None else 0
    if count == 0:
        # (name, short_name, default_duration, display_order, default_groups)
        default_levels = [
            ('6ème',               None, 85,  1,  10),
            ('5ème',               None, 85,  2,  10),
            ('4ème',               None, 85,  3,  10),
            ('3ème',               None, 85,  4,  10),
            ('SNT',                None, 85,  5,  10),
            ('SI',                 None, 110, 6,  10),
            ('2nd Classe',         None, 85,  7,  0),
            ('2nd TP',             None, 85,  8,  8),
            ('AP PP',              None, 55,  9,  1),
            ('AP 2nd',             None, 110, 10, 0),
            ('1ère ES',            None, 55,  11, 10),
            ('Terminale ES',       None, 110, 12, 10),
            ('1ère Spécialité',    None, 110, 13, 10),
            ('Terminale Spécialité', None, 110, 14, 10),
            ('Autre',              None, 55,  15, 0),
        ]
        cursor.executemany(
            f'INSERT INTO levels (name, short_name, default_duration, display_order, default_groups) VALUES ({placeholder},{placeholder},{placeholder},{placeholder},{placeholder})',
            default_levels
        )

    # Create users table for Google authentication and role management
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            id {auto_increment},
            google_sub {text_type} NOT NULL UNIQUE,
            email {text_type} NOT NULL UNIQUE,
            full_name {text_type},
            role {text_type} NOT NULL DEFAULT 'teacher',
            teacher_id INTEGER,
            created_at {timestamp_default},
            updated_at {timestamp_default},
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
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
            room_type_manual BOOLEAN DEFAULT FALSE,
            image_url {text_type},
            exam BOOLEAN DEFAULT FALSE,
            custom_duration INTEGER,
            is_lab_test BOOLEAN DEFAULT FALSE,
            is_draft BOOLEAN DEFAULT FALSE,
            labo_observations {text_type},
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
        ('image_url', 'TEXT'),
        ('custom_duration', 'INTEGER'),
        ('is_lab_test', 'BOOLEAN DEFAULT FALSE'),
        ('is_draft', 'BOOLEAN DEFAULT FALSE'),
        ('labo_observations', 'TEXT'),
        ('room_type_manual', 'BOOLEAN DEFAULT FALSE')
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

    user_columns_to_add = [
        ('google_sub', 'TEXT'),
        ('email', 'TEXT'),
        ('full_name', 'TEXT'),
        ('role', 'TEXT DEFAULT "teacher"'),
        ('teacher_id', 'INTEGER'),
        ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ]

    for column_name, column_type in user_columns_to_add:
        if db_type == 'postgresql':
            cursor.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name=%s
            """, (column_name,))
            exists = cursor.fetchone() is not None
            if exists:
                continue
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_type}')
        except (sqlite3.OperationalError, psycopg2.errors.DuplicateColumn):
            pass
    
    
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
            obscurite_totale INTEGER DEFAULT 0,
            becs_electriques INTEGER DEFAULT 0,
            support_filtration INTEGER DEFAULT 0,
            imprimante INTEGER DEFAULT 0,
            examen INTEGER DEFAULT 0,
            created_at {timestamp_default}
        )
    ''')

    # Migration : ordre d'affichage, regroupement (en-tête du planning) et disponibilité limitée.
    # Les valeurs de départ reprennent l'organisation qui était auparavant codée en dur.
    nouvelles_colonnes = [
        _add_column_if_missing(cursor, db_type, 'rooms', 'display_order', 'INTEGER DEFAULT 0'),
        _add_column_if_missing(cursor, db_type, 'rooms', 'room_group', 'TEXT'),
        _add_column_if_missing(cursor, db_type, 'rooms', 'limited_availability', 'INTEGER DEFAULT 0'),
    ]
    if any(nouvelles_colonnes):
        _appliquer_ancienne_organisation_des_salles(cursor, db_type)

    # Migration : renommer la colonne oscilloscopes en obscurite_totale (matériel peu mobile)
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='rooms' AND column_name='oscilloscopes'
        """)
        has_old_column = cursor.fetchone() is not None
    else:
        cursor.execute("PRAGMA table_info(rooms)")
        has_old_column = any(col[1] == 'oscilloscopes' for col in cursor.fetchall())
    if has_old_column:
        try:
            cursor.execute('ALTER TABLE rooms RENAME COLUMN oscilloscopes TO obscurite_totale')
        except (sqlite3.OperationalError, psycopg2.errors.DuplicateColumn):
            pass

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

    # Create app settings table (generic key/value store for admin-configurable options)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS app_settings (
            key {text_type} PRIMARY KEY,
            value {text_type} NOT NULL,
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

    # Créneaux de disponibilité des salles à disponibilité limitée (une ligne par salle et par
    # créneau). Remplace c21_availability, qui ne pouvait décrire qu'une seule salle ; l'ancienne
    # table n'est plus utilisée mais conservée, et ses créneaux sont copiés une seule fois.
    existait = _table_exists(cursor, db_type, 'room_availability')
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS room_availability (
            id {auto_increment},
            room_id INTEGER NOT NULL,
            jour {text_type} NOT NULL,
            heure_debut {text_type} NOT NULL,
            heure_fin {text_type} NOT NULL,
            created_at {timestamp_default},
            UNIQUE(room_id, jour, heure_debut, heure_fin)
        )
    ''')
    if not existait:
        cursor.execute("SELECT id FROM rooms WHERE limited_availability = 1 ORDER BY display_order, id")
        salle_limitee = cursor.fetchone()
        if salle_limitee:
            placeholder = '%s' if db_type == 'postgresql' else '?'
            cursor.execute(
                f'INSERT INTO room_availability (room_id, jour, heure_debut, heure_fin) '
                f'SELECT {placeholder}, jour, heure_debut, heure_fin FROM c21_availability',
                (salle_limitee[0],))

    # Create standard occupation table (nombre de cours attendus par jour de semaine et créneau,
    # colonne "Occupation standard" de l'éditeur de planning)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS standard_occupation (
            id {auto_increment},
            day_of_week {text_type} NOT NULL,
            slot {text_type} NOT NULL,
            value INTEGER NOT NULL,
            UNIQUE(day_of_week, slot)
        )
    ''')

    # Add a new table for storing planning data
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS plannings (
            date {text_type} PRIMARY KEY,
            data {text_type} NOT NULL,
            observations {text_type}
        );
    ''')
    # Migration : ajouter observations si absent
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='plannings' AND column_name='observations'
        """)
        if cursor.fetchone() is None:
            cursor.execute('ALTER TABLE plannings ADD COLUMN observations TEXT')
    else:
        try:
            cursor.execute('ALTER TABLE plannings ADD COLUMN observations TEXT')
        except Exception:
            pass

    # Table des templates de TP (TPs précédemment demandés, classés par enseignant+niveau)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS tp_templates (
            id {auto_increment},
            teacher_id INTEGER NOT NULL,
            level {text_type} NOT NULL,
            request_name {text_type} NOT NULL,
            material_description {text_type},
            selected_materials {text_type},
            material_prof {text_type},
            computers_needed INTEGER DEFAULT 0,
            group_count INTEGER DEFAULT 1,
            notes {text_type},
            image_url {text_type},
            room_type {text_type} DEFAULT 'Mixte',
            updated_at {timestamp_default},
            UNIQUE (teacher_id, level, request_name),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    ''')

    # Table de l'emploi du temps type (cours récurrents) d'un enseignant : jour de semaine (0=Lundi..4=Vendredi)
    # + horaire + niveau. Sert de base pour générer automatiquement des demandes "brouillon" chaque semaine.
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS recurring_courses (
            id {auto_increment},
            teacher_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            horaire {text_type} NOT NULL,
            class_name {text_type} NOT NULL,
            created_at {timestamp_default},
            UNIQUE (teacher_id, day_of_week, horaire),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    ''')

    _amorcer_reglages_etablissement(cursor, db_type)

    conn.commit()
    conn.close()


# Adresse du compte labo avant qu'elle ne devienne un réglage (/admin/establishment). Elle n'est
# reprise que pour une installation qui contient déjà des données, afin qu'elle continue de
# fonctionner après la mise à jour ; une installation neuve démarre sans compte labo.
ANCIEN_COMPTE_LABO_PAR_DEFAUT = 'labo.physiquechimie@lfmadrid.org'


def _amorcer_reglages_etablissement(cursor, db_type):
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT 1 FROM app_settings WHERE key = {placeholder}', ('labo_email',))
    if cursor.fetchone() is not None:
        return
    adresse = os.getenv('LABO_EMAIL', '').strip().lower()
    if not adresse:
        cursor.execute('SELECT COUNT(*) FROM material_requests')
        demandes = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM users')
        comptes = cursor.fetchone()[0]
        if demandes or comptes:
            adresse = ANCIEN_COMPTE_LABO_PAR_DEFAUT
    if adresse:
        cursor.execute(f'INSERT INTO app_settings (key, value) VALUES ({placeholder}, {placeholder})',
                       ('labo_email', adresse))
