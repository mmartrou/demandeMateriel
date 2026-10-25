#!/usr/bin/env python3
"""
Utilitaires pour la gestion des délais de demandes de matériel

Règle : le labo doit disposer d'un nombre configurable de jours ouvrés COMPLETS avant le
cours pour préparer le matériel (2 par défaut, réglable dans /admin/working-days). Le couperet
est fixé à une heure réglable (8h00 par défaut), heure de l'établissement, le premier de ces jours ouvrés : passé cette heure, le labo a
déjà commencé sa journée de travail et ce jour ne compte plus comme disponible pour préparer.

Exemple (2 jours ouvrés requis, cours un vendredi) : le labo a besoin du mercredi et du jeudi
pour préparer ; le couperet tombe donc à 8h00 le mercredi (heure de l'établissement, quel que soit le
fuseau horaire du serveur qui exécute ce code).
"""

from datetime import datetime, timedelta, date as date_cls
import logging

logger = logging.getLogger(__name__)

# Le couperet est toujours exprimé dans le fuseau horaire de l'établissement, indépendamment du
# fuseau du serveur (les hébergeurs type Railway tournent en UTC par défaut). Fuseau et heure
# viennent des réglages de /admin/establishment (Europe/Madrid et 8h par défaut).
def _school_tz():
    import site_settings
    return site_settings.get_timezone()


def _deadline_hour():
    import site_settings
    return site_settings.get_deadline_hour()


# Configuration des jours ouvrés (0=lundi, 6=dimanche)
WORKING_DAYS = [0, 1, 2, 3, 4]  # Lundi à Vendredi

def is_working_day(date):
    """
    Vérifie si une date est un jour ouvré par défaut (lundi-vendredi).

    Ceci est uniquement le défaut utilisé quand aucune configuration explicite
    n'existe dans `working_days_config` pour cette date. Les jours fériés ou
    autres exceptions (samedi/dimanche travaillé, pont, etc.) ne sont pas
    déduits automatiquement : ils doivent être déclarés au cas par cas sur
    /admin/working-days, pour que l'affichage de cette page et la validation
    des demandes restent toujours cohérents entre eux.

    Args:
        date (datetime): Date à vérifier

    Returns:
        bool: True si jour ouvré, False sinon
    """
    return date.weekday() in WORKING_DAYS

def _is_working_date(d, overrides):
    """d : objet date (ou datetime). overrides : dict {date_str: bool} ou None."""
    date_str = d.strftime('%Y-%m-%d')
    if overrides and date_str in overrides:
        return bool(overrides[date_str])
    return is_working_day(d)


def _deadline_moment(target_date, required_days, overrides=None):
    """
    Calcule l'instant limite (datetime timezone-aware, fuseau de l'établissement) au-delà duquel une
    demande concernant target_date (date) n'est plus acceptée.

    On remonte, en partant de la veille de target_date, les jours ouvrés un par un jusqu'à en
    avoir trouvé `required_days` ; le couperet est fixé à 8h00 (heure de l'établissement) le plus ancien
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
        return datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=_school_tz())

    d = target_date
    found = 0
    deadline_day = target_date
    while found < required_days:
        d = d - timedelta(days=1)
        if _is_working_date(d, overrides):
            found += 1
            deadline_day = d

    return datetime(deadline_day.year, deadline_day.month, deadline_day.day, _deadline_hour(), 0, 0, tzinfo=_school_tz())


def _now_local(current_datetime=None):
    """Normalise 'maintenant' dans le fuseau de l'établissement, quel que soit le fuseau du serveur.

    Un datetime naïf fourni par un appelant (tests, valeurs historiques) est traité comme déjà
    exprimé en heure de l'établissement plutôt que réinterprété dans un autre fuseau.
    """
    if current_datetime is None:
        return datetime.now(_school_tz())
    if current_datetime.tzinfo is None:
        return current_datetime.replace(tzinfo=_school_tz())
    return current_datetime.astimezone(_school_tz())

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

    Règle : le couperet tombe à 8h00, heure de l'établissement, le premier des jours ouvrés requis
    avant la date demandée (voir _deadline_moment). Exemple avec 2 jours ouvrés requis :
    - Cours un vendredi → couperet mercredi 8h00 (heure de l'établissement) : le labo dispose alors du
      reste du mercredi et de tout le jeudi pour préparer.
    - Cours un lundi → couperet jeudi 8h00 (heure de l'établissement) : le week-end ne compte pas comme
      jour ouvré, donc le labo dispose du jeudi et du vendredi.

    Args:
        request_date_str: date de la demande (str 'YYYY-MM-DD', 'DD-MM-YYYY', date ou datetime)
        current_datetime (datetime, optional): date/heure actuelle (pour les tests). Un datetime
            naïf est traité comme déjà exprimé en heure de l'établissement ; sinon il est converti.

    Returns:
        dict: {
            'valid': bool,
            'working_days': int (nombre de jours ouvrés requis, pour compatibilité),
            'message': str,
            'request_datetime': datetime | None
        }
    """
    import sys
    now_local = _now_local(current_datetime)

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
    is_valid = now_local < deadline

    # Log de diagnostic détaillé
    print(f"[DEBUG deadline_utils] Calcul délai: maintenant(local)={now_local.isoformat()} | demande={request_date_str} | couperet(local)={deadline.isoformat()} | valid={is_valid}", file=sys.stderr)

    deadline_str = deadline.strftime('%A %d/%m à %Hh%M')
    if is_valid:
        message = f"✅ Demande acceptée - couperet {deadline_str} (heure de l'établissement)"
    else:
        message = f"❌ Délai dépassé - le couperet était {deadline_str} (heure de l'établissement)"

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
    peuvent de toute façon pas accueillir de demande) dont le couperet de 8h00 heure de l'établissement
    n'est pas encore passé.
    overrides et required_days peuvent être pré-chargés pour éviter des connexions DB.
    """
    now_local = _now_local(current_datetime)

    if overrides is None:
        try:
            from database import get_working_day_overrides
            overrides = get_working_day_overrides()
        except ImportError:
            overrides = {}

    if required_days is None:
        required_days = get_required_working_days()

    candidate = now_local.date() + timedelta(days=1)
    while True:
        if _is_working_date(candidate, overrides):
            deadline = _deadline_moment(candidate, required_days, overrides=overrides)
            if now_local < deadline:
                return candidate.strftime('%Y-%m-%d')
        candidate += timedelta(days=1)

if __name__ == "__main__":
    # Tests de la logique — tous les datetime ci-dessous sont naïfs et donc interprétés comme
    # déjà en heure de l'établissement (voir _now_local).
    print("=== Test délai de dépôt (couperet 8h00 heure de l'établissement) ===")

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
