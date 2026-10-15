"""Authentification, rôles et protection des routes (hooks appliqués à toute l'application)."""
import json
import logging
import os

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from database import get_all_levels
import site_settings

logger = logging.getLogger(__name__)
bp = Blueprint('security', __name__)


def _parse_teacher_email_map():
    raw = os.getenv('TEACHER_EMAIL_MAP', '').strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k).strip().lower(): v for k, v in parsed.items()}
    except Exception as e:
        logger.warning(f"TEACHER_EMAIL_MAP invalide: {e}")
    return {}


def _get_current_user():
    user = session.get('user')
    if not user or not isinstance(user, dict):
        return None
    return user


def _get_effective_user_mode(user=None):
    """Retourne le mode effectif: admin, labo ou teacher."""
    if user is None:
        user = _get_current_user()
    if not user:
        return 'anonymous'
    if user.get('role') == 'labo':
        return 'labo'
    if user.get('role') != 'admin':
        return 'teacher'

    requested_mode = str(session.get('acting_mode', 'admin')).strip().lower()
    if requested_mode not in {'admin', 'teacher'}:
        requested_mode = 'admin'

    # Un admin non lié à un enseignant ne peut pas basculer en mode professeur.
    if requested_mode == 'teacher' and not user.get('teacher_id'):
        return 'admin'

    return requested_mode


def _is_teacher_scoped_user(user=None):
    return _get_effective_user_mode(user) == 'teacher'


def _is_labo_user(user=None):
    if user is None:
        user = _get_current_user()
    return bool(user and user.get('role') == 'labo')


def _is_admin_user(user=None):
    if user is None:
        user = _get_current_user()
    return bool(user and user.get('role') == 'admin' and _get_effective_user_mode(user) == 'admin')


def _is_privileged_user(user=None):
    """Retourne True pour admin (en mode admin) et labo."""
    return _is_admin_user(user) or _is_labo_user(user)


def _is_authenticated():
    return _get_current_user() is not None


def _is_owner_or_admin(request_teacher_id):
    user = _get_current_user()
    if not user:
        return False
    if _is_privileged_user(user):
        return True
    try:
        return int(user.get('teacher_id')) == int(request_teacher_id)
    except Exception:
        return False


def api_error(message="Erreur serveur interne", exception=None, status_code=500):
    """Retourne une erreur API sans exposer les détails internes en production."""
    if exception is not None:
        logger.exception(message)
    else:
        logger.error(message)

    payload = {'error': message}
    if current_app.debug and exception is not None:
        payload['details'] = str(exception)
    return jsonify(payload), status_code


def _is_admin_only_route(path, method):
    """Routes réservées aux admins uniquement."""
    if path.startswith('/admin'):
        return True
    admin_prefixes = (
        '/api/pending-modifications',
        '/api/requests-with-pending-modifications',
        '/api/working-days',
        '/api/room-availability',
        '/api/site-settings',
        '/api/standard-occupation',
        '/api/rooms',
        '/api/students',
        '/api/planning-editor',
        '/api/save-planning',
        '/api/get-planning',
        '/api/planning-observations',
        '/planning',
        '/api/generate-planning',
    )
    return any(path.startswith(prefix) for prefix in admin_prefixes)


def _is_privileged_route(path, method):
    """Routes accessibles aux admins ET au compte labo."""
    return path.startswith('/api/requests/') and (
        path.endswith('/toggle-prepared') or path.endswith('/room-type')
    )


def _is_sensitive_route(path, method):
    return _is_admin_only_route(path, method) or _is_privileged_route(path, method)


def _is_public_route(path):
    public_routes = {
        '/login',
        '/auth/google',
        '/logout',
        '/api/me',
    }
    if path == '/dev-login' and os.environ.get('FLASK_ENV') == 'development':
        return True
    return path in public_routes or path.startswith('/static/')


