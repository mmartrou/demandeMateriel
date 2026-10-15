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
    get_standard_occupation,
    set_standard_occupation,
)
from planning_generator import (
    build_course_data_entry,
    generer_excel_from_saved_planning,
    generer_planning_excel,
    get_new_requests_for_date,
    get_planning_data_for_editor_v2,
)
from planning_print import build_print_model, salles_a_jour
from security import _is_privileged_user, api_error
import site_settings

logger = logging.getLogger(__name__)
bp = Blueprint('edition_planning', __name__)


@bp.route('/admin/planning-editor')
def planning_editor():
    """Page d'édition interactive du planning"""
    teachers = get_all_teachers()
    return render_template('planning_editor.html', teachers=teachers)


@bp.route('/admin/planning-editor-test')
def planning_editor_test():
    """Variante de test de l'éditeur de planning (refonte visuelle) - mêmes données, même API"""
    teachers = get_all_teachers()
    return render_template('planning_editor_test.html', teachers=teachers)


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

        # Connexion à la base de données
        conn, db_type = get_db_connection()  # Extraire uniquement la connexion SQLite ou PostgreSQL
        cursor = conn.cursor()

        # Insertion ou mise à jour des données
        import json  # Importer le module JSON pour la conversion
        planning_data_json = json.dumps(planning_data)  # Convertir le dictionnaire en JSON

        # Insertion ou mise à jour des données
        placeholder = '%s' if db_type == 'postgresql' else '?'
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO plannings (date, data)
                VALUES ({placeholder}, {placeholder})
                ON CONFLICT(date) DO UPDATE SET data=EXCLUDED.data
            ''', (date, planning_data_json))
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO plannings (date, data)
                VALUES ({placeholder}, {placeholder})
            ''', (date, planning_data_json))
        conn.commit()
        conn.close()

        current_app.logger.info(f"Planning enregistré avec succès pour la date: {date}")
        return jsonify({'message': 'Planning enregistré avec succès'}), 200

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
        try:
            cursor.execute(f"SELECT data, observations FROM plannings WHERE date = {placeholder}", (date,))
        except Exception:
            cursor.execute(f"SELECT data FROM plannings WHERE date = {placeholder}", (date,))
        row = cursor.fetchone()
        conn.close()

        if row:
            if isinstance(row, dict):
                raw = row['data']
                obs = row.get('observations') or ''
            else:
                raw = row[0]
                obs = row[1] if len(row) > 1 else ''
            obs = obs or ''
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
            return jsonify({'planning': planning, 'observations': obs}), 200
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
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if db_type == 'postgresql' else '?'
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO plannings (date, data, observations)
                VALUES ({placeholder}, {placeholder}, {placeholder})
                ON CONFLICT(date) DO UPDATE SET observations=EXCLUDED.observations
            ''', (date, '{}', observations))
        else:
            cursor.execute(f'SELECT 1 FROM plannings WHERE date={placeholder}', (date,))
            if cursor.fetchone():
                cursor.execute(f'UPDATE plannings SET observations={placeholder} WHERE date={placeholder}', (observations, date))
            else:
                cursor.execute(f'INSERT INTO plannings (date, data, observations) VALUES ({placeholder},{placeholder},{placeholder})', (date, '{}', observations))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Observations enregistrées'}), 200
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
