#!/usr/bin/env python3
"""
Test de démarrage et vérification des routes Flask
"""

from app import app

def test_flask_app():
    """Test que l'application Flask démarre correctement"""
    print("=== TEST DÉMARRAGE APPLICATION FLASK ===\n")
    
    print("✅ Application Flask chargée avec succès!")
    print(f"📱 Nom de l'application: {app.name}")
    print(f"🔧 Mode debug: {app.debug}")
    
    print("\n📍 Routes disponibles:")
    routes = []
    for rule in app.url_map.iter_rules():
        methods = ', '.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        routes.append(f"  {rule.rule} [{methods}]")
    
    for route in sorted(routes):
        print(route)
    
    print(f"\n📊 Total routes: {len(routes)}")
    
    # Test spécifique des routes API
    api_routes = [r for r in routes if '/api/' in r]
    print(f"🔌 Routes API: {len(api_routes)}")
    for api_route in api_routes:
        print(f"  {api_route}")
    
    print("\n✅ Test réussi - Application prête!")

if __name__ == "__main__":
    test_flask_app()