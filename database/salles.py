"""Salles (équipements, ordre, import CSV) et créneaux des salles à disponibilité limitée."""
import logging

from .connexion import get_db_connection

logger = logging.getLogger(__name__)


_ROOM_COLUMNS = ('id, name, type, ordinateurs, chaises, eviers, hotte, bancs_optiques, '
                 'obscurite_totale, becs_electriques, support_filtration, imprimante, examen, '
                 'display_order, room_group, limited_availability')


# Colonnes décrivant les équipements d'une salle (toutes numériques)
_ROOM_FIELDS = ['name', 'type', 'ordinateurs', 'chaises', 'eviers', 'hotte', 'bancs_optiques',
                'obscurite_totale', 'becs_electriques', 'support_filtration', 'imprimante', 'examen']


def get_all_rooms():
    """Toutes les salles, dans l'ordre d'affichage réglé dans /admin/rooms."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT {_ROOM_COLUMNS} FROM rooms ORDER BY display_order, id')
    rooms = cursor.fetchall()
    conn.close()

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
            'obscurite_totale': room[8],
            'becs_electriques': room[9],
            'support_filtration': room[10],
            'imprimante': room[11],
            'examen': room[12],
            'display_order': room[13] or 0,
            'room_group': room[14] or '',
            'limited_availability': bool(room[15]),
        })

    return rooms_list


def update_room(room_id, room_data):
    """Update a room in the database"""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()

    placeholder = '%s' if db_type == 'postgresql' else '?'

    # Colonnes toujours écrites (0 si absentes), puis colonnes facultatives écrites
    # seulement si la requête les fournit.
    colonnes = list(_ROOM_FIELDS)
    valeurs = [room_data.get('name'), room_data.get('type')] + \
              [room_data.get(c, 0) for c in _ROOM_FIELDS[2:]]
    if 'room_group' in room_data:
        colonnes.append('room_group')
        valeurs.append((room_data.get('room_group') or '').strip() or None)
    if 'limited_availability' in room_data:
        colonnes.append('limited_availability')
        valeurs.append(1 if room_data.get('limited_availability') else 0)
    if 'display_order' in room_data:
        colonnes.append('display_order')
        valeurs.append(int(room_data.get('display_order') or 0))

    try:
        affectations = ', '.join(f'{c} = {placeholder}' for c in colonnes)
        cursor.execute(f'UPDATE rooms SET {affectations} WHERE id = {placeholder}',
                       tuple(valeurs) + (room_id,))
        if 'limited_availability' in room_data and not room_data.get('limited_availability'):
            cursor.execute(f'DELETE FROM room_availability WHERE room_id = {placeholder}', (room_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de la mise à jour de la salle: {e}")
        return False


def add_room(room_data):
    """Ajoute une salle en fin de liste. Renvoie son identifiant."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute('SELECT COALESCE(MAX(display_order), 0) + 1 FROM rooms')
    ordre = cursor.fetchone()[0]
    colonnes = list(_ROOM_FIELDS) + ['display_order', 'room_group', 'limited_availability']
    valeurs = [(room_data.get('name') or '').strip(), room_data.get('type') or 'mixte'] + \
              [room_data.get(c, 0) or 0 for c in _ROOM_FIELDS[2:]] + \
              [ordre, (room_data.get('room_group') or '').strip() or None,
               1 if room_data.get('limited_availability') else 0]
    sql = (f'INSERT INTO rooms ({", ".join(colonnes)}) '
           f'VALUES ({", ".join([placeholder] * len(colonnes))})')
    if db_type == 'postgresql':
        cursor.execute(sql + ' RETURNING id', tuple(valeurs))
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute(sql, tuple(valeurs))
        new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def set_room_limited_availability(room_id, limited):
    """Marque une salle comme « à disponibilité limitée » (ou non). Dans ce second cas, ses créneaux
    sont supprimés : une salle toujours disponible n'a pas de créneaux."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'UPDATE rooms SET limited_availability = {placeholder} WHERE id = {placeholder}',
                   (1 if limited else 0, room_id))
    existe = cursor.rowcount > 0
    if existe and not limited:
        cursor.execute(f'DELETE FROM room_availability WHERE room_id = {placeholder}', (room_id,))
    conn.commit()
    conn.close()
    return existe


def delete_room(room_id):
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'DELETE FROM room_availability WHERE room_id = {placeholder}', (room_id,))
    cursor.execute(f'DELETE FROM rooms WHERE id = {placeholder}', (room_id,))
    conn.commit()
    supprimee = cursor.rowcount > 0
    conn.close()
    return supprimee


def reorder_rooms(room_ids):
    """Réécrit l'ordre d'affichage : la salle en position n de la liste reçoit display_order n."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    for ordre, room_id in enumerate(room_ids, start=1):
        cursor.execute(f'UPDATE rooms SET display_order = {placeholder} WHERE id = {placeholder}',
                       (ordre, int(room_id)))
    conn.commit()
    conn.close()


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
            if row[0].strip().lower() in ('nom', 'name'):  # ligne d'en-tête (export CSV)
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
                int(row[7]),  # obscurite_totale
                int(row[8]),  # becs_electriques
                int(row[9]),  # support_filtration
                int(row[10]), # imprimante
                int(row[11]), # examen
                len(rooms_data) + 1,  # display_order : ordre du fichier
                (row[12].strip() or None) if len(row) > 12 else None,  # room_group (facultatif)
                1 if len(row) > 13 and row[13].strip().lower() in ('1', 'oui', 'true') else 0,  # limited_availability (facultatif)
            ))

        # Insert new rooms with proper placeholders
        placeholder = '%s' if db_type == 'postgresql' else '?'
        placeholders = ', '.join([placeholder] * 15)

        for room_data in rooms_data:
            cursor.execute(f'''
                INSERT INTO rooms (name, type, ordinateurs, chaises, eviers, hotte,
                                 bancs_optiques, obscurite_totale, becs_electriques,
                                 support_filtration, imprimante, examen,
                                 display_order, room_group, limited_availability)
                VALUES ({placeholders})
            ''', room_data)

        conn.commit()
        conn.close()
        return True, f"{len(rooms_data)} salle(s) importée(s)"
    except Exception as e:
        conn.close()
        logger.error(f"Erreur lors de l'import CSV: {e}")
        raise e


