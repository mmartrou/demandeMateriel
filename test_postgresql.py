#!/usr/bin/env python3
import os
import logging
from urllib.parse import urlparse

# Configuration des logs pour voir les détails
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_postgresql_url():
    """Test de l'URL PostgreSQL pour diagnostiquer les problèmes d'encodage"""
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ Aucune DATABASE_URL trouvée")
        return
    
    print(f"🔍 Test de l'URL PostgreSQL...")
    print(f"Longueur de l'URL: {len(database_url)} caractères")
    
    # Test d'encodage
    try:
        # Vérifier l'encodage de l'URL
        print(f"Type de l'URL: {type(database_url)}")
        
        if isinstance(database_url, bytes):
            print("⚠️  URL est en bytes, conversion...")
            database_url = database_url.decode('utf-8')
        
        # Chercher les caractères problématiques
        for i, char in enumerate(database_url):
            if ord(char) > 127:  # Caractères non-ASCII
                print(f"⚠️  Caractère non-ASCII trouvé à la position {i}: {repr(char)} (code: {ord(char)})")
        
        # Parser l'URL
        parsed = urlparse(database_url)
        print(f"✅ URL parsée avec succès:")
        print(f"  - Protocole: {parsed.scheme}")
        print(f"  - Host: {parsed.hostname}")
        print(f"  - Port: {parsed.port}")
        print(f"  - Database: {parsed.path}")
        print(f"  - Username: {parsed.username}")
        print(f"  - Password: {'*' * len(parsed.password) if parsed.password else 'None'}")
        
        # Test de connexion
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            print("🔗 Test de connexion PostgreSQL...")
            conn = psycopg2.connect(
                database_url, 
                cursor_factory=RealDictCursor,
                connect_timeout=5,
                client_encoding='utf8'
            )
            print("✅ Connexion PostgreSQL réussie!")
            conn.close()
            
        except Exception as e:
            print(f"❌ Erreur de connexion PostgreSQL: {e}")
            print(f"Type d'erreur: {type(e).__name__}")
    
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        print(f"Type d'erreur: {type(e).__name__}")

if __name__ == "__main__":
    test_postgresql_url()