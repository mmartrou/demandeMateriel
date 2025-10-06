#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script pour initialiser la base de données et ajouter des données de test
"""

import sys
import os

# Ajouter le répertoire parent au chemin pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database

def init_and_populate_database():
    """Initialiser la base de données et ajouter des données de test"""
    try:
        print("🔧 Initialisation de la base de données...")
        
        # Initialiser les tables
        database.init_database()
        print("✅ Tables créées avec succès")
        
        # Ajouter des professeurs de test
        print("👥 Ajout de professeurs de test...")
        teachers = [
            "Dupont Pierre",
            "Martin Sophie", 
            "Durand Jean",
            "Bernard Marie",
            "Rousseau Paul"
        ]
        
        for teacher in teachers:
            try:
                database.add_teacher(teacher)
                print(f"  ➕ Professeur ajouté : {teacher}")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) or "already exists" in str(e):
                    print(f"  ℹ️ Professeur déjà existant : {teacher}")
                else:
                    print(f"  ❌ Erreur pour {teacher}: {e}")
        
        # Ajouter des salles de test
        print("🏛️ Ajout de salles de test...")
        rooms_data = [
            {
                'name': 'Salle A101',
                'type': 'Physique',
                'computers': 16,
                'sinks': 2,
                'fume_hood': False,
                'optical_benches': 4,
                'oscilloscopes': 8,
                'electric_burners': 0,
                'support_filtration': 0,
                'printer': True
            },
            {
                'name': 'Salle A102', 
                'type': 'Chimie',
                'computers': 0,
                'sinks': 8,
                'fume_hood': True,
                'optical_benches': 0,
                'oscilloscopes': 0,
                'electric_burners': 16,
                'support_filtration': 8,
                'printer': False
            },
            {
                'name': 'Salle A103',
                'type': 'Mixte',
                'computers': 8,
                'sinks': 4,
                'fume_hood': False,
                'optical_benches': 2,
                'oscilloscopes': 4,
                'electric_burners': 8,
                'support_filtration': 4,
                'printer': True
            },
            {
                'name': 'Salle B201',
                'type': 'Informatique',
                'computers': 30,
                'sinks': 0,
                'fume_hood': False,
                'optical_benches': 0,
                'oscilloscopes': 0,
                'electric_burners': 0,
                'support_filtration': 0,
                'printer': True
            }
        ]
        
        for room in rooms_data:
            try:
                database.add_room(room)
                print(f"  ➕ Salle ajoutée : {room['name']} ({room['type']})")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e) or "already exists" in str(e):
                    print(f"  ℹ️ Salle déjà existante : {room['name']}")
                else:
                    print(f"  ❌ Erreur pour {room['name']}: {e}")
        
        # Ajouter des demandes de matériel pour test
        print("📋 Ajout de demandes de test pour 2025-10-04...")
        
        test_requests = [
            {
                'teacher_name': 'Dupont Pierre',
                'request_date': '2025-10-04',
                'horaire': '9h30',
                'class_name': '2nde A',
                'material_description': 'TP Optique - Réfraction',
                'selected_materials': '- Bancs optiques\n- Sources lumineuses\n- Lentilles convergentes',
                'room_type': 'Physique'
            },
            {
                'teacher_name': 'Martin Sophie',
                'request_date': '2025-10-04', 
                'horaire': '11h00',
                'class_name': '1ère S1',
                'material_description': 'TP Chimie - Dosage',
                'selected_materials': '- Éviers\n- Becs électriques\n- Hotte\n- Support de filtration',
                'room_type': 'Chimie'
            },
            {
                'teacher_name': 'Durand Jean',
                'request_date': '2025-10-04',
                'horaire': '13h30', 
                'class_name': 'Tale S2',
                'material_description': 'TP Électricité - Oscilloscope',
                'selected_materials': '- Oscilloscopes\n- Générateurs\n- Multimètres',
                'room_type': 'Physique'
            },
            {
                'teacher_name': 'Bernard Marie',
                'request_date': '2025-10-04',
                'horaire': '15h00',
                'class_name': '2nde B', 
                'material_description': 'Recherche Internet',
                'selected_materials': '- Ordinateurs\n- Imprimante',
                'room_type': 'Informatique'
            }
        ]
        
        for req in test_requests:
            try:
                # Récupérer l'ID du professeur
                teacher_id = database.get_teacher_id(req['teacher_name'])
                if teacher_id:
                    request_data = {
                        'teacher_id': teacher_id,
                        'request_date': req['request_date'],
                        'horaire': req['horaire'],
                        'class_name': req['class_name'],
                        'material_description': req['material_description'],
                        'selected_materials': req['selected_materials'],
                        'room_type': req['room_type']
                    }
                    
                    request_id = database.add_material_request(request_data)
                    print(f"  ➕ Demande ajoutée : {req['teacher_name']} - {req['class_name']} ({req['horaire']})")
                else:
                    print(f"  ❌ Professeur non trouvé : {req['teacher_name']}")
                    
            except Exception as e:
                print(f"  ❌ Erreur pour la demande de {req['teacher_name']}: {e}")
        
        print("✅ Base de données initialisée avec succès !")
        print("📊 Résumé :")
        
        # Vérifications finales
        conn, db_type = database.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM teachers")
        teacher_count = cursor.fetchone()[0]
        print(f"  - Professeurs : {teacher_count}")
        
        cursor.execute("SELECT COUNT(*) FROM rooms")
        room_count = cursor.fetchone()[0] 
        print(f"  - Salles : {room_count}")
        
        cursor.execute("SELECT COUNT(*) FROM material_requests WHERE request_date = '2025-10-04'")
        request_count = cursor.fetchone()[0]
        print(f"  - Demandes pour 2025-10-04 : {request_count}")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation : {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_and_populate_database()
    if success:
        print("\n🎉 Vous pouvez maintenant tester l'éditeur de planning !")
    else:
        print("\n💥 Échec de l'initialisation")