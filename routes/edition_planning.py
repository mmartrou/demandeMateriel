"""Éditeur de planning : génération OR-Tools, sauvegarde, observations et occupation standard."""
from datetime import datetime
import json
import logging

from flask import Blueprint, current_app, jsonify, make_response, render_template, request

from database import (
    get_all_levels,
    get_all_rooms,
    get_all_student_numbers,
    get_all_teachers,
    get_db_connection,
    get_planning_version,
    get_standard_occupation,
    move_course,
    set_planning_observations,
    set_standard_occupation,
)
from database import save_planning as enregistrer_planning
from planning import (
    build_course_data_entry,
    generer_excel_from_saved_planning,
    generer_planning_excel,
    get_new_requests_for_date,
    get_planning_data_for_editor_v2,
)
from planning import build_print_model, salles_a_jour
from security import _is_privileged_user, api_error
import site_settings

logger = logging.getLogger(__name__)
bp = Blueprint('edition_planning', __name__)


@bp.route('/admin/planning-editor')
def planning_editor():
    """Page d'édition interactive du planning"""
    teachers = get_all_teachers()
    return render_template('planning_editor.html', teachers=teachers)


@bp.route('/api/standard-occupation', methods=['GET', 'POST'])
def api_standard_occupation():
    """API pour gérer l'occupation standard (colonne "Occupation standard" de l'éditeur de planning)"""
    if request.method == 'GET':
        day = request.args.get('day')
        if not day:
            return jsonify({'error': 'Jour manquant'}), 400
        return jsonify(get_standard_occupation(day))
    elif request.method == 'POST':
        data = request.get_json()
        day = data.get('day')
        slot = data.get('slot')
        value = data.get('value')
        if not day or not slot:
            return jsonify({'error': 'Champs manquants'}), 400
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                return jsonify({'error': 'Valeur invalide'}), 400
        success = set_standard_occupation(day, slot, value)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Erreur lors de l\'enregistrement'}), 500


# Routes API pour l'éditeur de planning
@bp.route('/api/planning-editor/data', methods=['GET'])
def api_get_planning_data():
    """API endpoint pour récupérer les données du planning initial pour un jour donné"""
    try:
        target_date = request.args.get('date')
        
        if not target_date:
            return jsonify({'error': 'La date est requise'}), 400
            
        # Utiliser la vraie génération avec optimisation OR-Tools
        print(f"🔍 API: Génération OR-Tools pour {target_date}")
        
        try:
            # Utiliser la version V2 qui fait l'optimisation OR-Tools
            planning_data = get_planning_data_for_editor_v2(target_date)
            
            # Utiliser seulement les horaires de début de cours autorisés
            planning_data['time_slots'] = site_settings.get_time_layout()['slots']
            
            print(f"🔍 API: OR-Tools terminé - {len(planning_data.get('courses', []))} cours, {len(planning_data.get('rooms', []))} salles")
            return jsonify(planning_data)
            
        except Exception as e:
            print(f"❌ Erreur OR-Tools: {e}")
            # En cas d'erreur, retourner une structure vide
            return jsonify({
                'courses': [],
                'rooms': [{'name': r['name']} for r in get_all_rooms()],
                'time_slots': site_settings.get_time_layout()['slots'],
                'room_assignments': {},
                'days': [target_date],
                'error': str(e)
            })
    except Exception as e:
        return api_error('Erreur lors de la récupération des données planning', e)


@bp.route('/api/planning-editor/course/<int:request_id>', methods=['GET'])
def api_planning_editor_course(request_id):
    """Retourne les données à jour d'une demande au format 'courses_data', pour
    rafraîchir une carte du planning sans relancer l'optimiseur (et donc sans
    déplacer les autres cours)."""
    try:
        course = build_course_data_entry(request_id)
        if course is None:
            return jsonify({'error': 'Demande non trouvée'}), 404
        return jsonify(course)
    except Exception as e:
        return api_error('Erreur lors de la récupération du cours', e)


