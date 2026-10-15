"""Réglages de l'établissement (nom affiché, fuseau, heure limite, créneaux horaires, e-mails).

Ils sont modifiables dans /admin/establishment et stockés dans la table `app_settings`.
Toute valeur absente retombe sur DEFAULTS : un établissement n'a donc rien à configurer
pour démarrer, et un réglage vide n'empêche jamais l'application de fonctionner.
"""
import os
import re
from zoneinfo import ZoneInfo, available_timezones

import database

DEFAULTS = {
    'site_name': 'Demande matériel labo',
    'timezone': 'Europe/Madrid',
    'deadline_hour': '8',
    'time_slots': '9h00,9h30,10h00,10h45,11h15,11h45,12h15,12h45,13h15,13h45,'
                  '14h15,14h45,15h15,15h45,16h15,16h45,17h15,18h15',
    'afternoon_start': '13h00',
    'separators': '12h15,15h15',
    'labo_email': '',
    'allowed_domain': '',
}

# Réglages qui décident qui peut se connecter ou obtenir un rôle : réservés à l'administrateur.
SENSITIVE_KEYS = ('labo_email', 'allowed_domain')

_TIME_RE = re.compile(r'^(\d{1,2})h(\d{2})$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_DOMAIN_RE = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')


# --------------------------------------------------------------------------- heures

def parse_time(text):
    """'9h30' -> 570 minutes depuis minuit. Lève ValueError si le format est invalide."""
    match = _TIME_RE.match(str(text).strip().lower())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(f"Horaire invalide : « {text} » (format attendu : 9h30)")
    return int(match.group(1)) * 60 + int(match.group(2))


def format_time(minutes):
    """570 -> '9h30'."""
    return f"{minutes // 60}h{minutes % 60:02d}"


def parse_time_list(text, label='Les horaires'):
    """'9h00, 09h30' -> ['9h00', '9h30'] (normalisés, triés, sans doublon)."""
    items = [part for part in re.split(r'[,;\s]+', str(text or '')) if part]
    return sorted({format_time(parse_time(item)) for item in items}, key=parse_time)


# --------------------------------------------------------------------------- lecture

def get_site_settings():
    """Valeurs effectives (base de données, sinon valeurs par défaut)."""
    values = dict(DEFAULTS)
    try:
        stored = database.get_all_settings()
    except Exception:
        stored = {}
    for key in DEFAULTS:
        if stored.get(key) not in (None, ''):
            values[key] = stored[key]
        elif key in ('labo_email', 'allowed_domain'):
            env_name = 'LABO_EMAIL' if key == 'labo_email' else 'GOOGLE_WORKSPACE_DOMAIN'
            values[key] = os.getenv(env_name, '').strip().lower()
    return values


def get_timezone():
    try:
        return ZoneInfo(get_site_settings()['timezone'])
    except Exception:
        return ZoneInfo(DEFAULTS['timezone'])


def get_deadline_hour():
    try:
        return max(0, min(23, int(get_site_settings()['deadline_hour'])))
    except (TypeError, ValueError):
        return int(DEFAULTS['deadline_hour'])


