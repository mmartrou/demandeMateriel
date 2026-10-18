"""Données de la page imprimable du planning (/admin/planning-print).

Tout vient de la base : le planning enregistré (cours, salle de chaque cours), puis les informations
qui peuvent avoir changé depuis (noms courts, observations labo, effectifs, ordre des salles), les
tests au labo et les observations du jour. Ce module ne produit aucun HTML : il prépare un modèle
simple (lignes, colonnes, cellules fusionnées) que planning_print.html se contente d'afficher.
"""
from datetime import datetime

import database
import site_settings

JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
        'novembre', 'décembre']

# Valeurs de room_assignments qui signifient « pas de salle » dans l'éditeur
SANS_SALLE = ('', 'Non assigné', '__TEMP__')


# --------------------------------------------------------------------------- données partagées

def salles_a_jour(salles_sauvegardees):
    """Liste des salles d'un planning sauvegardé, remise dans l'ordre actuel de /admin/rooms.

    Un planning enregistre la liste des salles telle qu'elle était à sa création : sans cette mise
    à jour, changer l'ordre (ou ajouter une salle) n'aurait aucun effet sur les plannings déjà
    sauvegardés. Une salle supprimée ou renommée depuis reste affichée à la fin tant que le planning
    lui a affecté des cours, pour ne pas les faire disparaître."""
    anciennes = {s.get('name'): s for s in (salles_sauvegardees or [])}
    actuelles = [r['name'] for r in database.get_all_rooms()]
    if not actuelles:
        return salles_sauvegardees
    salles = [anciennes.get(nom, {'id': nom, 'name': nom}) for nom in actuelles]
    salles += [s for nom, s in anciennes.items() if nom not in actuelles]
    return salles


def rafraichir_cours(courses):
    """Met à jour, depuis la base, ce qui peut avoir changé depuis l'enregistrement du planning :
    noms courts des enseignants et des niveaux, observations labo, effectif des classes entières."""
    teacher_short = {t['name']: t['short_name'] for t in database.get_all_teachers()}
    level_short = {l['name']: l['short_name'] for l in database.get_all_levels()}
    effectifs = {s['teacher_name']: s['student_count'] for s in database.get_all_student_numbers()
                 if s.get('level') == '2nde'}
    labo = database.get_labo_observations_map([c['request_id'] for c in courses if c.get('request_id')])
    for c in courses:
        c['teacher_short_name'] = teacher_short.get(c.get('teacher', ''), c.get('teacher_short_name', ''))
        c['level_short_name'] = level_short.get(c.get('level', ''), c.get('level_short_name', ''))
        if c.get('request_id'):
            c['labo_observations'] = labo.get(c['request_id'], '')
        if c.get('level') == '2nd Classe':
            c['students'] = effectifs.get(c.get('teacher', ''), c.get('students', 20))


def libelle_date(date_str):
    """'2026-10-07' -> 'Mercredi 7 octobre 2026'."""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return date_str
    return f"{JOURS[d.weekday()].capitalize()} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


# --------------------------------------------------------------------------- construction du modèle

def _matiere(course):
    sujet = (course.get('subject') or 'mixte').lower()
    return sujet if sujet in ('physique', 'chimie') else 'autre'


def _lignes_occupees(course, minutes_lignes):
    """(première ligne, ligne de fin exclue) d'un cours dans la grille — même règle que l'export Excel."""
    debut = site_settings.parse_time(course.get('time') or '9h00')
    duree = int(course.get('duration') or 85)
    idx_debut, idx_fin = 0, 1
    for idx, minutes in enumerate(minutes_lignes):
        if minutes <= debut:
            idx_debut = idx
        if minutes >= debut + duree and idx_fin == 1:
            idx_fin = idx
            break
    else:
        idx_fin = len(minutes_lignes)
    if idx_fin <= idx_debut:
        idx_fin = idx_debut + 1
    return idx_debut, idx_fin


