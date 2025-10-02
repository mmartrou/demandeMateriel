from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import csv
import io
import logging
from datetime import datetime, timedelta
from database import (init_database, get_all_teachers, add_material_request, get_material_requests, 
                      get_requests_for_calendar, get_material_request_by_id, update_material_request, 
                      toggle_prepared_status, delete_material_request, update_room_type)

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
    
    # Convert to list of dictionaries for JSON serialization
    requests_list = []
    for req in requests:
        requests_list.append({
            'id': req['id'],
            'teacher_id': req['teacher_id'],
            'teacher_name': req['teacher_name'],
            'request_date': req['request_date'],
            'horaire': req['horaire'],
            'class_name': req['class_name'],
            'material_description': req['material_description'],
            'quantity': req['quantity'],
            'selected_materials': req['selected_materials'] if req['selected_materials'] else '',
            'computers_needed': req['computers_needed'] if req['computers_needed'] else 0,
            'notes': req['notes'],
            'prepared': req['prepared'] if req['prepared'] else False,
            'modified': req['modified'] if req['modified'] else False,
            'room_type': req['room_type'] if req['room_type'] else 'Mixte',
            'request_name': req['request_name'] if req['request_name'] else '',
            'created_at': req['created_at']
        })
    
    return jsonify(requests_list)

@app.route('/api/calendar-events', methods=['GET'])
def api_calendar_events():
    """API endpoint to get calendar events with optional filters"""
    teacher_id = request.args.get('teacher_id')
    status_filter = request.args.get('status')
    type_filter = request.args.get('type')
    
    # Get all requests with optional teacher filter
    requests = get_material_requests(teacher_id=teacher_id)
    
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
                    request_name=data.get('request_name', '')
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
        writer.writerow([
            req['id'],
            req['teacher_name'],
            req['request_date'],
            req['horaire'] if req['horaire'] else '',
            req['class_name'],
            req['selected_materials'] if req['selected_materials'] else '',
            req['computers_needed'] if req['computers_needed'] else 0,
            req['material_description'],
            req['quantity'],
            req['room_type'] if req['room_type'] else 'Mixte',
            req['notes'] if req['notes'] else '',
            req['created_at']
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
    
    # Convert to dictionary for JSON serialization
    request_dict = {
        'id': request_data['id'],
        'teacher_id': request_data['teacher_id'],
        'teacher_name': request_data['teacher_name'],
        'request_date': request_data['request_date'],
        'horaire': request_data['horaire'],
        'class_name': request_data['class_name'],
        'material_description': request_data['material_description'],
        'quantity': request_data['quantity'],
        'selected_materials': request_data['selected_materials'] if request_data['selected_materials'] else '',
        'computers_needed': request_data['computers_needed'] if request_data['computers_needed'] else 0,
        'notes': request_data['notes'],
        'prepared': request_data['prepared'] if request_data['prepared'] else False,
        'modified': request_data['modified'] if request_data['modified'] else False,
        'room_type': request_data['room_type'] if request_data['room_type'] else 'Mixte',
        'request_name': request_data['request_name'] if request_data['request_name'] else '',
        'created_at': request_data['created_at']
    }
    
    return jsonify(request_dict)

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
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f" * Application démarrée sur http://127.0.0.1:{port}")
    print(" * Gestion des erreurs UTF-8 activée")
    app.run(debug=debug, host='0.0.0.0', port=port)