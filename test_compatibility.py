#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import planning_generator
import database
from ortools.sat.python import cp_model

def test_planning_assignment(date_str):
    """Test planning assignment with detailed debug"""
    
    # Get data
    raw_requests = database.get_planning_data(date_str)
    raw_rooms = database.get_all_rooms()
    
    print(f"=== ANALYSE ASSIGNATION PLANNING POUR {date_str} ===")
    print(f"Total demandes: {len(raw_requests)}")
    print(f"Total salles: {len(raw_rooms)}")
    
    # Convert data like in the planning generator
    salles = {}
    salle_list = []
    for room in raw_rooms:
        salle_list.append(room['name'])
        salles[room['name']] = {
            "type": room['type'],
            "ordinateurs": room['ordinateurs'],
            "chaises": room['chaises'],
            "eviers": room['eviers'],
            "hotte": room['hotte'],
            "bancs_optiques": room['bancs_optiques'],
            "oscilloscopes": room['oscilloscopes'],
            "becs_electriques": room['becs_electriques'],
            "support_filtration": room['support_filtration'],
            "imprimante": room['imprimante'],
            "examen": room['examen']
        }
    
    # Convert requests to course format
    cours = []
    for i, req in enumerate(raw_requests):
        material_needs = planning_generator.extract_material_needs(req['selected_materials'])
        
        matiere = "mixte"
        if req['room_type'] == 'Physique':
            matiere = "physique"
        elif req['room_type'] == 'Chimie':
            matiere = "chimie"
        
        if req['computers_needed'] and req['computers_needed'] > 0:
            material_needs["ordinateurs"] = max(material_needs["ordinateurs"], req['computers_needed'])
        
        cours.append({
            "id": f"{req['teacher_name']}_{i}",
            "enseignant": req['teacher_name'],
            "horaire": req['horaire'] if req['horaire'] else '9h00',
            "niveau": req['class_name'],
            "matiere": matiere,
            "ordinateurs": material_needs["ordinateurs"],
            "eviers": material_needs["eviers"],
            "hotte": material_needs["hotte"],
            "bancs_optiques": material_needs["bancs_optiques"],
            "oscilloscopes": material_needs["oscilloscopes"],
            "becs_electriques": material_needs["becs_electriques"],
            "support_filtration": material_needs["support_filtration"],
            "imprimante": material_needs["imprimante"],
            "examen": material_needs["examen"],
            "duree": planning_generator.duree_par_niveau(req['class_name']),
            "chaises": planning_generator.eleves_par_niveau(req['class_name'], req['teacher_name'])
        })
    
    print(f"Cours créés: {len(cours)}")
    
    # Test compatibility
    print("\n=== ANALYSE DE COMPATIBILITÉ ===")
    for i, c in enumerate(cours):
        compatible_rooms = []
        for s in salles:
            if planning_generator.compatible(salles[s], c):
                compatible_rooms.append(s)
        
        has_equipment = (c["ordinateurs"] > 0 or c["eviers"] > 0 or 
                        c["hotte"] > 0 or c["bancs_optiques"] > 0 or 
                        c["oscilloscopes"] > 0 or c["becs_electriques"] > 0 or 
                        c["support_filtration"] > 0 or c["imprimante"] > 0 or 
                        c["examen"] > 0)
        
        print(f"Cours {i+1}: {c['enseignant']} - {c['niveau']} à {c['horaire']}")
        print(f"  Matière: {c['matiere']}, Équipement: {'Oui' if has_equipment else 'Non'}")
        print(f"  Salles compatibles: {compatible_rooms} ({len(compatible_rooms)} salles)")
        
        if len(compatible_rooms) == 0:
            print(f"  ⚠️  AUCUNE SALLE COMPATIBLE!")
        print()

if __name__ == "__main__":
    test_planning_assignment('2025-09-29')