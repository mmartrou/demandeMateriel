#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Simple test pour vérifier les données en base
import sys
import os
import sqlite3
from datetime import datetime

def check_database():
    """Vérifier le contenu de la base de données"""
    try:
        # Se connecter à SQLite - chercher les différents fichiers possibles
        possible_dbs = ['database.db', 'material_requests.db', 'requests.db']
        db_path = None
        
        for path in possible_dbs:
            if os.path.exists(path):
                db_path = path
                break
                
        if not db_path:
            print(f"❌ Aucune base de données trouvée parmi : {possible_dbs}")
            return
            
        print(f"📁 Utilisation de la base : {db_path}")
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Pour avoir des noms de colonnes
        cursor = conn.cursor()
        
        # Vérifier les demandes pour le 14 octobre 2025
        test_date = '2025-10-14'
        print(f"🔍 Recherche de demandes pour {test_date}")
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM material_requests 
            WHERE request_date = ?
        """, (test_date,))
        
        count = cursor.fetchone()['total']
        print(f"📊 Nombre de demandes trouvées : {count}")
        
        if count == 0:
            # Regarder toutes les dates disponibles
            cursor.execute("""
                SELECT DISTINCT request_date, COUNT(*) as count 
                FROM material_requests 
                GROUP BY request_date 
                ORDER BY request_date DESC 
                LIMIT 5
            """)
            
            dates = cursor.fetchall()
            print("📅 Dates avec des demandes :")
            for row in dates:
                print(f"  - {row['request_date']}: {row['count']} demandes")
        else:
            # Voir la structure de la table d'abord
            cursor.execute("PRAGMA table_info(material_requests)")
            columns = cursor.fetchall()
            print("🔍 Structure de la table material_requests :")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # Afficher quelques demandes avec les bonnes colonnes
            cursor.execute("""
                SELECT id, teacher_id, class_name, material_description 
                FROM material_requests 
                WHERE request_date = ?
                LIMIT 3
            """, (test_date,))
            
            requests = cursor.fetchall()
            print("📋 Exemples de demandes :")
            for req in requests:
                print(f"  - ID {req['id']}: Teacher {req['teacher_id']} - {req['class_name']}")
        
        # Vérifier les salles
        cursor.execute("SELECT COUNT(*) as total FROM rooms")
        room_count = cursor.fetchone()['total']
        print(f"🏛️ Nombre de salles : {room_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()