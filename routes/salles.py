"""Administration des salles : liste, ordre, équipements, import/export CSV et disponibilité limitée."""
import csv
import io

from flask import Blueprint, jsonify, make_response, render_template, request

from database import (
    add_room,
    add_room_availability,
    delete_room,
    delete_room_availability,
    get_all_rooms,
    get_room_availability,
    import_rooms_from_csv_content,
    reorder_rooms,
    set_room_limited_availability,
    update_room,
)
from security import api_error

bp = Blueprint('salles', __name__)


def _availability_page_title():
    """« Disponibilité autres salles (C21) » : les noms entre parenthèses sont ceux des salles
    marquées « à disponibilité limitée » dans /admin/rooms ou ayant des créneaux déclarés."""
    noms = [r['name'] for r in get_all_rooms() if r['limited_availability']]
    return 'Disponibilité autres salles' + (f" ({', '.join(noms)})" if noms else '')


@bp.route('/admin/rooms')
def view_rooms():
    """Room management page"""
    return render_template('rooms.html', availability_title=_availability_page_title())


@bp.route('/admin/room-availability')
def view_room_availability():
    """Page des créneaux des salles à disponibilité limitée"""
    return render_template('room_availability.html', availability_title=_availability_page_title(),
                           all_rooms=get_all_rooms())


@bp.route('/api/room-availability', methods=['GET', 'POST'])
def api_room_availability():
    """API pour gérer les créneaux de disponibilité des salles à disponibilité limitée"""
    if request.method == 'GET':
        return jsonify(get_room_availability())
    data = request.get_json(silent=True) or {}
    room_id = data.get('room_id')
    jour = data.get('jour')
    heure_debut = data.get('heure_debut')
    heure_fin = data.get('heure_fin')
    if not room_id or not jour or not heure_debut or not heure_fin:
        return jsonify({'error': 'Champs manquants'}), 400
    salles = {r['id']: r for r in get_all_rooms()}
    if int(room_id) not in salles:
        return jsonify({'error': 'Salle inconnue'}), 400
    if not salles[int(room_id)]['limited_availability']:
        return jsonify({'error': f"La salle {salles[int(room_id)]['name']} est toujours disponible : "
                                 "elle n'a pas de créneaux. Activez d'abord « disponibilité limitée »."}), 400
    if add_room_availability(int(room_id), jour, heure_debut, heure_fin):
        return jsonify({'success': True}), 201
    return jsonify({'error': 'Ce créneau existe déjà pour cette salle'}), 400


@bp.route('/api/room-availability/<int:availability_id>', methods=['DELETE'])
def api_delete_room_availability(availability_id):
    """API pour supprimer un créneau de disponibilité"""
    try:
        if delete_room_availability(availability_id):
            return jsonify({'success': True})
        return jsonify({'error': 'Créneau non trouvé'}), 404
    except Exception as e:
        return api_error('Erreur lors de la suppression du créneau', e)


@bp.route('/api/rooms', methods=['GET'])
def api_get_rooms():
    """API endpoint to get all rooms"""
    try:
        rooms = get_all_rooms()
        return jsonify(rooms)
    except Exception as e:
        return api_error('Erreur lors de la récupération des salles', e)


@bp.route('/api/rooms/<int:room_id>', methods=['PUT'])
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
        return api_error('Erreur lors de la mise à jour de la salle', e)


@bp.route('/api/rooms', methods=['POST'])
def api_add_room():
    """Ajoute une salle (en fin de liste)."""
    try:
        data = request.get_json(silent=True) or {}
        if not str(data.get('name', '')).strip():
            return jsonify({'error': 'Le nom de la salle est requis'}), 400
        try:
            new_id = add_room(data)
        except Exception:
            return jsonify({'error': 'Cette salle existe déjà ou les données sont invalides'}), 400
        return jsonify({'id': new_id}), 201
    except Exception as e:
        return api_error('Erreur lors de la création de la salle', e)


@bp.route('/api/rooms/<int:room_id>', methods=['DELETE'])
def api_delete_room(room_id):
    """Supprime une salle."""
    try:
        if delete_room(room_id):
            return jsonify({'message': 'Salle supprimée'})
        return jsonify({'error': 'Salle non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la suppression de la salle', e)


@bp.route('/api/rooms/<int:room_id>/limited-availability', methods=['PUT'])
def api_set_room_limited_availability(room_id):
    """Active ou désactive la « disponibilité limitée » d'une salle.
    La désactiver supprime ses créneaux : une salle toujours disponible n'en a pas."""
    try:
        limited = (request.get_json(silent=True) or {}).get('limited')
        if not isinstance(limited, bool):
            return jsonify({'error': "Le champ « limited » (vrai/faux) est requis"}), 400
        if set_room_limited_availability(room_id, limited):
            return jsonify({'success': True})
        return jsonify({'error': 'Salle non trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors de la modification de la salle', e)


@bp.route('/api/rooms/reorder', methods=['POST'])
def api_reorder_rooms():
    """Enregistre le nouvel ordre d'affichage : {"ids": [3, 1, 2, ...]}."""
    try:
        ids = (request.get_json(silent=True) or {}).get('ids')
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return jsonify({'error': 'Liste d\'identifiants invalide'}), 400
        reorder_rooms(ids)
        return jsonify({'message': 'Ordre enregistré'})
    except Exception as e:
        return api_error('Erreur lors du changement d\'ordre des salles', e)


@bp.route('/api/rooms/import-csv', methods=['POST'])
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
        return api_error('Erreur lors de l\'import du CSV des salles', e)


@bp.route('/api/rooms/export-csv', methods=['GET'])
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
            'bancs_optiques', 'obscurite_totale', 'becs_electriques',
            'support_filtration', 'imprimante', 'examen', 'groupe', 'disponibilite_limitee'
        ])
        
        # Données (get_all_rooms renvoie déjà des dictionnaires)
        for r in rooms:
            writer.writerow([
                r['name'], r['type'], r['ordinateurs'], r['chaises'],
                r['eviers'], r['hotte'], r['bancs_optiques'], r['obscurite_totale'],
                r['becs_electriques'], r['support_filtration'], r['imprimante'], r['examen'],
                r['room_group'], 1 if r['limited_availability'] else 0
            ])

        # Préparer la réponse
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=salles.csv'
        
        return response
        
    except Exception as e:
        return api_error('Erreur lors de l\'export CSV des salles', e)
