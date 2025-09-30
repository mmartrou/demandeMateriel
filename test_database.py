#!/usr/bin/env python3
import sqlite3
import os
import logging

# Test simple pour database.py
print("=== Test Database Connection ===")

try:
    # Import our database module
    import sys
    sys.path.append('.')
    
    # Force SQLite mode for testing
    os.environ.pop('DATABASE_URL', None)  # Remove PostgreSQL URL if any
    
    from database import init_database, get_all_teachers
    
    print("✅ Modules importés avec succès")
    
    # Initialize database
    print("Initialisation de la base de données...")
    init_database()
    print("✅ Base de données initialisée")
    
    # Test teachers
    print("Test de récupération des enseignants...")
    teachers = get_all_teachers()
    print(f"✅ Enseignants récupérés: {len(teachers) if teachers else 0}")
    
    if teachers:
        for teacher in teachers[:3]:  # Show first 3
            print(f"  - {teacher['name']}")
    
    print("\n🎉 Tous les tests réussis ! Database.py fonctionne correctement.")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    print(traceback.format_exc())