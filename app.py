from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import csv
import io
import logging
import os
from datetime import datetime, timedelta
import openpyxl
# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv()
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from database import (init_database, get_all_teachers, add_material_request, get_material_requests, 
                      get_requests_for_calendar, get_material_request_by_id, update_material_request, 
                      toggle_prepared_status, delete_material_request, update_room_type,
                      add_pending_modification, get_pending_modifications, get_requests_with_pending_modifications,
                      validate_pending_modifications, reject_pending_modifications, get_c21_availability, add_c21_availability, delete_c21_availability,
                      get_all_rooms, update_room, import_rooms_from_csv_content,
                      get_all_student_numbers, update_student_number, add_student_number, delete_student_number)
from google_drive_service import extract_google_drive_id, validate_google_drive_image, get_image_info
from planning_generator import generer_planning_excel, get_planning_data_for_editor, get_planning_data_for_editor_v2
from database import get_db_connection
import json

app = Flask(__name__)

# Configuration pour gérer les erreurs d'encodage UTF-8
app.config['JSON_AS_ASCII'] = False

# Middleware pour gérer les erreurs d'encodage dans les requêtes
@app.before_request  
def handle_encoding_errors():
    """Gère les erreurs d'encodage UTF-8 dans les requêtes de manière silencieuse"""
    try:
        # Nettoyer l'URL et les paramètres de requête
        if request.url and len(request.url) > 70:
            # Vérifier la zone problématique autour de la position 71
            problematic_section = request.url[65:75] if len(request.url) > 75 else request.url[65:]
            # Nettoyer les caractères problématiques
            cleaned_section = problematic_section.encode('utf-8', errors='ignore').decode('utf-8')
            if problematic_section != cleaned_section:
                # Log seulement si on détecte et nettoie des caractères problématiques
                app.logger.debug(f"Caractères UTF-8 invalides nettoyés dans l'URL")
        
        # Valider les paramètres de requête
        if request.args:
            for key, value in request.args.items():
                try:
                    # Forcer la validation UTF-8 avec nettoyage automatique
                    key.encode('utf-8', errors='ignore')
                    value.encode('utf-8', errors='ignore')
                except Exception:
                    pass
                    
    except Exception:
        # Ignorer complètement les erreurs d'encodage pour éviter le spam des logs
        pass

# Configuration des logs pour éviter le spam d'erreurs d'encodage
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Initialisation de la base de données au démarrage
init_database()

# Gestionnaire d'erreur global pour les erreurs d'encodage
@app.errorhandler(UnicodeDecodeError)
def handle_unicode_error(e):
    """Gère les erreurs d'encodage Unicode de manière silencieuse"""
    app.logger.debug(f"Erreur d'encodage Unicode interceptée: {e}")
    return "Erreur d'encodage", 400

@app.errorhandler(UnicodeEncodeError) 
def handle_unicode_encode_error(e):
    """Gère les erreurs d'encodage Unicode lors de l'envoi de réponses"""
    app.logger.debug(f"Erreur d'encodage Unicode lors de l'envoi: {e}")
    return "Erreur d'encodage", 400

# Route Générateur de Planning
@app.route('/planning')
def planning():
    """Page Générateur de Planning pour voir les demandes d'un jour"""
    return render_template('planning.html')

@app.route('/api/generate-planning', methods=['POST'])
def generate_planning():
    """Generate Excel planning for a specific date using OR-Tools optimization"""
    try:
        data = request.get_json()
        if not data or 'date' not in data:
            return jsonify({'error': 'Date manquante'}), 400
        
        date_str = data['date']
        
        # Use the existing planning generator
        success, result = generer_planning_excel(date_str)
        
        if not success:
            return jsonify({'error': result}), 404
        
        # Extract filename from result message
        if "Planning généré:" in result:
            # Extract filename from message like "Planning généré: filename.xlsx (2/3 cours assignés)"
            file_path = result.split("Planning généré: ")[1].split(" (")[0]
        else:
            return jsonify({'error': 'Erreur lors de l\'extraction du nom de fichier'}), 500
        
        # Read the generated file and return it
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except FileNotFoundError:
            return jsonify({'error': f'Fichier généré non trouvé: {file_path}'}), 500
        
        # Create response
        response = make_response(file_content)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        # Create filename based on date
        from datetime import datetime
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day_names = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
            day_name = day_names[date_obj.weekday()]
            formatted_date = date_obj.strftime('%d-%m-%Y')
            filename = f"planning{day_name.upper()}_{formatted_date}.xlsx"
        except:
            filename = f"planning_{date_str}.xlsx"
        
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        # Clean up the temporary file
        import os
        try:
            os.remove(file_path)
        except:
            pass
        
        return response
        
    except Exception as e:
        logging.error(f"Erreur génération planning: {e}")
        return jsonify({'error': f'Erreur lors de la génération: {str(e)}'}), 500

