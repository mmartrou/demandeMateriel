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


def assign_courses_greedy(cours, salles):
    """Assignation greedy pour les cas où le solveur CP ne trouve pas de solution."""
    print("Utilisation de l'algorithme greedy pour assignation partielle...")
    
    # Trier les cours par horaire pour traiter chronologiquement
    cours_sorted = sorted(enumerate(cours), key=lambda x: x[1]['horaire'])
    
    assignments = {}
    unassigned_courses = []
    room_schedule = {}  # room_id -> set of time slots
    
    for room in salles:
        room_schedule[room['id']] = set()
    
    for i, course in cours_sorted:
        assigned = False
        compatible_rooms = []
        
        # Trouver les salles compatibles et disponibles
        for room in salles:
            if compatible(course, room) and course['horaire'] not in room_schedule[room['id']]:
                compatible_rooms.append(room)
        
        if compatible_rooms:
            # Choisir la meilleure salle (préférer salles mixtes pour cours théoriques)
            best_room = compatible_rooms[0]
            if not course.get('materiel_demande') or course.get('materiel_demande') == "Pas besoin de matériel":
                # Pour cours théorique, préférer salle mixte
                for room in compatible_rooms:
                    if room.get('type_salle') == 'Mixte':
                        best_room = room
                        break
            
            assignments[i] = best_room['id']
            room_schedule[best_room['id']].add(course['horaire'])
            assigned = True
        
        if not assigned:
            unassigned_courses.append(f"{course['enseignant']} - {course['niveau']} à {course['horaire']}")
    
    print(f"Assignation greedy: {len(assignments)}/{len(cours)} cours assignés")
    if unassigned_courses:
        print("Cours non assignés:")
        for course in unassigned_courses:
            print(f"  - {course}")
    
    return generer_excel_greedy(cours, salles, assignments, unassigned_courses)

