"""Jours ouvrés : configuration des exceptions (jours fériés, jours travaillés)."""
import logging
import sqlite3

from .connexion import get_db_connection

logger = logging.getLogger(__name__)


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
            WHERE date >= {placeholder} AND date <= {placeholder}
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
    # Always return list of dicts, compatible with SQLite, PostgreSQL, tuple, or Row
    def row_to_dict(row):
        if isinstance(row, dict):
            return row
        elif hasattr(row, '_asdict'):
            return row._asdict()
        elif isinstance(row, sqlite3.Row):
            return {
                'date': row['date'],
                'is_working_day': row['is_working_day'],
                'description': row['description']
            }
        elif isinstance(row, (list, tuple)):
            # For PostgreSQL: (id, date, is_working_day, description, created_at, updated_at)
            # For SQLite: (date, is_working_day, description)
            if len(row) >= 6:
                return {
                    'date': row[1],
                    'is_working_day': row[2],
                    'description': row[3] if len(row) > 3 else ''
                }
            elif len(row) == 3:
                return {
                    'date': row[0],
                    'is_working_day': row[1],
                    'description': row[2]
                }
            else:
                return {
                    'date': row[0] if len(row) > 0 else None,
                    'is_working_day': row[1] if len(row) > 1 else None,
                    'description': row[2] if len(row) > 2 else ''
                }
        else:
            # Fallback: try attribute access
            return {
                'date': getattr(row, 'date', None),
                'is_working_day': getattr(row, 'is_working_day', None),
                'description': getattr(row, 'description', '')
            }
    return [row_to_dict(row) for row in results]


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


def get_working_day_overrides():
    """Retourne toutes les surcharges de jours ouvrés en une seule requête : {date_str: bool}."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, is_working_day FROM working_days_config')
    rows = cursor.fetchall()
    conn.close()
    return {str(row[0]): bool(row[1]) for row in rows}


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
        # Défaut: lundi-vendredi hors jours fériés (une entrée dans working_days_config
        # permet de forcer un jour normalement non-ouvré, ou l'inverse, au cas par cas)
        from datetime import datetime
        from deadline_utils import is_working_day
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        return is_working_day(date_obj)


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
