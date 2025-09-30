from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response, send_file
import csv
import io
import os
import logging
from datetime import datetime, timedelta
from database import (init_database, get_all_teachers, add_material_request, get_material_requests, 
                      get_requests_for_calendar, get_material_request_by_id, update_material_request, 
                      toggle_prepared_status, delete_material_request, update_room_type, 
                      get_all_rooms, get_planning_data, update_room, import_rooms_from_csv_content,
                      get_all_student_numbers, update_student_number, add_student_number, 
                      delete_student_number, get_student_count_for_teacher)

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialisation de la base de données au démarrage
try:
    logger.info("Initialisation de la base de données...")
    init_database()
    logger.info("Base de données initialisée avec succès")
except Exception as e:
    logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
    # Ne pas arrêter l'application, continuer avec SQLite en fallback


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
            'exam': req['exam'] if req['exam'] else False,
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
            prepared = req['prepared'] if req['prepared'] else False
            modified = req['modified'] if req['modified'] else False
            
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
            selected_materials = req['selected_materials'] if req['selected_materials'] else ''
            material_description = req['material_description'] if req['material_description'] else ''
            
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
        
        selected_materials = req['selected_materials'] if req['selected_materials'] else 'None'
        prepared = req['prepared'] if req['prepared'] else False
        modified = req['modified'] if req['modified'] else False
        
        if selected_materials == 'Absent':
            bg_color = '#dc3545'  # Red for absent
        elif selected_materials == 'Pas besoin de matériel':
            bg_color = '#20c997'  # Light green for no material
        elif selected_materials == 'Examen':
            bg_color = '#6f42c1'  # Purple for exam
        elif prepared:
            bg_color = '#28a745'  # Green for prepared
        elif modified:
            bg_color = '#ffc107'  # Yellow for modified
        
        events.append({
            'id': req['id'],
            'title': f"{req['teacher_name']} - {req['class_name']}",
            'start': req['request_date'],
            'description': f"Matériel: {req['material_description']} (Groupes: {req['group_count'] if req['group_count'] else 1})" + 
                          (f" - Ordinateurs: {req['computers_needed']}" if req['computers_needed'] and req['computers_needed'] > 0 else "") + 
                          (f" - Matériel Prof: {req['material_prof']}" if req['material_prof'] else ""),
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

        # Détecter le mode examen basé sur selected_materials
        is_exam = data.get('selected_materials', '') == 'Examen'
        
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
                    exam=is_exam,
                    group_count=data.get('group_count', 1),
                    material_prof=data.get('material_prof', '')
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

@app.route('/admin')
def admin():
    """Administration page"""
    return render_template('admin.html')

@app.route('/admin/rooms')
def view_rooms():
    """View and manage rooms configuration"""
    return render_template('rooms.html')

@app.route('/admin/students')
def view_students():
    """View and manage student numbers configuration"""
    return render_template('students.html')

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
        'exam': request_data['exam'] if request_data['exam'] else False,
        'group_count': request_data['group_count'] if request_data['group_count'] else 1,
        'material_prof': request_data['material_prof'] if request_data['material_prof'] else '',
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
            data.get('group_count', 1),
            data.get('material_prof', '')
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

@app.route('/api/rooms', methods=['GET'])
def api_get_rooms():
    """API endpoint to get all rooms"""
    rooms = get_all_rooms()
    rooms_list = []
    for room in rooms:
        rooms_list.append({
            'id': room['id'],
            'name': room['name'],
            'type': room['type'],
            'ordinateurs': room['ordinateurs'],
            'chaises': room['chaises'],
            'eviers': room['eviers'],
            'hotte': room['hotte'],
            'bancs_optiques': room['bancs_optiques'],
            'oscilloscopes': room['oscilloscopes'],
            'becs_electriques': room['becs_electriques'],
            'support_filtration': room['support_filtration'],
            'imprimante': room['imprimante'],
            'examen': room['examen']
        })
    return jsonify(rooms_list)

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
    """API endpoint to import rooms from CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.csv'):
            return jsonify({'error': 'Fichier CSV requis'}), 400
        
        # Read CSV content
        csv_content = file.read().decode('utf-8')
        import_rooms_from_csv_content(csv_content)
        
        return jsonify({'message': 'Salles importées avec succès depuis le CSV'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/export-csv', methods=['GET'])
def api_export_rooms_csv():
    """API endpoint to export rooms to CSV"""
    try:
        rooms = get_all_rooms()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header (matching original salles.csv format)
        writer.writerow(['# Liste des salles et leurs caractéristiques'])
        writer.writerow(['# Format CSV: nom,type,ordinateurs,chaises,eviers,hotte,bancs_optiques,oscilloscopes,becs_electriques,support_filtration,imprimante,examen'])
        
        # Write data
        for room in rooms:
            writer.writerow([
                room['name'], room['type'], room['ordinateurs'], room['chaises'],
                room['eviers'], room['hotte'], room['bancs_optiques'], room['oscilloscopes'],
                room['becs_electriques'], room['support_filtration'], room['imprimante'], room['examen']
            ])
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=salles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['GET'])
def api_get_students():
    """API endpoint to get all student numbers"""
    students = get_all_student_numbers()
    students_list = []
    for student in students:
        students_list.append({
            'id': student['id'],
            'teacher_name': student['teacher_name'],
            'student_count': student['student_count'],
            'level': student['level']
        })
    return jsonify(students_list)

@app.route('/api/students/<int:student_id>', methods=['PUT'])
def api_update_student(student_id):
    """API endpoint to update student numbers"""
    try:
        data = request.get_json()
        success = update_student_number(student_id, data)
        if success:
            return jsonify({'message': 'Effectif mis à jour avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def api_add_student():
    """API endpoint to add new student numbers"""
    try:
        data = request.get_json()
        student_id = add_student_number(
            data.get('teacher_name'),
            data.get('student_count', 20),
            data.get('level', '2nde')
        )
        if student_id:
            return jsonify({'message': 'Effectif ajouté avec succès', 'id': student_id}), 201
        else:
            return jsonify({'error': 'Erreur lors de l\'ajout'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    """API endpoint to delete student numbers"""
    try:
        success = delete_student_number(student_id)
        if success:
            return jsonify({'message': 'Effectif supprimé avec succès'})
        else:
            return jsonify({'error': 'Effectif non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-planning', methods=['POST'])
def api_generate_planning():
    """Generate Excel planning file for a specific date using OR-Tools optimization"""
    try:
        print("=== DEBUT GENERATION PLANNING ===")
        data = request.get_json()
        date_str = data.get('date')
        print(f"Date reçue: {date_str}")
        
        if not date_str:
            return jsonify({'error': 'Date requise'}), 400
        
        # Get data from database
        print("Récupération des données...")
        raw_requests = get_planning_data(date_str)
        print(f"Demandes récupérées: {len(raw_requests) if raw_requests else 0}")
        raw_rooms = get_all_rooms()
        print(f"Salles récupérées: {len(raw_rooms) if raw_rooms else 0}")
        
        if not raw_requests:
            return jsonify({'success': False, 'error': 'Aucune demande trouvée pour cette date'}), 400
        
        if not raw_rooms:
            return jsonify({'success': False, 'error': 'Aucune salle trouvée dans la base de données'}), 400
        
        # Generate filename based on date
        from datetime import datetime
        import tempfile
        import io
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        day_name = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][date_obj.weekday()]
        download_filename = f"planning{day_name.upper()}_{date_obj.strftime('%d-%m-%Y')}.xlsx"
        
        # Import OR-Tools for optimization
        print("Importation des modules...")
        from ortools.sat.python import cp_model
        print("OR-Tools importé avec succès")
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, PatternFill, Border, Side
        print("openpyxl importé avec succès")
        
        # Utility function AVANT son utilisation
        def h_to_min(hstr):
            if not hstr:
                return 540  # 9h00 by default
            if 'h' in hstr:
                h, m = hstr.split('h')
                return int(h) * 60 + int(m if m else 0)
            return 540

        # Chargement des disponibilités de C21
        disponibilite_C21 = {}
        try:
            import csv
            disponibilite_path = os.path.join(os.path.dirname(__file__), "disponibilite_C21.csv")
            print(f"Tentative de chargement du fichier C21: {disponibilite_path}")
            with open(disponibilite_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    jour_cle = row["jour"]
                    creneau = {
                        "debut": h_to_min(row["heure_debut"]),
                        "fin": h_to_min(row["heure_fin"])
                    }
                    
                    if jour_cle not in disponibilite_C21:
                        disponibilite_C21[jour_cle] = []
                    
                    disponibilite_C21[jour_cle].append(creneau)
            print(f"Disponibilités C21 chargées avec succès: {disponibilite_C21}")
        except FileNotFoundError as e:
            print(f"Fichier disponibilite_C21.csv non trouvé à {disponibilite_path}: {e}")
            print("C21 sera considérée comme toujours disponible")
            disponibilite_C21 = {}
        except Exception as e:
            print(f"Erreur lors du chargement des disponibilités C21: {e}")
            disponibilite_C21 = {}
        
        def duree_par_niveau(niveau):
            # Utiliser les noms exacts de l'interface utilisateur
            if niveau in ("Terminale Spécialité", "SI", "Terminale ES", "1ère Spécialité", "AP 2nd"):
                return 110
            elif niveau in ("AP PP", "1ère ES"):
                return 55
            else:
                return 85
        
        def eleves_par_niveau(niveau, enseignant=None):
            """
            Retourne le nombre d'élèves selon le niveau et l'enseignant.
            Pour les 2nde, cherche dans la base de données le nombre spécifique par enseignant.
            Pour les autres niveaux, retourne 20 par défaut.
            """
            if niveau == "2nde" and enseignant:
                try:
                    return get_student_count_for_teacher(enseignant, niveau)
                except Exception as e:
                    print(f"Erreur lors du chargement des effectifs depuis la BDD: {e}")
                    return 20  # Fallback par défaut
            
            return 20  # Valeur par défaut pour les autres niveaux
        
        def extract_material_needs(selected_materials):
            needs = {
                "ordinateurs": 0, "eviers": 0, "hotte": 0, "bancs_optiques": 0,
                "oscilloscopes": 0, "becs_electriques": 0, "support_filtration": 0,
                "imprimante": 0, "examen": 0
            }
            
            if not selected_materials:
                return needs
            
            materials = [m.strip().lower() for m in selected_materials.split(',')]
            
            for material in materials:
                if 'ordinateur' in material or 'pc' in material:
                    needs["ordinateurs"] = 1
                elif 'evier' in material:
                    needs["eviers"] = 1
                elif 'hotte' in material:
                    needs["hotte"] = 1
                elif 'optique' in material:
                    needs["bancs_optiques"] = 1
                elif 'oscilloscope' in material:
                    needs["oscilloscopes"] = 1
                elif 'bec' in material or 'électrique' in material:
                    needs["becs_electriques"] = 1
                elif 'filtration' in material:
                    needs["support_filtration"] = 1
                elif 'imprimante' in material:
                    needs["imprimante"] = 1
            
            return needs
        
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
        
        # Réorganiser les salles selon l'ordre voulu: PHYSIQUE + CHIMIE + C21
        physique_salles = ['C23', 'C25', 'C27', 'C22', 'C24']
        chimie_salles = ['C32', 'C33', 'C31']
        c21_salle = ['C21']
        salle_list = physique_salles + chimie_salles + c21_salle
        print(f"Ordre final des salles pour OR-Tools: {salle_list}")
        
        # Convert requests to course format
        cours = []
        for i, req in enumerate(raw_requests):
            material_needs = extract_material_needs(req['selected_materials'])
            
            # Determine subject based on room_type
            matiere = "mixte"
            if req['room_type'] == 'Physique':
                matiere = "physique"
            elif req['room_type'] == 'Chimie':
                matiere = "chimie"
            
            # Add computers from database
            if req['computers_needed'] and req['computers_needed'] > 0:
                material_needs["ordinateurs"] = max(material_needs["ordinateurs"], req['computers_needed'])
            
            # Use exam field from database if available
            if req['exam']:
                material_needs["examen"] = 1
            
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
            return jsonify({'success': False, 'error': 'Aucun cours valide à planifier'}), 400
        
        # Compatibility function
        def compatible(salle_name, besoin):
            salle = salles[salle_name]
            
            if besoin["matiere"] == "chimie" and salle["type"] not in ("chimie", "mixte"):
                return False
            if besoin["matiere"] == "physique" and salle["type"] not in ("physique", "mixte"):
                return False
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
        
        # Utility functions placées avant leur utilisation
        def h_to_min_local(hstr):
            if not hstr:
                return 540  # 9h00 by default
            if 'h' in hstr:
                h, m = hstr.split('h')
                return int(h) * 60 + int(m if m else 0)
            return 540
        
        def est_C21_disponible(cours, date_obj):
            """
            Vérifie si la salle C21 est disponible pour un cours donné à une date donnée
            """
            if not disponibilite_C21:  # Si pas de contraintes chargées, toujours disponible
                print(f"ATTENTION: Pas de contraintes C21 chargées - C21 sera toujours disponible")
                return True
                
            # Déterminer le jour de la semaine (lundi = 0, dimanche = 6)
            jour_semaine = date_obj.weekday()
            jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            jour_nom = jours[jour_semaine]
            
            if jour_nom not in disponibilite_C21:
                print(f"C21 pas disponible le {jour_nom} (pas de créneaux définis)")
                return False  # C21 n'est pas disponible ce jour-là
            
            # Convertir l'heure du cours en minutes
            cours_debut = h_to_min_local(cours["horaire"])
            cours_fin = cours_debut + cours["duree"]
            
            print(f"Vérification C21 {jour_nom}: cours {cours['horaire']} ({cours_debut}-{cours_fin}min) vs créneaux {disponibilite_C21[jour_nom]}")
            
            # Vérifier si le cours s'inscrit dans une plage de disponibilité
            for creneau in disponibilite_C21[jour_nom]:
                if cours_debut >= creneau["debut"] and cours_fin <= creneau["fin"]:
                    print(f"  ✓ C21 DISPONIBLE pour {cours['horaire']} le {jour_nom}")
                    return True
            
            print(f"  ✗ C21 NON DISPONIBLE pour {cours['horaire']} le {jour_nom}")
            return False
        
        def interval_cours(c):
            start = h_to_min(c["horaire"])
            return (start, start + c["duree"])
        
        # OR-Tools model
        model = cp_model.CpModel()
        x = {}
        poids_salle = {}
        
        for i, c in enumerate(cours):
            poids_salle[i] = {}
            for s in salle_list:  # Utiliser salle_list au lieu de salles
                # Vérification de compatibilité standard + vérification spéciale pour C21
                is_compatible = compatible(s, c)
                if is_compatible and s == "C21":
                    is_compatible = est_C21_disponible(c, date_obj)
                
                if is_compatible:
                    x[(i,s)] = model.NewBoolVar(f"x_{i}_{s}")
                    
                    # Weight based on room specialization
                    if c["matiere"] == salles[s]["type"]:
                        poids_salle[i][s] = 3  # Prefer specialized rooms
                    elif salles[s]["type"] == "mixte":
                        poids_salle[i][s] = 2  # Mixed rooms second choice
                    else:
                        poids_salle[i][s] = 1  # Last resort
                else:
                    poids_salle[i][s] = 0
        
        # Constraints: each course needs exactly one room
        for i in range(len(cours)):
            compatible_rooms = [x[(i,s)] for s in salle_list if (i,s) in x]
            if compatible_rooms:
                model.Add(sum(compatible_rooms) == 1)
        
        # Constraints: no room conflicts (time overlap)
        for i in range(len(cours)):
            for j in range(i + 1, len(cours)):
                start1, end1 = interval_cours(cours[i])
                start2, end2 = interval_cours(cours[j])
                
                # Check if courses overlap
                if not (end1 <= start2 or end2 <= start1):
                    for s in salle_list:
                        if (i,s) in x and (j,s) in x:
                            model.Add(x[(i,s)] + x[(j,s)] <= 1)
        
        # ===== OPTIMISATION SALLE UNIQUE PAR ENSEIGNANT (comme dans main.py) =====
        enseignants = list(set(c["enseignant"] for c in cours))
        objectif_pref = []
        
        # Variables pour salle préférée de chaque enseignant
        SallePreferee = {}
        for enseignant in enseignants:
            SallePreferee[enseignant] = model.NewIntVar(0, len(salle_list)-1, f"SallePref_{enseignant}")
        
        # Bonus quand enseignant utilise sa salle préférée
        for enseignant in enseignants:
            cours_ens = [i for i,c in enumerate(cours) if c["enseignant"] == enseignant]
            for i in cours_ens:
                for s in salle_list:
                    if (i,s) in x:
                        same_pref = model.NewBoolVar(f"samepref_{i}_{s}")
                        model.Add(SallePreferee[enseignant] == salle_list.index(s)).OnlyEnforceIf(same_pref)
                        model.Add(SallePreferee[enseignant] != salle_list.index(s)).OnlyEnforceIf(same_pref.Not())
                        objectif_pref.append(same_pref)
        
        # Pénalité pour changement de salle pour un même enseignant
        penalite_changement = []
        for enseignant in enseignants:
            cours_ens = [i for i, c in enumerate(cours) if c["enseignant"] == enseignant]
            for idx1 in range(len(cours_ens)):
                for idx2 in range(idx1 + 1, len(cours_ens)):
                    i, j = cours_ens[idx1], cours_ens[idx2]
                    for s1 in salle_list:
                        for s2 in salle_list:
                            if s1 != s2 and (i, s1) in x and (j, s2) in x:
                                penalite = model.NewBoolVar(f"penalite_{i}_{j}_{s1}_{s2}")
                                model.AddBoolAnd([x[(i, s1)], x[(j, s2)]]).OnlyEnforceIf(penalite)
                                model.AddBoolOr([x[(i, s1)].Not(), x[(j, s2)].Not()]).OnlyEnforceIf(penalite.Not())
                                penalite_changement.append(penalite)
        
        # Objective: combiné comme dans main.py
        model.Maximize(
            sum(x[(i,s)] * poids_salle[i][s] for (i,s) in x)  # priorité salle spécialisée
            + sum(objectif_pref)                               # maximiser mêmes salles par enseignant  
            - 10*sum(penalite_changement)                     # pénaliser les changements de salle
        )
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.Solve(model)
        
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return jsonify({'success': False, 'error': 'Aucune solution trouvée pour ce planning'}), 400
        
        # Generate Excel file with enhanced formatting (from original main.py)
        wb = Workbook()
        ws = wb.active
        ws.title = "Planning_Techniciens"

        # Créneaux horaires personnalisés
        horaires_str = [
            "9h00", "9h30", "10h00", "10h45", "11h15", "11h45", "12h15", "12h45",
            "13h15", "13h45", "14h15", "14h45", "15h15", "15h45", "16h15", "16h45",
            "17h15", "17h45", "18h15"
        ]
        horaires = [h_to_min(h) for h in horaires_str]
        horaires_aff = horaires_str

        # Debug: voir les salles disponibles
        print(f"Salles disponibles: {salle_list}")
        
        # Les groupes de salles sont déjà définis plus haut
        
        print(f"Salles physique: {physique_salles}")
        print(f"Salles chimie: {chimie_salles}")
        print(f"Ordre final des salles: {salle_list}")
        
        # Définir c21_salle pour le calcul des colonnes
        c21_salle = ["C21"]
        
        # En-tête : 1ère colonne = horaire, puis salles
        ws.cell(row=1, column=1, value=day_name.capitalize())
        ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions['A'].width = 12

        from openpyxl.styles import Font, Border, Side
        bold = Font(bold=True, size=36)
        encadre = Border(left=Side(style='thick'), right=Side(style='thick'), top=Side(style='thick'), bottom=Side(style='thick'))

        # Encadrés Physique, Chimie et C21
        col_physique = [2 + salle_list.index(s) for s in physique_salles if s in salle_list]
        col_chimie = [2 + salle_list.index(s) for s in chimie_salles if s in salle_list]
        col_c21 = [2 + salle_list.index(s) for s in c21_salle if s in salle_list]
        
        print(f"Colonnes physique: {col_physique}")
        print(f"Colonnes chimie: {col_chimie}")
        print(f"Colonnes C21: {col_c21}")
        
        if col_physique and len(col_physique) > 0:
            col_physique.sort()  # S'assurer que les colonnes sont triées
            if col_physique[0] <= col_physique[-1]:  # Vérifier l'ordre
                ws.merge_cells(start_row=1, start_column=col_physique[0], end_row=1, end_column=col_physique[-1])
                for col in range(col_physique[0], col_physique[-1]+1):
                    cell_phys = ws.cell(row=1, column=col, value="Physique" if col==col_physique[0] else None)
                    cell_phys.font = Font(bold=True, size=36)
                    cell_phys.alignment = Alignment(horizontal="center", vertical="center")
                    cell_phys.border = encadre
                
        if col_chimie and len(col_chimie) > 0:
            col_chimie.sort()  # S'assurer que les colonnes sont triées
            if col_chimie[0] <= col_chimie[-1]:  # Vérifier l'ordre
                ws.merge_cells(start_row=1, start_column=col_chimie[0], end_row=1, end_column=col_chimie[-1])
                for col in range(col_chimie[0], col_chimie[-1]+1):
                    cell_chim = ws.cell(row=1, column=col, value="Chimie" if col==col_chimie[0] else None)
                    cell_chim.font = Font(bold=True, size=36)
                    cell_chim.alignment = Alignment(horizontal="center", vertical="center")
                    cell_chim.border = encadre

        # C21 séparée
        if col_c21 and len(col_c21) > 0:
            for col in col_c21:
                cell_c21 = ws.cell(row=1, column=col, value="C21")
                cell_c21.font = Font(bold=True, size=36)
                cell_c21.alignment = Alignment(horizontal="center", vertical="center")
                cell_c21.border = encadre

        # Salles (ligne 2)
        for idx_s, s in enumerate(salle_list):
            col_letter = ws.cell(row=2, column=2+idx_s).column_letter
            cell = ws.cell(row=2, column=2+idx_s, value=s)
            ws.column_dimensions[col_letter].width = 20
            cell.font = Font(bold=True, size=36)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = encadre

        # Horaire (ligne 2) - Format jj/mm
        date_display = date_obj.strftime('%d/%m')
        ws.cell(row=2, column=1, value=date_display)
        ws.cell(row=2, column=1).font = Font(bold=True, size=16)
        ws.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=2, column=1).border = encadre

        # Préparation d'une matrice pour savoir quoi afficher et où fusionner
        cell_matrix = [[{"content": "", "merge": False, "merge_len": 1, "matiere": ""} for _ in salle_list] for _ in horaires]
        
        # Fill assignments from OR-Tools solution
        for i, c in enumerate(cours):
            for s in salle_list:
                if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                    start_time, end_time = interval_cours(c)
                    idx_start = next((idx for idx, h in enumerate(horaires) if h >= start_time), 0)
                    idx_end = next((idx for idx, h in enumerate(horaires) if h >= end_time), len(horaires))
                    merge_len = max(1, idx_end - idx_start)
                    
                    salle_idx = salle_list.index(s)
                    
                    # Construction du texte avec tous les besoins
                    besoins_txt = []
                    if c.get("ordinateurs", 0) > 0: besoins_txt.append(f"Ordinateurs: {c['ordinateurs']}")
                    if c.get("hotte", 0) > 0: besoins_txt.append("Hotte")
                    if c.get("bancs_optiques", 0) > 0: besoins_txt.append("Bancs optiques")
                    if c.get("oscilloscopes", 0) > 0: besoins_txt.append("Oscilloscopes")
                    if c.get("becs_electriques", 0) > 0: besoins_txt.append("Becs électriques")
                    if c.get("support_filtration", 0) > 0: besoins_txt.append("Support filtration")
                    if c.get("imprimante", 0) > 0: besoins_txt.append("Imprimante")
                    if c.get("examen", 0) > 0: besoins_txt.append("Examen")
                    
                    content = f"{c['enseignant']}\n{c['niveau']}\n" + ", ".join(besoins_txt)
                    
                    for idx in range(idx_start, min(idx_end, len(horaires))):
                        cell_matrix[idx][salle_idx]["content"] = content
                        cell_matrix[idx][salle_idx]["matiere"] = c["matiere"]
                    
                    if idx_start < len(horaires):
                        cell_matrix[idx_start][salle_idx]["merge"] = True
                        cell_matrix[idx_start][salle_idx]["merge_len"] = merge_len

        # Remplissage du tableau avec fusion verticale
        for idx_h, h in enumerate(horaires):
            ws.cell(row=3+idx_h, column=1, value=horaires_aff[idx_h])
            ws.cell(row=3+idx_h, column=1).alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=3+idx_h, column=1).border = encadre
            
            for idx_s, s in enumerate(salle_list):
                cell = cell_matrix[idx_h][idx_s]
                excel_row = 3+idx_h
                excel_col = 2+idx_s
                
                if cell["merge"]:
                    ws.cell(row=excel_row, column=excel_col, value=cell["content"])
                    ws.cell(row=excel_row, column=excel_col).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    ws.cell(row=excel_row, column=excel_col).border = encadre
                    
                    # Couleur selon la matière du cours affecté à la cellule
                    matiere = cell["matiere"].lower() if cell["matiere"] else ""
                    if "chimie" in matiere:
                        ws.cell(row=excel_row, column=excel_col).fill = PatternFill(start_color="B2F2E9", end_color="B2F2E9", fill_type="solid")
                    elif "physique" in matiere:
                        ws.cell(row=excel_row, column=excel_col).fill = PatternFill(start_color="FFD580", end_color="FFD580", fill_type="solid")
                    elif "mixte" in matiere:
                        ws.cell(row=excel_row, column=excel_col).fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
                    
                    ws.merge_cells(start_row=excel_row, start_column=excel_col, end_row=excel_row+cell["merge_len"]-1, end_column=excel_col)
                elif cell["content"] and not cell["merge"]:
                    continue
                else:
                    try:
                        ws.cell(row=excel_row, column=excel_col, value="")
                        ws.cell(row=excel_row, column=excel_col).border = encadre
                    except AttributeError:
                        pass

        for idx_h in range(len(horaires)):
            ws.row_dimensions[3 + idx_h].height = 20

        # Créer la feuille d'affichage (version simplifiée pour affichage public)
        ws2 = wb.create_sheet(title="Affichage")
        # En-tête : 1ère colonne = horaire, puis salles
        ws2.cell(row=1, column=1, value=day_name.capitalize())
        ws2.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws2.column_dimensions['A'].width = 12

        if col_physique and len(col_physique) > 0 and col_physique[0] <= col_physique[-1]:
            ws2.merge_cells(start_row=1, start_column=col_physique[0], end_row=1, end_column=col_physique[-1])
            for col in range(col_physique[0], col_physique[-1]+1):
                cell_phys = ws2.cell(row=1, column=col, value="Physique" if col==col_physique[0] else None)
                cell_phys.font = Font(bold=True, size=36)
                cell_phys.alignment = Alignment(horizontal="center", vertical="center")
                cell_phys.border = encadre
                
        if col_chimie and len(col_chimie) > 0 and col_chimie[0] <= col_chimie[-1]:
            ws2.merge_cells(start_row=1, start_column=col_chimie[0], end_row=1, end_column=col_chimie[-1])
            for col in range(col_chimie[0], col_chimie[-1]+1):
                cell_chim = ws2.cell(row=1, column=col, value="Chimie" if col==col_chimie[0] else None)
                cell_chim.font = Font(bold=True, size=36)
                cell_chim.alignment = Alignment(horizontal="center", vertical="center")
                cell_chim.border = encadre

        # Salles (ligne 2)
        for idx_s, s in enumerate(salle_list):
            col_letter = ws2.cell(row=2, column=2+idx_s).column_letter
            cell = ws2.cell(row=2, column=2+idx_s, value=s)
            ws2.column_dimensions[col_letter].width = 20
            cell.font = Font(bold=True, size=36)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = encadre

        # Horaire (ligne 2)
        ws2.cell(row=2, column=1, value=date_str)
        ws2.cell(row=2, column=1).font = Font(bold=True, size=16)
        ws2.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws2.cell(row=2, column=1).border = encadre

        # Préparation d'une matrice pour la feuille d'affichage (seulement enseignant)
        cell_matrix2 = [[{"content": "", "merge": False, "merge_len": 1, "matiere": ""} for _ in salle_list] for _ in horaires]
        
        for i, c in enumerate(cours):
            for s in salle_list:
                if (i, s) in x and solver.Value(x[(i, s)]) == 1:
                    start_time, end_time = interval_cours(c)
                    idx_start = next((idx for idx, h in enumerate(horaires) if h >= start_time), 0)
                    idx_end = next((idx for idx, h in enumerate(horaires) if h >= end_time), len(horaires))
                    merge_len = max(1, idx_end - idx_start)
                    
                    salle_idx = salle_list.index(s)
                    content = f"{c['enseignant']}"  # Version simplifiée pour affichage
                    
                    for idx in range(idx_start, min(idx_end, len(horaires))):
                        cell_matrix2[idx][salle_idx]["content"] = content
                        cell_matrix2[idx][salle_idx]["matiere"] = c["matiere"]
                    
                    if idx_start < len(horaires):
                        cell_matrix2[idx_start][salle_idx]["merge"] = True
                        cell_matrix2[idx_start][salle_idx]["merge_len"] = merge_len

        # Remplissage du tableau d'affichage
        for idx_h, h in enumerate(horaires):
            ws2.cell(row=3+idx_h, column=1, value=horaires_aff[idx_h])
            ws2.cell(row=3+idx_h, column=1).alignment = Alignment(horizontal="center", vertical="center")
            ws2.cell(row=3+idx_h, column=1).border = encadre
            
            for idx_s, s in enumerate(salle_list):
                cell = cell_matrix2[idx_h][idx_s]
                excel_row = 3+idx_h
                excel_col = 2+idx_s
                
                if cell["merge"]:
                    ws2.cell(row=excel_row, column=excel_col, value=cell["content"])
                    ws2.cell(row=excel_row, column=excel_col).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    ws2.cell(row=excel_row, column=excel_col).border = encadre
                    # Couleur grise uniforme pour l'affichage public
                    ws2.cell(row=excel_row, column=excel_col).fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
                    ws2.merge_cells(start_row=excel_row, start_column=excel_col, end_row=excel_row+cell["merge_len"]-1, end_column=excel_col)
                elif cell["content"] and not cell["merge"]:
                    continue
                else:
                    try:
                        ws2.cell(row=excel_row, column=excel_col, value="")
                        ws2.cell(row=excel_row, column=excel_col).border = encadre
                    except AttributeError:
                        pass

        for idx_h in range(len(horaires)):
            ws2.row_dimensions[3 + idx_h].height = 20
        
        # Save to memory buffer instead of file
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERREUR COMPLETE: {error_trace}")
        return jsonify({'success': False, 'error': f'Erreur lors de la génération: {str(e)}', 'trace': error_trace}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    # Production mode pour Railway
    debug = os.environ.get('FLASK_ENV') != 'production'
    logger.info(f"Démarrage de l'application sur le port {port}, debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)