@bp.route('/api/planning-editor/new-requests', methods=['GET'])
def api_planning_new_requests():
    """Liste les demandes de la date qui ne sont pas encore dans le planning
    sauvegardé (ajoutées après la génération), avec suggestion de salles libres
    et compatibles pour un ajout rapide sans relancer OR-Tools."""
    try:
        target_date = request.args.get('date')
        if not target_date:
            return jsonify({'error': 'La date est requise'}), 400
        new_requests = get_new_requests_for_date(target_date)
        return jsonify({'new_requests': new_requests})
    except Exception as e:
        return api_error('Erreur lors de la détection des nouvelles demandes', e)


@bp.route('/api/planning-editor/generate', methods=['POST'])
def api_generate_planning_from_editor():
    """API endpoint pour générer le planning Excel depuis l'éditeur (planning sauvegardé ou OR-Tools)"""
    try:
        data = request.get_json()
        target_date = data.get('date')

        if not target_date:
            return jsonify({'error': 'La date est requise'}), 400

        # Priorité 1 : planning sauvegardé en base (inclut les modifications glisser-déposer)
        saved_planning = None
        try:
            conn, db_type = get_db_connection()
            cursor = conn.cursor()
            placeholder = '%s' if db_type == 'postgresql' else '?'
            cursor.execute(f'SELECT data FROM plannings WHERE date = {placeholder}', (target_date,))
            row = cursor.fetchone()
            conn.close()
            if row:
                raw = row['data'] if isinstance(row, dict) else row[0]
                saved_planning = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            print(f"⚠️ Impossible de charger le planning sauvegardé: {e}")

        if saved_planning and saved_planning.get('courses'):
            success, result = generer_excel_from_saved_planning(saved_planning, target_date)
        else:
            # Fallback : relancer OR-Tools avec les assignations de salle envoyées par le client
            room_assignments = data.get('room_assignments', {})
            print(f"🔍 Pas de planning sauvegardé — génération OR-Tools avec room_assignments: {room_assignments}")
            success, result = generer_planning_excel(target_date, custom_room_assignments=room_assignments)
        
        if not success:
            return jsonify({'error': result}), 500
        
        # Si result est un string (chemin de fichier), lire le fichier
        if isinstance(result, str):
            try:
                with open(result, 'rb') as f:
                    file_content = f.read()
            except FileNotFoundError:
                return jsonify({'error': f'Fichier généré non trouvé: {result}'}), 500
                
            # Nettoyer le fichier temporaire
            import os
            try:
                os.remove(result)
            except:
                pass
                
            file_data = file_content
        else:
            # Si result est un BytesIO (buffer mémoire)
            file_data = result.getvalue()
        
        # Créer la réponse avec le même nommage que la page planning
        from datetime import datetime
        try:
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            day_name = day_names[date_obj.weekday()]
            formatted_date = date_obj.strftime('%d-%m-%Y')
            filename = f"planning{day_name.upper()}_{formatted_date}.xlsx"
        except:
            filename = f"planning_{target_date}.xlsx"
        
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
            
    except Exception as e:
        return api_error('Erreur lors de la génération du planning depuis l\'éditeur', e)


def _date_valide(valeur):
    try:
        datetime.strptime(valeur or '', '%Y-%m-%d')
        return True
    except (TypeError, ValueError):
        return False


@bp.route('/api/planning-editor/version', methods=['GET'])
def api_planning_version():
    """Numéro de version du planning d'une date : appelé toutes les quelques secondes par chaque poste
    ouvert sur l'éditeur, pour savoir s'il doit recharger le planning (voir database/plannings.py)."""
    date = request.args.get('date', '')
    if not _date_valide(date):
        return jsonify({'error': 'Date invalide'}), 400
    version, existe = get_planning_version(date)
    return jsonify({'version': version, 'existe': existe})


_ERREURS_DEPLACEMENT = {
    'planning_introuvable': ("Aucun planning enregistré pour cette date", 404),
    'cours_introuvable': ("Ce cours n'existe plus dans le planning (supprimé par quelqu'un d'autre ?)", 404),
    'salle_inconnue': ("Salle inconnue", 400),
    'creneau_invalide': ("Horaire invalide", 400),
    'conflit': ("Le planning est modifié en ce moment par plusieurs personnes, réessayez", 409),
}


