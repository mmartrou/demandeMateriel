#!/usr/bin/env python3
"""
Correction de la configuration des jours ouvrés
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection

def fix_working_days_config():
    print("=== CORRECTION CONFIGURATION JOURS OUVRÉS ===\n")
    
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    # Supprimer toutes les configurations problématiques d'octobre 2025
    print("🧹 Suppression des configurations problématiques...")
    
    cursor.execute("DELETE FROM working_days_config WHERE date LIKE '2025-10-%'")
    affected = cursor.rowcount
    print(f"   ✅ {affected} configurations supprimées")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Correction terminée - les défauts weekday s'appliquent maintenant")
    print("   Lundi-Vendredi: ✅ Ouvrés")
    print("   Samedi-Dimanche: ❌ Non ouvrés")
    
    # Vérification
    print(f"\n🔍 Vérification après correction:")
    from database import is_working_day_configured
    
    test_dates = [
        ('2025-10-06', 'Lundi'),
        ('2025-10-07', 'Mardi'), 
        ('2025-10-08', 'Mercredi'),
        ('2025-10-04', 'Samedi'),
        ('2025-10-05', 'Dimanche'),
    ]
    
    for date_str, day_name in test_dates:
        is_working = is_working_day_configured(date_str)
        status = "✅ Ouvré" if is_working else "❌ Non ouvré"
        print(f"   {date_str} ({day_name}): {status}")

if __name__ == "__main__":
    fix_working_days_config()