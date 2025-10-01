#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.INFO)

print('=== Test Chargement Demandes ===')

try:
    from database import get_material_requests, get_all_teachers, add_material_request
    
    # Test get_material_requests (fonction qui causait l'erreur)
    print('Test get_material_requests()...')
    requests = get_material_requests()
    print(f'✅ Demandes récupérées: {len(requests) if requests else 0}')
    
    # Test ajout d'une demande fictive
    teachers = get_all_teachers()
    if teachers:
        print('Test ajout demande...')
        teacher_id = teachers[0]['id']
        request_id = add_material_request(
            teacher_id=teacher_id,
            request_date='2025-10-02',
            class_name='Test Class',
            material_description='Test matériel',
            horaire='10h00-11h00'
        )
        print(f'✅ Demande ajoutée avec ID: {request_id}')
        
        # Test de récupération après ajout
        requests = get_material_requests()
        print(f'✅ Demandes après ajout: {len(requests) if requests else 0}')
        
    print('\n🎉 Tous les tests de chargement réussis!')
    print('\n➡️ Problème "Erreur lors du chargement des demandes" résolu!')
    
except Exception as e:
    print(f'❌ Erreur: {e}')
    import traceback
    traceback.print_exc()