def _occupation(date_str, lignes_horaires, courses_en_salle):
    """Colonnes « Occupation standard » et « Cours simultanés » de l'éditeur, pour chaque ligne affichée.

    standard : nombre de cours attendu à ce créneau (réglé dans l'éditeur, par jour de semaine) ;
    simultanes : cours réellement en salle à cet instant ; statut : 'ok' s'ils sont égaux, 'ecart' sinon."""
    try:
        jour = JOURS[datetime.strptime(date_str, '%Y-%m-%d').weekday()]
    except ValueError:
        jour = ''
    standard = database.get_standard_occupation(jour) if jour in JOURS[:5] else {}
    resultat = []
    for libelle in lignes_horaires:
        instant = site_settings.parse_time(libelle)
        simultanes = sum(1 for c in courses_en_salle
                         if site_settings.parse_time(c.get('time') or '9h00') <= instant
                         < site_settings.parse_time(c.get('time') or '9h00') + int(c.get('duration') or 85))
        attendu = standard.get(libelle)
        statut = '' if attendu in (None, '') else ('ok' if simultanes == int(attendu) else 'ecart')
        resultat.append({'standard': '' if attendu is None else attendu, 'simultanes': simultanes, 'statut': statut})
    return resultat


def _vue_cours(course, mode, lignes):
    """Ce qui est affiché dans la case d'un cours."""
    enseignant = course.get('teacher') or ''
    niveau = course.get('level') or ''
    vue = {
        'matiere': _matiere(course),
        'lignes': lignes,
        'enseignant': enseignant,
        'niveau': niveau,
        'details': mode == 'technicien',
    }
    if mode == 'technicien':
        vue['enseignant'] = course.get('teacher_short_name') or enseignant
        vue['niveau'] = course.get('level_short_name') or niveau
        vue['observations'] = (course.get('labo_observations') or '').strip()
        vue['effectif'] = course.get('students') if niveau == '2nd Classe' and course.get('students') else None
        vue['ordinateurs'] = course.get('ordinateurs') or 0
        vue['ordinateurs_depassement'] = bool(course.get('ordinateurs_overflow'))
        vue['prepare'] = bool(course.get('prepared'))
    return vue


