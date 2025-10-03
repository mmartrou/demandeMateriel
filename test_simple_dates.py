#!/usr/bin/env python3
"""
Test rapide de validation des dates - version simple
"""
from datetime import datetime, timedelta

def count_working_days_simple(start_datetime, end_datetime):
    """Version simple du calcul sans base de données"""
    current = (start_datetime + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    
    working_days = 0
    while current < end:
        # Lundi = 0, ..., Vendredi = 4 (jours ouvrés)
        if current.weekday() < 5:  
            working_days += 1
        current += timedelta(days=1)
    
    return working_days

def test_simple():
    print("=== TEST SIMPLE DATES OCTOBRE 2025 ===\n")
    
    # Aujourd'hui: jeudi 3 octobre 2025
    current = datetime(2025, 10, 3, 14, 0)  # Jeudi 3 octobre 14h
    print(f"📅 Date actuelle: {current.strftime('%A %d/%m/%Y %H:%M')}")
    
    # Tests pour plusieurs dates
    test_dates = [
        (datetime(2025, 10, 7, 8, 0), "Lundi 7 octobre"),
        (datetime(2025, 10, 8, 8, 0), "Mardi 8 octobre"),  
        (datetime(2025, 10, 9, 8, 0), "Mercredi 9 octobre"),
        (datetime(2025, 10, 10, 8, 0), "Jeudi 10 octobre"),
    ]
    
    for request_date, description in test_dates:
        working_days = count_working_days_simple(current, request_date)
        
        print(f"\n🔍 Test {description} 8h:")
        print(f"   - Début: {current.strftime('%A %d/%m/%Y %H:%M')}")
        print(f"   - Fin: {request_date.strftime('%A %d/%m/%Y %H:%M')}")
        print(f"   - Jours ouvrés comptés: {working_days}")
        print(f"   - Requis: 2 minimum")
        print(f"   - Valide: {'✅ OUI' if working_days >= 2 else '❌ NON'}")
    
    # Fonction de recherche de première date valide
    def get_first_valid_date(current_dt):
        candidate = current_dt + timedelta(days=1)
        while True:
            candidate_8h = candidate.replace(hour=8, minute=0, second=0, microsecond=0)
            working_days = count_working_days_simple(current_dt, candidate_8h)
            if working_days >= 2:
                return candidate.strftime('%Y-%m-%d')
            candidate += timedelta(days=1)
    
    first_valid = get_first_valid_date(current)
    print(f"\n🗓️ Première date valide calculée: {first_valid}")

if __name__ == "__main__":
    test_simple()