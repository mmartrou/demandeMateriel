"""Connexion à la base : PostgreSQL (DATABASE_URL) en priorité, SQLite en secours ;
une connexion partagée par requête HTTP."""
import logging
import os
import psycopg2
import psycopg2.extras
import sqlite3

import database  # le paquet : DATABASE_PATH y est relu à chaque connexion (les tests le modifient)

logger = logging.getLogger(__name__)


# Flask est optionnel : le paquet database doit rester utilisable en script autonome
try:
    from flask import g, has_app_context
    _FLASK_DISPONIBLE = True
except ImportError:
    _FLASK_DISPONIBLE = False


def _ouvrir_connexion():
    """Ouvre réellement une nouvelle connexion - PostgreSQL en priorité, SQLite en fallback"""

    # Essayer PostgreSQL d'abord
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        try:
            logger.info("Tentative de connexion PostgreSQL")
            conn = psycopg2.connect(database_url)
            conn.autocommit = True
            logger.info("Connexion PostgreSQL réussie")
            return conn, 'postgresql'
        except Exception as e:
            logger.warning(f"Échec PostgreSQL: {e}")

    # Fallback vers SQLite
    os.makedirs(os.path.dirname(database.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(database.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    logger.info(f"Fallback vers SQLite: {database.DATABASE_PATH}")
    return conn, 'sqlite'


class _ConnexionPartagee:
    """
    Enveloppe la connexion réutilisée pendant une requête HTTP.

    Ouvrir une connexion vers Neon coûte ~690 ms (handshake TLS transatlantique)
    contre ~106 ms pour une requête. Comme chaque fonction de ce module fait
    connexion -> requête -> close(), une page pouvait payer ce coût 5 à 7 fois.

    close() est donc neutralisé ici : la fermeture réelle est faite une seule
    fois en fin de requête par close_request_connection().
    """

    def __init__(self, conn):
        object.__setattr__(self, '_conn', conn)

    def close(self):
        # Fermeture différée à la fin de la requête - voir close_request_connection()
        pass

    def __getattr__(self, nom):
        return getattr(object.__getattribute__(self, '_conn'), nom)

    def __setattr__(self, nom, valeur):
        setattr(object.__getattribute__(self, '_conn'), nom, valeur)


def _connexion_morte(conn):
    """psycopg2 expose .closed (0 = ouverte) ; sqlite3 n'a pas cet attribut."""
    return bool(getattr(conn, 'closed', 0))


def get_db_connection():
    """
    Connexion à la base - PostgreSQL en priorité, SQLite en fallback.

    Dans une requête HTTP, la même connexion est réutilisée d'un appel à l'autre
    (voir _ConnexionPartagee). Hors contexte Flask (scripts, init_database,
    planning_generator lancé seul), le comportement historique est conservé :
    une connexion neuve à chaque appel, que l'appelant referme lui-même.
    """
    if not (_FLASK_DISPONIBLE and has_app_context()):
        return _ouvrir_connexion()

    en_cache = getattr(g, '_db_conn', None)
    if en_cache is not None:
        conn, db_type = en_cache
        if not _connexion_morte(conn):
            return _ConnexionPartagee(conn), db_type
        # La connexion a été coupée en cours de requête : on repart sur une neuve
        try:
            conn.close()
        except Exception:
            pass

    conn, db_type = _ouvrir_connexion()
    g._db_conn = (conn, db_type)
    return _ConnexionPartagee(conn), db_type


def close_request_connection(exception=None):
    """
    Ferme la connexion partagée en fin de requête.
    À enregistrer via app.teardown_appcontext(close_request_connection).
    """
    if not _FLASK_DISPONIBLE:
        return
    en_cache = g.pop('_db_conn', None) if hasattr(g, 'pop') else None
    if en_cache is not None:
        conn, _ = en_cache
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Fermeture de la connexion en fin de requête: {e}")
