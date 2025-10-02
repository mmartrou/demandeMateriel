#!/usr/bin/env python3
"""
Test d'intégration pour la validation du délai de 48h ouvrées
"""

import sys
import os
from datetime import datetime, timedelta

# Ajouter le répertoire du projet au PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deadline_utils import is_request_deadline_respected, get_earliest_valid_date

def test_deadline_validation():
    """Test complet de la validation des délais"""
    print("=== TEST VALIDATION DÉLAI 48H OUVRÉES ===\n")
    
    # Test 1: Date trop proche (demain)
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime('%Y-%m-%d')
    print(f"📅 Test demain ({tomorrow_str}):")
    validation = is_request_deadline_respected(tomorrow_str)
    print(f"   ✓ Valide: {validation['valid']}")
    print(f"   📝 Message: {validation['message']}")
    print()
    
    # Test 2: Date dans une semaine
    next_week = datetime.now() + timedelta(days=7)
    next_week_str = next_week.strftime('%Y-%m-%d')
    print(f"📅 Test dans 7 jours ({next_week_str}):")
    validation = is_request_deadline_respected(next_week_str)
    print(f"   ✓ Valide: {validation['valid']}")
    print(f"   📝 Message: {validation['message']}")
    print()
    
    # Test 3: Date dans 2 semaines (devrait être valide)
    two_weeks = datetime.now() + timedelta(days=14)
    two_weeks_str = two_weeks.strftime('%Y-%m-%d')
    print(f"📅 Test dans 14 jours ({two_weeks_str}):")
    validation = is_request_deadline_respected(two_weeks_str)
    print(f"   ✓ Valide: {validation['valid']}")
    print(f"   📝 Message: {validation['message']}")
    print()
    
    # Test 4: Première date disponible
    earliest = get_earliest_valid_date()
    print(f"🗓️  Première date disponible: {earliest}")
    print()
    
    # Test 5: Validation de la première date disponible
    print(f"📅 Validation de la première date disponible ({earliest}):")
    validation = is_request_deadline_respected(earliest)
    print(f"   ✓ Valide: {validation['valid']}")
    print(f"   📝 Message: {validation['message']}")
    
    print("\n=== FIN DES TESTS ===")

if __name__ == "__main__":
    test_deadline_validation()