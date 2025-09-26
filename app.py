from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import csv
import io
from datetime import datetime, timedelta
from database import init_database, get_all_teachers, add_material_request, get_material_requests, get_requests_for_calendar

app = Flask(__name__)

# Initialisation de la base de données au démarrage
init_database()


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
    return render_template('calendar.html')


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
            'class_name': req['class_name'],
            'material_description': req['material_description'],
            'quantity': req['quantity'],
            'selected_materials': req['selected_materials'] if 'selected_materials' in req.keys() else '',
            'computers_needed': req['computers_needed'] if 'computers_needed' in req.keys() else 0,
            'notes': req['notes'],
            'created_at': req['created_at']
        })
    
    return jsonify(requests_list)

@app.route('/api/calendar-events', methods=['GET'])
def api_calendar_events():
    """API endpoint to get calendar events"""
    requests = get_requests_for_calendar()
    
    events = []
    for req in requests:
        events.append({
            'id': req['id'],
            'title': f"{req['teacher_name']} - {req['class_name']}",
            'start': req['request_date'],
            'description': f"Matériel: {req['material_description']} (Quantité: {req['quantity']})",
            'backgroundColor': '#007bff',
            'borderColor': '#0056b3'
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
                    notes=data.get('notes', '')
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
        'Nombre de groupes', 'Notes', 'Date création'
    ])
    
    # Write data
    for req in requests:
        writer.writerow([
            req['id'],
            req['teacher_name'],
            req['request_date'],
            req['horaire'] if 'horaire' in req.keys() else '',
            req['class_name'],
            req['selected_materials'] if 'selected_materials' in req.keys() else '',
            req['computers_needed'] if 'computers_needed' in req.keys() else 0,
            req['material_description'],
            req['quantity'],
            req['notes'] if 'notes' in req.keys() else '',
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

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)