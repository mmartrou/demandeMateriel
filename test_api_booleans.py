#!/usr/bin/env python3

import json
import logging
logging.basicConfig(level=logging.INFO)

def test_api_boolean_conversion():
    """Test de la conversion des booléens dans l'API"""
    
    print("=== Test API Conversion Booléens ===")
    
    try:
        from app import app
        
        # Créer un client de test Flask
        with app.test_client() as client:
            print("\n1. Test de l'API /api/requests:")
            
            response = client.get('/api/requests')
            
            if response.status_code == 200:
                requests = response.get_json()
                print(f"   ✅ API répond OK - {len(requests)} demandes")
                
                # Analyser les types de données
                print("\n2. Analyse des types de données:")
                for req in requests[:3]:  # Premiers 3
                    prepared = req.get('prepared')
                    modified = req.get('modified')
                    exam = req.get('exam')
                    
                    print(f"   ID {req['id']}:")
                    print(f"     prepared: {prepared} (type: {type(prepared).__name__})")
                    print(f"     modified: {modified} (type: {type(modified).__name__})")
                    print(f"     exam: {exam} (type: {type(exam).__name__})")
                    
                    # Vérifier que ce sont bien des booléens
                    if isinstance(prepared, bool) and isinstance(modified, bool):
                        print(f"     ✅ Types corrects")
                    else:
                        print(f"     ❌ Types incorrects")
                
                # Test des filtres JavaScript
                print("\n3. Test des conditions de filtrage:")
                prepared_count = len([r for r in requests if r.get('prepared') is True])
                modified_count = len([r for r in requests if r.get('modified') is True])
                not_prepared_count = len([r for r in requests if r.get('prepared') is False])
                
                print(f"   Demandes préparées: {prepared_count}")
                print(f"   Demandes modifiées: {modified_count}")
                print(f"   Demandes non préparées: {not_prepared_count}")
                
                if prepared_count > 0 or modified_count > 0:
                    print("   ✅ Le filtrage devrait maintenant fonctionner!")
                else:
                    print("   ⚠️  Aucune demande avec statut préparé/modifié pour tester")
                
            else:
                print(f"   ❌ API erreur: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_boolean_conversion()