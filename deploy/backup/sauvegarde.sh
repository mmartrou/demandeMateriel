#!/usr/bin/env bash
# Sauvegarde quotidienne de la base PostgreSQL et des images jointes (static/uploads/).
# Lancé chaque nuit par cron (voir docs/DEPLOYMENT.md, section "Sauvegardes").
#
# Produit dans $BACKUP_DIR :
#   base_AAAA-MM-JJ_HHMM.dump     base complète (format pg_dump -Fc, restaurable avec pg_restore)
#   uploads_AAAA-MM-JJ_HHMM.tar.gz  images jointes aux demandes
# Les sauvegardes de plus de $KEEP_DAYS jours sont supprimées.
#
# La connexion est lue dans DATABASE_URL du .env : postgresql://utilisateur:motdepasse@hote:port/base
# (le mot de passe ne doit pas contenir de caractères spéciaux : @ / : # ?).
set -euo pipefail
umask 077

APP_DIR="${APP_DIR:-/opt/demande-materiel}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/sauvegardes}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%F_%H%M)"

url="$(grep -m1 '^DATABASE_URL=' "$APP_DIR/.env" | cut -d= -f2-)"
case "$url" in
    postgresql://*|postgres://*) ;;
    *) echo "ERREUR : DATABASE_URL absente ou non PostgreSQL dans $APP_DIR/.env" >&2; exit 1 ;;
esac

# Décompose l'URL (le mot de passe passe par PGPASSWORD pour ne pas apparaître dans la liste des processus)
reste="${url#*://}"
identifiants="${reste%%@*}"
destination="${reste#*@}"
db_user="${identifiants%%:*}"
export PGPASSWORD="${identifiants#*:}"
db_hote="${destination%%[:/]*}"
db_port="5432"
if [[ "${destination%%/*}" == *:* ]]; then db_port="${destination%%/*}"; db_port="${db_port#*:}"; fi
db_nom="${destination#*/}"; db_nom="${db_nom%%\?*}"

mkdir -p "$BACKUP_DIR"

# 1) Base de données : écrite dans un fichier temporaire, puis renommée seulement si elle est valide
cible="$BACKUP_DIR/base_$STAMP.dump"
pg_dump -h "$db_hote" -p "$db_port" -U "$db_user" -d "$db_nom" -Fc --no-owner --no-privileges -f "$cible.tmp"
pg_restore --list "$cible.tmp" > /dev/null
mv "$cible.tmp" "$cible"

# 2) Images jointes
if [ -d "$APP_DIR/static/uploads" ]; then
    tar -czf "$BACKUP_DIR/uploads_$STAMP.tar.gz.tmp" -C "$APP_DIR/static" uploads
    mv "$BACKUP_DIR/uploads_$STAMP.tar.gz.tmp" "$BACKUP_DIR/uploads_$STAMP.tar.gz"
fi

# 3) Rotation
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'base_*.dump' -o -name 'uploads_*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete

echo "$(date '+%F %T') OK : $(basename "$cible") ($(du -h "$cible" | cut -f1)), conservation $KEEP_DAYS jours"
