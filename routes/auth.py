"""Connexion Google, déconnexion et changement de mode (admin / enseignant)."""
import logging
import os

from flask import abort, Blueprint, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from database import find_teacher_id_by_name, get_all_teachers, get_user_by_email, upsert_user
from security import (
    _get_current_user,
    _get_effective_user_mode,
    _is_authenticated,
    _parse_teacher_email_map,
    api_error,
)
import site_settings

logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)


@bp.route('/login')
def login():
    """Page de connexion via Google."""
    if _is_authenticated():
        return redirect(url_for('pages.index'))
    return render_template('login.html')


@bp.route('/auth/google', methods=['POST'])
def auth_google():
    """Authentifie un utilisateur à partir d'un token Google ID."""
    try:
        payload = request.get_json(silent=True) or {}
        credential = payload.get('credential', '').strip()
        if not credential:
            return jsonify({'error': 'Token Google manquant'}), 400

        google_client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
        if not google_client_id:
            return jsonify({'error': 'GOOGLE_CLIENT_ID non configuré'}), 500

        id_info = id_token.verify_oauth2_token(credential, google_requests.Request(), google_client_id)
        email = (id_info.get('email') or '').strip().lower()
        full_name = (id_info.get('name') or '').strip()
        google_sub = (id_info.get('sub') or '').strip()

        if not id_info.get('email_verified') or not email or not google_sub:
            return jsonify({'error': 'Compte Google invalide'}), 401

        settings = site_settings.get_site_settings()
        allowed_domain = settings['allowed_domain']
        if allowed_domain and not email.endswith(f'@{allowed_domain}'):
            return jsonify({'error': 'Compte hors domaine autorisé'}), 403

        admin_email = os.getenv('ADMIN_EMAIL', '').strip().lower()
        labo_email = settings['labo_email']

        if admin_email and email == admin_email:
            role = 'admin'
        elif labo_email and email == labo_email:
            role = 'labo'
        else:
            role = 'teacher'

        existing_user = get_user_by_email(email)
        teacher_id = existing_user.get('teacher_id') if existing_user else None

        email_map = _parse_teacher_email_map()
        mapped_value = email_map.get(email)
        if mapped_value is not None:
            try:
                teacher_id = int(mapped_value)
            except Exception:
                teacher_id = find_teacher_id_by_name(str(mapped_value).strip())

        if role == 'teacher' and teacher_id is None:
            return jsonify({
                'error': "Compte enseignant non associé. Configure TEACHER_EMAIL_MAP ou associe ce compte en base."
            }), 403

        upsert_user(
            google_sub=google_sub,
            email=email,
            full_name=full_name,
            role=role,
            teacher_id=teacher_id
        )

        user = get_user_by_email(email)
        if not user:
            return jsonify({'error': 'Impossible de charger le compte utilisateur'}), 500

        effective_role = user.get('role') or role
        session.clear()
        session.permanent = True
        session['user'] = {
            'id': user.get('id'),
            'email': user.get('email'),
            'full_name': 'Labo' if effective_role == 'labo' else (user.get('full_name') or full_name),
            'role': effective_role,
            'teacher_id': user.get('teacher_id'),
            'teacher_name': user.get('teacher_name')
        }
        session['acting_mode'] = 'admin' if effective_role == 'admin' else 'teacher'

        return jsonify({'success': True, 'user': session['user']})
    except ValueError as e:
        logger.warning(f"Token Google invalide: {e}")
        return jsonify({'error': 'Échec de validation du token Google'}), 401
    except Exception as e:
        return api_error('Erreur lors de la connexion Google', e)


@bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """Déconnecte l'utilisateur courant."""
    session.clear()
    if request.path.startswith('/api/'):
        return jsonify({'success': True})
    return redirect(url_for('auth.login'))


if os.environ.get('FLASK_ENV') == 'development' and not os.environ.get('RAILWAY_ENVIRONMENT'):
    @bp.route('/dev-login')
    def dev_login():
        """Connexion rapide sans Google OAuth (dev uniquement)."""
        if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
            abort(404)
        teachers = get_all_teachers()
        teacher_id = request.args.get('teacher_id', type=int)
        role = request.args.get('role', 'teacher')
        if teacher_id:
            teacher = next((t for t in teachers if int(t['id']) == teacher_id), None)
            if not teacher:
                return f"Teacher id {teacher_id} introuvable", 404
            session.clear()
            session.permanent = True
            session['user'] = {
                'id': teacher_id,
                'email': f"dev-{teacher_id}@local",
                'full_name': teacher['name'],
                'role': role,
                'teacher_id': teacher_id,
                'teacher_name': teacher['name']
            }
            session['acting_mode'] = 'admin' if role == 'admin' else 'teacher'
            return redirect(url_for('pages.index'))
        return '<h3>Dev Login</h3><ul>' + ''.join(
            f'<li><a href="?teacher_id={t["id"]}&role=teacher">{t["name"]}</a>'
            f' — <a href="?teacher_id={t["id"]}&role=admin">(admin)</a></li>'
            for t in teachers
        ) + '</ul>'


@bp.route('/api/acting-mode', methods=['POST'])
def api_set_acting_mode():
    """Permet à l'admin de choisir son mode: admin ou professeur."""
    user = _get_current_user()
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403

    payload = request.get_json(silent=True) or {}
    mode = str(payload.get('mode', '')).strip().lower()
    if mode not in {'admin', 'teacher'}:
        return jsonify({'error': 'Mode invalide'}), 400

    if mode == 'teacher' and not user.get('teacher_id'):
        email = (user.get('email') or '').strip().lower()
        resolved_teacher_id = None

        db_user = get_user_by_email(email) if email else None
        if db_user and db_user.get('teacher_id'):
            resolved_teacher_id = db_user.get('teacher_id')

        if resolved_teacher_id is None:
            email_map = _parse_teacher_email_map()
            mapped_value = email_map.get(email)
            if mapped_value is not None:
                try:
                    resolved_teacher_id = int(mapped_value)
                except Exception:
                    resolved_teacher_id = find_teacher_id_by_name(str(mapped_value).strip())

        if resolved_teacher_id is None:
            return jsonify({'error': 'Aucun profil enseignant associé'}), 400

        # Met à jour la session courante pour activer immédiatement le mode professeur.
        user['teacher_id'] = int(resolved_teacher_id)

        # Met à jour le nom enseignant en session si possible.
        teacher_name_by_id = {int(t['id']): t['name'] for t in get_all_teachers()}
        if int(resolved_teacher_id) in teacher_name_by_id:
            user['teacher_name'] = teacher_name_by_id[int(resolved_teacher_id)]
        session['user'] = user

        # Persiste l'association pour les prochaines connexions si l'utilisateur existe en base.
        if db_user and db_user.get('google_sub'):
            upsert_user(
                google_sub=db_user.get('google_sub'),
                email=db_user.get('email') or email,
                full_name=db_user.get('full_name') or user.get('full_name') or '',
                role='admin',
                teacher_id=int(resolved_teacher_id)
            )

    session['acting_mode'] = mode
    return jsonify({'success': True, 'effective_mode': _get_effective_user_mode(user)})
