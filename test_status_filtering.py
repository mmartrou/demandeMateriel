#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.INFO)

def test_status_filtering():
    """Test du filtrage des statuts prepared/modified"""
    
    print("=== Test Filtrage Statuts ===")
    
    try:
        from database import get_material_requests, add_material_request, get_all_teachers
        
        # Récupérer toutes les demandes
        print("\n1. Récupération de toutes les demandes:")
        requests = get_material_requests()
        print(f"   Total demandes: {len(requests)}")
        
        # Analyser les valeurs des champs prepared/modified
        print("\n2. Analyse des champs prepared/modified:")
        for req in requests[:5]:  # Premiers 5
            prepared = req['prepared'] if 'prepared' in req.keys() else None
            modified = req['modified'] if 'modified' in req.keys() else None
            print(f"   ID {req['id']}: prepared={prepared} (type: {type(prepared).__name__}), modified={modified} (type: {type(modified).__name__})")
            print(f"   Colonnes disponibles: {list(req.keys())}")
        
        # Test de création d'une demande avec statuts différents
        print("\n3. Test création demande avec statuts:")
        teachers = get_all_teachers()
        if teachers:
            teacher_id = teachers[0]['id']
            
            # Ajouter une demande
            request_id = add_material_request(
                teacher_id=teacher_id,
                request_date='2025-10-02',
                class_name='Test Status',
                material_description='Test pour filtrage statut'
            )
            print(f"   ✅ Demande créée ID: {request_id}")
            
            # Vérifier les valeurs par défaut
            from database import get_material_request_by_id
            new_req = get_material_request_by_id(request_id)
            if new_req:
                prepared = new_req['prepared'] if 'prepared' in new_req.keys() else None
                modified = new_req['modified'] if 'modified' in new_req.keys() else None
                print(f"   Nouvelle demande - prepared: {prepared} (type: {type(prepared).__name__})")
                print(f"   Nouvelle demande - modified: {modified} (type: {type(modified).__name__})")
            
            # Test du toggle prepared
            from database import toggle_prepared_status
            print("\n4. Test toggle prepared status:")
            success = toggle_prepared_status(request_id)
            print(f"   Toggle réussi: {success}")
            
            # Vérifier après toggle
            toggled_req = get_material_request_by_id(request_id)
            if toggled_req:
                prepared = toggled_req['prepared'] if 'prepared' in toggled_req.keys() else None
                print(f"   Après toggle - prepared: {prepared} (type: {type(prepared).__name__})")
        
        print("\n🔍 Diagnostic:")
        print("   - Vérifier si prepared/modified sont des booléens (True/False)")
        print("   - Ou des entiers (1/0) selon le type de base de données")
        print("   - Le JavaScript doit comparer avec les bonnes valeurs")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_status_filtering()