# Middleware pour gérer les erreurs d'encodage dans les requêtes
@bp.before_app_request  
def handle_encoding_errors():
    """Gère les erreurs d'encodage UTF-8 dans les requêtes de manière silencieuse"""
    try:
        # Nettoyer l'URL et les paramètres de requête
        if request.url and len(request.url) > 70:
            # Vérifier la zone problématique autour de la position 71
            problematic_section = request.url[65:75] if len(request.url) > 75 else request.url[65:]
            # Nettoyer les caractères problématiques
            cleaned_section = problematic_section.encode('utf-8', errors='ignore').decode('utf-8')
            if problematic_section != cleaned_section:
                # Log seulement si on détecte et nettoie des caractères problématiques
                current_app.logger.debug(f"Caractères UTF-8 invalides nettoyés dans l'URL")
        
        # Valider les paramètres de requête
        if request.args:
            for key, value in request.args.items():
                try:
                    # Forcer la validation UTF-8 avec nettoyage automatique
                    key.encode('utf-8', errors='ignore')
                    value.encode('utf-8', errors='ignore')
                except Exception:
                    pass
                    
    except Exception:
        # Ignorer complètement les erreurs d'encodage pour éviter le spam des logs
        pass


@bp.before_app_request
def enforce_authentication():
    """Force l'authentification Google pour toute route non publique."""
    if _is_public_route(request.path):
        return None

    if _is_authenticated():
        return None

    if request.path.startswith('/api/'):
        return jsonify({'error': 'Authentification requise'}), 401
    return redirect(url_for('auth.login'))


@bp.after_app_request
def add_no_cache_to_api(response):
    """Les réponses des API ne doivent jamais être mises en cache (données dynamiques)."""
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@bp.before_app_request
def protect_sensitive_routes():
    """Protège les routes sensibles."""
    if _is_admin_only_route(request.path, request.method):
        if _is_privileged_user():
            return None
        logger.warning(f"Accès refusé à {request.path} ({request.method}) - rôle admin ou labo requis")
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Non autorisé'}), 403
        return "Non autorisé", 403

    if _is_privileged_route(request.path, request.method):
        if _is_privileged_user():
            return None
        logger.warning(f"Accès refusé à {request.path} ({request.method}) - rôle admin ou labo requis")
        return jsonify({'error': 'Non autorisé'}), 403

    return None


@bp.app_context_processor
def inject_auth_context():
    user = _get_current_user()
    try:
        levels = get_all_levels()
    except Exception:
        levels = []
    settings = site_settings.get_site_settings()
    layout = site_settings.get_time_layout(settings)
    return {
        'current_user': user,
        'effective_user_mode': _get_effective_user_mode(user),
        'google_client_id': os.getenv('GOOGLE_CLIENT_ID', '').strip(),
        'levels': levels,
        'site': {'name': settings['site_name'], 'slots_morning': layout['morning'],
                 'slots_afternoon': layout['afternoon']},
        'site_config': site_settings.get_client_config(settings),
    }


# Gestionnaire d'erreur global pour les erreurs d'encodage
@bp.app_errorhandler(UnicodeDecodeError)
def handle_unicode_error(e):
    """Gère les erreurs d'encodage Unicode de manière silencieuse"""
    current_app.logger.debug(f"Erreur d'encodage Unicode interceptée: {e}")
    return "Erreur d'encodage", 400


@bp.app_errorhandler(UnicodeEncodeError) 
def handle_unicode_encode_error(e):
    """Gère les erreurs d'encodage Unicode lors de l'envoi de réponses"""
    current_app.logger.debug(f"Erreur d'encodage Unicode lors de l'envoi: {e}")
    return "Erreur d'encodage", 400


@bp.app_errorhandler(413)
def handle_payload_too_large(e):
    """Retourne une erreur explicite si le fichier uploadé dépasse la taille autorisée."""
    return jsonify({'error': "Fichier trop volumineux"}), 413
