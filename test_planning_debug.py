#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import planning_generator
import database

# Test avec du debug pour vérifier l'assignation des salles
def test_planning_with_debug(date_str):
    """Test planning generation with debug information"""
    
    # Get raw data first
    raw_requests = database.get_planning_data(date_str)
    raw_rooms = database.get_all_rooms()
    
    print(f"=== TEST PLANNING POUR {date_str} ===")
    print(f"Demandes trouvées: {len(raw_requests)}")
    print(f"Salles disponibles: {len(raw_rooms)}")
    print()
    
    # Show requests details
    print("DEMANDES:")
    for i, req in enumerate(raw_requests):
        material_needs = planning_generator.extract_material_needs(req['selected_materials'])
        has_equipment = any(material_needs[key] > 0 for key in material_needs) or (req['computers_needed'] and req['computers_needed'] > 0)
        
        print(f"  {i+1}. {req['teacher_name']} - {req['class_name']}")
        print(f"      Type salle: {req['room_type']}")
        print(f"      Matériel: {req['selected_materials'] or 'Aucun'}")
        print(f"      Ordinateurs: {req['computers_needed'] or 0}")
        print(f"      Besoins équipement: {'Oui' if has_equipment else 'Non (théorique)'}")
        print()
    
    # Test the planning generation
    success, message = planning_generator.generate_planning(date_str)
    print("RÉSULTAT:")
    print(f"  Succès: {success}")
    print(f"  Message: {message}")

if __name__ == "__main__":
    test_planning_with_debug('2025-09-29')