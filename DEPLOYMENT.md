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
PORT=8080

# Sécurité API/admin (obligatoire en production)
ADMIN_TOKEN=remplace_par_un_token_long_aleatoire
MAX_UPLOAD_MB=10

# Base de données (choisir une option)
# Option A (recommandée): PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/database

# Option B: SQLite fallback si DATABASE_URL absent/invalide
# (rien à configurer)
```

Générer un token fort:

```bash
python3 - << 'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

## 5) Service systemd (Gunicorn)

Copier le modèle fourni dans ce repo:

- Source: `deploy/systemd/demande-materiel.service`
- Destination: `/etc/systemd/system/demande-materiel.service`

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

## 6) Nginx reverse proxy

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

## 7) HTTPS avec Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
```

Tester le renouvellement auto:

```bash
sudo certbot renew --dry-run
```

## 8) Vérifications rapides

- `https://example.com` charge bien la page
- `sudo systemctl status demande-materiel`
- `sudo nginx -t`
- `curl -I https://example.com`

## 9) Déploiement des mises à jour

```bash
cd /opt/demande-materiel
source .venv/bin/activate
git pull
pip install -r requirements.txt
sudo systemctl restart demande-materiel
sudo systemctl status demande-materiel --no-pager
```

## 10) Notes importantes pour ce projet

- Les routes admin/API sensibles exigent `ADMIN_TOKEN` si défini.
- Depuis un client JS, envoyer le token via:
  - Header `X-Admin-Token: <token>`
  - ou `Authorization: Bearer <token>`
- Le backend limite les uploads selon `MAX_UPLOAD_MB`.
- Le service Gunicorn écoute en local `127.0.0.1:8080`; Nginx publie en 80/443.
