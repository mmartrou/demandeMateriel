"""Images des demandes : envoi de fichiers vers Google Drive (ou stockage local de secours)."""
from flask import Blueprint, jsonify, request

from security import api_error

bp = Blueprint('images', __name__)


@bp.route('/api/upload-image', methods=['POST'])
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
        return api_error('Erreur lors de l\'upload de l\'image', e)