@bp.route('/api/planning-editor/move', methods=['POST'])
def api_planning_move():
    """Déplace un cours (salle + horaire) dans le planning enregistré, en l'appliquant à la version la plus
    récente : deux techniciens qui déplacent deux cours en même temps ne s'écrasent pas."""
    data = request.get_json(silent=True) or {}
    date, course_id, room, creneau = data.get('date'), data.get('course_id'), data.get('room'), data.get('time')
    if not _date_valide(date) or course_id in (None, '') or not isinstance(room, str) or not room:
        return jsonify({'error': 'Requête invalide'}), 400
    try:
        statut, version = move_course(date, course_id, room, creneau,
                                      extra_rooms=[r['name'] for r in get_all_rooms()])
    except Exception as e:
        return api_error('Erreur lors du déplacement du cours', e)
    if statut == 'ok':
        return jsonify({'version': version})
    message, code = _ERREURS_DEPLACEMENT[statut]
    return jsonify({'error': message, 'statut': statut, 'version': version}), code


@bp.route('/api/save-planning', methods=['POST'])
def save_planning():
    """API endpoint to save planning data into the database"""
    try:
        # Parse JSON payload robustly
        data = request.get_json(silent=True) or {}
        current_app.logger.info(f"Données reçues pour enregistrement: {data}")

        # Normalize keys: accept 'data' or legacy 'planning_data'
        if 'data' not in data and 'planning_data' in data:
            data['data'] = data.get('planning_data')

        # Validate required 'date'; default empty dict for data if missing
        if 'date' not in data or not data['date']:
            current_app.logger.error("Requête invalide: date ou données manquantes")
            return jsonify({'error': "Requête invalide: date ou données manquantes"}), 400

        date = data['date']
        planning_data = data.get('data') if data.get('data') is not None else {}

        # Édition à plusieurs : `base_version` est la version du planning que l'éditeur affichait. Si un
        # collègue l'a modifié depuis, on refuse (409) plutôt que d'écraser son travail. `force` (génération
        # d'un nouveau planning, confirmée par l'utilisateur) écrase sans condition, comme le font les anciens
        # navigateurs qui n'envoient pas de version.
        base_version = data.get('base_version')
        if data.get('force') or base_version is None:
            base_version = None
        elif isinstance(base_version, bool) or not isinstance(base_version, int):
            return jsonify({'error': 'base_version invalide'}), 400

        ok, version = enregistrer_planning(date, planning_data, base_version)
        if not ok:
            current_app.logger.info(f"Enregistrement refusé pour {date} : le planning a changé (version {version})")
            return jsonify({'error': 'Le planning a été modifié par quelqu\'un d\'autre entre-temps',
                            'conflit': True, 'version': version}), 409

        current_app.logger.info(f"Planning enregistré avec succès pour la date: {date} (version {version})")
        return jsonify({'message': 'Planning enregistré avec succès', 'version': version}), 200

    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'enregistrement du planning: {e}")
        return api_error('Erreur lors de l\'enregistrement du planning', e)


