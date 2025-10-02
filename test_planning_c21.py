#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour tester la génération de planning avec les demandes C21
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8080"

def generer_planning_test():
    """Génère un planning de test pour vérifier C21"""
    
    # Configuration pour le planning
    data = {
        "date": "2025-10-13"  # Lundi avec nos demandes
    }
    
    print("=== Test génération planning C21 ===")
    print(f"Date: {data['date']}")
    print("Génération du planning...\n")
    
    try:
        response = requests.post(f"{BASE_URL}/api/generate-planning", json=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Planning généré avec succès!")
            
            # Analyser le résultat
            if 'planning_data' in result:
                planning = result['planning_data']
                print(f"\nNombre total de cours planifiés: {len(planning)}")
                
                # Compter les cours C21
                cours_c21 = [c for c in planning if c.get('selected_materials') == 'C21']
                print(f"Cours nécessitant C21: {len(cours_c21)}")
                
                # Afficher les détails des cours C21
                if cours_c21:
                    print("\n--- Cours C21 planifiés ---")
                    for cours in cours_c21:
                        print(f"• {cours.get('teacher_name', 'N/A')} - {cours.get('class_name', 'N/A')}")
                        print(f"  Horaire: {cours.get('horaire', 'N/A')}")
                        print(f"  Date: {cours.get('request_date', 'N/A')}")
                        print(f"  Matériel: {cours.get('material_description', 'N/A')}")
                        print()
                
                # Vérifier les conflits potentiels
                conflits = result.get('conflicts', [])
                if conflits:
                    print(f"\n⚠️ Conflits détectés: {len(conflits)}")
                    for conflit in conflits:
                        print(f"  - {conflit}")
                else:
                    print("\n✅ Aucun conflit détecté")
                
            else:
                print("❌ Format de réponse inattendu")
                print(result)
                
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

def verifier_demandes():
    """Vérifie les demandes existantes"""
    
    print("=== Vérification des demandes ===")
    
    try:
        response = requests.get(f"{BASE_URL}/api/requests")
        if response.status_code == 200:
            demandes = response.json()
            
            # Filtrer les demandes pour le 13/10/2025
            demandes_test = [d for d in demandes if d.get('request_date') == '2025-10-13']
            
            print(f"Demandes totales: {len(demandes)}")
            print(f"Demandes pour le 13/10/2025: {len(demandes_test)}")
            
            # Demandes C21
            demandes_c21 = [d for d in demandes_test if d.get('selected_materials') == 'C21']
            print(f"Demandes C21 pour le 13/10: {len(demandes_c21)}")
            
            if demandes_c21:
                print("\n--- Détail demandes C21 ---")
                for d in demandes_c21:
                    print(f"• {d.get('teacher_name', d.get('teacher_id', 'N/A'))} - {d.get('class_name')}")
                    print(f"  Horaire: {d.get('horaire')}")
                    print(f"  ID: {d.get('id')}")
                    print()
            
            return demandes_c21
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def main():
    print("🧪 Test de la disponibilité C21 dans le planning\n")
    
    # Étape 1: Vérifier les demandes
    demandes_c21 = verifier_demandes()
    
    if not demandes_c21:
        print("❌ Aucune demande C21 trouvée pour le test")
        return
    
    print("\n" + "="*50 + "\n")
    
    # Étape 2: Générer le planning
    generer_planning_test()

if __name__ == "__main__":
    main()