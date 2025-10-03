"""
Service Google Drive pour la gestion des images
Upload automatique vers Google Drive et gestion des URLs
"""
import re
import requests
import io
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
import os
from PIL import Image
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from config_google import *

def extract_google_drive_id(url_or_id):
    """
    Extrait l'ID Google Drive depuis une URL ou retourne l'ID s'il est déjà propre
    Formats supportés:
    - https://drive.google.com/file/d/1ABC123.../view
    - https://drive.google.com/open?id=1ABC123...
    - 1ABC123... (ID direct)
    """
    if not url_or_id:
        return None
    # Si c'est déjà un ID (pas d'URL), le retourner
    if not url_or_id.startswith('http'):
        # Valider que ça ressemble à un ID Google Drive (caractères alphanumériques et tirets)
        if re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
            return url_or_id.strip()
        return None
    # Extraire l'ID depuis l'URL
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None

def get_google_drive_image_url(drive_id):
    """
    Convertit un ID Google Drive en URL d'affichage direct
    Nouveau format: https://lh3.googleusercontent.com/d/ID
    """
    if not drive_id:
        return None
    
    # Nouveau format Google Drive plus fiable pour l'affichage d'images
    return f"https://lh3.googleusercontent.com/d/{drive_id}"

def validate_google_drive_image(drive_id):
    """
    Valide qu'un ID Google Drive correspond bien à une image accessible
    Retourne (is_valid, error_message, image_url)
    """
    if not drive_id:
        return False, "ID Google Drive manquant", None
    
    image_url = get_google_drive_image_url(drive_id)
    
    try:
        # Tenter de récupérer l'image
        response = requests.get(image_url, timeout=10, allow_redirects=True)
        
        # Vérifier le statut HTTP
        if response.status_code != 200:
            return False, f"Impossible d'accéder à l'image (code {response.status_code})", None
        
        # Vérifier que c'est bien une image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            # Peut-être que Google Drive renvoie du HTML au lieu de l'image
            if 'text/html' in content_type:
                return False, "Image non accessible - vérifiez que le lien de partage est public", None
            return False, f"Le fichier n'est pas une image (type: {content_type})", None
        
        # Optionnel: valider que l'image peut être ouverte avec PIL
        try:
            image = Image.open(io.BytesIO(response.content))
            width, height = image.size
            
            # Limites raisonnables
            if width > 4000 or height > 4000:
                return False, f"Image trop grande ({width}x{height}px), maximum 4000x4000px", None
            
            if width < 10 or height < 10:
                return False, f"Image trop petite ({width}x{height}px), minimum 10x10px", None
                
        except Exception as e:
            return False, f"Format d'image invalide: {str(e)}", None
        
        return True, None, image_url
        
    except requests.exceptions.Timeout:
        return False, "Timeout lors de la vérification de l'image", None
    except requests.exceptions.ConnectionError:
        return False, "Impossible de se connecter à Google Drive", None
    except Exception as e:
        logger.error(f"Erreur lors de la validation Google Drive: {e}")
        return False, f"Erreur lors de la validation: {str(e)}", None

def get_image_info(drive_id):
    """
    Récupère les informations d'une image Google Drive (taille, format, etc.)
    Retourne un dictionnaire avec les infos ou None si erreur
    """
    is_valid, error, image_url = validate_google_drive_image(drive_id)
    
    if not is_valid:
        return None
    
    try:
        response = requests.get(image_url, timeout=10)
        image = Image.open(io.BytesIO(response.content))
        
        return {
            'width': image.width,
            'height': image.height,
            'format': image.format,
            'mode': image.mode,
            'size_bytes': len(response.content),
            'url': image_url
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos image: {e}")
        return None

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

    def extract_google_drive_id(url_or_id):
        """
        Extrait l'ID Google Drive depuis une URL ou retourne l'ID s'il est déjà propre
        Formats supportés:
        - https://drive.google.com/file/d/1ABC123.../view
        - https://drive.google.com/open?id=1ABC123...
        - 1ABC123... (ID direct)
        """
        if not url_or_id:
            return None
        if not url_or_id.startswith('http'):
            if re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
                return url_or_id.strip()
            return None
        patterns = [
            r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return None
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
def optimize_image_for_upload(image_file, max_size=(1024, 1024), quality=85):
    """
    Optimise une image avant l'upload (redimensionnement et compression)
    Args:
        image_file: Fichier image
        max_size: Taille maximale (largeur, hauteur)
        quality: Qualité JPEG (1-100)
    Returns:
        BytesIO: Image optimisée
    """
    try:
        # Ouvrir l'image
        img = Image.open(image_file)
        # Convertir en RGB si nécessaire (pour les PNG avec transparence, etc.)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        # Redimensionner si nécessaire
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        # Sauvegarder dans un BytesIO
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Erreur lors de l'optimisation de l'image: {e}")
        return None

def process_and_upload_image(file_storage, base_filename="image"):
    """
    Traite et upload une image vers Google Drive
    Args:
        file_storage: Fichier Flask (request.files['image'])
        base_filename: Nom de base pour le fichier
    Returns:
        dict: Résultat de l'upload
    """
    try:
        # Générer un nom de fichier unique
        from datetime import datetime
        import uuid
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{base_filename}_{timestamp}_{unique_id}.jpg"
        
        # Optimiser l'image
        optimized_image = optimize_image_for_upload(file_storage.stream)
        
        if not optimized_image:
            return {
                'success': False,
                'error': 'Impossible d\'optimiser l\'image'
            }
        
        # Upload vers Google Drive
        result = upload_image_to_google_drive(optimized_image, filename)
        
        if result['success']:
            logger.info(f"Image uploadée avec succès: {filename} -> {result['file_id']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'image: {e}")
        return {
            'success': False,
            'error': f'Erreur de traitement: {str(e)}'
        }