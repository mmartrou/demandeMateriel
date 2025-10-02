#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour cr    print(f"=== Création de demandes de test pour lundi {DATE_COURS} ===\n")er des demandes de test pour lundi prochain
"""

import requests
import json

# Configuration
BASE_URL = "http://127.0.0.1:8080"
DATE_COURS = "2025-10-13"  # Première date disponible selon l'API (respecte le délai de 48h ouvrées)

# Liste d'enseignants de test
enseignants = [
    {"id": "PROF001", "nom": "Dupont"},
    {"id": "PROF002", "nom": "Martin"}, 
    {"id": "PROF003", "nom": "Durand"},
    {"id": "PROF004", "nom": "Moreau"}
]

# Créneaux horaires possibles (plus de créneaux pour permettre 2 par enseignant)
horaires = [
    "09h00-10h00",
    "10h00-11h00", 
    "11h00-12h00",
    "14h00-15h00",
    "15h00-16h00",
    "16h00-17h00",
    "08h00-09h00",
    "13h00-14h00"
]

def creer_demande(teacher_id, horaire, class_name, material_desc):
    """Créer une demande de matériel via l'API"""
    
    data = {
        "teacher_id": teacher_id,
        "class_name": class_name,
        "material_description": material_desc,
        "quantity": 1,
        "selected_materials": "C21",  # Indique que la salle C21 est nécessaire
        "computers_needed": 0,
        "notes": f"Test demande pour vérifier disponibilité C21 - {horaire}",
        "group_count": 1,
        "material_prof": "",
        "days_horaires": [
            {
                "date": DATE_COURS,
                "horaires": [horaire]
            }
        ]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/requests", json=data)
        if response.status_code == 201:
            result = response.json()
            print(f"✅ Demande créée: {teacher_id} - {class_name} - {horaire}")
            return True
        else:
            print(f"❌ Erreur: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur réseau: {e}")
        return False

def main():
    print("=== Création de demandes de test pour lundi 06/10/2025 ===\n")
    
    demandes_creees = 0
    
    # Créer 2 demandes par enseignant
    for i, enseignant in enumerate(enseignants):
        print(f"--- Enseignant: {enseignant['nom']} ---")
        
        # Première demande
        if creer_demande(
            teacher_id=enseignant["id"],
            horaire=horaires[i*2],  # Horaire différent pour chaque prof
            class_name=f"2nd{i+1}",
            material_desc="Cours nécessitant salle C21"
        ):
            demandes_creees += 1
        
        # Deuxième demande
        if creer_demande(
            teacher_id=enseignant["id"], 
            horaire=horaires[i*2+1],  # Horaire différent
            class_name=f"1re{i+1}",
            material_desc="TP avec besoin salle C21"
        ):
            demandes_creees += 1
    
    print(f"\n=== Résumé ===")
    print(f"Demandes créées: {demandes_creees}")
    print(f"Date des cours: {DATE_COURS}")
    print(f"Type de salle demandé: C21")

if __name__ == "__main__":
    main()