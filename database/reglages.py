"""Paramètres de l'application (table app_settings, clé/valeur) avec cache."""
import time

from .connexion import get_db_connection


DEADLINE_WORKING_DAYS_KEY = 'deadline_working_days'


DEFAULT_DEADLINE_WORKING_DAYS = 2


def get_setting(key, default=None):
    """Récupère une valeur de app_settings (str), ou default si absente."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    cursor.execute(f'SELECT value FROM app_settings WHERE key = {placeholder}', (key,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return default
    return row['value'] if isinstance(row, dict) else row[0]


# Les réglages sont lus à chaque page affichée : on les garde 30 s en mémoire pour éviter une
# requête par page. set_setting() vide le cache du processus qui écrit ; les autres processus
# (workers gunicorn) voient le changement au plus tard 30 s après.
_SETTINGS_TTL_SECONDS = 30


_settings_cache = {'at': 0.0, 'values': None}


def clear_settings_cache():
    _settings_cache['at'] = 0.0
    _settings_cache['values'] = None


def get_all_settings():
    """Tous les réglages de app_settings sous forme de dict {clé: valeur} (avec cache)."""
    maintenant = time.monotonic()
    if _settings_cache['values'] is not None and maintenant - _settings_cache['at'] < _SETTINGS_TTL_SECONDS:
        return dict(_settings_cache['values'])
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM app_settings')
    rows = cursor.fetchall()
    conn.close()
    values = {(row['key'] if isinstance(row, dict) else row[0]): (row['value'] if isinstance(row, dict) else row[1])
              for row in rows}
    _settings_cache['values'] = values
    _settings_cache['at'] = maintenant
    return dict(values)


def set_setting(key, value):
    """Crée ou met à jour une valeur de app_settings."""
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    placeholder = '%s' if db_type == 'postgresql' else '?'
    if db_type == 'postgresql':
        cursor.execute(f'''
            INSERT INTO app_settings (key, value, updated_at)
            VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        ''', (key, str(value)))
    else:
        cursor.execute(f'''
            INSERT OR REPLACE INTO app_settings (key, value, updated_at)
            VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP)
        ''', (key, str(value)))
    conn.commit()
    conn.close()
    clear_settings_cache()


def get_deadline_working_days():
    """Nombre de jours ouvrés requis avant une demande (délai de dépôt). Configurable par un admin/labo."""
    value = get_setting(DEADLINE_WORKING_DAYS_KEY, DEFAULT_DEADLINE_WORKING_DAYS)
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_DEADLINE_WORKING_DAYS


def set_deadline_working_days(days):
    """Définit le nombre de jours ouvrés requis avant une demande."""
    days = int(days)
    if days < 0:
        raise ValueError('Le délai ne peut pas être négatif')
    set_setting(DEADLINE_WORKING_DAYS_KEY, days)
    return days
