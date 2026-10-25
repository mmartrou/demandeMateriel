"""Images des demandes : envoi de fichiers, stockés sur le serveur dans static/uploads/ (non versionné)."""
import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from security import api_error

bp = Blueprint('images', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}


@bp.route('/api/upload-image', methods=['POST'])
def api_upload_image():
    """Enregistre l'image envoyée dans static/uploads/ et renvoie son URL."""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'Aucune image fournie'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400

        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': 'Format de fichier non supporté'}), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"demande_materiel_{timestamp}_{unique_id}.{file_ext}"

        upload_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))

        return jsonify({
            'success': True,
            'image_url': f"/static/uploads/{filename}",
        })

    except Exception as e:
        return api_error('Erreur lors de l\'upload de l\'image', e)
