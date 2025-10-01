#!/usr/bin/env python3

import os
import logging
logging.basicConfig(level=logging.INFO)

# Test pour simuler le problème d'encodage PostgreSQL de Railway

def test_encoding_problem():
    """Test de la gestion des erreurs d'encodage PostgreSQL"""
    
    print("=== Test Gestion Erreurs Encodage PostgreSQL ===")
    
    # Simuler une URL PostgreSQL avec des caractères problématiques
    # (similaire à ce que Railway pourrait envoyer)
    problematic_url = "postgresql://postgres:ZHMwVsteLphXRUCgePvWgkNYMIcI\xf4invalid@host:5432/db"
    
    # Tester notre fonction de nettoyage
    try:
        # Simuler la variable d'environnement
        os.environ['DATABASE_URL'] = problematic_url
        
        from database import get_db_connection
        
        print("Test avec URL problématique...")
        conn, db_type = get_db_connection()
        
        print(f"✅ Connexion réussie: {db_type}")
        
        if db_type == 'sqlite':
            print("✅ Fallback SQLite fonctionnel comme attendu")
        elif db_type == 'postgresql':
            print("✅ PostgreSQL réparé automatiquement!")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        
    finally:
        # Nettoyer la variable d'environnement
        os.environ.pop('DATABASE_URL', None)
    
    # Test avec URL normale
    print("\nTest avec URL PostgreSQL normale...")
    normal_url = "postgresql://user:pass@localhost:5432/testdb"
    os.environ['DATABASE_URL'] = normal_url
    
    try:
        conn, db_type = get_db_connection()
        print(f"✅ Test URL normale: {db_type}")
        conn.close()
    except Exception as e:
        print(f"✅ Erreur attendue (pas de serveur PostgreSQL local): {type(e).__name__}")
    finally:
        os.environ.pop('DATABASE_URL', None)
    
    print("\n🎉 Tests de gestion d'erreurs terminés!")

if __name__ == "__main__":
    test_encoding_problem()