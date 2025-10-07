#!/usr/bin/env python3
"""
Script de test pour vérifier la connexion PostgreSQL
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

print("=== Test de configuration PostgreSQL ===")
print(f"DATABASE_URL défini: {bool(os.getenv('DATABASE_URL'))}")
print(f"PGHOST: {os.getenv('PGHOST')}")
print(f"PGPORT: {os.getenv('PGPORT')}")
print(f"PGUSER: {os.getenv('PGUSER')}")
print(f"PGDATABASE: {os.getenv('PGDATABASE')}")

# Test d'importation de psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print("✅ psycopg2 importé avec succès")
except ImportError as e:
    print(f"❌ Erreur d'import psycopg2: {e}")
    exit(1)

# Test de connexion
try:
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        print(f"Tentative de connexion avec DATABASE_URL...")
        conn = psycopg2.connect(
            database_url,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            client_encoding='utf8'
        )
        print("✅ Connexion PostgreSQL réussie avec DATABASE_URL !")
        
        # Test simple
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"Version PostgreSQL: {version[0]}")
        
        cursor.close()
        conn.close()
        
    else:
        print("❌ DATABASE_URL non défini")
        
except Exception as e:
    print(f"❌ Erreur de connexion PostgreSQL: {e}")
    
    # Essayer avec les variables séparées
    try:
        print("Tentative avec variables séparées...")
        conn = psycopg2.connect(
            host=os.getenv('PGHOST'),
            port=os.getenv('PGPORT'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            database=os.getenv('PGDATABASE'),
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            client_encoding='utf8'
        )
        print("✅ Connexion PostgreSQL réussie avec variables séparées !")
        conn.close()
        
    except Exception as e2:
        print(f"❌ Erreur avec variables séparées: {e2}")

print("=== Fin du test ===")