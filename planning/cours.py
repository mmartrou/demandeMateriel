"""Préparation des données d'un cours : conversion des demandes, durées, effectifs,
besoins en matériel, matière ; salles et leur ordre d'affichage."""
import database


def to_dict_request(req):
    # Compatibilité tuple/dict/sqlite3.Row pour les demandes
    if isinstance(req, dict):
        return req
    elif hasattr(req, '_fields'):
        return req._asdict()
    elif hasattr(req, 'keys'):
        return dict(req)
    else:
        # Ordre des colonnes : adapter selon la structure de la table
        return {
            'id': req[0],
            'teacher_id': req[1],
            'request_date': req[2],
            'horaire': req[3],
            'class_name': req[4],
            'material_description': req[5],
            'quantity': req[6],
            'selected_materials': req[7] if len(req) > 7 and req[7] else '',
            'computers_needed': req[8] if len(req) > 8 and req[8] else 0,
            'notes': req[9] if len(req) > 9 else '',
            'prepared': req[10] if len(req) > 10 and req[10] else False,
            'modified': req[11] if len(req) > 11 and req[11] else False,
            'group_count': req[12] if len(req) > 12 else 1,
            'material_prof': req[13] if len(req) > 13 else '',
            'request_name': req[14] if len(req) > 14 else '',
            'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
            'image_url': req[16] if len(req) > 16 else None,
            'exam': req[17] if len(req) > 17 else False,
            'created_at': req[18] if len(req) > 18 else None,
            'teacher_name': req[19] if len(req) > 19 else '',
            'custom_duration': req[20] if len(req) > 20 else None,
            'labo_observations': req[21] if len(req) > 21 else '',
            'room_type_manual': bool(req[22]) if len(req) > 22 and req[22] is not None else False,
        }


def duree_par_niveau(niveau, levels_map=None):
    """Durée par défaut (minutes) d'un niveau. levels_map : {nom: durée} lu dans la table
    `levels` (réglable dans /admin/niveaux). Un niveau inconnu dure 85 minutes."""
    if levels_map and niveau in levels_map:
        return levels_map[niveau]
    return 85


def eleves_par_niveau(niveau, enseignant=None):
    """Get number of students by level"""
    if niveau == "2nd Classe" and enseignant:
        return database.get_student_count_for_teacher(enseignant, '2nde')
    return 20


def interval_cours(c):
    """Get interval (start, end) for a course"""
    start = h_to_min(c["horaire"])
    return (start, start + c["duree"])


def extract_material_needs(selected_materials):
    """Extract material needs from selected_materials string with improved parsing"""
    needs = {
        "ordinateurs": 0,
        "eviers": 0,
        "hotte": 0,
        "bancs_optiques": 0,
        "obscurite_totale": 0,
        "becs_electriques": 0,
        "support_filtration": 0,
        "imprimante": 0,
        "examen": 0
    }
    
    if not selected_materials:
        return needs

    # Convert to lowercase for case-insensitive matching
    materials_text = selected_materials.lower()
    
    # Parse materials - handle both new format (with dashes) and legacy format
    materials = []
    
    # Split by lines first (new format with dashes)
    lines = materials_text.split('\n')
    for line in lines:
        # Remove leading dashes and whitespace
        clean_line = line.strip().lstrip('- ').strip()
        if clean_line:
            materials.append(clean_line)
            # Also split by commas within each line for mixed formats
            if ',' in clean_line:
                materials.extend([m.strip() for m in clean_line.split(',') if m.strip()])
    
    # Also add the full text for pattern matching
    materials.append(materials_text)
    
    # Direct material matching (new system with specific materials)
    specific_materials = {
        'éviers': 'eviers',
        'evier': 'eviers',
        'hotte': 'hotte',
        'bancs optiques': 'bancs_optiques',
        'banc optique': 'bancs_optiques',
        'obscurité totale': 'obscurite_totale',
        'obscurite totale': 'obscurite_totale',
        'becs électriques': 'becs_electriques',
        'bec électrique': 'becs_electriques',
        'support de filtration': 'support_filtration',
        'imprimante': 'imprimante'
    }
    
    # Check for direct matches first (more accurate)
    for material in materials:
        material_clean = material.strip().lower()
        
        # Direct material name matches
        if material_clean in specific_materials:
            needs[specific_materials[material_clean]] = 1
            continue
        
    
    return needs


