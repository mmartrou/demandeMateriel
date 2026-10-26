"""Compatibilité salle / cours (équipements, créneaux des salles à disponibilité limitée)
et suggestions de salles pour une nouvelle demande."""
from datetime import datetime

import database

from .cours import (
    _build_salles_dict,
    _max_ordinateurs,
    build_course_data_entry,
    get_room_layout,
    h_to_min,
    to_dict_request,
)


def est_disponible_aux_creneaux(cours_info, creneaux_salle):
    """Vérifie si une salle à disponibilité limitée est libre pour ce cours, selon les
    créneaux déclarés pour elle dans /admin/room-availability (liste des créneaux de CETTE salle)"""
    if not creneaux_salle:
        return True  # Aucun créneau déclaré pour cette salle : elle reste utilisable
    
    # Convertir l'horaire du cours
    horaire_debut = cours_info.get('horaire', '8:00')
    duree = cours_info.get('duree', 110)  # Durée par défaut en minutes
    
    debut_cours = h_to_min(horaire_debut)
    fin_cours = debut_cours + duree
    
    # Obtenir le jour de la semaine du cours (pour l'instant on assume 'lundi' par défaut)
    jour_cours = cours_info.get('jour', 'lundi').lower()
    
    # Vérifier si le cours peut tenir dans au moins un des créneaux disponibles pour ce jour
    for slot in creneaux_salle:
        if slot['jour'].lower() == jour_cours:
            debut_dispo = h_to_min(slot['heure_debut'])
            fin_dispo = h_to_min(slot['heure_fin'])
            
            # Le cours doit être entièrement dans la plage de disponibilité
            if debut_cours >= debut_dispo and fin_cours <= fin_dispo:
                return True
    
    return False  # Aucun créneau ne convient


