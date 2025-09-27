#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import database

def check_requests():
    # Vérifier toutes les demandes
    all_requests = database.get_material_requests()
    print(f"Total toutes demandes: {len(all_requests)}")
    
    # Vérifier les demandes pour le 29/09
    sept29_requests = [r for r in all_requests if r['request_date'] == '2025-09-29']
    print(f"Demandes avec request_date = '2025-09-29': {len(sept29_requests)}")
    
    # Vérifier avec get_planning_data
    planning_requests = database.get_planning_data('2025-09-29')
    print(f"Demandes via get_planning_data('2025-09-29'): {len(planning_requests)}")
    
    print("\nDemandes avec request_date = '2025-09-29':")
    for i, r in enumerate(sept29_requests):
        horaire = r['horaire'] if r['horaire'] else 'Non défini'
        print(f"  {i+1}. {r['teacher_name']} - {r['class_name']} à {horaire}")
    
    print("\nDemandes via get_planning_data:")
    for i, r in enumerate(planning_requests):
        horaire = r['horaire'] if r['horaire'] else 'Non défini'
        print(f"  {i+1}. {r['teacher_name']} - {r['class_name']} à {horaire}")

if __name__ == "__main__":
    check_requests()