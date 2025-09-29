#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import database
from datetime import datetime
from ortools.sat.python import cp_model


def h_to_min(hstr):
    """Convert hour string (like '9h30') to minutes"""
    if 'h' in hstr:
        h, m = hstr.split('h')
        return int(h) * 60 + int(m if m else 0)
    else:
        # Handle format like '9:30'
        parts = hstr.split(':')
        return int(parts[0]) * 60 + int(parts[1] if len(parts) > 1 else 0)


def duree_par_niveau(niveau):
    """Get duration by level"""
    if niveau in ("Terminale Spécialité", "SI", "Terminale ES", "1ère Spécialité", "AP 2nd"):
        return 110
    elif niveau in ("AP PP", "1ère ES"):
        return 55
    else:
        return 85


def eleves_par_niveau(niveau, enseignant=None):
    """Get number of students by level"""
    if niveau == "2nde":
        return 20
    else:
        return 20


def interval_cours(c):
    """Get interval (start, end) for a course"""
    start = h_to_min(c["horaire"])
    return (start, start + c["duree"])


def extract_material_needs(selected_materials):
    """Extract material needs from selected_materials string"""
    needs = {
        "ordinateurs": 0,
        "eviers": 0,
        "hotte": 0,
        "bancs_optiques": 0,
        "oscilloscopes": 0,
        "becs_electriques": 0,
        "support_filtration": 0,
        "imprimante": 0,
        "examen": 0
    }
    
    if not selected_materials:
        return needs

    materials = [m.strip().lower() for m in selected_materials.split(',')]
    for material in materials:
        if 'ordinateur' in material or 'pc' in material:
            needs["ordinateurs"] = 1
        elif 'evier' in material or 'évier' in material or 'lavabo' in material:
            needs["eviers"] = 1
        elif 'hotte' in material:
            needs["hotte"] = 1
        elif 'banc optique' in material or 'optique' in material:
            needs["bancs_optiques"] = 1
        elif 'oscilloscope' in material:
            needs["oscilloscopes"] = 1
        elif 'bec' in material or 'électrique' in material:
            needs["becs_electriques"] = 1
        elif 'filtration' in material or 'support' in material:
            needs["support_filtration"] = 1
        elif 'imprimante' in material:
            needs["imprimante"] = 1
        elif 'examen' in material:
            needs["examen"] = 1
    
    return needs


def compatible(salle, besoin):
    """Check if a room is compatible with course needs"""
    # Check if this is a theoretical course (no specific equipment needs)
    has_equipment_needs = (besoin["ordinateurs"] > 0 or besoin["eviers"] > 0 or 
                          besoin["hotte"] > 0 or besoin["bancs_optiques"] > 0 or 
                          besoin["oscilloscopes"] > 0 or besoin["becs_electriques"] > 0 or 
                          besoin["support_filtration"] > 0 or besoin["imprimante"] > 0 or 
                          besoin["examen"] > 0)
    
    # For theoretical courses (no equipment needs), any room type is acceptable
    # This allows flexibility for courses that don't need specific lab equipment
    if not has_equipment_needs:
        # Still need to check capacity
        if besoin["chaises"] > salle["chaises"]:
            return False
        return True
    
    # For courses with specific equipment needs, check subject compatibility
    if besoin["matiere"] == "chimie" and salle["type"] not in ("chimie", "mixte"):
        return False
    if besoin["matiere"] == "physique" and salle["type"] not in ("physique", "mixte"):
        return False
    
    # Check equipment needs
    if besoin["ordinateurs"] > salle["ordinateurs"]:
        return False
    if besoin["eviers"] > salle["eviers"]:
        return False
    if besoin["chaises"] > salle["chaises"]:
        return False
    if besoin["hotte"] > salle["hotte"]:
        return False
    if besoin["bancs_optiques"] > salle["bancs_optiques"]:
        return False
    if besoin["oscilloscopes"] > salle["oscilloscopes"]:
        return False
    if besoin["becs_electriques"] > salle["becs_electriques"]:
        return False
    if besoin["support_filtration"] > salle["support_filtration"]:
        return False
    if besoin["imprimante"] > salle["imprimante"]:
        return False
    if besoin["examen"] > salle["examen"]:
        return False
    
    return True




