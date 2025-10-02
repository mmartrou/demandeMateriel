#!/usr/bin/env python3
"""
Script de migration des créneaux C21 du CSV vers la base de données
"""

import csv
import os
import sys

# Ajouter le répertoire parent au path pour importer nos modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import add_c21_availability, get_c21_availability

def migrate_c21_data():
    """Migre les données du CSV vers la base de données"""
    
    # Vérifier s'il y a déjà des données
    existing_data = get_c21_availability()
    if existing_data:
        print(f"⚠️  {len(existing_data)} créneaux déjà en base de données:")
        for slot in existing_data:
            print(f"   {slot['jour']} {slot['heure_debut']}-{slot['heure_fin']}")
        
        response = input("Voulez-vous continuer et ajouter les données du CSV? (y/N): ")
        if response.lower() not in ['y', 'yes', 'oui']:
            print("Migration annulée.")
            return
    
    # Chemin vers le fichier CSV
    csv_path = os.path.join(os.path.dirname(__file__), "disponibilite_C21.csv")
    
    if not os.path.exists(csv_path):
        print(f"❌ Fichier CSV non trouvé: {csv_path}")
        return
    
    print(f"📂 Lecture du fichier: {csv_path}")
    
    # Lire et migrer les données
    migrated_count = 0
    error_count = 0
    
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            print("\n🔄 Migration en cours...")
            
            for row in reader:
                jour = row["jour"]
                heure_debut = row["heure_debut"] 
                heure_fin = row["heure_fin"]
                
                # Convertir le format d'heure si nécessaire (ex: 13h15 -> 13:15)
                heure_debut = heure_debut.replace('h', ':')
                heure_fin = heure_fin.replace('h', ':')
                
                # Assurer le format HH:MM
                if len(heure_debut.split(':')[1]) == 1:
                    heure_debut = heure_debut.replace(':', ':0')
                if len(heure_fin.split(':')[1]) == 1:
                    heure_fin = heure_fin.replace(':', ':0')
                
                print(f"   Ajout: {jour} {heure_debut}-{heure_fin}")
                
                success = add_c21_availability(jour, heure_debut, heure_fin)
                if success:
                    migrated_count += 1
                    print(f"   ✅ Ajouté")
                else:
                    error_count += 1
                    print(f"   ❌ Erreur (peut-être un doublon)")
    
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du CSV: {e}")
        return
    
    print(f"\n📊 Résultat de la migration:")
    print(f"   ✅ {migrated_count} créneaux migrés avec succès")
    print(f"   ❌ {error_count} erreurs (doublons probables)")
    
    # Afficher le résultat final
    final_data = get_c21_availability()
    print(f"\n📋 Total en base de données: {len(final_data)} créneaux")
    
    if final_data:
        print("\n📅 Créneaux configurés:")
        for slot in final_data:
            print(f"   {slot['jour'].capitalize()} {slot['heure_debut']}-{slot['heure_fin']}")

if __name__ == "__main__":
    print("🚀 Migration des créneaux C21 du CSV vers la base de données")
    print("=" * 60)
    migrate_c21_data()