def build_print_model(date_str, mode='technicien', trim=True):
    """Modèle de la page imprimable pour une date, ou None si aucun planning n'est enregistré.

    mode : 'technicien' (détaillé : observations, effectifs, ordinateurs) ou 'affichage' (simple,
    pour l'affichage en salle : enseignant et niveau seulement).
    trim : ne garder que les lignes horaires utilisées par les cours (sinon toute la journée)."""
    planning = database.get_saved_planning(date_str)
    if planning is None:
        return None
    mode = 'affichage' if mode == 'affichage' else 'technicien'
    courses = planning.get('courses', []) or []
    room_assignments = planning.get('room_assignments', {}) or {}
    rafraichir_cours(courses)

    settings = site_settings.get_site_settings()
    layout = site_settings.get_time_layout(settings)

    # --- colonnes : les salles dans l'ordre de /admin/rooms, avec leur regroupement
    groupes_par_salle = {r['name']: r['room_group'] for r in database.get_all_rooms()}
    noms = [s['name'] for s in (salles_a_jour(planning.get('rooms')) or [])]

    def salle_du_cours(c):
        return c.get('room') or room_assignments.get(str(c.get('id', '')), '')

    for c in courses:                                  # une salle utilisée mais inconnue reste visible
        salle = salle_du_cours(c)
        if salle not in SANS_SALLE and salle not in noms:
            noms.append(salle)
    salles = [{'name': n, 'group': groupes_par_salle.get(n, '')} for n in noms]
    index_salle = {n: i for i, n in enumerate(noms)}

    # --- lignes horaires
    libelles = layout['grid_rows']
    minutes_lignes = [site_settings.parse_time(h) for h in libelles]
    durees = [layout['durations'].get(h, 30) for h in libelles]
    separateurs = set(layout['separators'])

    # --- placement des cours (sans chevauchement dans une même colonne)
    placements = []   # (colonne, ligne_debut, ligne_fin, cours)
    non_places = []
    for c in sorted(courses, key=lambda c: site_settings.parse_time(c.get('time') or '9h00')):
        salle = salle_du_cours(c)
        if salle in SANS_SALLE:
            non_places.append(c)
            continue
        debut, fin = _lignes_occupees(c, minutes_lignes)
        placements.append([index_salle[salle], debut, fin, c])
    par_colonne = {}
    for p in placements:
        par_colonne.setdefault(p[0], []).append(p)
    conflits = []
    for liste in par_colonne.values():
        liste.sort(key=lambda p: p[1])
        precedent = None
        for p in list(liste):
            if precedent is not None and p[1] < precedent[2]:
                if p[1] == precedent[1]:               # même ligne de départ : impossible à afficher
                    conflits.append(p)
                    placements.remove(p)
                    continue
                precedent[2] = p[1]                    # le précédent s'arrête où le suivant commence
            precedent = p

    # --- plage de lignes affichée
    if trim and placements:
        premiere = min(p[1] for p in placements)
        derniere = max(p[2] for p in placements)
    else:
        premiere, derniere = 0, len(libelles)

    nb_cellules = len(salles)
    lignes = []
    for i in range(premiere, derniere):
        lignes.append({'label': libelles[i], 'separator': libelles[i] in separateurs,
                       'minutes': durees[i], 'cells': [{'vide': True} for _ in range(nb_cellules)]})
    if mode == 'technicien':
        en_salle = [c for c in courses if salle_du_cours(c) not in SANS_SALLE]
        for ligne, occ in zip(lignes, _occupation(date_str, [l['label'] for l in lignes], en_salle)):
            ligne['occupation'] = occ
    for col, debut, fin, c in placements:
        r0, r1 = max(debut, premiere) - premiere, min(fin, derniere) - premiere
        lignes[r0]['cells'][col] = {'cours': _vue_cours(c, mode, r1 - r0), 'lignes': r1 - r0}
        for r in range(r0 + 1, r1):
            lignes[r]['cells'][col] = None             # recouvert par la case au-dessus (rowspan)

    # --- pied de page
    lab_tests = []
    observations = ''
    if mode == 'technicien':
        for lt in database.get_lab_test_requests(date_str):
            texte = lt.get('teacher_name', '') or ''
            if lt.get('class_name'):
                texte += f" ({lt['class_name']})"
            if lt.get('request_name'):
                texte += f" — {lt['request_name']}"
            lab_tests.append({'horaire': lt.get('horaire') or '', 'texte': texte,
                              'description': (lt.get('material_description') or '').strip()})
        observations = (database.get_planning_observations(date_str) or '').strip()
    a_signaler = [{'texte': f"{c.get('time', '')} — {c.get('teacher_short_name') or c.get('teacher', '')}"
                            f" ({c.get('level_short_name') or c.get('level', '')})"}
                  for c in non_places + [p[3] for p in conflits]] if mode == 'technicien' else []

    # La grille remplit la place restante de la page (CSS) ; chaque ligne y pèse autant que sa durée.
    # La taille d'une case ne dépend donc que de sa durée et décide de ce qu'elle peut afficher.
    for i, ligne in enumerate(lignes):
        for cellule in ligne['cells']:
            if cellule and 'cours' in cellule:
                minutes = sum(l['minutes'] for l in lignes[i:i + cellule['lignes']])
                cellule['taille'] = 'xs' if minutes < 45 else 's' if minutes < 70 else 'm' if minutes < 100 else 'l'

    # --- en-têtes de groupes (colonnes consécutives de même groupe)
    groupes = []
    for salle in salles:
        if groupes and groupes[-1]['label'] == salle['group']:
            groupes[-1]['span'] += 1
        else:
            groupes.append({'label': salle['group'], 'span': 1})

    return {
        'date': date_str,
        'date_label': libelle_date(date_str),
        'site_name': settings['site_name'],
        'mode': mode,
        'salles': salles,
        'groupes': groupes,
        'lignes': lignes,
        'avec_occupation': mode == 'technicien',
        'lab_tests': lab_tests,
        'a_signaler': a_signaler,
        'observations': observations,
        'nb_cours': len(placements),
        'edite_le': datetime.now(site_settings.get_timezone()).strftime('%d/%m/%Y à %Hh%M'),
    }
