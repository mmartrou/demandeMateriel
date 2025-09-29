#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import database
import os
from datetime import datetime

def test_planning_generation():
    """Test direct de la génération de planning"""
    print("=== TEST DE GÉNÉRATION DE PLANNING ===")
    
    # 1. Vérifier les demandes
    conn = database.get_db_connection()
    requests = conn.execute('SELECT * FROM material_requests WHERE request_date = ?', ('2025-09-29',)).fetchall()
    print(f"Demandes trouvées pour 2025-09-29: {len(requests)}")
    
    for req in requests:
        print(f"  - Enseignant: {req['enseignant'] if 'enseignant' in req.keys() else 'N/A'}")
        print(f"    Colonnes: {list(req.keys())}")
        break  # Juste le premier pour voir la structure
    
    # 2. Vérifier les salles
    rooms = conn.execute('SELECT name FROM rooms ORDER BY id').fetchall()
    print(f"Salles disponibles: {[r[0] for r in rooms]}")
    conn.close()
    
    if len(requests) == 0:
        print("❌ Aucune demande trouvée - ajout d'une demande de test")
        # Ajouter une demande de test
        conn = database.get_db_connection()
        teacher_id = conn.execute('SELECT id FROM teachers LIMIT 1').fetchone()[0]
        database.add_material_request(
            teacher_id, 
            '2025-09-29',
            '9h30', 
            'Test Enseignant', 
            '2nd', 
            'Physique',
            'Ordinateurs: 5',
            False,
            False
        )
        conn.close()
        print("✅ Demande de test ajoutée")
    
    # 3. Test de la fonction de génération depuis app.py
    print("\n=== TEST DE LA FONCTION DE GÉNÉRATION ===")
    
    try:
        # Import des modules nécessaires
        from ortools.sat.python import cp_model
        from openpyxl import Workbook
        print("✅ Modules OR-Tools et openpyxl disponibles")
        
        # Test de génération
        from app import api_generate_planning
        print("✅ Fonction api_generate_planning importée")
        
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_planning_generation()