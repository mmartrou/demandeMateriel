#!/usr/bin/env python3
"""
Test de diagnostic pour la validation des délais
"""
import sys
import os
from datetime import datetime

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_real_functions():
    print("=== TEST FONCTIONS RÉELLES ===\n")
    
    # Import des vraies fonctions
    from deadline_utils import is_request_deadline_respected, get_earliest_valid_date, count_working_days_between
    from database import is_working_day_configured
    
    # Date actuelle: jeudi 3 octobre 2025
    current = datetime.datetime(2025, 10, 3, 14, 0)
    print(f"📅 Date actuelle: {current.strftime('%A %d/%m/%Y %H:%M')}")
    
    # Test de configuration des jours ouvrés
    print(f"\n🔍 Test configuration jours ouvrés:")
    test_dates = ['2025-10-04', '2025-10-05', '2025-10-06', '2025-10-07', '2025-10-08']
    for date in test_dates:
        date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        is_working = is_working_day_configured(date)
        day_name = date_obj.strftime('%A')
        print(f"   {date} ({day_name}): {'✅ Ouvré' if is_working else '❌ Non ouvré'}")
    
    # Test du calcul des jours ouvrés pour mardi 8 octobre
    print(f"\n🔍 Test calcul jours ouvrés pour mardi 8 octobre:")
    target_date = datetime.datetime(2025, 10, 8, 8, 0)
    working_days = count_working_days_between(current, target_date)
    print(f"   De {current.strftime('%A %d/%m %H:%M')} à {target_date.strftime('%A %d/%m %H:%M')}")
    print(f"   Jours ouvrés calculés: {working_days}")
    
    # Test de validation complète pour mardi 8 octobre
    print(f"\n🔍 Test validation complète pour mardi 8 octobre:")
    result = is_request_deadline_respected('2025-10-08', current)
    print(f"   Valide: {result['valid']}")
    print(f"   Message: {result['message']}")
    print(f"   Jours ouvrés: {result['working_days']}")
    
    # Test première date disponible
    print(f"\n🔍 Test première date disponible:")
    earliest = get_earliest_valid_date(current)
    print(f"   Première date disponible: {earliest}")
    
    # Debug détaillé du calcul
    print(f"\n🔍 Debug détaillé du calcul:")
    current_debug = (current + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_debug = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f"   Début calcul: {current_debug.strftime('%A %d/%m %H:%M')}")
    print(f"   Fin calcul: {end_debug.strftime('%A %d/%m %H:%M')}")
    
    working_count = 0
    check_current = current_debug
    while check_current < end_debug:
        date_str = check_current.strftime('%Y-%m-%d')
        is_working = is_working_day_configured(date_str)
        if is_working:
            working_count += 1
        day_name = check_current.strftime('%A')
        status = "✅ Ouvré" if is_working else "❌ Non ouvré"
        print(f"   {date_str} ({day_name}): {status} - Total: {working_count}")
        check_current += datetime.timedelta(days=1)

if __name__ == "__main__":
    import datetime
    test_real_functions()