def generer_excel_optimise(cours, salles, x, solver, unassigned_courses):
    """Génération Excel optimisée avec le solveur CP."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, PatternFill, Border, Side, Font
        
        wb = Workbook()
        
        # Feuille 1: Planning par horaire
        ws1 = wb.active
        ws1.title = "Planning par horaire"
        
        # Group courses by time slot
        planning_par_heure = {}
        for i, c in enumerate(cours):
            horaire = c['horaire']
            if horaire not in planning_par_heure:
                planning_par_heure[horaire] = []
            
            # Find assigned room
            salle_assignee = None
            for s in salles:
                if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                    salle_assignee = s
                    break
            
            planning_par_heure[horaire].append({
                'course': c,
                'room': salle_assignee
            })
        
        # Headers
        headers = ['Horaire', 'Salle', 'Enseignant', 'Niveau', 'Matériel']
        for col, header in enumerate(headers, 1):
            cell = ws1.cell(row=1, col=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.font = Font(color='FFFFFF', bold=True)
        
        # Data rows
        row = 2
        for horaire in sorted(planning_par_heure.keys()):
            for assignment in planning_par_heure[horaire]:
                course = assignment['course']
                room = assignment['room']
                
                ws1.cell(row=row, col=1).value = horaire
                ws1.cell(row=row, col=2).value = room['nom'] if room else 'NON ASSIGNÉ'
                ws1.cell(row=row, col=3).value = course['enseignant']
                ws1.cell(row=row, col=4).value = course['niveau']
                ws1.cell(row=row, col=5).value = course.get('materiel_demande', 'N/A')
                
                # Color unassigned courses
                if not room:
                    for col in range(1, 6):
                        ws1.cell(row=row, col=col).fill = PatternFill(
                            start_color='FFE6E6', end_color='FFE6E6', fill_type='solid'
                        )
                
                row += 1
        
        # Feuille 2: Planning par salle
        ws2 = wb.create_sheet("Planning par salle")
        
        # Group by room
        planning_par_salle = {}
        for i, c in enumerate(cours):
            for s in salles:
                if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                    salle_nom = s['nom']
                    if salle_nom not in planning_par_salle:
                        planning_par_salle[salle_nom] = []
                    planning_par_salle[salle_nom].append({
                        'horaire': c['horaire'],
                        'enseignant': c['enseignant'],
                        'niveau': c['niveau'],
                        'materiel': c.get('materiel_demande', 'N/A')
                    })
                    break
        
        # Headers for room view
        for col, header in enumerate(headers, 1):
            cell = ws2.cell(row=1, col=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='70AD47', end_color='70AD47', fill_type='solid')
            cell.font = Font(color='FFFFFF', bold=True)
        
        row = 2
        for salle_nom in sorted(planning_par_salle.keys()):
            for course in sorted(planning_par_salle[salle_nom], key=lambda x: x['horaire']):
                ws2.cell(row=row, col=1).value = course['horaire']
                ws2.cell(row=row, col=2).value = salle_nom
                ws2.cell(row=row, col=3).value = course['enseignant']
                ws2.cell(row=row, col=4).value = course['niveau']
                ws2.cell(row=row, col=5).value = course['materiel']
                row += 1
        
        # Add unassigned courses if any
        if unassigned_courses:
            row += 2
            cell = ws2.cell(row=row, col=1)
            cell.value = "COURS NON ASSIGNÉS"
            cell.font = Font(bold=True, color='FF0000')
            row += 1
            
            for course_info in unassigned_courses:
                ws2.cell(row=row, col=1).value = course_info
                ws2.cell(row=row, col=1).font = Font(color='FF0000')
                row += 1
        
        # Auto-adjust column widths for both sheets
        for ws in [ws1, ws2]:
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width
        
        filename = f"planning_optimise_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(filename)
        
        assigned_count = len(cours) - len(unassigned_courses)
        return True, f"Planning généré: {filename} ({assigned_count}/{len(cours)} cours assignés)"
        
    except Exception as e:
        return False, f"Erreur lors de la génération Excel: {str(e)}"

def generer_planning_excel(date):
    """Generate planning Excel file for a specific date"""
    try:
        # Get data from database  
        date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
        raw_requests = database.get_planning_data(date_str)
        raw_rooms = database.get_all_rooms()
        
        if not raw_requests:
            return False, "Aucune demande trouvée pour cette date"
        
        if not raw_rooms:
            return False, "Aucune salle trouvée dans la base de données"
        
        # Convert rooms to dict format
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
            # Extract material needs
            material_needs = extract_material_needs(req['selected_materials'])
            
            # Determine subject based on room_type and materials
            matiere = "mixte"  # default
            if req['room_type'] == 'Physique':
                matiere = "physique"
            elif req['room_type'] == 'Chimie':
                matiere = "chimie"
            
            # Add computers needed from database
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
                "duree": duree_par_niveau(req['class_name']),
                "chaises": eleves_par_niveau(req['class_name'], req['teacher_name'])
            })

        if not cours:
            return False, "Aucun cours valide à planifier"
        
        # OR-Tools optimization model
        model = cp_model.CpModel()
        x = {}
        poids_salle = {}
        
        # Variables for room assignment
        for i, c in enumerate(cours):
            poids_salle[i] = {}
            for s in salles:
                if compatible(salles[s], c):
                    x[(i,s)] = model.NewBoolVar(f"x_{i}_{s}")
                    
                    # Check if this is a theoretical course (no specific equipment needs)
                    has_equipment_needs = (c["ordinateurs"] > 0 or c["eviers"] > 0 or 
                                          c["hotte"] > 0 or c["bancs_optiques"] > 0 or 
                                          c["oscilloscopes"] > 0 or c["becs_electriques"] > 0 or 
                                          c["support_filtration"] > 0 or c["imprimante"] > 0 or 
                                          c["examen"] > 0)
                    
                    # Weight based on room specialization
                    if has_equipment_needs:
                        # For courses with equipment needs, prefer specialized rooms
                        if c["matiere"] == salles[s]["type"]:
                            poids_salle[i][s] = 5  # Strong preference for specialized rooms
                        elif salles[s]["type"] == "mixte":
                            poids_salle[i][s] = 3  # Mixed rooms are good choice
                        else:
                            poids_salle[i][s] = 1  # Last resort
                    else:
                        # For theoretical courses, prefer mixed rooms to save specialized ones
                        if salles[s]["type"] == "mixte":
                            poids_salle[i][s] = 4  # Prefer mixed rooms for theoretical courses
                        elif c["matiere"] == salles[s]["type"]:
                            poids_salle[i][s] = 2  # Lower priority for specialized rooms
                        else:
                            poids_salle[i][s] = 3  # Any room is acceptable
                else:
                    poids_salle[i][s] = 0

        # Constraints: each course must have exactly one room
        for i in range(len(cours)):
            compatible_rooms = [x[(i,s)] for s in salles if (i,s) in x]
            if compatible_rooms:
                model.Add(sum(compatible_rooms) == 1)

        # Constraints: no room conflicts (time overlap)
        for i in range(len(cours)):
            for j in range(i + 1, len(cours)):
                start1, end1 = interval_cours(cours[i])
                start2, end2 = interval_cours(cours[j])
                
                # Check if courses overlap in time
                if not (end1 <= start2 or end2 <= start1):
                    # They overlap, so they can't use the same room
                    for s in salles:
                        if (i,s) in x and (j,s) in x:
                            model.Add(x[(i,s)] + x[(j,s)] <= 1)

        # Get list of teachers
        enseignants = list(set(c["enseignant"] for c in cours))
        
        # Preference for same teacher to use same room
        objectif_pref = []
        for enseignant in enseignants:
            cours_ens = [i for i, c in enumerate(cours) if c["enseignant"] == enseignant]
            for idx1 in range(len(cours_ens)):
                for idx2 in range(idx1 + 1, len(cours_ens)):
                    i, j = cours_ens[idx1], cours_ens[idx2]
                    for s in salle_list:
                        if (i, s) in x and (j, s) in x:
                            pref = model.NewBoolVar(f"pref_{i}_{j}_{s}")
                            model.AddBoolAnd([x[(i, s)], x[(j, s)]]).OnlyEnforceIf(pref)
                            model.AddBoolOr([x[(i, s)].Not(), x[(j, s)].Not()]).OnlyEnforceIf(pref.Not())
                            objectif_pref.append(pref)

        # Variables for room usage
        salle_utilisee = {}
        for s in salles:
            salle_utilisee[s] = model.NewBoolVar(f"salle_utilisee_{s}")
            model.AddMaxEquality(salle_utilisee[s], [x[(i,s)] for i in range(len(cours)) if (i,s) in x])

        # Objective: maximize room specialization + teacher preference + room usage
        model.Maximize(
            sum(x[(i,s)] * poids_salle[i][s] for (i,s) in x) +  # room specialization
            sum(objectif_pref) +  # same room for same teacher
            0.1 * sum(salle_utilisee.values())  # encourage room usage diversity
        )
        
        # Solve the model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60
        status = solver.Solve(model)

        print(f"Statut de la résolution: {status}")
        print(f"Nombre de cours: {len(cours)}")
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Count assignments
            assignments = 0
            unassigned_courses = []
            for i, c in enumerate(cours):
                assigned = False
                for s in salles:
                    if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                        assignments += 1
                        assigned = True
                        break
                if not assigned:
                    unassigned_courses.append(f"{c['enseignant']} - {c['niveau']} à {c['horaire']}")
            
            print(f"Cours assignés: {assignments}/{len(cours)}")
            if unassigned_courses:
                print("Cours NON assignés:")
                for course in unassigned_courses:
                    print(f"  - {course}")
            
            # Generate Excel even with partial assignments
            return generer_excel_optimise(cours, salles, x, solver, unassigned_courses)
        
        elif status == cp_model.INFEASIBLE:
            return False, "ERREUR: Il y a plus de cours simultanés que de salles disponibles! Impossible de générer le planning."
        
        else:
            return False, f"ERREUR: Résolution échouée avec le statut: {status}. Impossible de générer le planning."

    except Exception as e:
        import traceback
        return False, f"Erreur lors de la génération du planning: {str(e)}\n{traceback.format_exc()}"


if __name__ == "__main__":
    # Test the function
    success, message = generer_planning_excel("2024-09-29")
    print(message)