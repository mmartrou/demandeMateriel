#!/usr/bin/env python3

import os
import logging
logging.basicConfig(level=logging.INFO)

def test_postgresql_variables():
    """Test des variables PostgreSQL séparées"""
    
    print("=== Test Variables PostgreSQL Séparées ===")
    
    # Simuler les variables Railway PostgreSQL
    test_vars = {
        'PGHOST': 'localhost',
        'PGPORT': '5432', 
        'PGUSER': 'testuser',
        'PGPASSWORD': 'testpass',
        'PGDATABASE': 'testdb'
    }
    
    # Tester sans variables (SQLite par défaut)
    print("\n1. Test sans variables PostgreSQL:")
    from database import get_db_connection
    conn, db_type = get_db_connection()
    print(f"   ✅ Connexion: {db_type}")
    conn.close()
    
    # Tester avec variables PostgreSQL (mais serveur inexistant)
    print("\n2. Test avec variables PostgreSQL (serveur inexistant):")
    for key, value in test_vars.items():
        os.environ[key] = value
    
    try:
        # Recharger le module pour prendre en compte les nouvelles variables
        import importlib
        import database
        importlib.reload(database)
        
        conn, db_type = get_db_connection()
        print(f"   ✅ Connexion: {db_type}")
        conn.close()
        
    except Exception as e:
        print(f"   ⚠️  Erreur attendue: {e}")
    
    finally:
        # Nettoyer les variables
        for key in test_vars:
            os.environ.pop(key, None)
    
    # Test avec URL problématique mais variables OK
    print("\n3. Test priorité variables vs URL:")
    os.environ['DATABASE_URL'] = 'postgresql://invalid\xf4url'
    os.environ['PGHOST'] = 'localhost'  # Variable prioritaire
    
    try:
        importlib.reload(database)
        conn, db_type = get_db_connection()
        print(f"   ✅ Variables prioritaires: {db_type}")
        conn.close()
    except Exception as e:
        print(f"   ⚠️  Fallback SQLite: {e}")
    finally:
        os.environ.pop('DATABASE_URL', None)
        os.environ.pop('PGHOST', None)
    
    print("\n🎉 Tests variables PostgreSQL terminés!")
    print("\n📝 Sur Railway, configurez ces variables:")
    for key, desc in [
        ('PGHOST', 'postgres.railway.internal'),
        ('PGPORT', '5432'),
        ('PGUSER', 'postgres'), 
        ('PGPASSWORD', 'ZHMwVsteLphXRUCgePvWgkNYMIcIUoQB'),
        ('PGDATABASE', 'railway')
    ]:
        print(f"   {key} = {desc}")

if __name__ == "__main__":
    test_postgresql_variables()