_ORDRE_DES_JOURS = ("CASE a.jour WHEN 'lundi' THEN 1 WHEN 'mardi' THEN 2 WHEN 'mercredi' THEN 3 "
                    "WHEN 'jeudi' THEN 4 WHEN 'vendredi' THEN 5 WHEN 'samedi' THEN 6 "
                    "WHEN 'dimanche' THEN 7 END")


def get_room_availability():
    """Créneaux pendant lesquels les salles à disponibilité limitée sont utilisables.

    Chaque créneau : id, room_id, salle (nom actuel de la salle), jour, heure_debut, heure_fin.
    """
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT a.id, a.room_id, r.name, a.jour, a.heure_debut, a.heure_fin
            FROM room_availability a
            JOIN rooms r ON r.id = a.room_id
            WHERE r.limited_availability = 1
            ORDER BY r.display_order, r.id, {_ORDRE_DES_JOURS}, a.heure_debut
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': row[0], 'room_id': row[1], 'salle': row[2], 'jour': row[3],
                 'heure_debut': row[4], 'heure_fin': row[5]} for row in rows]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des créneaux de disponibilité: {e}")
        return []


def add_room_availability(room_id, jour, heure_debut, heure_fin):
    """Ajoute un créneau pour une salle (l'appelant vérifie qu'elle est « à disponibilité limitée »)."""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'''
            INSERT INTO room_availability (room_id, jour, heure_debut, heure_fin)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
        ''', (room_id, jour, heure_debut, heure_fin))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du créneau {jour} {heure_debut}-{heure_fin} (salle {room_id}): {e}")
        return False


def delete_room_availability(availability_id):
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f'DELETE FROM room_availability WHERE id = {placeholder}', (availability_id,))
        conn.commit()
        supprime = cursor.rowcount > 0
        conn.close()
        return supprime
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du créneau {availability_id}: {e}")
        return False