@app.route('/')
def index():
    """Home page with material request form"""
    teachers = get_all_teachers()
    return render_template('index.html', teachers=teachers)


@app.route('/calendar')
def calendar():
    """Calendar view of material requests"""
    teachers = get_all_teachers()
    return render_template('calendar.html', teachers=teachers)

@app.route('/api/teachers', methods=['GET'])
def api_get_teachers():
    """API endpoint to get all teachers"""
    teachers = get_all_teachers()
    teachers_list = []
    for teacher in teachers:
        teachers_list.append({
            'id': teacher['id'],
            'name': teacher['name']
        })
    return jsonify(teachers_list)

@app.route('/api/requests', methods=['GET'])
def api_get_requests():
    """API endpoint to get material requests"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    teacher_id = request.args.get('teacher_id')
    
    requests = get_material_requests(start_date, end_date, teacher_id)
    # Compatibilité PostgreSQL/SQLite : transformer en liste de dicts
    requests_list = []
    for req in requests:
        if isinstance(req, dict):
            r = req
        elif hasattr(req, '_fields'):  # namedtuple (rare)
            r = req._asdict()
        else:
            # sqlite3.Row peut être converti en dict avec dict()
            try:
                r = dict(req)
                # Ajouter teacher_name si manquant (dernière colonne)
                if 'teacher_name' not in r and len(req.keys()) > 0:
                    r['teacher_name'] = req[list(req.keys())[-1]]
                print(f"🔍 SQLite Row converti: id={r.get('id')}, group_count={r.get('group_count')}, quantity={r.get('quantity')}")
                requests_list.append(r)
                continue
            except (TypeError, AttributeError):
                pass
            # tuple (PostgreSQL sans row_factory)
            # Ordre des colonnes : voir la requête SELECT
            r = {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': req[12] if len(req) > 12 else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[-1]  # la dernière colonne de la requête SELECT
            }
            # Debug log
            if req[12] != 1:
                print(f"🔍 Backend: Request #{req[0]} has group_count={req[12]} (type={type(req[12])})")
        requests_list.append(r)
    return jsonify(requests_list)

@app.route('/api/calendar-events', methods=['GET'])
def api_calendar_events():
    """API endpoint to get calendar events with optional filters"""
    teacher_id = request.args.get('teacher_id')
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')
    
    # Get all requests with optional teacher filter
    requests = get_material_requests(teacher_id=teacher_id)

    # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
    def to_dict(req):
        if isinstance(req, dict):
            return req
        elif hasattr(req, '_fields'):
            return req._asdict()
        else:
            return {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': req[12] if len(req) > 12 else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[-1]
            }

    requests = [to_dict(req) for req in requests]

    # Filter by status if needed
    if status_filter:
        filtered_requests = []
        for req in requests:
            prepared = req.get('prepared', False)
            modified = req.get('modified', False)
            if status_filter == 'prepared' and prepared:
                filtered_requests.append(req)
            elif status_filter == 'not-prepared' and not prepared:
                filtered_requests.append(req)
            elif status_filter == 'modified' and modified:
                filtered_requests.append(req)
        requests = filtered_requests

    # Filter by type if needed
    if type_filter:
        filtered_requests = []
        for req in requests:
            selected_materials = req.get('selected_materials', '')
            material_description = req.get('material_description', '')
            if type_filter == 'absent' and selected_materials == 'Absent':
                filtered_requests.append(req)
            elif type_filter == 'no-material' and selected_materials == 'Pas besoin de matériel':
                filtered_requests.append(req)
            elif type_filter == 'normal' and selected_materials not in ['Absent', 'Pas besoin de matériel']:
                filtered_requests.append(req)
        requests = filtered_requests

    events = []
    for req in requests:
        # Choose color based on status and type
        bg_color = '#007bff'  # Default blue

        if req['selected_materials'] == 'Absent':
            bg_color = '#dc3545'  # Red for absent
        elif req['selected_materials'] == 'Pas besoin de matériel':
            bg_color = '#6f42c1'  # Purple for no material
        elif req['prepared']:
            bg_color = '#28a745'  # Green for prepared
        elif req['modified']:
            bg_color = '#ffc107'  # Yellow for modified

        events.append({
            'id': req['id'],
            'title': f"{req['teacher_name']} - {req['class_name']}",
            'start': req['request_date'],
            'description': f"Matériel: {req['material_description']} (Quantité: {req['quantity'] if req['quantity'] else 1})",
            'backgroundColor': bg_color,
            'borderColor': bg_color,
            'textColor': '#ffffff'
        })

    return jsonify(events)

@app.route('/api/requests', methods=['POST'])
def api_add_request():
    """API endpoint to add a new material request"""
    try:
        data = request.get_json()
        
        # Validation des champs principaux
        required_fields = ['teacher_id', 'class_name', 'material_description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Le champ {field} est requis'}), 400
        if not data.get('days_horaires') or not isinstance(data['days_horaires'], list) or len(data['days_horaires']) == 0:
            return jsonify({'error': 'Veuillez ajouter au moins un jour avec des horaires.'}), 400

        # Validation du délai de 2 jours ouvrés pour chaque date
        from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
        
        for dh in data['days_horaires']:
            date = dh.get('date')
            if not date:
                return jsonify({'error': 'Date manquante pour un des jours'}), 400
                
            # Vérifier le délai de 2 jours ouvrés
            validation = is_request_deadline_respected(date)
            if not validation['valid']:
                earliest_date = get_earliest_valid_date()
                return jsonify({
                    'error': f'Délai insuffisant pour le {date}. {validation["message"]} Première date disponible: {earliest_date}'
                }), 400

        # Ajout de chaque demande (jour/horaire)
        request_ids = []
        for dh in data['days_horaires']:
            date = dh.get('date')
            horaires = dh.get('horaires', [])
            for horaire in horaires:
                request_id = add_material_request(
                    teacher_id=data['teacher_id'],
                    request_date=date,
                    horaire=horaire,
                    class_name=data['class_name'],
                    material_description=data['material_description'],
                    quantity=data.get('quantity', 1),
                    selected_materials=data.get('selected_materials', ''),
                    computers_needed=data.get('computers_needed', 0),
                    notes=data.get('notes', ''),
                    group_count=data.get('group_count', data.get('quantity', 1)),
                    request_name=data.get('request_name', ''),
                    image_url=data.get('image_url', '')
                )
                request_ids.append(request_id)

        return jsonify({'success': True, 'request_ids': request_ids}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/csv')
def export_csv():
    """Export material requests to CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    teacher_id = request.args.get('teacher_id')
    
    requests = get_material_requests(start_date, end_date, teacher_id)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Enseignant', 'Date demande', 'Horaire', 'Niveau',
        'Matériel sélectionné', 'Ordinateurs', 'Description matériel',
        'Nombre de groupes', 'Type de salle', 'Notes', 'Date création'
    ])
    
    # Write data
    for req in requests:
        # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
        if isinstance(req, dict):
            r = req
        elif hasattr(req, '_fields'):
            r = req._asdict()
        else:
            r = {
                'id': req[0],
                'teacher_id': req[1],
                'request_date': req[2],
                'horaire': req[3],
                'class_name': req[4],
                'material_description': req[5],
                'quantity': req[6],
                'selected_materials': req[7] if req[7] else '',
                'computers_needed': req[8] if req[8] else 0,
                'notes': req[9],
                'prepared': req[10] if req[10] else False,
                'modified': req[11] if req[11] else False,
                'group_count': req[12] if len(req) > 12 else 1,
                'material_prof': req[13] if len(req) > 13 else '',
                'request_name': req[14] if len(req) > 14 else '',
                'room_type': req[15] if len(req) > 15 and req[15] else 'Mixte',
                'image_url': req[16] if len(req) > 16 else None,
                'exam': req[17] if len(req) > 17 else False,
                'created_at': req[18] if len(req) > 18 else None,
                'teacher_name': req[-1]  # la dernière colonne de la requête SELECT
            }
        writer.writerow([
            r['id'],
            r['teacher_name'],
            r['request_date'],
            r['horaire'] if r['horaire'] else '',
            r['class_name'],
            r['selected_materials'] if r['selected_materials'] else '',
            r['computers_needed'] if r['computers_needed'] else 0,
            r['material_description'],
            r['quantity'],
            r['room_type'] if r['room_type'] else 'Mixte',
            r['notes'] if r['notes'] else '',
            r['created_at']
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=demandes_materiel_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route('/requests')
def view_requests():
    """View all material requests in a table"""
    teachers = get_all_teachers()
    return render_template('requests.html', teachers=teachers)

@app.route('/api/requests/<int:request_id>', methods=['GET'])
def api_get_request_by_id(request_id):
    """API endpoint to get a specific material request by ID"""
    request_data = get_material_request_by_id(request_id)
    if not request_data:
        return jsonify({'error': 'Demande non trouvée'}), 404

    # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
    if isinstance(request_data, dict):
        r = request_data
    elif hasattr(request_data, '_fields'):
        r = request_data._asdict()
    else:
        # tuple (ordre des colonnes comme dans SELECT)
        r = {
            'id': request_data[0],
            'teacher_id': request_data[1],
            'request_date': request_data[2],
            'horaire': request_data[3],
            'class_name': request_data[4],
            'material_description': request_data[5],
            'quantity': request_data[6],
            'selected_materials': request_data[7] if request_data[7] else '',
            'computers_needed': request_data[8] if request_data[8] else 0,
            'notes': request_data[9],
            'prepared': request_data[10] if request_data[10] else False,
            'modified': request_data[11] if request_data[11] else False,
            'group_count': request_data[12] if len(request_data) > 12 else 1,
            'material_prof': request_data[13] if len(request_data) > 13 else '',
            'request_name': request_data[14] if len(request_data) > 14 else '',
            'room_type': request_data[15] if len(request_data) > 15 and request_data[15] else 'Mixte',
            'image_url': request_data[16] if len(request_data) > 16 else None,
            'exam': request_data[17] if len(request_data) > 17 else False,
            'created_at': request_data[18] if len(request_data) > 18 else None,
            'teacher_name': request_data[-1]  # dernière colonne
        }

    # Calcul du délai (jours ouvrés)
    from deadline_utils import is_request_deadline_respected
    deadline_info = is_request_deadline_respected(r['request_date'])
    r['deadline'] = deadline_info
    return jsonify(r)

@app.route('/api/requests/<int:request_id>', methods=['PUT'])
def api_update_request(request_id):
    """API endpoint to update a material request"""
    try:
        data = request.get_json()
        
        # Validation des champs principaux
        required_fields = ['teacher_id', 'class_name', 'material_description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Le champ {field} est requis'}), 400
        
        # Validation du délai de 2 jours ouvrés pour toute modification
        current_request = get_material_request_by_id(request_id)
        if current_request:
            current_date = current_request['request_date']
            
            from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
            validation = is_request_deadline_respected(current_date)
            if not validation['valid']:
                earliest_date = get_earliest_valid_date()
                return jsonify({
                    'error': f'Modification interdite - délai insuffisant. {validation["message"]} Première date modifiable: {earliest_date}'
                }), 400
        
        # Si la date est modifiée, valider aussi la nouvelle date
        if 'request_date' in data:
            new_date = data['request_date']
            from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
            validation = is_request_deadline_respected(new_date)
            if not validation['valid']:
                earliest_date = get_earliest_valid_date()
                return jsonify({
                    'error': f'Nouvelle date invalide - délai insuffisant. {validation["message"]} Première date disponible: {earliest_date}'
                }), 400
        
        success = update_material_request(
            request_id,
            data['teacher_id'],
            data['request_date'],
            data['class_name'],
            data['material_description'],
            data.get('horaire'),
            data.get('quantity', 1),
            data.get('selected_materials', ''),
            data.get('computers_needed', 0),
            data.get('notes', ''),
            group_count=data.get('group_count', 1),
            material_prof=data.get('material_prof', ''),
            request_name=data.get('request_name', '')
        )
        
        if success:
            return jsonify({'message': 'Demande mise à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/requests/<int:request_id>/toggle-prepared', methods=['POST'])
def api_toggle_prepared(request_id):
    """API endpoint to toggle prepared status of a request"""
    try:
        success = toggle_prepared_status(request_id)
        if success:
            return jsonify({'message': 'Statut mis à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/requests/<int:request_id>', methods=['DELETE'])
def api_delete_request(request_id):
    """API endpoint to delete a material request"""
    try:
        success = delete_material_request(request_id)
        if success:
            return jsonify({'message': 'Demande supprimée avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/requests/<int:request_id>/room-type', methods=['PUT'])
def api_update_room_type(request_id):
    """API endpoint to update room type of a material request"""
    try:
        data = request.get_json()
        room_type = data.get('room_type')
        
        if room_type not in ['Physique', 'Chimie', 'Mixte']:
            return jsonify({'error': 'Type de salle invalide'}), 400
        
        success = update_room_type(request_id, room_type)
        if success:
            return jsonify({'message': 'Type de salle mis à jour avec succès'})
        else:
            return jsonify({'error': 'Demande non trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin():
    """Admin dashboard page"""
    return render_template('admin.html')

@app.route('/admin/rooms')
def view_rooms():
    """Room management page"""
    return render_template('rooms.html')

@app.route('/admin/students')
def view_students():
    """Student management page"""
    return render_template('students.html')

@app.route('/admin/working-days')
def view_working_days():
    """Working days configuration page"""
    return render_template('working_days.html')

@app.route('/admin/c21-availability')
def view_c21_availability():
    """C21 availability management page"""
    return render_template('c21_availability.html')

@app.route('/admin/planning-editor')
def planning_editor():
    """Page d'édition interactive du planning"""
    return render_template('planning_editor.html')

@app.route('/api/pending-modifications', methods=['GET', 'POST'])
def api_pending_modifications():
    """API endpoint to get all pending modifications or add a new one"""
    if request.method == 'GET':
        try:
            request_id = request.args.get('request_id')
            
            if request_id:
                modifications = get_pending_modifications(int(request_id))
            else:
                modifications = get_pending_modifications()
            
            # Fonction helper pour normaliser les résultats (dict ou tuple)
            def to_dict(mod):
                if isinstance(mod, dict):
                    return mod
                elif hasattr(mod, '_asdict'):
                    # NamedTuple
                    return mod._asdict()
                else:
                    # Tuple classique - ordre des colonnes dans la requête SQL :
                    # pm.id, pm.request_id, pm.field_name, pm.original_value, pm.new_value,
                    # pm.created_at, pm.modified_by, mr.teacher_id, t.name as teacher_name, mr.request_name
                    return {
                        'id': mod[0],
                        'request_id': mod[1],
                        'field_name': mod[2],
                        'original_value': mod[3],
                        'new_value': mod[4],
                        'created_at': mod[5],
                        'modified_by': mod[6],
                        'teacher_id': mod[7] if len(mod) > 7 else None,
                        'teacher_name': mod[8] if len(mod) > 8 else '',
                        'request_name': mod[9] if len(mod) > 9 else ''
                    }
            
            # Convert to list of dicts for JSON serialization
            modifications_list = []
            for mod in modifications:
                mod_dict = to_dict(mod)
                modifications_list.append({
                    'id': mod_dict.get('id'),
                    'request_id': mod_dict.get('request_id'),
                    'field_name': mod_dict.get('field_name'),
                    'original_value': mod_dict.get('original_value'),
                    'new_value': mod_dict.get('new_value'),
                    'created_at': mod_dict.get('created_at'),
                    'modified_by': mod_dict.get('modified_by'),
                    'teacher_name': mod_dict.get('teacher_name', ''),
                    'request_name': mod_dict.get('request_name', '')
                })
            
            return jsonify(modifications_list)
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des modifications: {str(e)}")
            return jsonify({'error': f'Erreur serveur: {str(e)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Validation des champs requis
            required_fields = ['request_id', 'field_name', 'original_value', 'new_value']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Champ manquant: {field}'}), 400
            
            # Validation du délai de 2 jours ouvrés si la modification concerne la date
            if data['field_name'] == 'request_date' or data.get('field_name') == 'request_date':
                # Récupérer la demande actuelle pour vérifier la date
                current_request = get_material_request_by_id(data['request_id'])
                if current_request:
                    # Utiliser la date actuelle de la demande pour la validation
                    current_date = current_request['request_date']
                    
                    from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
                    validation = is_request_deadline_respected(current_date)
                    if not validation['valid']:
                        earliest_date = get_earliest_valid_date()
                        return jsonify({
                            'error': f'Modification interdite - délai insuffisant. {validation["message"]} Première date modifiable: {earliest_date}'
                        }), 400
            
            # Si la modification concerne une nouvelle date, valider aussi cette nouvelle date
            if data['field_name'] == 'request_date':
                new_date = data['new_value']
                from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
                validation = is_request_deadline_respected(new_date)
                if not validation['valid']:
                    earliest_date = get_earliest_valid_date()
                    return jsonify({
                        'error': f'Nouvelle date invalide - délai insuffisant. {validation["message"]} Première date disponible: {earliest_date}'
                    }), 400
            
            success = add_pending_modification(
                data['request_id'],
                data['field_name'],
                data['original_value'],
                data['new_value'],
                data.get('modified_by', 'User')
            )
            
            if success:
                return jsonify({'message': 'Modification en attente ajoutée avec succès'})
            else:
                return jsonify({'error': 'Erreur lors de l\'ajout de la modification'}), 500
                
        except Exception as e:
            return jsonify({'error': f'Erreur lors de l\'ajout: {str(e)}'}), 500

@app.route('/api/requests-with-pending-modifications', methods=['GET'])
def api_get_requests_with_pending_modifications():
    """API endpoint to get all request IDs that have pending modifications"""
    request_ids = get_requests_with_pending_modifications()
    return jsonify(request_ids)

@app.route('/api/pending-modifications/<int:request_id>/validate', methods=['POST'])
def api_validate_pending_modifications(request_id):
    """API endpoint to validate and apply pending modifications for a request"""
    try:
        # Validation du délai de 2 jours ouvrés avant d'appliquer les modifications
        current_request = get_material_request_by_id(request_id)
        if current_request:
            current_date = current_request['request_date']
            
            from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
            validation = is_request_deadline_respected(current_date)
            if not validation['valid']:
                earliest_date = get_earliest_valid_date()
                return jsonify({
                    'error': f'Validation interdite - délai insuffisant pour la demande du {current_date}. {validation["message"]} Première date modifiable: {earliest_date}'
                }), 400
        
        success = validate_pending_modifications(request_id)
        if success:
            return jsonify({'message': 'Modifications validées avec succès'})
        else:
            return jsonify({'error': 'Aucune modification en attente trouvée'}), 404
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la validation: {str(e)}'}), 500

@app.route('/api/pending-modifications/<int:request_id>/reject', methods=['POST'])
def api_reject_pending_modifications(request_id):
    """API endpoint to reject and remove pending modifications for a request"""
    try:
        success = reject_pending_modifications(request_id)
        if success:
            return jsonify({'message': 'Modifications rejetées avec succès'})
        else:
            return jsonify({'error': 'Aucune modification en attente trouvée'}), 404
    except Exception as e:
        return jsonify({'error': f'Erreur lors du rejet: {str(e)}'}), 500

# API endpoints pour les images Google Drive
@app.route('/api/validate-google-drive-image', methods=['POST'])
def api_validate_google_drive_image():
    """API endpoint to validate a Google Drive image URL/ID"""
    try:
        data = request.get_json()
        url_or_id = data.get('url_or_id', '').strip()
        
        if not url_or_id:
            return jsonify({'error': 'URL ou ID Google Drive manquant'}), 400
        
        # Extraire l'ID depuis l'URL ou valider l'ID
        drive_id = extract_google_drive_id(url_or_id)
        if not drive_id:
            return jsonify({'error': 'URL ou ID Google Drive invalide'}), 400
        
        # Valider que l'image est accessible
        is_valid, error_message, image_url = validate_google_drive_image(drive_id)
        
        if not is_valid:
            return jsonify({'error': error_message}), 400
        
        # Récupérer les informations de l'image
        image_info = get_image_info(drive_id)
        
        return jsonify({
            'valid': True,
            'drive_id': drive_id,
            'image_url': image_url,
            'image_info': image_info
        })
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la validation: {str(e)}'}), 500

@app.route('/api/image-info/<drive_id>', methods=['GET'])
def api_get_image_info(drive_id):
    """API endpoint to get information about a Google Drive image"""
    try:
        image_info = get_image_info(drive_id)
        if not image_info:
            return jsonify({'error': 'Image non trouvée ou inaccessible'}), 404
        
        return jsonify(image_info)
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la récupération: {str(e)}'}), 500

@app.route('/api/upload-image', methods=['POST'])
def api_upload_image():
    """API endpoint to upload images directly to Google Drive"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'Aucune image fournie'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400
        
        # Vérifier le type de fichier
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Format de fichier non supporté'}), 400
        
        # Tentative d'upload vers Google Drive
        try:
            from google_drive_service import get_google_drive_service, upload_image_to_google_drive
            
            print("Tentative d'upload vers Google Drive...")
            
            # Obtenir le service Google Drive
            service = get_google_drive_service()
            if service is None:
                raise Exception("Impossible d'obtenir le service Google Drive")
            
            # Conversion du fichier Flask en BytesIO
            import io
            file.stream.seek(0)
            file_bytes = io.BytesIO(file.read())
            file_bytes.seek(0)
            # Upload vers Google Drive
            result = upload_image_to_google_drive(file_bytes, file.filename)
            if result['success']:
                print(f"Image uploadée avec succès vers Google Drive: {result['file_id']}")
                return jsonify({
                    'success': True,
                    'image_url': result['public_url'],
                    'google_drive_id': result['file_id'],
                    'message': 'Image uploadée vers Google Drive avec succès!'
                })
            else:
                raise Exception(result['error'] or "Échec de l'upload vers Google Drive")
                
        except Exception as google_error:
            print(f"Erreur Google Drive: {google_error}")
            print("Fallback vers stockage local...")
            
            # Fallback vers stockage local
            import uuid, os
            from datetime import datetime
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            filename = f"demande_materiel_{timestamp}_{unique_id}.{file_ext}"
            
            # Sauvegarder l'image localement
            upload_dir = os.path.join('static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            
            # Reset du pointeur du fichier si nécessaire
            file.stream.seek(0)
            file.save(filepath)
            
            # URL locale
            local_url = f"/static/uploads/{filename}"
            
            return jsonify({
                'success': True,
                'image_url': local_url,
                'local_storage': True,
                'fallback': True,
                'message': f'Fallback local - Google Drive indisponible: {str(google_error)}'
            })
        
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'upload: {str(e)}'}), 500

@app.route('/api/c21-availability', methods=['GET', 'POST'])
def api_c21_availability():
    """API pour gérer les créneaux de disponibilité C21"""
    if request.method == 'GET':
        slots = get_c21_availability()
        return jsonify(slots)
    elif request.method == 'POST':
        data = request.get_json()
        jour = data.get('jour')
        heure_debut = data.get('heure_debut')
        heure_fin = data.get('heure_fin')
        if not jour or not heure_debut or not heure_fin:
            return jsonify({'error': 'Champs manquants'}), 400
        success = add_c21_availability(jour, heure_debut, heure_fin)
        if success:
            return jsonify({'success': True}), 201
        else:
            return jsonify({'error': 'Erreur lors de l\'ajout'}), 500

@app.route('/api/c21-availability/<int:availability_id>', methods=['DELETE'])
def api_delete_c21_availability(availability_id):
    """API pour supprimer un créneau de disponibilité C21"""
    try:
        success = delete_c21_availability(availability_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Créneau non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API Routes pour la gestion des salles
@app.route('/api/rooms', methods=['GET'])
def api_get_rooms():
    """API endpoint to get all rooms"""
    try:
        rooms = get_all_rooms()
        return jsonify(rooms)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
def api_update_room(room_id):
    """API endpoint to update a room"""
    try:
        data = request.get_json()
        success = update_room(room_id, data)
        if success:
            return jsonify({'message': 'Salle mise à jour avec succès'})
        else:
            return jsonify({'error': 'Salle non trouvée'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/import-csv', methods=['POST'])
def api_import_rooms_csv():
    """API endpoint to import rooms from CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'Le fichier doit être au format CSV'}), 400
        
        # Lire le contenu du fichier
        csv_content = file.read().decode('utf-8')
        
        # Importer les salles
        success, message = import_rooms_from_csv_content(csv_content)
        
        if success:
            return jsonify({'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'import: {str(e)}'}), 500

@app.route('/api/rooms/export-csv', methods=['GET'])
def api_export_rooms_csv():
    """API endpoint to export rooms as CSV"""
    try:
        rooms = get_all_rooms()
        
        # Créer le CSV en mémoire
        output = io.StringIO()
        writer = csv.writer(output)
        
        # En-tête
        writer.writerow([
            'nom', 'type', 'ordinateurs', 'chaises', 'eviers', 'hotte',
            'bancs_optiques', 'oscilloscopes', 'becs_electriques',
            'support_filtration', 'imprimante', 'examen'
        ])
        
        # Données
        for room in rooms:
            # Compatibilité PostgreSQL/SQLite : transformer en dict si besoin
            if isinstance(room, dict):
                r = room
            elif hasattr(room, '_fields'):
                r = room._asdict()
            else:
                r = {
                    'name': room[0],
                    'type': room[1],
                    'ordinateurs': room[2],
                    'chaises': room[3],
                    'eviers': room[4],
                    'hotte': room[5],
                    'bancs_optiques': room[6],
                    'oscilloscopes': room[7],
                    'becs_electriques': room[8],
                    'support_filtration': room[9],
                    'imprimante': room[10],
                    'examen': room[11]
                }
            writer.writerow([
                r['name'], r['type'], r['ordinateurs'], r['chaises'],
                r['eviers'], r['hotte'], r['bancs_optiques'], r['oscilloscopes'],
                r['becs_electriques'], r['support_filtration'], r['imprimante'], r['examen']
            ])
        
        # Préparer la réponse
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=salles.csv'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API Routes pour la gestion des effectifs d'étudiants
@app.route('/api/students', methods=['GET'])
def api_get_students():
    """API endpoint to get all student numbers"""
    try:
        students = get_all_student_numbers()
        return jsonify(students)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def api_add_student():
    """API endpoint to add a new student number entry"""
    try:
        data = request.get_json()
        teacher_name = data.get('teacher_name')
        student_count = data.get('student_count')
        level = data.get('level', '2nde')
        
        if not teacher_name or not student_count:
            return jsonify({'error': 'Nom de l\'enseignant et nombre d\'élèves requis'}), 400
        
        success = add_student_number(teacher_name, student_count, level)
        if success:
            return jsonify({'message': 'Effectif ajouté avec succès'}), 201
        else:
            return jsonify({'error': 'Erreur lors de l\'ajout'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:student_id>', methods=['PUT'])
def api_update_student(student_id):
    """API endpoint to update a student number entry"""
    try:
        data = request.get_json()
        success = update_student_number(student_id, data)
        if success:
            return jsonify({'message': 'Effectif mis à jour avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    """API endpoint to delete a student number entry"""
    try:
        success = delete_student_number(student_id)
        if success:
            return jsonify({'message': 'Effectif supprimé avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Routes API pour l'éditeur de planning
@app.route('/api/planning-editor/data', methods=['GET'])
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
            
            # Corriger l'ordre des salles pour correspondre au fichier Excel
            if 'rooms' in planning_data and planning_data['rooms']:
                # Ordre correct du fichier Excel
                correct_order = ['C23', 'C25', 'C27', 'C22', 'C24', 'C32', 'C33', 'C31', 'C21']
                
                # Réorganiser les salles selon l'ordre correct
                rooms_dict = {room['name']: room for room in planning_data['rooms']}
                planning_data['rooms'] = [rooms_dict[name] for name in correct_order if name in rooms_dict]
            
            # Forcer l'utilisation de tous les créneaux horaires
            full_time_slots = ['9h00', '9h30', '10h00', '10h45', '11h15', '11h45', '12h15', '12h45', 
                              '13h15', '13h45', '14h15', '14h45', '15h15', '15h45', '16h15', '16h45', 
                              '17h15', '17h45', '18h15']
            planning_data['time_slots'] = full_time_slots
            
            print(f"🔍 API: OR-Tools terminé - {len(planning_data.get('courses', []))} cours, {len(planning_data.get('rooms', []))} salles")
            return jsonify(planning_data)
            
        except Exception as e:
            print(f"❌ Erreur OR-Tools: {e}")
            # En cas d'erreur, retourner une structure vide
            return jsonify({
                'courses': [],
                'rooms': [{'name': name} for name in ['C23', 'C25', 'C27', 'C22', 'C24', 'C32', 'C33', 'C31', 'C21']],
                'time_slots': ['9h00', '9h30', '10h00', '10h45', '11h15', '11h45', '12h15', '12h45', '13h15', '13h45', '14h15', '14h45', '15h15', '15h45', '16h15', '16h45', '17h15', '17h45', '18h15'],
                'room_assignments': {},
                'days': [target_date],
                'error': str(e)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/planning-editor/generate', methods=['POST'])
def api_generate_planning_from_editor():
    """API endpoint pour générer le planning Excel avec les assignations personnalisées"""
    try:
        data = request.get_json()
        assignments = data.get('assignments', {})
        target_date = data.get('date')
        room_assignments = data.get('room_assignments', {})
        
        if not target_date:
            return jsonify({'error': 'La date est requise'}), 400
        
        print(f"🔍 Génération Excel avec room_assignments: {room_assignments}")
        
        # Utiliser exactement la même logique que /api/generate-planning mais avec assignations custom
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
            day_names = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-planning', methods=['POST'])
def save_planning():
    """API endpoint to save planning data into the database"""
    try:
        data = request.get_json()
        app.logger.info(f"Données reçues pour enregistrement: {data}")

        if not data or 'date' not in data or 'data' not in data:
            app.logger.error("Requête invalide: date ou données manquantes")
            return jsonify({'error': 'Requête invalide: date ou données manquantes'}), 400

        date = data['date']
        planning_data = data['data']

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

        app.logger.info(f"Planning enregistré avec succès pour la date: {date}")
        return jsonify({'message': 'Planning enregistré avec succès'}), 200

    except Exception as e:
        app.logger.error(f"Erreur lors de l'enregistrement du planning: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-planning', methods=['GET'])
def get_planning():
    """API endpoint to retrieve planning data from the database"""
    try:
        date = request.args.get('date')
        app.logger.info(f"Requête reçue pour récupérer le planning de la date: {date}")

        if not date:
            app.logger.error("La date est manquante dans la requête.")
            return jsonify({'error': 'La date est requise'}), 400

        # Connexion à la base de données
        conn, db_type = get_db_connection()  # Extraire uniquement la connexion SQLite ou PostgreSQL
        cursor = conn.cursor()

        # Récupérer les données du planning
        placeholder = '%s' if db_type == 'postgresql' else '?'
        cursor.execute(f"SELECT data FROM plannings WHERE date = {placeholder}", (date,))
        row = cursor.fetchone()
        conn.close()

        if row:
            app.logger.info(f"Planning trouvé pour la date {date}: {row[0]}")
            return jsonify({'planning': row[0]}), 200
        else:
            app.logger.warning(f"Aucun planning trouvé pour la date {date}.")
            return jsonify({'error': 'Aucun planning trouvé pour cette date'}), 404

    except Exception as e:
        app.logger.error(f"Erreur lors de la récupération du planning: {e}")
        return jsonify({'error': str(e)}), 500

        
if __name__ == '__main__':
    import os
    import sys
    
    # Supprimer tous les messages d'erreur d'encodage UTF-8
    class SilentUnicodeFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Filtrer les erreurs d'encodage UTF-8 spécifiques
            if ("'utf-8' codec can't decode" in message or 
                "Erreur d'encodage URL" in message or
                "UnicodeDecodeError" in message or
                "invalid continuation byte" in message):
                return False
            return True
    
    # Appliquer le filtre à tous les loggers
    for logger_name in ['werkzeug', 'app', '']:
        logger = logging.getLogger(logger_name)
        logger.addFilter(SilentUnicodeFilter())
    
    # Configuration complète pour éviter les erreurs d'encodage
    if hasattr(sys, '_getframe'):
        # Rediriger stderr pour capturer les erreurs d'encodage non loggées
        class SafeStderr:
            def write(self, data):
                try:
                    if isinstance(data, bytes):
                        data = data.decode('utf-8', errors='ignore')
                    if not ("'utf-8' codec can't decode" in str(data) or 
                           "Erreur d'encodage URL" in str(data)):
                        sys.__stderr__.write(data)
                except:
                    pass
            def flush(self):
                try:
                    sys.__stderr__.flush()
                except:
                    pass
        
        # sys.stderr = SafeStderr()
    
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f" * Application démarrée sur http://127.0.0.1:{port}")
    print(" * Gestion des erreurs UTF-8 activée")
    app.run(debug=True, host='0.0.0.0', port=port)