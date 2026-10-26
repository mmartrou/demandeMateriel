# Déploiement OVH VPS (Ubuntu + Nginx + Gunicorn + systemd)

Ce guide permet de déployer `demandeMateriel` sur un VPS OVH en production, avec HTTPS et redémarrage automatique.

## 1) Pré-requis

- VPS OVH sous Ubuntu 22.04+ (ou Debian proche)
- Accès SSH root ou sudo
- Un domaine ou sous-domaine pointant vers l'IP du VPS
- Ports ouverts: `22`, `80`, `443`

## 2) Installation système

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git ufw
```

Firewall recommandé:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

## 3) Déployer le code

```bash
sudo mkdir -p /opt/demande-materiel
sudo chown -R $USER:$USER /opt/demande-materiel
cd /opt/demande-materiel

git clone <URL_DE_TON_REPO> .
```

Créer l'environnement Python et installer les dépendances:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Variables d'environnement (.env)

Créer `/opt/demande-materiel/.env`:

```env
# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=remplace_par_une_cle_longue_aleatoire
SESSION_COOKIE_SECURE=true
MAX_UPLOAD_MB=10

# Base de données PostgreSQL (Neon)
# Sans DATABASE_URL, ou si la connexion échoue, l'appli bascule sur SQLite (data/material_requests.db)
DATABASE_URL=postgresql://user:password@host:5432/database

# Connexion Google des utilisateurs
GOOGLE_CLIENT_ID=xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
ADMIN_EMAIL=prenom.nom@etablissement.fr
```

La liste complète des variables est dans `.env.example`. Ne jamais mettre `DEV_LOGIN` sur le serveur.

Protéger le fichier (lisible uniquement par root et par le compte du service, ici `ubuntu`) :

```bash
sudo chown root:ubuntu /opt/demande-materiel/.env
sudo chmod 640 /opt/demande-materiel/.env
```

> ⚠️ Le compte qui fait tourner le service (ligne `User=` du fichier systemd) doit pouvoir lire ce fichier : l'appli le relit au démarrage et plante (`PermissionError`) sinon.

Générer une clé secrète forte :

```bash
python3 - << 'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

## 5) Lancement local (développement)

Pour tester l'application sur votre machine avant de déployer :

```bash
# Activer l'environnement virtuel
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Lancer le serveur de développement Flask (port 8080)
python app.py
```

L'application est accessible sur `http://localhost:8080`.

Flask recharge automatiquement le code quand un fichier est modifié (mode debug activé par défaut dans `app.py`).

> **Note :** un fichier `.env` valide est nécessaire (cf. section 4). Pour un test rapide en local avec SQLite, seuls `FLASK_SECRET_KEY` et `GOOGLE_CLIENT_ID` sont indispensables.
>
> Pour se connecter sans Google en local, ajouter `DEV_LOGIN=1` au `.env` de son poste puis ouvrir `http://localhost:8080/dev-login`. Cette route n'existe que si `DEV_LOGIN=1` et ne répond qu'à `localhost`.

## 6) Service systemd (Gunicorn)

Copier le modèle fourni dans ce repo:

- Source: `deploy/systemd/demande-materiel.service`
- Destination: `/etc/systemd/system/demande-materiel.service`

Vérifier les lignes `User=` / `Group=` : elles doivent désigner le compte propriétaire du code (`ubuntu` sur le VPS actuel). Puis créer le dossier des images avec ce même compte :

```bash
mkdir -p /opt/demande-materiel/static/uploads
sudo chown -R ubuntu:ubuntu /opt/demande-materiel/static/uploads
```

Puis:

```bash
sudo systemctl daemon-reload
sudo systemctl enable demande-materiel
sudo systemctl start demande-materiel
sudo systemctl status demande-materiel --no-pager
```

Logs en direct:

```bash
sudo journalctl -u demande-materiel -f
```

## 7) Nginx reverse proxy

Copier le modèle:

- Source: `deploy/nginx/demande-materiel.conf`
- Destination: `/etc/nginx/sites-available/demande-materiel`

Éditer le fichier et remplacer:

- `example.com` par ton domaine
- (optionnel) `www.example.com`

Activer la config:

```bash
sudo ln -s /etc/nginx/sites-available/demande-materiel /etc/nginx/sites-enabled/demande-materiel
sudo nginx -t
sudo systemctl reload nginx
```

## 8) HTTPS avec Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
```

Tester le renouvellement auto:

```bash
sudo certbot renew --dry-run
```

## 9) Vérifications rapides

- `https://example.com` charge bien la page
- `sudo systemctl status demande-materiel`
- `sudo nginx -t`
- `curl -I https://example.com`

## 10) Déploiement des mises à jour

### Étape 1 — Pousser les changements vers GitHub (depuis votre machine locale)

```bash
# Vérifier ce qui a changé
git status
git diff --stat

# Ajouter les fichiers modifiés (liste explicite recommandée)
git add app.py database.py templates/index.html templates/requests.html
# ou pour tout ajouter d'un coup :
git add -A

# Créer un commit
git commit -m "Description courte des modifications"

# Pousser vers GitHub
git push origin main
```

### Étape 2 — Mettre à jour le serveur (sur le VPS via SSH)

```bash
cd /opt/demande-materiel
source .venv/bin/activate
git pull
pip install -r requirements.txt
sudo systemctl restart demande-materiel
sudo systemctl status demande-materiel --no-pager
```

## 11) Sauvegardes

Les images jointes aux demandes sont stockées **uniquement** sur le serveur, dans `/opt/demande-materiel/static/uploads/` (ce dossier n'est pas versionné). Il doit faire partie des sauvegardes du VPS. La base de données, elle, est sur Neon.

## 12) Notes importantes pour ce projet

- L'accès est protégé par la connexion Google et les rôles (admin, labo, enseignant) ; il n'y a pas de jeton d'API.
- Le backend limite les uploads selon `MAX_UPLOAD_MB` (et nginx selon `client_max_body_size`).
- Le service Gunicorn écoute en local `127.0.0.1:8080`; Nginx publie en 80/443.
- Gunicorn est lancé avec `--preload` : la vérification de la base (`init_database()`) n'est faite qu'une fois au démarrage, et non par chacun des workers en parallèle.
- En cas d'échec au démarrage, `sudo journalctl -u demande-materiel -n 300 --no-pager | grep -A 30 Traceback | head -40` affiche la vraie cause.
