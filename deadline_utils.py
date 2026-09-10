#!/usr/bin/env python3
"""
Utilitaires pour la gestion des délais de demandes de matériel

Règle : le labo doit disposer d'un nombre configurable de jours ouvrés COMPLETS avant le
cours pour préparer le matériel (2 par défaut, réglable dans /admin/working-days). Le couperet
est fixé à 8h00, heure de Madrid, le premier de ces jours ouvrés : passé cette heure, le labo a
déjà commencé sa journée de travail et ce jour ne compte plus comme disponible pour préparer.

Exemple (2 jours ouvrés requis, cours un vendredi) : le labo a besoin du mercredi et du jeudi
pour préparer ; le couperet tombe donc à 8h00 le mercredi (heure de Madrid, quel que soit le
fuseau horaire du serveur qui exécute ce code).
"""

from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# Le couperet est toujours exprimé en heure de Madrid, indépendamment du fuseau horaire du
# serveur (les plateformes d'hébergement type Railway tournent en UTC par défaut).
MADRID_TZ = ZoneInfo("Europe/Madrid")
DEADLINE_HOUR = 8

# Configuration des jours ouvrés (0=lundi, 6=dimanche)
WORKING_DAYS = [0, 1, 2, 3, 4]  # Lundi à Vendredi

# Jours fériés fixes (format MM-DD)
FRENCH_HOLIDAYS = [
    '01-01',  # Jour de l'an
    '05-01',  # Fête du travail
    '05-08',  # Victoire 1945
    '07-14',  # Fête nationale
    '08-15',  # Assomption
    '11-01',  # Toussaint
    '11-11',  # Armistice
    '12-25',  # Noël
]

def is_working_day(date):
    """
    Vérifie si une date est un jour ouvré (lundi-vendredi, hors jours fériés)
    
    Args:
        date (datetime): Date à vérifier
        
    Returns:
        bool: True si jour ouvré, False sinon
    """
    # Vérifier si c'est un weekend
    if date.weekday() not in WORKING_DAYS:
        return False
    
    # Vérifier si c'est un jour férié
    date_str = date.strftime('%m-%d')
    if date_str in FRENCH_HOLIDAYS:
        return False
    
    # TODO: Ajouter Pâques, Ascension, Pentecôte (dates variables)
    
    return True

def add_working_hours(start_datetime, hours_to_add):
    """
    Ajoute des heures ouvrées à partir d'une date/heure de départ
    
    Args:
        start_datetime (datetime): Date/heure de départ
        hours_to_add (int): Nombre d'heures ouvrées à ajouter
        
    Returns:
        datetime: Date/heure après ajout des heures ouvrées
    """
    current = start_datetime
    remaining_hours = hours_to_add
    
    while remaining_hours > 0:
        # Si on n'est pas sur un jour ouvré, passer au prochain jour ouvré
        if not is_working_day(current):
            current = current.replace(hour=8, minute=0, second=0) + timedelta(days=1)
            continue
        
        # Heures de travail : 8h-18h (10h par jour)
        work_start = current.replace(hour=8, minute=0, second=0)
        work_end = current.replace(hour=18, minute=0, second=0)
        
        # Si on est avant les heures de travail
        if current < work_start:
            current = work_start
        
        # Si on est après les heures de travail, passer au jour suivant
        if current >= work_end:
            current = current.replace(hour=8, minute=0, second=0) + timedelta(days=1)
            continue
        
        # Calculer les heures disponibles aujourd'hui
        hours_left_today = (work_end - current).total_seconds() / 3600
        
        if remaining_hours <= hours_left_today:
            # On peut terminer aujourd'hui
            current += timedelta(hours=remaining_hours)
            remaining_hours = 0
        else:
            # Passer au jour suivant
            remaining_hours -= hours_left_today
            current = current.replace(hour=8, minute=0, second=0) + timedelta(days=1)
    
    return current

def _is_working_date(d, overrides):
    """d : objet date (ou datetime). overrides : dict {date_str: bool} ou None."""
    date_str = d.strftime('%Y-%m-%d')
    if overrides and date_str in overrides:
        return bool(overrides[date_str])
    return is_working_day(d)


