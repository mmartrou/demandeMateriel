#!/usr/bin/env python3
"""
Test des routes Flask
"""

from app import app

def test_routes():
    print("=== ROUTES FLASK DISPONIBLES ===")
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(f'{rule.rule} -> {rule.endpoint}')
    
    for route in sorted(routes):
        print(route)
    
    print("\n=== RECHERCHE working_days ===")
    working_routes = [r for r in routes if 'working' in r]
    if working_routes:
        for route in working_routes:
            print(f"TROUVÉ: {route}")
    else:
        print("❌ Aucune route working_days trouvée")
    
    # Test spécifique
    print("\n=== TEST URL_FOR ===")
    try:
        with app.app_context():
            url = app.url_for('view_working_days')
            print(f"✅ URL générée: {url}")
    except Exception as e:
        print(f"❌ Erreur url_for: {e}")

if __name__ == "__main__":
    test_routes()