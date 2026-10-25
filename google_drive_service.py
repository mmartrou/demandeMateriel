"""
Service Google Drive pour la gestion des images
Upload automatique vers Google Drive et gestion des URLs
"""
import io
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from config_google import *

def get_google_drive_service():
    """
    Authentification et création du service Google Drive
    """
    creds = None
    
    # Le fichier token.json stocke les tokens d'accès et de rafraîchissement de l'utilisateur.
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)
    
    # Si il n'y a pas de credentials valides disponibles, laissez l'utilisateur se connecter.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise Exception("Fichier credentials.json manquant. Veuillez le télécharger depuis Google Cloud Console.")
            
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Sauvegarder les credentials pour la prochaine exécution
        with open(GOOGLE_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    return service

def upload_image_to_google_drive(image_file, filename):
    """
    Upload une image vers Google Drive et retourne l'URL publique
    
    Args:
        image_file: Fichier image (BytesIO ou chemin)
        filename: Nom du fichier
    
    Returns:
        dict: {'success': bool, 'file_id': str, 'public_url': str, 'error': str}
    """
    try:
        service = get_google_drive_service()
        # Préparer les métadonnées du fichier
        file_metadata = {
            'name': filename,
            'parents': [GOOGLE_FOLDER_ID] if GOOGLE_FOLDER_ID else []
        }
        # S'assurer que l'image est bien un BytesIO
        if hasattr(image_file, 'read') and hasattr(image_file, 'seek'):
            image_file.seek(0)
            media_body = MediaIoBaseUpload(
                image_file,
                mimetype='image/jpeg',
                resumable=True
            )
        elif isinstance(image_file, str):
            with open(image_file, 'rb') as f:
                media_body = MediaIoBaseUpload(
                    io.BytesIO(f.read()),
                    mimetype='image/jpeg',
                    resumable=True
                )
        else:
            raise Exception("Le fichier image n'est pas du bon type (BytesIO ou chemin)")
        # Upload du fichier
        file = service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        
        # Rendre le fichier public
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        # Générer l'URL publique compatible <img> avec le nouveau format
        public_url = f"https://lh3.googleusercontent.com/d/{file_id}"
        return {
            'success': True,
            'file_id': file_id,
            'public_url': public_url,
            'error': None
        }
    except Exception as e:
        logger.error(f"Erreur lors de l'upload vers Google Drive: {e}")
        return {
            'success': False,
            'file_id': None,
            'public_url': None,
            'error': str(e)
        }
