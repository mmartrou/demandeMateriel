"""Répartition des cours d'une journée dans les salles avec OR-Tools (generer_planning_excel)."""
from datetime import timedelta

from ortools.sat.python import cp_model

import database
import site_settings

from .compatibilite import compatible
from .cours import (
    _max_ordinateurs,
    duree_par_niveau,
    eleves_par_niveau,
    extract_material_needs,
    interval_cours,
    matiere_de_la_demande,
    to_dict_request,
)
from .export_excel import generer_excel_optimise


def generer_planning_excel(date, end_date=None, return_data_only=False, custom_room_assignments=None):
    """Generate planning Excel file for a specific date or date range"""
    try:
        # Get data from database  
        date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
        raw_requests = database.get_planning_data(date_str)
        raw_rooms = database.get_all_rooms()
        
        # Si on a des assignations personnalisées, modifier les données avant génération
        if custom_room_assignments:
            print(f"📝 Génération avec assignations personnalisées: {custom_room_assignments}")
            # On va continuer la génération normale mais modifier les assignations à la fin
        
        # Récupérer les créneaux des salles à disponibilité limitée
        creneaux_salles = database.get_room_availability()

        # Maps nom court pour enseignants et niveaux
        all_levels = database.get_all_levels()
        teacher_short_map = {t['name']: t['short_name'] for t in database.get_all_teachers()}
        level_short_map = {l['name']: l['short_name'] for l in all_levels}
        levels_duration_map = {l['name']: l['default_duration'] for l in all_levels}

        if not raw_requests:
            return False, "Aucune demande trouvée pour cette date"
        
        if not raw_rooms:
            return False, "Aucune salle trouvée dans la base de données"
        
        # Convert rooms to dict format
        salles = {}
        salle_list = []
        for raw_room in raw_rooms:
            # Convert sqlite3.Row to dict
            room = dict(raw_room) if hasattr(raw_room, 'keys') else raw_room
            
            room_name = room.get('name', f'Room_{len(salle_list)}')
            salle_list.append(room_name)
            salles[room_name] = {
                "nom": room_name,
                "type": str(room.get('type', 'mixte') or 'mixte').strip().lower(),
                "ordinateurs": room.get('ordinateurs', 0) or 0,
                "chaises": room.get('chaises', 20) or 20,
                "eviers": room.get('eviers', 0) or 0,
                "hotte": room.get('hotte', 0) or 0,
                "bancs_optiques": room.get('bancs_optiques', 0) or 0,
                "obscurite_totale": room.get('obscurite_totale', 0) or 0,
                "becs_electriques": room.get('becs_electriques', 0) or 0,
                "support_filtration": room.get('support_filtration', 0) or 0,
                "imprimante": room.get('imprimante', 0) or 0,
                "examen": room.get('examen', 0) or 0,
                "disponibilite_limitee": bool(room.get('limited_availability'))
            }

        max_ordinateurs = _max_ordinateurs(salles)

        # Déterminer le jour de la semaine à partir de la date
        from datetime import datetime
        if isinstance(date, str):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
        else:
            date_obj = date
        
        jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
        jour_planning = jours_semaine[date_obj.weekday()]
        
        # Convert requests to course format
        cours = []
        for i, raw_req in enumerate(raw_requests):
            req = to_dict_request(raw_req)
            material_needs = extract_material_needs(req.get('selected_materials', ''))
            matiere = matiere_de_la_demande(req)
            computers_needed = req.get('computers_needed', 0)
            if computers_needed and computers_needed > 0:
                material_needs["ordinateurs"] = max(material_needs["ordinateurs"], computers_needed)
            cours.append({
                "id": f"{req.get('teacher_name', 'Unknown')}_{i}",
                "request_id": req.get('id'),
                "prepared": bool(req.get('prepared', False)),
                "enseignant": req.get('teacher_name', 'Unknown'),
                "horaire": req.get('horaire', '9h00') or '9h00',
                "niveau": req.get('class_name', ''),
                "matiere": matiere,
                "jour": jour_planning,
                "ordinateurs": material_needs["ordinateurs"],
                "ordinateurs_overflow": material_needs["ordinateurs"] > max_ordinateurs,
                "eviers": material_needs["eviers"],
                "hotte": material_needs["hotte"],
                "bancs_optiques": material_needs["bancs_optiques"],
                "obscurite_totale": material_needs["obscurite_totale"],
                "becs_electriques": material_needs["becs_electriques"],
                "support_filtration": material_needs["support_filtration"],
                "imprimante": material_needs["imprimante"],
                "examen": material_needs["examen"],
                "duree": req.get('custom_duration') or duree_par_niveau(req.get('class_name', ''), levels_duration_map),
                "chaises": eleves_par_niveau(req.get('class_name', ''), req.get('teacher_name', 'Unknown')),
                "materiel_demande": req.get('material_description', 'N/A'),
                "selected_materials": req.get('selected_materials', ''),
                "request_name": req.get('request_name', ''),
                "teacher_short_name": teacher_short_map.get(req.get('teacher_name', ''), ''),
                "level_short_name": level_short_map.get(req.get('class_name', ''), ''),
                "labo_observations": req.get('labo_observations', '') or '',
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
                if compatible(salles[s], c, creneaux_salles, max_ordinateurs):
                    x[(i,s)] = model.NewBoolVar(f"x_{i}_{s}")
                    
                    # Check if this is a theoretical course (no specific equipment needs)
                    has_equipment_needs = (c["ordinateurs"] > 0 or c["eviers"] > 0 or
                                          c["hotte"] > 0 or c["bancs_optiques"] > 0 or
                                          c["obscurite_totale"] > 0 or c["becs_electriques"] > 0 or
                                          c["support_filtration"] > 0 or c["imprimante"] > 0 or
                                          c["examen"] > 0)
                    
                    # Weight based on room specialization and REAL EQUIPMENT
                    # AMÉLIORATION: Priorité basée sur les équipements réels, pas seulement le type déclaré
                    
                    # Analyser les équipements réels de la salle
                    room_has_chemistry_equipment = (salles[s]["eviers"] > 0 or salles[s]["hotte"] > 0 or 
                                                   salles[s]["becs_electriques"] > 0 or salles[s]["support_filtration"] > 0)
                    room_has_physics_equipment = (salles[s]["obscurite_totale"] > 0 or salles[s]["bancs_optiques"] > 0)
                    
                    # Pondération intelligente basée sur matière + équipements réels
                    if c["matiere"] == "chimie":
                        if room_has_chemistry_equipment:
                            # Salle avec équipements de chimie - PRIORITÉ MAXIMALE
                            poids_salle[i][s] = 10 if has_equipment_needs else 9
                        elif salles[s]["type"] == "chimie":
                            # Salle déclarée chimie mais sans équipements - BONNE
                            poids_salle[i][s] = 8 if has_equipment_needs else 7
                        elif salles[s]["type"] == "mixte" and not room_has_physics_equipment:
                            # Salle mixte sans équipements physique - ACCEPTABLE
                            poids_salle[i][s] = 6
                        elif room_has_physics_equipment or salles[s]["type"] == "physique":
                            # Salle avec équipements physique - À ÉVITER
                            poids_salle[i][s] = 2
                        else:
                            # Dernière option
                            poids_salle[i][s] = 4
                            
                    elif c["matiere"] == "physique":
                        if room_has_physics_equipment:
                            # Salle avec équipements de physique - PRIORITÉ MAXIMALE
                            poids_salle[i][s] = 10 if has_equipment_needs else 9
                        elif salles[s]["type"] == "physique":
                            # Salle déclarée physique mais sans équipements - BONNE
                            poids_salle[i][s] = 8 if has_equipment_needs else 7
                        elif salles[s]["type"] == "mixte" and not room_has_chemistry_equipment:
                            # Salle mixte sans équipements chimie - ACCEPTABLE
                            poids_salle[i][s] = 6
                        elif room_has_chemistry_equipment or salles[s]["type"] == "chimie":
                            # Salle avec équipements chimie - À ÉVITER
                            poids_salle[i][s] = 2
                        else:
                            # Dernière option
                            poids_salle[i][s] = 4
                            
                    else:  # matiere == "mixte" ou autres
                        if salles[s]["type"] == "mixte":
                            poids_salle[i][s] = 7  # Parfait pour cours mixtes
                        elif not room_has_chemistry_equipment and not room_has_physics_equipment:
                            poids_salle[i][s] = 6  # Salles théoriques sont bien
                        else:
                            poids_salle[i][s] = 4  # Éviter les salles spécialisées pour cours mixtes
                else:
                    poids_salle[i][s] = 0

        # Constraints: each course with compatible rooms must have exactly one room
        for i in range(len(cours)):
            compatible_rooms = [x[(i,s)] for s in salles if (i,s) in x]
            if compatible_rooms:
                model.Add(sum(compatible_rooms) == 1)
            else:
                print(f"⚠️ ATTENTION: Cours {i} ({cours[i]['enseignant']} - {cours[i]['niveau']}) n'a AUCUNE salle compatible!")
                print(f"   Matière: {cours[i]['matiere']}, Horaire: {cours[i]['horaire']}")
                print(f"   Besoins: ordinateurs={cours[i]['ordinateurs']}, eviers={cours[i]['eviers']}, hotte={cours[i]['hotte']}")

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
            vars_for_salle = [x[(i,s)] for i in range(len(cours)) if (i,s) in x]
            if vars_for_salle:
                model.AddMaxEquality(salle_utilisee[s], vars_for_salle)
            else:
                # Aucune variable pour cette salle -> elle n'est pas utilisée
                model.Add(salle_utilisee[s] == 0)

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
        print(f"Nombre de salles disponibles: {len(salles)}")
        print(f"Salles: {list(salles.keys())}")
        print(f"Variables x créées: {len(x)}")
        
        # Debug: afficher les cours et leurs salles compatibles
        for i, c in enumerate(cours):
            compatible_rooms_list = [s for s in salles if (i,s) in x]
            print(f"Cours {i} ({c['enseignant']} - {c['niveau']} à {c['horaire']}): {len(compatible_rooms_list)} salles compatibles - {compatible_rooms_list}")
        
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
            if return_data_only:
                # Retourner les données structurées pour l'éditeur
                courses_data = []
                assignments_data = {}
                room_assignments = {}
                
                for i, course in enumerate(cours):
                    course_id = course['id']  # Utiliser l'ID artificiel généré par la conversion 
                    courses_data.append({
                        'id': course_id,
                        'request_id': course.get('request_id'),
                        'prepared': course.get('prepared', False),
                        'subject': course['matiere'],
                        'level': course['niveau'],
                        'teacher': course['enseignant'],
                        'date': date_str,  # Utiliser date_str de la fonction
                        'time': course['horaire'],
                        'duration': course['duree'],
                        'students': course.get('chaises', 20),  # Utiliser 'chaises' au lieu de 'nb_eleves'
                        'request_name': course.get('request_name', ''),
                        'material_description': course.get('materiel_demande', ''),
                        'ordinateurs': course.get('ordinateurs', 0),
                        'ordinateurs_overflow': course.get('ordinateurs_overflow', False),
                        'eviers': course.get('eviers', 0),
                        'hotte': course.get('hotte', 0),
                        'bancs_optiques': course.get('bancs_optiques', 0),
                        'obscurite_totale': course.get('obscurite_totale', 0),
                        'becs_electriques': course.get('becs_electriques', 0),
                        'support_filtration': course.get('support_filtration', 0),
                        'imprimante': course.get('imprimante', 0),
                        'examen': course.get('examen', 0),
                        'teacher_short_name': course.get('teacher_short_name', ''),
                        'level_short_name': course.get('level_short_name', ''),
                        'labo_observations': course.get('labo_observations', ''),
                    })
                    
                    # Trouver l'assignation de salle
                    assigned_room = None
                    for s in salles:
                        if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                            assigned_room = s
                            course_id = course['id']
                            print(f"Cours {course_id} ({course['enseignant']} - {course['niveau']}) assigné à {s} ({salles[s]['nom']})")
                            slot_key = f"{date_str}_{course['horaire']}"
                            if slot_key not in assignments_data:
                                assignments_data[slot_key] = []
                            assignments_data[slot_key].append(course_id)
                            break
                    
                    # Ajouter l'assignation de salle pour l'interface
                    course_id = course['id']
                    if assigned_room:
                        room_assignments[course_id] = salles[assigned_room]['nom']
                    else:
                        room_assignments[course_id] = 'Non assigné'
                
                # Créer la liste des jours
                if end_date:
                    days = []
                    start = datetime.strptime(date, '%Y-%m-%d').date() if isinstance(date, str) else date
                    end = datetime.strptime(end_date, '%Y-%m-%d').date() if isinstance(end_date, str) else end_date
                    current_date = start
                    while current_date <= end:
                        if current_date.weekday() < 5:  # Lundi à vendredi
                            days.append(current_date.strftime('%Y-%m-%d'))
                        current_date += timedelta(days=1)
                else:
                    days = [date if isinstance(date, str) else date.strftime('%Y-%m-%d')]
                
                # Horaires autorisés pour le début des cours (pas toutes les 15 minutes)
                time_slots = site_settings.get_time_layout()['slots']
                
                print(f"⏰ Créneaux autorisés pour début de cours - Total: {len(time_slots)} horaires")
                print(f"📝 Tous les créneaux: {time_slots}")
                
                rooms_list = [{'id': s, 'name': salles[s]['nom']} for s in salles]
                print(f"📍 Rooms list pour l'API: {rooms_list}")
                print(f"📍 Room assignments: {dict(list(room_assignments.items())[:5])}")  # Premiers 5 pour debug
                
                return True, {
                    'courses': courses_data,
                    'days': days,
                    'time_slots': time_slots,
                    'assignments': assignments_data,
                    'room_assignments': room_assignments,
                    'rooms': rooms_list
                }
            else:
                return generer_excel_optimise(cours, salles, x, solver, unassigned_courses, date_str, custom_room_assignments)
        
        elif status == cp_model.INFEASIBLE:
            return False, "ERREUR: Il y a plus de cours simultanés que de salles disponibles! Impossible de générer le planning."
        
        else:
            return False, f"ERREUR: Résolution échouée avec le statut: {status}. Impossible de générer le planning."

    except Exception as e:
        import traceback
        return False, f"Erreur lors de la génération du planning: {str(e)}\n{traceback.format_exc()}"
