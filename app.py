"""Point d'entrée de l'application (gunicorn app:app) : configuration et enregistrement des routes.

Les routes sont regroupées par thème dans routes/ ; l'authentification, les rôles et la
protection des routes sont dans security.py.
"""
import logging
import os
import secrets
from datetime import timedelta

# Charger les variables d'environnement depuis .env avant tout le reste
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, url_for  # noqa: E402

import security  # noqa: E402
from database import close_request_connection, init_database  # noqa: E402
from routes import (  # noqa: E402
    admin, auth, demandes, edition_planning, images, jours, mes_tps, modifications, pages, salles,
)

app = Flask(__name__)

# Une seule connexion à la base par requête HTTP, refermée automatiquement ici.
# Sans cela, chaque fonction de database.py rouvrait sa propre connexion (~690 ms
# de handshake vers Neon à chaque fois, contre ~106 ms pour la requête elle-même).
app.teardown_appcontext(close_request_connection)

app.secret_key = os.getenv('FLASK_SECRET_KEY', os.getenv('SECRET_KEY', secrets.token_hex(32)))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.permanent_session_lifetime = timedelta(hours=8)

# Configuration pour gérer les erreurs d'encodage UTF-8
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024

logging.basicConfig(level=logging.INFO)
# Configuration des logs pour éviter le spam d'erreurs d'encodage
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.template_global()
def asset(filename):
    """URL d'un fichier de static/ suivie de sa date de modification (?v=...) : le navigateur
    recharge un fichier dès qu'il change, sans numéro de version à incrémenter à la main."""
    try:
        version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
    except OSError:
        version = 0
    return url_for('static', filename=filename, v=version)


# security en premier : ses hooks (encodage, authentification, rôles) s'appliquent à toutes les routes
for module in (security, auth, pages, mes_tps, demandes, modifications, images, admin, salles, jours,
               edition_planning):
    app.register_blueprint(module.bp)

# Initialisation de la base de données au démarrage
init_database()


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
    
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f" * Application démarrée sur http://127.0.0.1:{port}")
    print(" * Gestion des erreurs UTF-8 activée")
    app.run(debug=debug, host='0.0.0.0', port=port)
