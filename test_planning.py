#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test simple pour la génération de planning
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from planning_generator import generer_planning_excel
from datetime import date

def test_planning():
    """Test basique de génération de planning"""
    try:
        print("Test de génération de planning...")
        
        # Test avec la date d'aujourd'hui
        today = date.today()
        print(f"Date de test: {today}")
        
        success, message = generer_planning_excel(today)
        
        if success:
            print(f"✅ Succès: {message}")
        else:
            print(f"❌ Erreur: {message}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_planning()