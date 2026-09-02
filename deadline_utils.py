#!/usr/bin/env python3
"""
Utilitaires pour la gestion des délais de demandes de matériel
Règle: 48h ouvrées avant les cours pour nouvelles demandes et modifications
"""

from datetime import datetime, timedelta, time
import logging

logger = logging.getLogger(__name__)

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

def count_working_days_between(start_datetime, end_date, overrides=None):
    """
    Compte les jours ouvrés complets entre maintenant et une date cible.
    overrides : dict {date_str: bool} pré-chargé (évite une connexion DB si fourni).
    """
    # Appliquer la règle de 17h
    if start_datetime.hour >= 17:
        current = (start_datetime + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        current = (start_datetime + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if overrides is None:
        try:
            from database import get_working_day_overrides
            overrides = get_working_day_overrides()
        except ImportError:
            logger.warning("Base de données non disponible, utilisation logique par défaut")
            overrides = {}

    working_days = 0
    while current < end:
        date_str = current.strftime('%Y-%m-%d')
        if date_str in overrides:
            if overrides[date_str]:
                working_days += 1
        elif current.weekday() < 5:
            working_days += 1
        current += timedelta(days=1)

    return working_days

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
    Vérifie si une demande respecte le délai de 2 jours ouvrés
    
    Règles:
    - Avant 17h : peut demander pour J+3 minimum (2 jours ouvrés entre J+1 et date demandée)
    - Après 17h : peut demander pour J+4 minimum (2 jours ouvrés entre J+2 et date demandée)
    
    Exemples:
    - Vendredi 16h → Mardi OK (lundi et mardi = 2 jours ouvrés entre samedi et mercredi)
    - Vendredi 18h → Mercredi OK (lundi et mardi = 2 jours ouvrés entre dimanche et mercredi)
    
    Args:
        request_date_str (str): Date de la demande au format YYYY-MM-DD
        current_datetime (datetime, optional): Date/heure actuelle (pour les tests)
        
    Returns:
        dict: {
            'valid': bool,
            'working_days': int,
            'message': str
        }
    """
    import sys
    if current_datetime is None:
        current_datetime = datetime.utcnow()


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

    # Log de diagnostic détaillé
    print(f"[DEBUG deadline_utils] Calcul délai: now(UTC)={current_datetime.isoformat()} | demande={request_date_str} → {request_datetime.isoformat()}", file=sys.stderr)

    # Compter les jours ouvrés entre maintenant et la date du cours
    working_days = count_working_days_between(current_datetime, request_datetime, overrides=overrides)

    # Log du nombre de jours ouvrés
    print(f"[DEBUG deadline_utils] Jours ouvrés calculés: {working_days}", file=sys.stderr)

    # Nombre de jours ouvrés requis (configurable par un admin/labo, 2 par défaut)
    if required_days is None:
        required_days = get_required_working_days()

    # Vérifier si on a au moins le nombre de jours ouvrés requis
    is_valid = working_days >= required_days

    # Message informatif
    if is_valid:
        message = f"✅ Demande acceptée - {working_days} jour(s) ouvré(s) d'avance"
    else:
        missing = required_days - working_days
        message = f"❌ Délai insuffisant - manque {missing} jour(s) ouvré(s)"

    # Log du résultat final
    print(f"[DEBUG deadline_utils] Résultat: valid={is_valid} | message={message}", file=sys.stderr)

    return {
        'valid': is_valid,
        'working_days': working_days,
        'message': message,
        'request_datetime': request_datetime
    }

def get_earliest_valid_date(current_datetime=None, overrides=None, required_days=None):
    """
    Retourne la première date valide pour une nouvelle demande (2 jours ouvrés).
    overrides et required_days peuvent être pré-chargés pour éviter des connexions DB.
    """
    if current_datetime is None:
        current_datetime = datetime.now()

    if overrides is None:
        try:
            from database import get_working_day_overrides
            overrides = get_working_day_overrides()
        except ImportError:
            overrides = {}

    if required_days is None:
        required_days = get_required_working_days()

    # Appliquer la règle de 17h pour déterminer le point de départ
    if current_datetime.hour >= 17:
        candidate_date = current_datetime + timedelta(days=2)
    else:
        candidate_date = current_datetime + timedelta(days=1)

    while True:
        candidate_datetime = candidate_date.replace(hour=8, minute=0, second=0, microsecond=0)
        working_days = count_working_days_between(current_datetime, candidate_datetime, overrides=overrides)
        if working_days >= required_days:
            return candidate_date.strftime('%Y-%m-%d')
        candidate_date += timedelta(days=1)

if __name__ == "__main__":
    # Tests de la logique
    print("=== Test Délais 48h Ouvrées ===")
    
    # Test 1: Demande pour lundi prochain (depuis vendredi)
    friday = datetime(2025, 10, 3, 14, 0)  # Vendredi 14h
    monday = "2025-10-07"  # Lundi suivant
    
    result = is_request_deadline_respected(monday, friday)
    print(f"Vendredi 14h → Lundi: {result['message']}")
    
    # Test 2: Demande trop tard
    result = is_request_deadline_respected("2025-10-02", friday)
    print(f"Vendredi 14h → Mercredi: {result['message']}")
    
    # Test 3: Date minimale
    earliest = get_earliest_valid_date(friday)
    print(f"Plus tôt possible depuis vendredi: {earliest}")