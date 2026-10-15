"""Modifications de demandes proposées par les enseignants, en attente de validation."""
import logging
import traceback

from flask import Blueprint, jsonify, request

from database import (
    add_pending_modification,
    get_material_request_by_id,
    get_pending_modifications,
    get_requests_with_pending_modifications,
    reject_pending_modifications,
    validate_pending_modifications,
)
from security import _is_privileged_user, api_error

logger = logging.getLogger(__name__)
bp = Blueprint('modifications', __name__)


@bp.route('/api/pending-modifications', methods=['GET', 'POST'])
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
            return api_error('Erreur serveur lors de la récupération des modifications', e)
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Log pour debug
            logger.info(f"📥 Pending modification reçue: {data}")
            logger.info(f"📥 Type de données: {type(data)}")
            logger.info(f"📥 Clés disponibles: {list(data.keys()) if data else 'None'}")
            
            # Validation des champs requis
            required_fields = ['request_id', 'field_name', 'original_value', 'new_value']
            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Champ manquant: {field}")
                    return jsonify({'error': f'Champ manquant: {field}'}), 400
            
            # Un TP ne peut jamais être programmé un jour non-ouvré, y compris pour admin/labo
            if data['field_name'] == 'request_date':
                from database import is_working_day_configured
                new_date = data['new_value']
                if not is_working_day_configured(new_date):
                    return jsonify({'error': f'Le {new_date} n\'est pas un jour ouvré (week-end ou jour férié).'}), 400

            # Validation du délai de 2 jours ouvrés (sauf admin et labo)
            if not _is_privileged_user():
                if data['field_name'] == 'request_date':
                    current_request = get_material_request_by_id(data['request_id'])
                    if current_request:
                        current_date = current_request['request_date']
                        from deadline_utils import is_request_deadline_respected, get_earliest_valid_date
                        validation = is_request_deadline_respected(current_date)
                        if not validation['valid']:
                            earliest_date = get_earliest_valid_date()
                            return jsonify({
                                'error': f'Modification interdite - délai insuffisant. {validation["message"]} Première date modifiable: {earliest_date}'
                            }), 400

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
            
            logger.info(f"✅ Résultat add_pending_modification: {success}")
            
            if success:
                return jsonify({'message': 'Modification en attente ajoutée avec succès'})
            else:
                logger.error(f"❌ add_pending_modification a retourné False")
                return jsonify({'error': 'Erreur lors de l\'ajout de la modification'}), 500
                
        except Exception as e:
            logger.error(f"❌ Exception dans POST /api/pending-modifications: {str(e)}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return api_error('Erreur lors de l\'ajout de la modification', e)


@bp.route('/api/requests-with-pending-modifications', methods=['GET'])
def api_get_requests_with_pending_modifications():
    """API endpoint to get all request IDs that have pending modifications"""
    request_ids = get_requests_with_pending_modifications()
    return jsonify(request_ids)


@bp.route('/api/pending-modifications/<int:request_id>/validate', methods=['POST'])
def api_validate_pending_modifications(request_id):
    """API endpoint to validate and apply pending modifications for a request"""
    try:
        # Validation du délai de 2 jours ouvrés avant d'appliquer les modifications (sauf admin et labo)
        if not _is_privileged_user():
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
        return api_error('Erreur lors de la validation des modifications', e)


@bp.route('/api/pending-modifications/<int:request_id>/reject', methods=['POST'])
def api_reject_pending_modifications(request_id):
    """API endpoint to reject and remove pending modifications for a request"""
    try:
        success = reject_pending_modifications(request_id)
        if success:
            return jsonify({'message': 'Modifications rejetées avec succès'})
        else:
            return jsonify({'error': 'Aucune modification en attente trouvée'}), 404
    except Exception as e:
        return api_error('Erreur lors du rejet des modifications', e)
