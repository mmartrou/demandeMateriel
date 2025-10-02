#!/usr/bin/env python3
"""
Test des endpoints API avec validation délai 48h
"""

import sys
import os
from datetime import datetime, timedelta
import json

# Ajouter le répertoire du projet au PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app

def test_api_endpoints():
    """Test des endpoints API avec validation délai"""
    print("=== TEST ENDPOINTS API AVEC VALIDATION DÉLAI ===\n")
    
    # Configuration du client de test Flask
    app.config['TESTING'] = True
    client = app.test_client()
    
    # Test 1: GET /api/requests (devrait marcher)
    print("📡 Test GET /api/requests...")
    response = client.get('/api/requests')
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.get_json()
        print(f"   ✅ Réponse OK - {len(data)} demandes trouvées")
    else:
        print(f"   ❌ Erreur: {response.get_data(as_text=True)}")
    
    # Test 2: POST /api/requests avec date invalide (demain)
    print("\n📤 Test POST /api/requests avec date trop proche...")
    tomorrow = datetime.now() + timedelta(days=1)
    invalid_data = {
        'teacher_id': 1,
        'class_name': 'Test Class',
        'material_description': 'Test Material',
        'days_horaires': [
            {
                'date': tomorrow.strftime('%Y-%m-%d'),
                'horaire': '08:00-10:00'
            }
        ],
        'quantity': 1,
        'selected_materials': 'Ordinateurs'
    }
    
    response = client.post('/api/requests', 
                          data=json.dumps(invalid_data),
                          content_type='application/json')
    print(f"   Status: {response.status_code}")
    if response.status_code == 400:
        data = response.get_json()
        print(f"   ✅ Rejet correct - {data.get('error', 'Erreur inconnue')}")
    else:
        print(f"   ❌ Devrait être rejeté: {response.get_data(as_text=True)}")
    
    # Test 3: POST /api/requests avec date valide (dans 2 semaines)
    print("\n📤 Test POST /api/requests avec date valide...")
    future_date = datetime.now() + timedelta(days=14)
    valid_data = {
        'teacher_id': 1,
        'class_name': 'Test Class Valid',
        'material_description': 'Test Material Valid',
        'days_horaires': [
            {
                'date': future_date.strftime('%Y-%m-%d'),
                'horaire': '08:00-10:00'
            }
        ],
        'quantity': 1,
        'selected_materials': 'Ordinateurs'
    }
    
    response = client.post('/api/requests', 
                          data=json.dumps(valid_data),
                          content_type='application/json')
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        print(f"   ✅ Création réussie")
    elif response.status_code == 400:
        data = response.get_json()
        print(f"   ⚠️  Rejetée - {data.get('error', 'Erreur inconnue')}")
    else:
        print(f"   ❌ Erreur inattendue: {response.get_data(as_text=True)}")
    
    print("\n=== FIN DES TESTS API ===")

if __name__ == "__main__":
    test_api_endpoints()