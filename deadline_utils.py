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

def count_working_days_between(start_datetime, end_date):
    """
    Compte les jours ouvrés complets entre maintenant et une date cible
    Utilise la configuration personnalisée des jours ouvrés
    Exclut le jour de départ et le jour d'arrivée
    
    Args:
        start_datetime (datetime): Date/heure de début
        end_date (datetime): Date de fin (à 8h00)
        
    Returns:
        int: Nombre de jours ouvrés complets entre les deux
    """
    # Import ici pour éviter les dépendances circulaires
    try:
        from database import is_working_day_configured
    except ImportError:
        # Fallback vers la logique par défaut si la base n'est pas disponible
        logger.warning("Base de données non disponible, utilisation logique par défaut")
        current = (start_datetime + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        working_days = 0
        while current < end:
            if current.weekday() < 5:  # Lundi à vendredi par défaut
                working_days += 1
            current += timedelta(days=1)
        
        return working_days
    
    # Commencer au jour suivant après start_datetime
    current = (start_datetime + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    working_days = 0
    while current < end:
        # Utiliser la configuration personnalisée
        date_str = current.strftime('%Y-%m-%d')
        if is_working_day_configured(date_str):
            working_days += 1
        current += timedelta(days=1)
    
    return working_days

def is_request_deadline_respected(request_date_str, current_datetime=None):
    """
    Vérifie si une demande respecte le délai de 2 jours ouvrés
    
    Règles:
    - Lundi 18h: plus possible pour mercredi 18h, mais OK pour jeudi 9h
    - Vendredi 18h: plus possible pour mardi 18h, mais OK pour mercredi 9h
    
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
    if current_datetime is None:
        current_datetime = datetime.now()
    
    try:
        # Parser la date de demande (cours à 8h00)
        request_date = datetime.strptime(request_date_str, '%Y-%m-%d')
        request_datetime = request_date.replace(hour=8, minute=0, second=0)
        
        # Compter les jours ouvrés entre maintenant et la date du cours
        working_days = count_working_days_between(current_datetime, request_datetime)
        
        # Vérifier si on a au moins 2 jours ouvrés complets
        is_valid = working_days >= 2
        
        # Message informatif
        if is_valid:
            message = f"✅ Demande acceptée - {working_days} jour(s) ouvré(s) d'avance"
        else:
            missing = 2 - working_days
            message = f"❌ Délai insuffisant - manque {missing} jour(s) ouvré(s)"
        
        return {
            'valid': is_valid,
            'working_days': working_days,
            'message': message,
            'request_datetime': request_datetime
        }
        
    except ValueError as e:
        logger.error(f"Erreur parsing date: {e}")
        return {
            'valid': False,
            'working_days': 0,
            'message': f"❌ Format de date invalide: {request_date_str}",
            'request_datetime': None
        }

def get_earliest_valid_date(current_datetime=None):
    """
    Retourne la première date valide pour une nouvelle demande (2 jours ouvrés)
    
    Args:
        current_datetime (datetime, optional): Date/heure actuelle
        
    Returns:
        str: Date au format YYYY-MM-DD
    """
    if current_datetime is None:
        current_datetime = datetime.now()
    
    # Commencer par demain
    candidate_date = current_datetime + timedelta(days=1)
    
    # Chercher la première date avec au moins 2 jours ouvrés
    while True:
        # Important: considérer le cours à 8h00 pour le calcul
        candidate_datetime = candidate_date.replace(hour=8, minute=0, second=0, microsecond=0)
        working_days = count_working_days_between(current_datetime, candidate_datetime)
        if working_days >= 2:
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