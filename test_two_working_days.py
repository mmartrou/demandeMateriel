#!/usr/bin/env python3
"""
Test spécifique pour la validation de 2 jours ouvrés
"""

import sys
import os
from datetime import datetime

# Ajouter le répertoire du projet au PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deadline_utils import is_request_deadline_respected, get_earliest_valid_date

def test_two_working_days():
    """Test des cas spécifiques demandés"""
    print("=== TEST VALIDATION 2 JOURS OUVRÉS ===\n")
    
    # Test 1: Lundi 18h → mercredi 18h (NON) vs jeudi 9h (OUI)
    print("📅 Test 1: Lundi 18h")
    monday_6pm = datetime(2025, 10, 6, 18, 0)  # Lundi 6 octobre 18h
    
    # Mercredi (2 jours après, mais pas 2 jours ouvrés complets)
    wednesday = "2025-10-08"  # Mercredi 8 octobre
    result_wed = is_request_deadline_respected(wednesday, monday_6pm)
    print(f"   → Mercredi 8h: {result_wed['message']} (Jours ouvrés: {result_wed['working_days']})")
    
    # Jeudi (3 jours après, 2 jours ouvrés complets)
    thursday = "2025-10-09"  # Jeudi 9 octobre
    result_thu = is_request_deadline_respected(thursday, monday_6pm)
    print(f"   → Jeudi 8h: {result_thu['message']} (Jours ouvrés: {result_thu['working_days']})")
    
    # Test 2: Vendredi 18h → mardi 18h (NON) vs mercredi 9h (OUI)
    print("\n📅 Test 2: Vendredi 18h")
    friday_6pm = datetime(2025, 10, 3, 18, 0)  # Vendredi 3 octobre 18h
    
    # Mardi (4 jours après, mais seulement 1 jour ouvré complet à cause du weekend)
    tuesday = "2025-10-07"  # Mardi 7 octobre
    result_tue = is_request_deadline_respected(tuesday, friday_6pm)
    print(f"   → Mardi 8h: {result_tue['message']} (Jours ouvrés: {result_tue['working_days']})")
    
    # Mercredi (5 jours après, 2 jours ouvrés complets)
    wednesday2 = "2025-10-08"  # Mercredi 8 octobre
    result_wed2 = is_request_deadline_respected(wednesday2, friday_6pm)
    print(f"   → Mercredi 8h: {result_wed2['message']} (Jours ouvrés: {result_wed2['working_days']})")
    
    # Test 3: Première date disponible
    print(f"\n🗓️  Première date disponible depuis lundi 18h: {get_earliest_valid_date(monday_6pm)}")
    print(f"🗓️  Première date disponible depuis vendredi 18h: {get_earliest_valid_date(friday_6pm)}")
    
    print("\n=== RÉSUMÉ DES RÈGLES ===")
    print("✅ Il faut 2 JOURS OUVRÉS COMPLETS entre la demande et le cours")
    print("✅ Les weekends ne comptent pas comme jours ouvrés")
    print("✅ Le cours est considéré à 8h du matin")
    
    print("\n=== FIN DES TESTS ===")

if __name__ == "__main__":
    test_two_working_days()