def get_time_layout(settings=None):
    """Tout ce qui découle de la liste des créneaux de début de cours.

    slots        : créneaux de début proposés dans les formulaires
    morning      : ceux qui commencent avant `afternoon_start` ; afternoon : les autres
    grid_rows    : lignes de l'Excel (créneaux + une ligne de 30 min dans chaque trou d'au moins 1 h)
    editor_rows  : lignes de l'éditeur de planning (grid_rows + une ligne finale de 30 min)
    durations    : {ligne: minutes jusqu'à la ligne suivante} pour l'éditeur
    separators   : lignes renforcées (pause) dans l'éditeur et l'Excel
    """
    settings = settings or get_site_settings()
    try:
        slots = parse_time_list(settings['time_slots']) or parse_time_list(DEFAULTS['time_slots'])
    except ValueError:
        slots = parse_time_list(DEFAULTS['time_slots'])
    minutes = [parse_time(s) for s in slots]

    rows = []
    for index, start in enumerate(minutes):
        rows.append(start)
        following = minutes[index + 1] if index + 1 < len(minutes) else None
        if following is not None and following - start >= 60:
            rows.append(start + 30)
    editor = rows + [rows[-1] + 30]

    try:
        afternoon = parse_time(settings['afternoon_start'])
    except ValueError:
        afternoon = parse_time(DEFAULTS['afternoon_start'])
    try:
        separators = parse_time_list(settings['separators'])
    except ValueError:
        separators = parse_time_list(DEFAULTS['separators'])

    return {
        'slots': slots,
        'morning': [s for s, m in zip(slots, minutes) if m < afternoon],
        'afternoon': [s for s, m in zip(slots, minutes) if m >= afternoon],
        'grid_rows': [format_time(m) for m in rows],
        'editor_rows': [format_time(m) for m in editor],
        'durations': {format_time(m): (editor[i + 1] - m if i + 1 < len(editor) else 30)
                      for i, m in enumerate(editor)},
        'separators': separators,
    }


def get_client_config(settings=None):
    """Ce que le navigateur doit connaître (injecté dans base.html sous window.SITE_CONFIG)."""
    settings = settings or get_site_settings()
    layout = get_time_layout(settings)
    return {
        'siteName': settings['site_name'],
        'timezone': settings['timezone'],
        'deadlineHour': int(settings['deadline_hour']),
        'timeSlots': layout['slots'],
        'editorRows': layout['editor_rows'],
        'slotDurations': layout['durations'],
        'separators': layout['separators'],
    }


# --------------------------------------------------------------------------- écriture

def validate_settings(values):
    """Vérifie les valeurs reçues du formulaire. Renvoie (valeurs_normalisées, erreurs)."""
    clean, errors = {}, {}

    def check(key, label, fn):
        if key not in values:
            return
        try:
            clean[key] = fn(str(values[key]).strip())
        except ValueError as e:
            errors[key] = f"{label} : {e}"

    def site_name(v):
        if not 1 <= len(v) <= 80:
            raise ValueError("entre 1 et 80 caractères")
        return v

    def timezone(v):
        if v not in available_timezones():
            raise ValueError(f"fuseau inconnu « {v} » (exemple : Europe/Paris)")
        return v

    def deadline_hour(v):
        if not v.isdigit() or not 0 <= int(v) <= 23:
            raise ValueError("un nombre entre 0 et 23")
        return str(int(v))

    def time_slots(v):
        slots = parse_time_list(v)
        if len(slots) < 2:
            raise ValueError("au moins deux horaires, séparés par des virgules (ex : 9h00, 9h30)")
        return ','.join(slots)

    def afternoon_start(v):
        return format_time(parse_time(v))

    def separators(v):
        return ','.join(parse_time_list(v))

    def labo_email(v):
        v = v.lower()
        if v and not _EMAIL_RE.match(v):
            raise ValueError("adresse e-mail invalide")
        return v

    def allowed_domain(v):
        v = v.lower().lstrip('@')
        if v and not _DOMAIN_RE.match(v):
            raise ValueError("domaine invalide (exemple : monlycee.fr)")
        return v

    check('site_name', "Nom affiché", site_name)
    check('timezone', "Fuseau horaire", timezone)
    check('deadline_hour', "Heure limite", deadline_hour)
    check('time_slots', "Créneaux horaires", time_slots)
    check('afternoon_start', "Début de l'après-midi", afternoon_start)
    check('separators', "Pauses", separators)
    check('labo_email', "E-mail du compte labo", labo_email)
    check('allowed_domain', "Domaine autorisé", allowed_domain)
    return clean, errors


def save_settings(clean):
    for key, value in clean.items():
        database.set_setting(key, value)