@bp.route('/api/get-planning', methods=['GET'])
def get_planning():
    """API endpoint to retrieve planning data from the database"""
    try:
        date = request.args.get('date')
        current_app.logger.info(f"Requête reçue pour récupérer le planning de la date: {date}")

        if not date:
            current_app.logger.error("La date est manquante dans la requête.")
            return jsonify({'error': 'La date est requise'}), 400

        # Connexion à la base de données
        conn, db_type = get_db_connection()  # Extraire uniquement la connexion SQLite ou PostgreSQL
        cursor = conn.cursor()

        # Récupérer les données du planning
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f"SELECT data, observations, version FROM plannings WHERE date = {placeholder}", (date,))
        row = cursor.fetchone()
        conn.close()

        if row:
            if isinstance(row, dict):
                raw = row['data']
                obs = row.get('observations') or ''
                version = row.get('version') or 0
            else:
                raw, obs, version = row[0], row[1], row[2]
            obs = obs or ''
            version = int(version or 0)
            planning = json.loads(raw) if isinstance(raw, str) else raw

            # Enrichir les courses avec les noms courts et labo_observations à jour
            courses = planning.get('courses', [])
            if courses:
                teacher_short_map = {t['name']: t['short_name'] for t in get_all_teachers()}
                level_short_map = {l['name']: l['short_name'] for l in get_all_levels()}
                # Effectifs "2nde classe entière" par enseignant, chargés en une seule requête
                # (plutôt qu'une connexion DB par cours "2nd Classe")
                student_count_map = {s['teacher_name']: s['student_count'] for s in get_all_student_numbers() if s.get('level') == '2nde'}

                # Charger labo_observations pour tous les request_ids en une seule requête
                req_ids = [c['request_id'] for c in courses if c.get('request_id')]
                labo_map = {}
                if req_ids:
                    conn2, db_type2 = get_db_connection()
                    cursor2 = conn2.cursor()
                    placeholder2 = '%s' if db_type2 == 'postgresql' else '?'
                    placeholders_list = ','.join([placeholder2] * len(req_ids))
                    cursor2.execute(f'SELECT id, labo_observations FROM material_requests WHERE id IN ({placeholders_list})', req_ids)
                    for r in cursor2.fetchall():
                        rid = r['id'] if isinstance(r, dict) else r[0]
                        labo_obs = r['labo_observations'] if isinstance(r, dict) else r[1]
                        labo_map[rid] = labo_obs or ''
                    conn2.close()

                for c in courses:
                    c.setdefault('teacher_short_name', teacher_short_map.get(c.get('teacher', ''), ''))
                    c.setdefault('level_short_name', level_short_map.get(c.get('level', ''), ''))
                    c['teacher_short_name'] = teacher_short_map.get(c.get('teacher', ''), '')
                    c['level_short_name'] = level_short_map.get(c.get('level', ''), '')
                    c['labo_observations'] = labo_map.get(c.get('request_id'), '')
                    if c.get('level') == '2nd Classe':
                        c['students'] = student_count_map.get(c.get('teacher', ''), 20)

            if planning.get('rooms') is not None:
                planning['rooms'] = salles_a_jour(planning['rooms'])

            current_app.logger.info(f"Planning trouvé pour la date {date}")
            return jsonify({'planning': planning, 'observations': obs, 'version': version}), 200
        else:
            current_app.logger.warning(f"Aucun planning trouvé pour la date {date}.")
            return jsonify({'error': 'Aucun planning trouvé pour cette date'}), 404

    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération du planning: {e}")
        return api_error('Erreur lors de la récupération du planning', e)


@bp.route('/api/planning-observations', methods=['PUT'])
def save_planning_observations():
    """Sauvegarde les observations d'un planning (par date)"""
    if not _is_privileged_user():
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        data = request.get_json(silent=True) or {}
        date = data.get('date')
        observations = data.get('observations', '')
        if not date:
            return jsonify({'error': 'Date requise'}), 400
        version = set_planning_observations(date, observations)
        return jsonify({'message': 'Observations enregistrées', 'version': version}), 200
    except Exception as e:
        return api_error('Erreur lors de la sauvegarde des observations', e)


@bp.route('/admin/planning-print')
def planning_print():
    """Page imprimable (A4 paysage) du planning enregistré pour une date.

    ?date=AAAA-MM-JJ  ?mode=technicien|affichage  ?print=1 (ouvre directement la fenêtre d'impression)"""
    date = request.args.get('date', '')
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return render_template('planning_print_vide.html', date=date, invalide=True), 400
    modele = build_print_model(date, request.args.get('mode', 'technicien'))
    if modele is None:
        return render_template('planning_print_vide.html', date=date, invalide=False), 404
    return render_template('planning_print.html', p=modele, auto_print=request.args.get('print') == '1')
