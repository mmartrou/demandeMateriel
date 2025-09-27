#!/usr/bin/env python3
"""
Script de test pour vérifier que l'API renvoie bien les horaires
"""

import requests
import json

def test_api_requests():
    """Test de l'API /api/requests pour vérifier la présence des horaires"""
    try:
        url = "http://127.0.0.1:5000/api/requests"
        print(f"🔍 Test de l'API: {url}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            requests_data = response.json()
            print(f"✅ API accessible - {len(requests_data)} demandes trouvées")
            
            if requests_data:
                # Vérifier la première demande
                first_request = requests_data[0]
                print("\n📋 Première demande:")
                print(f"  - ID: {first_request.get('id')}")
                print(f"  - Enseignant: {first_request.get('teacher_name')}")
                print(f"  - Date: {first_request.get('request_date')}")
                print(f"  - Horaire: {first_request.get('horaire', 'MANQUANT!')}")
                print(f"  - Niveau: {first_request.get('class_name')}")
                
                # Vérifier que le champ horaire existe
                if 'horaire' in first_request:
                    print("✅ Le champ 'horaire' est présent dans l'API")
                else:
                    print("❌ Le champ 'horaire' est MANQUANT dans l'API")
                
                return 'horaire' in first_request
            else:
                print("ℹ️  Aucune demande dans la base de données")
                return True
        else:
            print(f"❌ Erreur API: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur de connexion: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Test des horaires dans l'API des demandes")
    print("=" * 50)
    
    success = test_api_requests()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Test RÉUSSI - Les horaires sont correctement renvoyés par l'API")
    else:
        print("🚨 Test ÉCHOUÉ - Problème avec les horaires dans l'API")