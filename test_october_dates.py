#!/usr/bin/env python3
"""
Test rapide de validation des dates
"""
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deadline_utils import is_request_deadline_respected, get_earliest_valid_date, count_working_days_between

def test_october_dates():
    """Test spécifique pour octobre 2025"""
    print("=== TEST DATES OCTOBRE 2025 ===\n")
    
    # Aujourd'hui: jeudi 3 octobre 2025
    current = datetime(2025, 10, 3, 14, 0)  # Jeudi 3 octobre 14h
    print(f"📅 Date actuelle: {current.strftime('%A %d/%m/%Y %H:%M')}")
    
    # Test dates spécifiques
    test_dates = [
        ("2025-10-04", "Vendredi 4 octobre"),  # Demain
        ("2025-10-07", "Lundi 7 octobre"),     # Dans 4 jours
        ("2025-10-08", "Mardi 8 octobre"),    # Dans 5 jours
        ("2025-10-09", "Mercredi 9 octobre"),  # Dans 6 jours
        ("2025-10-17", "Jeudi 17 octobre"),   # Dans 2 semaines
    ]
    
    print("\n📊 Validation des dates:")
    for date_str, description in test_dates:
        result = is_request_deadline_respected(date_str, current)
        
        # Calculer manuellement les jours ouvrés pour vérification
        request_datetime = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=8, minute=0)
        working_days = count_working_days_between(current, request_datetime)
        
        status = "✅" if result['valid'] else "❌"
        print(f"   {status} {description}: {result['message']} (Calculé: {working_days} jours ouvrés)")
    
    # Première date disponible
    earliest = get_earliest_valid_date(current)
    print(f"\n🗓️  Première date disponible: {earliest}")
    
    # Détail du calcul pour mercredi 9 octobre
    print(f"\n🔍 Détail pour mercredi 9 octobre:")
    request_date = datetime(2025, 10, 9, 8, 0)
    working_days = count_working_days_between(current, request_date)
    
    print(f"   - De jeudi 3 oct 14h à mercredi 9 oct 8h")
    print(f"   - Jours entre: vendredi 4, lundi 7, mardi 8")
    print(f"   - Jours ouvrés: lundi 7 + mardi 8 = {working_days} jours")
    print(f"   - Requis: 2 jours minimum")
    print(f"   - Valide: {'OUI' if working_days >= 2 else 'NON'}")

if __name__ == "__main__":
    test_october_dates()