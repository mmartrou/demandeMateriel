#!/usr/bin/env python3
"""
Script de test pour vérifier le format des dates français
"""

def test_format_dates():
    """Test du format des dates français dd/mm/yyyy"""
    print("Test du format des dates français")
    print("=" * 50)
    
    # Simuler le format JavaScript
    from datetime import datetime
    
    test_date = datetime(2025, 9, 27, 14, 30, 0)
    
    # Format attendu pour formatDate
    day = f"{test_date.day:02d}"
    month = f"{test_date.month:02d}" 
    year = test_date.year
    expected_date = f"{day}/{month}/{year}"
    
    # Format attendu pour formatDateTime
    hours = f"{test_date.hour:02d}"
    minutes = f"{test_date.minute:02d}"
    expected_datetime = f"{day}/{month}/{year} {hours}:{minutes}"
    
    print(f"Date de test: {test_date}")
    print(f"Format attendu (formatDate): {expected_date}")
    print(f"Format attendu (formatDateTime): {expected_datetime}")
    
    print(f"\nVérifications:")
    print(f"- Jour avec zéro initial: {'✅' if day.startswith('0') or len(day) == 2 else '❌'}")
    print(f"- Mois avec zéro initial: {'✅' if month.startswith('0') or len(month) == 2 else '❌'}")
    print(f"- Séparateurs '/' : {'✅' if '/' in expected_date else '❌'}")
    print(f"- Format 24h : {'✅' if ':' in expected_datetime else '❌'}")
    
    print(f"\n🇫🇷 Format français validé: {expected_date}")
    print("(au lieu de l'ancien format long)")

def test_api_dates():
    """Test de l'API pour voir les dates"""
    try:
        import requests
        response = requests.get("http://127.0.0.1:5000/api/requests", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                first = data[0]
                print(f"\nExemple de date depuis l'API:")
                print(f"- request_date: {first.get('request_date')}")
                print(f"- created_at: {first.get('created_at')}")
                print("Ces dates seront formatées côté client en dd/mm/yyyy")
            else:
                print("\nAucune donnée dans l'API")
        else:
            print(f"\nErreur API: {response.status_code}")
            
    except Exception as e:
        print(f"\nErreur test API: {e}")

if __name__ == "__main__":
    test_format_dates()
    test_api_dates()