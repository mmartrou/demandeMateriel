# Configuration Google Drive
# ACTIVÉ - Intégration Google Drive avec fallback local
# Pour plus d'informations, voir OAUTH_SETUP.md

# Option 1: Si vous avez un fichier credentials.json de Google Cloud
GOOGLE_CREDENTIALS_FILE = "credentials.json"

# Option 2: Si vous avez les credentials directs
GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = ""
GOOGLE_FOLDER_ID = "1lAIXtdzfOyjucr9h38v8vEzI3ORE1wY8"  # Remplacez par l'ID de votre dossier Google Drive

# Scopes nécessaires pour l'API Google Drive
# https://www.googleapis.com/auth/drive.file = accès uniquement aux fichiers créés par l'app (recommandé)
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Configuration des tokens d'accès (sera généré automatiquement)
GOOGLE_TOKEN_FILE = "token.json"

# STATUS: Google Drive ACTIVÉ avec fallback local si indisponible