def _deadline_moment(target_date, required_days, overrides=None):
    """
    Calcule l'instant limite (datetime timezone-aware, Europe/Madrid) au-delà duquel une
    demande concernant target_date (date) n'est plus acceptée.

    On remonte, en partant de la veille de target_date, les jours ouvrés un par un jusqu'à en
    avoir trouvé `required_days` ; le couperet est fixé à 8h00 (heure de Madrid) le plus ancien
    de ces jours : passé ce couperet, ce jour est considéré comme "commencé" pour le labo et ne
    compte plus comme disponible pour préparer.

    overrides : dict {date_str: bool} pré-chargé (évite une connexion DB si fourni).
    """
    if overrides is None:
        try:
            from database import get_working_day_overrides
            overrides = get_working_day_overrides()
        except ImportError:
            logger.warning("Base de données non disponible, utilisation logique par défaut")
            overrides = {}

    if required_days <= 0:
        # Aucun délai requis : le couperet est le tout début de la journée cible elle-même.
        return datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=MADRID_TZ)

    d = target_date
    found = 0
    deadline_day = target_date
    while found < required_days:
        d = d - timedelta(days=1)
        if _is_working_date(d, overrides):
            found += 1
            deadline_day = d

    return datetime(deadline_day.year, deadline_day.month, deadline_day.day, DEADLINE_HOUR, 0, 0, tzinfo=MADRID_TZ)


def _now_madrid(current_datetime=None):
    """Normalise 'maintenant' en heure de Madrid, quel que soit le fuseau du serveur.

    Un datetime naïf fourni par un appelant (tests, valeurs historiques) est traité comme déjà
    exprimé en heure de Madrid plutôt que réinterprété dans un autre fuseau.
    """
    if current_datetime is None:
        return datetime.now(MADRID_TZ)
    if current_datetime.tzinfo is None:
        return current_datetime.replace(tzinfo=MADRID_TZ)
    return current_datetime.astimezone(MADRID_TZ)

def get_required_working_days():
    """
    Nombre de jours ouvrés requis avant une demande. Configurable en base
    (table app_settings, via /admin/working-days) pour gérer les cas exceptionnels.
    Retombe sur 2 si la base n'est pas disponible.
    """
    try:
        from database import get_deadline_working_days
        return get_deadline_working_days()
    except ImportError:
        return 2

def is_request_deadline_respected(request_date_str, current_datetime=None, overrides=None, required_days=None):
    """
    Vérifie si une demande respecte le délai de dépôt (2 jours ouvrés par défaut).

    Règle : le couperet tombe à 8h00, heure de Madrid, le premier des jours ouvrés requis
    avant la date demandée (voir _deadline_moment). Exemple avec 2 jours ouvrés requis :
    - Cours un vendredi → couperet mercredi 8h00 (heure de Madrid) : le labo dispose alors du
      reste du mercredi et de tout le jeudi pour préparer.
    - Cours un lundi → couperet jeudi 8h00 (heure de Madrid) : le week-end ne compte pas comme
      jour ouvré, donc le labo dispose du jeudi et du vendredi.

    Args:
        request_date_str: date de la demande (str 'YYYY-MM-DD', 'DD-MM-YYYY', date ou datetime)
        current_datetime (datetime, optional): date/heure actuelle (pour les tests). Un datetime
            naïf est traité comme déjà exprimé en heure de Madrid ; sinon il est converti.

    Returns:
        dict: {
            'valid': bool,
            'working_days': int (nombre de jours ouvrés requis, pour compatibilité),
            'message': str,
            'request_datetime': datetime | None
        }
    """
    import sys
    now_madrid = _now_madrid(current_datetime)

    # Si déjà un objet date ou datetime, utiliser directement
    from datetime import date, datetime as dt
    if isinstance(request_date_str, dt):
        request_date = request_date_str
    elif isinstance(request_date_str, date):
        request_date = dt.combine(request_date_str, dt.min.time())
    else:
        # Essayer plusieurs formats de date
        parsed = False
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%a, %d %b %Y %H:%M:%S GMT'):
            try:
                request_date = dt.strptime(request_date_str, fmt)
                if fmt == '%d-%m-%Y':
                    logger.warning(f"Date reçue au format français: {request_date_str} → {request_date.strftime('%Y-%m-%d')}")
                parsed = True
                break
            except ValueError:
                continue
        if not parsed:
            logger.error(f"Erreur parsing date (formats attendus YYYY-MM-DD, DD-MM-YYYY ou RFC1123): {request_date_str}")
            print(f"[DEBUG deadline_utils] Erreur parsing date: {request_date_str}", file=sys.stderr)
            return {
                'valid': False,
                'working_days': 0,
                'message': f"❌ Format de date invalide: {request_date_str}",
                'request_datetime': None
            }

    request_datetime = request_date.replace(hour=8, minute=0, second=0)

    # Nombre de jours ouvrés requis (configurable par un admin/labo, 2 par défaut)
    if required_days is None:
        required_days = get_required_working_days()

    deadline = _deadline_moment(request_date.date(), required_days, overrides=overrides)
    is_valid = now_madrid < deadline

    # Log de diagnostic détaillé
    print(f"[DEBUG deadline_utils] Calcul délai: maintenant(Madrid)={now_madrid.isoformat()} | demande={request_date_str} | couperet(Madrid)={deadline.isoformat()} | valid={is_valid}", file=sys.stderr)

    deadline_str = deadline.strftime('%A %d/%m à %Hh%M')
    if is_valid:
        message = f"✅ Demande acceptée - couperet {deadline_str} (heure de Madrid)"
    else:
        message = f"❌ Délai dépassé - le couperet était {deadline_str} (heure de Madrid)"

    return {
        'valid': is_valid,
        'working_days': required_days,
        'message': message,
        'request_datetime': request_datetime
    }

