#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Ajouter le répertoire parent au chemin pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_planning_function():
    """Test direct de la fonction de planning"""
    try:
        from planning_generator import get_planning_data_for_editor_v2
        
        print("🧪 Test de get_planning_data_for_editor_v2")
        result = get_planning_data_for_editor_v2('2025-10-14')
        
        print(f"✅ Résultat:")
        print(f"  - Cours: {len(result.get('courses', []))}")
        print(f"  - Créneaux: {len(result.get('time_slots', []))}")
        print(f"  - Salles: {len(result.get('rooms', []))}")
        print(f"  - Assignations: {len(result.get('room_assignments', {}))}")
        
        if result.get('courses'):
            print(f"\n📋 Premier cours:")
            print(f"  {result['courses'][0]}")
            
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_planning_function()