def matiere_de_la_demande(req):
    """'physique', 'chimie' ou 'mixte' selon le type de salle de la demande.

    Une salle 'Mixte' laissée par défaut est devinée par mots-clés ; une fois que les
    techniciens/admin ont choisi le type (room_type_manual), leur choix est respecté tel quel.
    """
    room_type = req.get('room_type') or 'Mixte'
    if room_type == 'Physique':
        return "physique"
    if room_type == 'Chimie':
        return "chimie"
    if req.get('room_type_manual'):
        return "mixte"
    materials_text = str(req.get('selected_materials', '')).lower()
    description_text = str(req.get('material_description', '')).lower()
    combined_text = f"{materials_text} {description_text}"
    physics_keywords = ['oscilloscope', 'générateur', 'signal', 'optique', 'laser', 'prisme', 'lentille', 'physique', 'électricité', 'mécanique', 'ondes']
    chemistry_keywords = ['burette', 'erlenmeyer', 'bécher', 'pipette', 'solution', 'naoh', 'hcl', 'acide', 'base', 'dosage', 'titrage', 'chimie', 'réaction', 'molécule', 'ion', 'ph']
    physics_score = sum(1 for kw in physics_keywords if kw in combined_text)
    chemistry_score = sum(1 for kw in chemistry_keywords if kw in combined_text)
    if physics_score > chemistry_score:
        return "physique"
    if chemistry_score > physics_score:
        return "chimie"
    return "mixte"


def build_course_data_entry(request_id):
    """
    Construit, pour une seule demande, le dictionnaire au format 'courses_data'
    utilisé par l'éditeur de planning (mêmes calculs que la boucle de
    generer_planning_excel), sans relancer l'optimiseur OR-Tools.
    Permet de rafraîchir une carte de cours après modification/suppression
    sans déplacer les autres cours déjà placés.
    """
    raw_req = database.get_material_request_by_id(request_id)
    if not raw_req:
        return None
    req = to_dict_request(raw_req)

    material_needs = extract_material_needs(req.get('selected_materials', ''))
    all_levels = database.get_all_levels()
    teacher_short_map = {t['name']: t['short_name'] for t in database.get_all_teachers()}
    level_short_map = {l['name']: l['short_name'] for l in all_levels}
    levels_duration_map = {l['name']: l['default_duration'] for l in all_levels}
    max_ordinateurs = _max_ordinateurs(_build_salles_dict(database.get_all_rooms()))
    matiere = matiere_de_la_demande(req)

    computers_needed = req.get('computers_needed', 0)
    if computers_needed and computers_needed > 0:
        material_needs["ordinateurs"] = max(material_needs["ordinateurs"], computers_needed)

    return {
        'request_id': req.get('id'),
        'prepared': bool(req.get('prepared', False)),
        'subject': matiere,
        'level': req.get('class_name', ''),
        'teacher': req.get('teacher_name', 'Unknown'),
        'time': req.get('horaire', '9h00') or '9h00',
        'duration': req.get('custom_duration') or duree_par_niveau(req.get('class_name', ''), levels_duration_map),
        'students': eleves_par_niveau(req.get('class_name', ''), req.get('teacher_name', 'Unknown')),
        'request_name': req.get('request_name', ''),
        'material_description': req.get('material_description', 'N/A'),
        'ordinateurs': material_needs["ordinateurs"],
        'ordinateurs_overflow': material_needs["ordinateurs"] > max_ordinateurs,
        'eviers': material_needs["eviers"],
        'hotte': material_needs["hotte"],
        'bancs_optiques': material_needs["bancs_optiques"],
        'obscurite_totale': material_needs["obscurite_totale"],
        'becs_electriques': material_needs["becs_electriques"],
        'support_filtration': material_needs["support_filtration"],
        'imprimante': material_needs["imprimante"],
        'examen': material_needs["examen"],
        'teacher_short_name': teacher_short_map.get(req.get('teacher_name', ''), ''),
        'level_short_name': level_short_map.get(req.get('class_name', ''), ''),
        'labo_observations': req.get('labo_observations', '') or '',
    }


def h_to_min(hstr):
    """Convertit une heure en format HH:MM ou HHhMM en minutes."""
    try:
        if 'h' in hstr:
            h, m = map(int, hstr.replace("h", ":").split(":"))
        elif ':' in hstr:
            h, m = map(int, hstr.split(":"))
        else:
            h = int(hstr)
            m = 0
        return h * 60 + m
    except:
        return 8 * 60  # Défaut 8h00


def _build_salles_dict(raw_rooms):
    """Convertit les lignes de la table rooms en dict {nom_salle: {champs...}}
    au format attendu par compatible()."""
    salles = {}
    for raw_room in raw_rooms:
        room = dict(raw_room) if hasattr(raw_room, 'keys') else raw_room
        room_name = room.get('name', f'Room_{len(salles)}')
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
    return salles


def get_room_layout():
    """Salles dans l'ordre d'affichage (réglé dans /admin/rooms) et leurs regroupements pour
    l'en-tête du planning. Renvoie (noms, groupes) où groupes = [(libellé, [noms de salles])]."""
    noms = []
    groupes = {}
    for room in database.get_all_rooms():
        noms.append(room['name'])
        if room['room_group']:
            groupes.setdefault(room['room_group'], []).append(room['name'])
    return noms, list(groupes.items())


def _max_ordinateurs(salles):
    """Nombre maximum d'ordinateurs disponible dans une salle, toutes salles confondues."""
    if not salles:
        return 0
    return max((s.get("ordinateurs", 0) or 0) for s in salles.values())