def get_earliest_valid_date(current_datetime=None, overrides=None, required_days=None):
    """
    Retourne la première date (YYYY-MM-DD) pour laquelle une nouvelle demande serait encore
    acceptée : le premier jour ouvré (on ignore d'emblée les week-ends/jours fériés, qui ne
    peuvent de toute façon pas accueillir de demande) dont le couperet de 8h00 heure de Madrid
    n'est pas encore passé.
    overrides et required_days peuvent être pré-chargés pour éviter des connexions DB.
    """
    now_madrid = _now_madrid(current_datetime)

    if overrides is None:
        try:
            from database import get_working_day_overrides
            overrides = get_working_day_overrides()
        except ImportError:
            overrides = {}

    if required_days is None:
        required_days = get_required_working_days()

    candidate = now_madrid.date() + timedelta(days=1)
    while True:
        if _is_working_date(candidate, overrides):
            deadline = _deadline_moment(candidate, required_days, overrides=overrides)
            if now_madrid < deadline:
                return candidate.strftime('%Y-%m-%d')
        candidate += timedelta(days=1)

if __name__ == "__main__":
    # Tests de la logique — tous les datetime ci-dessous sont naïfs et donc interprétés comme
    # déjà en heure de Madrid (voir _now_madrid).
    print("=== Test délai de dépôt (couperet 8h00 heure de Madrid) ===")

    target_friday = "2026-09-18"  # vendredi

    # Mardi 15/09, juste avant le couperet du mercredi 8h : encore accepté
    result = is_request_deadline_respected(target_friday, datetime(2026, 9, 15, 23, 59))
    print(f"Mardi 23h59 → Vendredi: {result['message']}")

    # Mercredi 16/09 8h00 pile : refusé (le couperet tombe AU couperet, pas juste après)
    result = is_request_deadline_respected(target_friday, datetime(2026, 9, 16, 8, 0))
    print(f"Mercredi 8h00 → Vendredi: {result['message']}")

    # Mercredi 16/09 7h59 : encore accepté
    result = is_request_deadline_respected(target_friday, datetime(2026, 9, 16, 7, 59))
    print(f"Mercredi 7h59 → Vendredi: {result['message']}")

    # Date minimale pour une nouvelle demande, calculée depuis un jeudi après-midi
    thursday = datetime(2026, 9, 10, 14, 0)
    earliest = get_earliest_valid_date(thursday)
    print(f"Plus tôt possible depuis jeudi 14h: {earliest}")