def compatible(salle, besoin, creneaux_salles=None, max_ordinateurs=None):
    """Check if a room is compatible with course needs.

    max_ordinateurs : nombre maximum d'ordinateurs présents dans une salle,
    toutes salles confondues. Si la demande dépasse ce maximum, on la borne à
    ce maximum pour la comparaison : la demande ne peut jamais être satisfaite
    intégralement, mais on l'assigne quand même à la (aux) salle(s) offrant le
    plus d'ordinateurs plutôt que de ne l'assigner à aucune salle.
    """
    room_type = str(salle.get("type", "mixte") or "mixte").strip().lower()

    # Salle à disponibilité limitée (case cochée dans /admin/rooms) : créneaux à respecter
    if salle.get("disponibilite_limitee") and creneaux_salles is not None:
        creneaux_de_la_salle = [c for c in creneaux_salles if c.get("salle") == salle.get("nom")]
        if not est_disponible_aux_creneaux(besoin, creneaux_de_la_salle):
            return False
    
    # Check if this is a theoretical course (no specific equipment needs)
    has_equipment_needs = (besoin["ordinateurs"] > 0 or besoin["eviers"] > 0 or
                          besoin["hotte"] > 0 or besoin["bancs_optiques"] > 0 or
                          besoin["obscurite_totale"] > 0 or besoin["becs_electriques"] > 0 or
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
    if besoin["matiere"] == "chimie" and room_type not in ("chimie", "mixte"):
        return False
    if besoin["matiere"] == "physique" and room_type not in ("physique", "mixte"):
        return False
    
    # Check equipment needs
    ordinateurs_requis = besoin["ordinateurs"]
    if max_ordinateurs is not None and ordinateurs_requis > max_ordinateurs:
        ordinateurs_requis = max_ordinateurs
    if ordinateurs_requis > salle["ordinateurs"]:
        return False
    if besoin["eviers"] > salle["eviers"]:
        return False
    if besoin["chaises"] > salle["chaises"]:
        return False
    if besoin["hotte"] > salle["hotte"]:
        return False
    if besoin["bancs_optiques"] > salle["bancs_optiques"]:
        return False
    if besoin["obscurite_totale"] > salle["obscurite_totale"]:
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


def find_available_rooms_for_request(request_id, date_str, salles=None, creneaux_salles=None, saved_planning=None):
    """
    Pour une demande (TP) donnée, cherche les salles libres et compatibles à son
    créneau horaire en se basant sur le planning déjà sauvegardé pour cette date,
    sans relancer l'optimiseur OR-Tools (donc sans déplacer les cours déjà placés).
    Permet l'ajout rapide d'un TP de dernière minute après la génération du planning.

    Retourne (course_data, suggested_rooms) :
      - course_data : dict au format 'courses_data' (voir build_course_data_entry)
      - suggested_rooms : liste des noms de salles libres et compatibles, dans
        l'ordre d'affichage habituel des salles.
    """
    course = build_course_data_entry(request_id)
    if course is None:
        return None, []

    if salles is None:
        salles = _build_salles_dict(database.get_all_rooms())
    if creneaux_salles is None:
        creneaux_salles = database.get_room_availability()
    if saved_planning is None:
        saved_planning = database.get_saved_planning(date_str) or {}

    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    jours_semaine = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    jour_planning = jours_semaine[date_obj.weekday()]

    besoin = {
        "matiere": course.get('subject', 'mixte'),
        "chaises": course.get('students', 20),
        "ordinateurs": course.get('ordinateurs', 0),
        "eviers": course.get('eviers', 0),
        "hotte": course.get('hotte', 0),
        "bancs_optiques": course.get('bancs_optiques', 0),
        "obscurite_totale": course.get('obscurite_totale', 0),
        "becs_electriques": course.get('becs_electriques', 0),
        "support_filtration": course.get('support_filtration', 0),
        "imprimante": course.get('imprimante', 0),
        "examen": course.get('examen', 0),
        "horaire": course.get('time', '9h00'),
        "duree": course.get('duration', 85),
        "jour": jour_planning,
    }

    debut_new = h_to_min(besoin['horaire'])
    fin_new = debut_new + besoin['duree']

    # Déterminer les salles déjà occupées sur ce créneau, d'après les cours
    # déjà placés dans le planning sauvegardé (on exclut cette demande elle-même
    # si elle y figure déjà, au cas où on rappellerait la fonction après ajout).
    room_assignments = saved_planning.get('room_assignments', {}) or {}
    occupied_rooms = set()
    for c in (saved_planning.get('courses', []) or []):
        if c.get('request_id') == request_id:
            continue
        room = room_assignments.get(str(c.get('id')))
        if not room or room in ('Non assigné', '__TEMP__'):
            continue
        debut_c = h_to_min(c.get('time', '9h00'))
        fin_c = debut_c + (c.get('duration') or 85)
        if debut_new < fin_c and debut_c < fin_new:
            occupied_rooms.add(room)

    max_ordinateurs = _max_ordinateurs(salles)
    ordered_rooms = get_room_layout()[0]
    suggested_rooms = [
        room_name for room_name in ordered_rooms
        if room_name in salles and room_name not in occupied_rooms
        and compatible(salles[room_name], besoin, creneaux_salles, max_ordinateurs)
    ]

    return course, suggested_rooms


def get_new_requests_for_date(date_str):
    """
    Liste les demandes de la base pour cette date qui ne figurent pas encore dans
    le planning sauvegardé (typiquement une demande créée après la génération du
    planning). Pour chacune, calcule les salles libres et compatibles à son
    créneau, sans relancer OR-Tools.
    """
    saved_planning = database.get_saved_planning(date_str) or {}
    existing_request_ids = {
        c.get('request_id') for c in (saved_planning.get('courses', []) or [])
        if c.get('request_id') is not None
    }

    raw_requests = database.get_planning_data(date_str) or []
    salles = _build_salles_dict(database.get_all_rooms())
    creneaux_salles = database.get_room_availability()

    result = []
    for raw_req in raw_requests:
        req = to_dict_request(raw_req)
        req_id = req.get('id')
        if req_id in existing_request_ids:
            continue
        course, suggested_rooms = find_available_rooms_for_request(
            req_id, date_str, salles=salles, creneaux_salles=creneaux_salles, saved_planning=saved_planning
        )
        if course is None:
            continue
        result.append({**course, 'suggested_rooms': suggested_rooms})
    return result