def generer_excel_greedy(cours, salles, assignments, unassigned_courses):
    """Génération Excel pour l'assignation greedy."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, PatternFill, Border, Side, Font
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Planning Partiel"
        
        # Headers
        headers = ['Horaire', 'Salle', 'Enseignant', 'Niveau', 'Matériel']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, col=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color='D0D0D0', end_color='D0D0D0', fill_type='solid')
        
        # Data rows for assigned courses
        row = 2
        for i, course in enumerate(cours):
            if i in assignments:
                room_id = assignments[i]
                room = next((s for s in salles if s['id'] == room_id), None)
                
                ws.cell(row=row, col=1).value = course['horaire']
                ws.cell(row=row, col=2).value = room['nom'] if room else 'ERREUR'
                ws.cell(row=row, col=3).value = course['enseignant']
                ws.cell(row=row, col=4).value = course['niveau']
                ws.cell(row=row, col=5).value = course.get('materiel_demande', 'N/A')
                row += 1
        
        # Add unassigned courses section if any
        if unassigned_courses:
            row += 1
            cell = ws.cell(row=row, col=1)
            cell.value = "COURS NON ASSIGNÉS"
            cell.font = Font(bold=True, color='FF0000')
            row += 1
            
            for course_info in unassigned_courses:
                ws.cell(row=row, col=1).value = course_info
                ws.cell(row=row, col=1).font = Font(color='FF0000')
                row += 1
        
        # Auto-adjust column widths
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
        
        filename = f"planning_partiel_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(filename)
        return True, f"Planning partiel généré: {filename} ({len(assignments)}/{len(cours)} cours assignés)"
        
    except Exception as e:
        return False, f"Erreur lors de la génération Excel: {str(e)}"

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
            print("PROBLÈME: Il y a plus de cours simultanés que de salles disponibles!")
            # Try to assign as many courses as possible using a greedy approach
            print("Tentative d'assignation partielle...")
            return assign_courses_greedy(cours, salles)
        
        else:
            print(f"Résolution échouée avec le statut: {status}")
            # Still try greedy assignment
            return assign_courses_greedy(cours, salles)
            
            # Time slots
            horaires_str = [
                "9h00", "9h30", "10h00", "10h45", "11h15", "11h45", "12h15", "12h45",
                "13h15", "13h45", "14h15", "14h45", "15h15", "15h45", "16h15", "16h45",
                "17h15", "17h45", "18h15"
            ]
            horaires = [h_to_min(h) for h in horaires_str]
            
            # Define room groups based on actual room types
            physique_salles = [s for s in salle_list if s in salles and salles[s]["type"] in ("physique", "mixte")]
            chimie_salles = [s for s in salle_list if s in salles and salles[s]["type"] in ("chimie", "mixte")]
            
            # Create header with day name
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day_name = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][date_obj.weekday()]
            
            ws.cell(row=1, column=1, value=day_name.upper())
            ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions['A'].width = 12
            
            # Styling
            bold_large = Font(bold=True, size=36)
            bold_medium = Font(bold=True, size=16)
            thick_border = Border(
                left=Side(style='thick'), right=Side(style='thick'),
                top=Side(style='thick'), bottom=Side(style='thick')
            )
            
            # Room type headers with grouping - only if rooms exist
            col_physique = [2 + salle_list.index(s) for s in physique_salles if s in salle_list]
            col_chimie = [2 + salle_list.index(s) for s in chimie_salles if s in salle_list]
            
            if col_physique:
                ws.merge_cells(start_row=1, start_column=col_physique[0], end_row=1, end_column=col_physique[-1])
                for col in range(col_physique[0], col_physique[-1]+1):
                    cell_phys = ws.cell(row=1, column=col, value="Physique" if col==col_physique[0] else None)
                    cell_phys.font = bold_large
                    cell_phys.alignment = Alignment(horizontal="center", vertical="center")
                    cell_phys.border = thick_border
            
            if col_chimie:
                ws.merge_cells(start_row=1, start_column=col_chimie[0], end_row=1, end_column=col_chimie[-1])
                for col in range(col_chimie[0], col_chimie[-1]+1):
                    cell_chim = ws.cell(row=1, column=col, value="Chimie" if col==col_chimie[0] else None)
                    cell_chim.font = bold_large
                    cell_chim.alignment = Alignment(horizontal="center", vertical="center")
                    cell_chim.border = thick_border

            # Room headers (row 2)
            for idx_s, s in enumerate(salle_list):
                col_letter = ws.cell(row=2, column=2+idx_s).column_letter
                cell = ws.cell(row=2, column=2+idx_s, value=s)
                ws.column_dimensions[col_letter].width = 20
                cell.font = bold_large
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thick_border

            # Date header (row 2, column 1)
            ws.cell(row=2, column=1, value=date_str)
            ws.cell(row=2, column=1).font = bold_medium
            ws.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=2, column=1).border = thick_border

            # Create time grid matrix
            cell_matrix = [[{"content": "", "merge": False, "merge_len": 1, "matiere": ""} 
                           for _ in salle_list] for _ in horaires]
            
            # Fill assignments
            for i, c in enumerate(cours):
                for s in salles:
                    if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                        start_time, end_time = interval_cours(c)
                        
                        # Find time slot indices safely
                        idx_start = None
                        idx_end = None
                        for idx, h in enumerate(horaires):
                            if h <= start_time and (idx+1 >= len(horaires) or start_time < horaires[idx+1]):
                                idx_start = idx
                                break
                        for idx in range(len(horaires)):
                            if horaires[idx] >= end_time:
                                idx_end = idx
                                break
                        
                        if idx_start is None:
                            idx_start = 0
                        if idx_end is None:
                            idx_end = len(horaires)
                            
                        merge_len = max(1, idx_end - idx_start)

                        # Build material requirements text
                        besoins_txt = []
                        if c["ordinateurs"] > 0: besoins_txt.append(f"Ordinateurs: {c['ordinateurs']}")
                        if c["hotte"] > 0: besoins_txt.append("Hotte")
                        if c["bancs_optiques"] > 0: besoins_txt.append("Bancs optiques")
                        if c["oscilloscopes"] > 0: besoins_txt.append("Oscilloscopes")
                        if c["becs_electriques"] > 0: besoins_txt.append("Becs électriques")
                        if c["support_filtration"] > 0: besoins_txt.append("Support filtration")
                        if c["imprimante"] > 0: besoins_txt.append("Imprimante")
                        if c["examen"] > 0: besoins_txt.append("Examen")
                        
                        # Fill the grid
                        salle_idx = salle_list.index(s)
                        for idx in range(idx_start, min(idx_end, len(horaires))):
                            cell_matrix[idx][salle_idx]["content"] = f"{c['enseignant']}\n{c['niveau']}\n" + ", ".join(besoins_txt)
                            cell_matrix[idx][salle_idx]["matiere"] = c["matiere"]
                        
                        if idx_start < len(horaires):
                            cell_matrix[idx_start][salle_idx]["merge"] = True
                            cell_matrix[idx_start][salle_idx]["merge_len"] = merge_len

            # Fill Excel sheet with time grid
            for idx_h, h in enumerate(horaires_str):
                ws.cell(row=3+idx_h, column=1, value=h)
                ws.cell(row=3+idx_h, column=1).alignment = Alignment(horizontal="center", vertical="center")
                ws.cell(row=3+idx_h, column=1).border = thick_border
                
                for idx_s, s in enumerate(salle_list):
                    cell = cell_matrix[idx_h][idx_s]
                    excel_row = 3+idx_h
                    excel_col = 2+idx_s
                    
                    if cell["merge"]:
                        # Set content and formatting before merging
                        ws.cell(row=excel_row, column=excel_col, value=cell["content"])
                        ws.cell(row=excel_row, column=excel_col).alignment = Alignment(
                            horizontal="center", vertical="center", wrap_text=True
                        )
                        ws.cell(row=excel_row, column=excel_col).border = thick_border
                        
                        # Color coding by subject
                        matiere = cell["matiere"].lower() if cell["matiere"] else ""
                        if "chimie" in matiere:
                            fill_color = PatternFill(start_color="B2F2E9", end_color="B2F2E9", fill_type="solid")
                        elif "physique" in matiere:
                            fill_color = PatternFill(start_color="FFD580", end_color="FFD580", fill_type="solid")
                        elif "mixte" in matiere:
                            fill_color = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
                        else:
                            fill_color = None
                        
                        if fill_color:
                            ws.cell(row=excel_row, column=excel_col).fill = fill_color
                        
                        # Merge cells if needed and apply formatting to all merged cells
                        if cell["merge_len"] > 1:
                            # Apply formatting to all cells that will be merged
                            for merge_row in range(excel_row, excel_row + cell["merge_len"]):
                                if merge_row != excel_row:  # Skip the main cell
                                    ws.cell(row=merge_row, column=excel_col).border = thick_border
                                    if fill_color:
                                        ws.cell(row=merge_row, column=excel_col).fill = fill_color
                            
                            # Now merge the cells
                            ws.merge_cells(
                                start_row=excel_row, start_column=excel_col,
                                end_row=excel_row + cell["merge_len"] - 1, end_column=excel_col
                            )
                    else:
                        # Only write to cells that are not part of a merged range
                        if not any(cell_matrix[r][idx_s]["merge"] and 
                                 idx_h >= r and idx_h < r + cell_matrix[r][idx_s]["merge_len"] 
                                 for r in range(min(idx_h, len(cell_matrix)))):
                            ws.cell(row=excel_row, column=excel_col, value="")
                            ws.cell(row=excel_row, column=excel_col).border = thick_border

            # Set row heights
            for idx_h in range(len(horaires)):
                ws.row_dimensions[3 + idx_h].height = 25

            # Save file with proper naming
            if output_filename is None:
                output_filename = f"planning{day_name.upper()}.xlsx"
            
            wb.save(output_filename)
            return True, f"Planning généré avec succès: {output_filename}"

    except Exception as e:
        import traceback
        return False, f"Erreur lors de la génération du planning: {str(e)}\n{traceback.format_exc()}"


if __name__ == "__main__":
    # Test the function
    success, message = generer_planning_excel("2024-09-29")
    print(message)