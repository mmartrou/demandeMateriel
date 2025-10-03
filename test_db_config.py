#!/usr/bin/env python3
"""
Test de la configuration des jours ouvrés dans la base
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def check_working_days_config():
    print("=== VÉRIFICATION TABLE WORKING_DAYS_CONFIG ===\n")
    
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier le contenu de la table
    print("📊 Contenu de la table working_days_config:")
    cursor.execute("SELECT date, is_working_day, description FROM working_days_config ORDER BY date")
    results = cursor.fetchall()
    
    if not results:
        print("   ✅ Table vide - défauts weekday devraient s'appliquer")
    else:
        print(f"   ⚠️  {len(results)} configurations trouvées:")
        for date, is_working, desc in results[:10]:  # Limiter à 10 pour éviter trop de sortie
            status = "✅ Ouvré" if is_working else "❌ Non ouvré"
            print(f"   {date}: {status} {f'({desc})' if desc else ''}")
        if len(results) > 10:
            print(f"   ... et {len(results) - 10} autres")
    
    conn.close()
    
    # Test de la fonction is_working_day_configured avec weekday par défaut
    print(f"\n🔍 Test fonction is_working_day_configured:")
    from database import is_working_day_configured
    import datetime
    
    test_dates = [
        ('2025-10-06', 'Lundi'),    # Lundi = weekday 0
        ('2025-10-07', 'Mardi'),    # Mardi = weekday 1  
        ('2025-10-08', 'Mercredi'), # Mercredi = weekday 2
        ('2025-10-04', 'Samedi'),   # Samedi = weekday 5
        ('2025-10-05', 'Dimanche'), # Dimanche = weekday 6
    ]
    
    for date_str, day_name in test_dates:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        weekday = date_obj.weekday()
        expected_working = weekday < 5
        actual_working = is_working_day_configured(date_str)
        
        match = "✅" if expected_working == actual_working else "❌"
        print(f"   {match} {date_str} ({day_name}, weekday={weekday}): attendu={expected_working}, obtenu={actual_working}")

if __name__ == "__main__":
    check_working_days_config()